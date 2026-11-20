"""核心编排：把「意图匹配 -> 查索引 -> 安装/直调 -> 执行」串起来。

两阶段共用同一条路径：
  - 索引命中且版本一致 -> cache-hit -> 直调
  - 索引命中且 catalog 版本更新 -> upgrade -> 重装
  - 索引未命中 -> install -> 下载安装写索引 -> 调用

依赖解析：安装某插件前，先递归确保其 dependencies 里的能力已就绪（含循环依赖检测）。
运行层注入：插件可通过 resolve(dep_capability, payload) 调用依赖能力，得到其产出。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .catalog import Catalog
from .index_store import IndexStore
from .installer import Installer
from .matcher import SemanticMatcher
from .models import InstalledPlugin, Manifest
from .runtime import Runtime


def _version_key(v: str) -> tuple:
    parts = []
    for item in str(v).split("."):
        m = re.match(r"(\d+)", item)
        parts.append(int(m.group(1)) if m else 0)
    return tuple(parts)


def is_newer(new: str, old: str) -> bool:
    """简单 semver 比较：new 比 old 更「新」才返回 True。"""
    return _version_key(new) > _version_key(old)


class Resolver:
    def __init__(self, root: Path, catalog_path: Union[str, Path, None] = None,
                 isolated: bool = False, timeout: int = 5):
        self.root = Path(root)
        if catalog_path is None:
            cf: Union[str, Path] = self.root / "catalog" / "catalog.json"
        elif isinstance(catalog_path, str) and catalog_path.startswith(("http://", "https://")):
            cf = catalog_path
        else:
            cf = Path(catalog_path)
            if not cf.is_absolute():
                cf = self.root / cf
        self.catalog = Catalog(cf)
        self.index = IndexStore(self.root / "index.json")
        self.installer = Installer(self.root / "plugins", self.root)
        if isolated:
            from .isolated_runtime import IsolatedRuntime
            self.runtime = IsolatedRuntime(timeout=timeout)
        else:
            self.runtime = Runtime()
        self.matcher = SemanticMatcher(
            self.catalog.list(), semantics_file=self.root / "catalog" / "semantics.json"
        )

    def resolve_and_invoke(self, request_text: str, payload: Dict[str, Any] | None = None) -> List[dict]:
        caps = self.matcher.match(request_text)
        body = payload if payload is not None else {"text": request_text}
        return [self._call(cap, body, []) for cap in caps]

    def _call(self, cap: str, payload: dict, stack: List[str]) -> dict:
        """确保能力就绪并执行，返回结果 dict；支持运行层依赖注入与循环检测。"""
        if cap in stack:
            return {"capability": cap, "status": "missing",
                    "note": "运行层循环调用: " + " -> ".join(stack + [cap])}
        try:
            manifest, plugin, action, deps_log = self._ensure(cap, stack)
            out: Dict[str, Any] = {"capability": cap, "dependencies": deps_log}
            if manifest is None or plugin is None:
                out.update({"status": "missing", "note": "无插件提供该能力 -> 走 DIY 临时实现"})
                return out

            def resolve(dep_cap: str, dep_payload: dict | None = None) -> dict:
                return self._call(dep_cap, dep_payload if dep_payload is not None else {}, stack + [cap])

            result = self.runtime.load(manifest, plugin, payload, resolve=resolve)
            out.update({
                "plugin": plugin.plugin_id,
                "version": plugin.version,
                "status": "ok",
                "action": action,
                "result": result,
            })
            return out
        except Exception as e:  # noqa: BLE001
            return {"capability": cap, "status": "error",
                    "note": f"{type(e).__name__}: {e}"}

    def _ensure(
        self, cap: str, stack: List[str]
    ) -> Tuple[Optional[Manifest], Optional[InstalledPlugin], str, List[dict]]:
        """确保某能力已就绪（未装则递归装依赖后安装）。

        返回 (manifest, plugin, action, deps_log)。
        """
        if cap in stack:
            cycle = " -> ".join(stack + [cap])
            return None, None, "missing", [{"capability": cap, "action": "cycle", "note": cycle}]

        action = "install"
        manifest: Manifest | None = None
        plugin: InstalledPlugin | None = None
        deps_log: List[dict] = []

        pid = self.index.has_capability(cap)
        if pid:
            manifest = self.catalog.get(pid)
            plugin = self.index.index.plugins.get(pid)
            if manifest and plugin:
                if manifest.version == plugin.version:
                    action = "cache-hit"
                elif is_newer(manifest.version, plugin.version):
                    action = "upgrade"
                else:
                    action = "cache-hit"

        if action in ("install", "upgrade"):
            if manifest is None:
                manifest = self.catalog.find_by_capability(cap)
            if manifest is None:
                return None, None, "missing", deps_log
            # 先递归确保依赖就绪
            for dep in manifest.dependencies:
                dm, _dp, dact, dlog = self._ensure(dep, stack + [cap])
                deps_log.append({"capability": dep, "action": dact, "ok": dm is not None})
                deps_log.extend(dlog)
            plugin = self.installer.install(manifest)
            self.index.register(cap, plugin)

        return manifest, plugin, action, deps_log