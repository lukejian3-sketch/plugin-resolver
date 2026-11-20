"""调用运行时：加载已安装插件的入口文件并执行。

约定：
- 插件入口文件（manifest.entry）暴露 run(request) 或 run(request, resolve)。
- resolve(dep_capability, payload) 让插件在运行时调用其依赖能力，返回能力产出 dict。

inspect 自适应参数个数：单参数插件只用 request，双参数插件注入 resolve。
"""
from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import Any, Callable, Optional

from .models import InstalledPlugin, Manifest


class Runtime:
    def __init__(self):
        self._counter = 0  # 保证同一插件多次加载得到独立模块名，避免缓存干扰

    def load(
        self,
        manifest: Manifest,
        plugin: InstalledPlugin,
        request: dict,
        resolve: Optional[Callable] = None,
    ) -> Any:
        entry = Path(plugin.path) / manifest.entry
        if not entry.exists():
            raise RuntimeError(f"插件入口缺失: {entry}")
        self._counter += 1
        module_name = f"_plugin_{manifest.id}_{self._counter}"
        spec = importlib.util.spec_from_file_location(module_name, entry)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"无法加载插件模块: {entry}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fn = getattr(mod, "run", None)
        if fn is None:
            raise RuntimeError(f"插件 {manifest.id} 缺少 run 函数")
        # 自适应：run(request) 或 run(request, resolve)
        try:
            params = list(inspect.signature(fn).parameters.values())
        except (TypeError, ValueError):
            params = []
        if len(params) >= 2:
            return fn(request, resolve)
        return fn(request)