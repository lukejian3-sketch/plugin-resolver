"""把 demo/source 下的插件「发布」到 registry：打包 zip + 签名 + 生成清单。

签名：HMAC-SHA256（对称签名，演示「验谁发布」；生产应换 Ed25519/RSA 非对称）。
密钥：tools/signing.key（首次自动生成 32 字节随机密钥，发布者持有）。

本地模式（默认）：download.type=zip，source 为本地相对路径。
远程模式：--base-url 指定前缀，download.type=url，source 为完整网络地址。

用法:
  python tools/build_registry.py
  python tools/build_registry.py --base-url http://127.0.0.1:8765 --out registry.remote.json
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "demo" / "source"
REGISTRY = ROOT / "registry"
PKG = REGISTRY / "packages"
TOOLS = ROOT / "tools"
KEY_FILE = TOOLS / "signing.key"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_or_create_key() -> bytes:
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    KEY_FILE.write_bytes(key)
    return key


def sign(key: bytes, data: bytes) -> str:
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description="打包并签名发布插件到 registry")
    ap.add_argument("--base-url", default=None, help="远程前缀（生成 type=url 的远程清单）")
    ap.add_argument("--out", default="registry.json", help="清单输出文件名（放在 registry/ 下）")
    args = ap.parse_args()

    key = load_or_create_key()
    PKG.mkdir(parents=True, exist_ok=True)
    plugins = []
    for pdir in sorted(SOURCE.iterdir()):
        if not pdir.is_dir():
            continue
        m = json.loads((pdir / "manifest.json").read_text(encoding="utf-8"))
        pid = m["id"]
        version = m.get("version", "0.0.0")
        zip_name = f"{pid}-{version}.zip"
        zip_path = PKG / zip_name
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(pdir.iterdir()):
                if f.name == "__pycache__":
                    continue
                z.write(f, f.name)
        data = zip_path.read_bytes()
        sha = sha256_file(zip_path)
        sig = sign(key, data)
        if args.base_url:
            dl = {"type": "url",
                  "source": f"{args.base_url.rstrip('/')}/registry/packages/{zip_name}",
                  "version": version, "sha256": sha, "signature": sig}
        else:
            dl = {"type": "zip", "source": f"registry/packages/{zip_name}",
                  "version": version, "sha256": sha, "signature": sig}
        plugins.append({
            "id": pid, "name": m.get("name", pid), "version": version,
            "description": m.get("description", ""), "triggers": m.get("triggers", []),
            "capabilities": m.get("capabilities", []), "entry": m.get("entry", "plugin.py"),
            "dependencies": m.get("dependencies", []),
            "rating": float(m.get("rating", 0.0)),
            "downloads": int(m.get("downloads", 0)),
            "download": dl,
        })
    out = REGISTRY / args.out
    out.write_text(json.dumps({"plugins": plugins}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已发布 {len(plugins)} 个插件 -> {out.relative_to(ROOT)}（签名密钥 tools/signing.key）")
    for p in plugins:
        d = p["download"]
        print(f"  {p['id']}@{p['version']}  type={d['type']}  sig={d['signature'][:16]}...")


if __name__ == "__main__":
    main()