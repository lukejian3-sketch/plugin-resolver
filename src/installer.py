"""安装器：下载/复制 -> sha256 校验 -> 签名验签 -> 解压落盘 -> 返回 InstalledPlugin。

校验链（生产安全底线）：
  1. sha256     完整性：发行包在传输/存储中未被损坏或篡改
  2. signature  来源认证：发行包确实由持有签名密钥的发布者签发（防伪造）

下载类型：
  - local: 从本地目录复制（开发期演示用）
  - zip:   从本地发行包 zip 解压
  - url:   从网络 URL 下载 zip（真实远程市场用）
  - git:   预留扩展点
"""
from __future__ import annotations

import hashlib
import hmac
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .models import DownloadSpec, InstalledPlugin, Manifest
from .net import download as net_download


class InstallError(Exception):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class Installer:
    def __init__(self, plugins_dir: Path, root: Path):
        self.plugins_dir = Path(plugins_dir)
        self.root = Path(root)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

    def install(self, manifest: Manifest) -> InstalledPlugin:
        if manifest.download is None:
            raise InstallError(f"插件 {manifest.id} 缺少 download 信息，无法安装")
        dest = self.plugins_dir / manifest.id
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        self._fetch(manifest.download, dest)
        return InstalledPlugin(
            plugin_id=manifest.id,
            version=manifest.version,
            path=str(dest),
            sha256=manifest.download.sha256,
            installed_at=datetime.now(timezone.utc).isoformat(),
        )

    def _resolve(self, source: str) -> Path:
        p = Path(source)
        return p if p.is_absolute() else self.root / p

    def _fetch(self, ds: DownloadSpec, dest: Path) -> None:
        if ds.type == "local":
            src = self._resolve(ds.source)
            if not src.exists():
                raise InstallError(f"本地源不存在: {src}")
            shutil.copytree(src, dest)
        elif ds.type == "zip":
            self._install_zip(self._resolve(ds.source), ds, dest)
        elif ds.type == "url":
            self._install_url(ds, dest)
        elif ds.type == "git":
            raise InstallError("git 下载尚未实现")
        else:
            raise InstallError(f"不支持的下载类型: {ds.type}")

    def _install_url(self, ds: DownloadSpec, dest: Path) -> None:
        tmp = Path(tempfile.mktemp(suffix=".zip"))
        try:
            net_download(ds.source, tmp, timeout=30)
            self._install_zip(tmp, ds, dest)
        finally:
            tmp.unlink(missing_ok=True)

    def _install_zip(self, src: Path, ds: DownloadSpec, dest: Path) -> None:
        if not src.exists():
            raise InstallError(f"发行包不存在: {src}")
        data = src.read_bytes()
        # 1) 完整性
        if ds.sha256:
            actual = sha256_file(src)
            if actual != ds.sha256:
                raise InstallError(
                    f"sha256 校验失败(内容被篡改): 期望 {ds.sha256[:12]}... 实际 {actual[:12]}..."
                )
        # 2) 来源认证
        if ds.signature:
            self._verify_signature(data, ds.signature)
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(src) as z:
            z.extractall(dest)

    def _verify_signature(self, data: bytes, want: str) -> None:
        key_path = self.root / "tools" / "signing.key"
        if not key_path.exists():
            raise InstallError("签名密钥缺失，无法验签")
        key = key_path.read_bytes()
        actual = hmac.new(key, data, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(actual, want):
            raise InstallError("签名校验失败(来源不可信/伪造包): 拒绝安装")