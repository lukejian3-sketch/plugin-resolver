"""提供能力：csv-report。约定入口 run(request: dict) -> Any。"""
import csv
import io


def run(request):
    rows = request.get("rows", [["name", "age"], ["Alice", 30], ["Bob", 25]])
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return {"csv": buf.getvalue(), "row_count": len(rows)}