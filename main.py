"""插件解析器 CLI 演示。

用法：
  python main.py "压缩这段 json 并生成 csv 报告"      # 本地 catalog 模式
  python main.py "压缩json" --explain
  python main.py "压缩json" --rebuild
  python main.py "压缩json" --no-cache
  python main.py "压缩json" --registry                # 本地 registry（zip 模式）
  python main.py "压缩json" --registry-url http://127.0.0.1:8765/registry/registry.remote.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.resolver import Resolver

SAMPLE_PAYLOAD = {
    "json": '{"name": "Alice", "items": [1, 2, 3], "active": true}',
    "rows": [["name", "age"], ["Alice", 30], ["Bob", 25], ["Carol", 28]],
}


def main() -> None:
    ap = argparse.ArgumentParser(description="插件解析器 demo")
    ap.add_argument("req", help="任务描述文字")
    ap.add_argument("--explain", action="store_true", help="打印意图匹配明细")
    ap.add_argument("--rebuild", action="store_true", help="先按 plugins/ 重建索引")
    ap.add_argument("--no-cache", action="store_true", help="跳过索引命中，模拟冷启动")
    ap.add_argument("--registry", action="store_true", help="使用本地 registry（zip）清单")
    ap.add_argument("--registry-url", default=None, help="远程 registry 清单 URL")
    ap.add_argument("--isolated", action="store_true", help="使用独立进程沙箱执行插件")
    ap.add_argument("--timeout", type=int, default=5, help="沙箱模式下的执行超时秒数")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent), help="工程根目录")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if args.registry_url:
        catalog_path = args.registry_url
    elif args.registry:
        catalog_path = root / "registry" / "registry.json"
    else:
        catalog_path = None
    r = Resolver(root, catalog_path=catalog_path, isolated=args.isolated, timeout=args.timeout)

    if args.explain:
        print("== 意图匹配明细 ==")
        for row in r.matcher.explain(args.req):
            print(f"  plugin={row['plugin']:<15} capability={row['capability']:<15} "
                  f"score={row['score']:<6} layers={row['layers']} hits={row['hits']}")

    if args.rebuild:
        n = r.index.rebuild(root / "plugins")
        print(f"== 重建索引完成，恢复 {n} 个插件 ==")

    if args.no_cache:
        r.index.index.capabilities.clear()
        print("== 已清空索引（模拟第一阶段冷启动）==")

    print(f"== 请求：{args.req} ==")
    results = r.resolve_and_invoke(args.req, SAMPLE_PAYLOAD)
    for out in results:
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()