"""数据模型：Manifest / DownloadSpec / InstalledPlugin / Index。

设计要点：
- 索引以「能力(capability)」为检索键，一个插件可提供多个能力；
- Manifest 描述「能力由哪个插件提供、怎么下载、依赖哪些能力、市场评分如何」，
  索引描述「本地已装什么」。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DownloadSpec:
    type: str
    source: str
    version: str = "0.0.0"
    sha256: Optional[str] = None
    signature: Optional[str] = None
    peer: List[str] = field(default_factory=list)


@dataclass
class Manifest:
    id: str
    name: str
    version: str
    triggers: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    description: str = ""
    entry: str = "plugin.py"
    dependencies: List[str] = field(default_factory=list)  # 依赖的其他能力
    rating: float = 0.0      # 市场评分 0-5
    downloads: int = 0       # 市场下载量
    download: Optional[DownloadSpec] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Manifest":
        dl = d.get("download")
        return cls(
            id=d["id"],
            name=d.get("name", d["id"]),
            version=d.get("version", "0.0.0"),
            triggers=list(d.get("triggers", [])),
            capabilities=list(d.get("capabilities", [])),
            description=d.get("description", ""),
            entry=d.get("entry", "plugin.py"),
            dependencies=list(d.get("dependencies", d.get("peer", []))),
            rating=float(d.get("rating", 0.0)),
            downloads=int(d.get("downloads", 0)),
            download=DownloadSpec(**dl) if dl else None,
        )


@dataclass
class InstalledPlugin:
    """索引里记录的一条「已安装插件」。"""
    plugin_id: str
    version: str
    path: str
    sha256: Optional[str] = None
    installed_at: str = ""


@dataclass
class Index:
    """本地已装索引。

    - plugins:      plugin_id -> InstalledPlugin
    - capabilities: capability -> plugin_id
    """
    plugins: Dict[str, InstalledPlugin] = field(default_factory=dict)
    capabilities: Dict[str, str] = field(default_factory=dict)