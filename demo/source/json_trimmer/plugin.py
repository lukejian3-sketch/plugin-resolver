"""另一个 minify-json 实现（评分较低，用于演示多候选择优）。"""


def run(request, resolve=None):
    sample = request.get("json", '{"x": 1, "y": 2}')
    return {"trimmed": " ".join(sample.split()), "impl": "json-trimmer"}