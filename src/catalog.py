"""能力目录：加载清单（本地文件或远程 URL），提供按 id / capability 的查询。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Union

from .models import Manifest


class Catalog:
    def __init__(self, source: Union[str, Path]):
        self.source = source
        self._manifests: dict = self._load()

    @staticmethod
    def _read_source(source) -> str:
        if isinstance(source, str) and source.startswith(("http://", "https://")):
            from .net import url_to_text
            return url_to_text(source)
        return Path(source).read_text(encoding="utf-8")

    def _load(self) -> dict:
        text = self._read_source(self.source)
        data = json.loads(text)
        manifests = {}
        for item in data.get("plugins", []):
            m = Manifest.from_dict(item)
            manifests[m.id] = m
        return manifests

    def list(self) -> List[Manifest]:
        return list(self._manifests.values())

    def get(self, plugin_id: str) -> Optional[Manifest]:
        return self._manifests.get(plugin_id)

    def candidates_for(self, cap: str) -> List[Manifest]:
        """返回所有提供该能力的插件（未排序）。"""
        return [m for m in self._manifests.values() if cap in m.capabilities]

    def find_by_capability(self, cap: str, prefer: str = "rating") -> Optional[Manifest]:
        """从多个候选中择优：评分优先，平手比下载量（prefer 可扩展策略）。"""
        cands = self.candidates_for(cap)
        if not cands:
            return None
        if prefer == "rating":
            return sorted(cands, key=lambda m: (m.rating, m.downloads), reverse=True)[0]
        return cands[0]