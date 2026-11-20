"""模拟攻击者：篡改某插件的发行包并重算 sha256，但无法伪造签名（没有密钥）。

用法: python tools/simulate_tamper.py [plugin_id]
默认篡改 json-minify。

随后运行 `python main.py "压缩json" --registry`：
  - sha256 会被攻击者改对、通过校验；
  - 但签名验签失败 -> 拒绝安装（status=error）。
随后运行 `python tools/build_registry.py` 可恢复为正常签名包。
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "registry" / "registry.json"
PKG = ROOT / "registry" / "packages"


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "json-minify"
    reg = json.loads(REG.read_text(encoding="utf-8"))
    entry = next((p for p in reg["plugins"] if p["id"] == target), None)
    if entry is None:
        print(f"未找到插件 {target}")
        return
    src = entry["download"]["source"].split("/")[-1]
    zip_path = PKG / src

    # 读原 zip 内容，替换 plugin.py（注入恶意逻辑）
    items = {}
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            items[name] = z.read(name)
    items["plugin.py"] = b'def run(request, resolve=None):\n    return {"evil": True, "pwned": 1}\n'
    with zipfile.ZipFile(zip_path, "w") as z:
        for name, data in items.items():
            z.writestr(name, data)

    # 攻击者能重算 sha256（完整性可伪造），但算不出 HMAC 签名
    new_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    entry["download"]["sha256"] = new_sha  # 改 sha256 让它通过
    # signature 保持旧值 —— 攻击者没有 signing.key，无法签出匹配值
    REG.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已篡改 {target}：替换 plugin.py + 重算 sha256；signature 保持旧值（即将验签失败）")


if __name__ == "__main__":
    main()