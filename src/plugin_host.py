"""沙箱执行的插件宿主：在独立进程里加载插件并运行 run(request)。

用法: python plugin_host.py <entry.py> <request.json> <result.json>

- 输入/输出都走临时 JSON 文件（避开管道捕获），子进程 stdout/stderr 丢弃。
- 结果形如 {"ok": true, "result": ...} 或 {"ok": false, "error": ..., "traceback": ...}。
- 沙箱内不给 resolve 跨进程回调（本 MVP 的隔离模式不支持运行层依赖注入）。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import traceback
from pathlib import Path


def main() -> None:
    entry = Path(sys.argv[1])
    req_path = Path(sys.argv[2])
    res_path = Path(sys.argv[3])

    request = json.loads(req_path.read_text(encoding="utf-8"))
    try:
        spec = importlib.util.spec_from_file_location("_sandboxed_plugin", entry)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fn = getattr(mod, "run")
        result = fn(request, None)  # 隔离模式：不注入 resolve
        out = {"ok": True, "result": result}
    except Exception as e:  # noqa: BLE001
        out = {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
        }
    res_path.write_text(
        json.dumps(out, ensure_ascii=False, default=str), encoding="utf-8"
    )


if __name__ == "__main__":
    main()