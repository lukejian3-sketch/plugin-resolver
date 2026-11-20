"""本地已装索引的读写与自愈。

这是「第二阶段不需要下载」的关键：resolver 先查这里，命中即直调。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import Index, InstalledPlugin


class IndexStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.index: Index = self._load()

    def _load(self) -> Index:
        if not self.path.exists():
            return Index()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        idx = Index()
        for pid, p in data.get("plugins", {}).items():
            idx.plugins[pid] = InstalledPlugin(**p)
        idx.capabilities = dict(data.get("capabilities", {}))
        return idx

    def save(self) -> None:
        data = {
            "plugins": {pid: vars(p) for pid, p in self.index.plugins.items()},
            "capabilities": self.index.capabilities,
        }
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def has_capability(self, cap: str) -> Optional[str]:
        """命中返回 plugin_id，未命中返回 None。"""
        return self.index.capabilities.get(cap)

    def register(self, cap: str, plugin: InstalledPlugin) -> None:
        self.index.plugins[plugin.plugin_id] = plugin
        self.index.capabilities[cap] = plugin.plugin_id
        self.save()

    def rebuild(self, plugins_dir: Path) -> int:
        """自愈：扫描插件目录下各 manifest.json，重建索引。返回恢复的插件数。

        用于解决「索引文件与磁盘实际文件不一致」的脏数据问题。
        """
        plugins_dir = Path(plugins_dir)
        if not plugins_dir.exists():
            return 0
        restored = 0
        for manifest_file in plugins_dir.glob("*/manifest.json"):
            try:
                data = json.loads(manifest_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            plugin = InstalledPlugin(
                plugin_id=data["id"],
                version=data.get("version", "0.0.0"),
                path=str(manifest_file.parent),
            )
            self.index.plugins[plugin.plugin_id] = plugin
            for cap in data.get("capabilities", []):
                self.index.capabilities[cap] = plugin.plugin_id
            restored += 1
        self.save()
        return restored