"""提供能力：minify-json。约定入口 run(request: dict) -> Any。"""
import json


def run(request):
    sample = request.get("json", '{"name": "Alice", "items": [1, 2, 3]}')
    data = json.loads(sample)
    compact = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return {
        "minified": compact,
        "saved_chars": len(sample) - len(compact),
        "origin_chars": len(sample),
        "plugin_version": "1.1.0",
    }