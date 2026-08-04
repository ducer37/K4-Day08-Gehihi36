"""Minimal API smoke test. Run after starting server.py."""
import json
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8765"

assert json.load(urlopen(BASE + "/health"))["status"] == "ok"
testcases = json.load(urlopen(BASE + "/api/testcases"))["items"]
assert len(testcases) >= 20, len(testcases)

req = Request(
    BASE + "/api/chat",
    data=json.dumps(
        {
            "query": testcases[0]["question"],
            "top_k": 3,
            "score_threshold": 0.48,
            "use_reranking": True,
        }
    ).encode(),
    headers={"Content-Type": "application/json"},
)
result = json.load(urlopen(req))
assert all(key in result for key in ("answer", "sources", "trace", "metrics")), result
assert result["answer"] and isinstance(result["trace"], list)
assert result["metrics"]["top_k"] == 3, result["metrics"]
assert result["metrics"]["score_threshold"] == 0.48, result["metrics"]
print("Smoke test passed: testcases, answer, sources, trace, and metrics returned.")
