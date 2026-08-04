"""Minimal API smoke test. Run after starting server.py."""
import json
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8765"
assert json.load(urlopen(BASE + "/health"))["status"] == "ok"
req = Request(BASE + "/api/chat", data=json.dumps({"query": "Shopee hoàn tiền trong bao lâu?"}).encode(), headers={"Content-Type": "application/json"})
result = json.load(urlopen(req))
assert all(key in result for key in ("answer", "sources", "trace", "metrics")), result
assert result["answer"] and isinstance(result["trace"], list)
print("Smoke test passed: answer, sources, trace, and metrics returned.")
