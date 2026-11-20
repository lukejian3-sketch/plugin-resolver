"""网络访问工具：下载 URL 到内存/文件（标准库 urllib，零依赖）。"""
from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

_HEADERS = {"User-Agent": "plugin-resolver/0.1"}


def url_to_bytes(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def url_to_text(url: str, timeout: int = 30) -> str:
    return url_to_bytes(url, timeout).decode("utf-8")


def download(url: str, dest: Path, timeout: int = 30) -> None:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)