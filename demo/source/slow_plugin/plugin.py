"""提供能力：slow-job。故意长时间阻塞，演示沙箱超时隔离。"""
import time


def run(request, resolve=None):
    time.sleep(60)  # 沙箱模式下会被超时终止
    return {"done": True}