"""提供能力：report-bundle。依赖 minify-json 与 csv-report。

run(request, resolve)：通过 resolve(dep_capability, payload) 在运行时调用依赖能力，
把它们的产出组合进本次结果，证明「依赖真的被用起来」，而非只装不调。
"""


def run(request, resolve=None):
    out = {"bundle": "report-bundle-v1.0.0"}
    if resolve is None:
        out["note"] = "resolve 未注入（单插件直调场景）"
        return out

    minify_out = resolve("minify-json", {"json": '{"name": "demo", "count": 2}'})
    csv_out = resolve("csv-report", {"rows": [["k", "v"], ["a", 1], ["b", 2]]})

    out["minified_by_dep"] = minify_out.get("result") if isinstance(minify_out, dict) else minify_out
    out["csv_by_dep"] = csv_out.get("result") if isinstance(csv_out, dict) else csv_out
    return out