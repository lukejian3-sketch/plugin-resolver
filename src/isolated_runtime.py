"""进程隔离运行时：把插件放到独立子进程执行，超时自动终止。

与 Runtime 的区别：
  - Runtime：在 resolver 进程内 importlib 直接执行（快，支持 resolve 依赖注入）
  - IsolatedRuntime：subprocess 独立进程执行（慢一点，但可超时隔离；
    本 MVP 不在子进程内提供跨进程 resolve）
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

from .models import InstalledPlugin, Manifest

HOST = Path(__file__).parent / "plugin_host.py"


class IsolatedRuntime:
    def __init__(self, timeout: int = 5):
        self.timeout = timeout

    def load(
        self,
        manifest: Manifest,
        plugin: InstalledPlugin,
        request: dict,
        resolve: Optional[Callable] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        entry = Path(plugin.path) / manifest.entry
        if not entry.exists():
            raise RuntimeError(f"插件入口缺失: {entry}")

        req_f = Path(tempfile.mktemp(suffix=".req.json"))
        res_f = Path(tempfile.mktemp(suffix=".res.json"))
        req_f.write_text(
            json.dumps(request, ensure_ascii=False, default=str), encoding="utf-8"
        )
        t = timeout if timeout is not None else self.timeout
        try:
            subprocess.run(
                [sys.executable, str(HOST), str(entry), str(req_f), str(res_f)],
                timeout=t,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            data = json.loads(res_f.read_text(encoding="utf-8"))
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"插件执行超时(>{t}s)，已隔离终止")
        except json.JSONDecodeError:
            raise RuntimeError("插件子进程未返回有效结果")
        finally:
            req_f.unlink(missing_ok=True)
            res_f.unlink(missing_ok=True)

        if not data.get("ok"):
            raise RuntimeError(f"插件执行失败: {data.get('error')}")
        return data.get("result")