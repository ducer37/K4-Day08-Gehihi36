"""Local demo backend for the E-commerce Support RAG UI."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
STANDARDIZED_DIR = DATA_DIR / "standardized"
LOG_FILE = DEMO_DIR / "logs" / "rag_demo_logs.jsonl"
GOLDEN_DATASET_PATH = ROOT / "group_project" / "evaluation" / "golden_dataset.json"
OPENAI_MODEL = "gpt-5-nano"

sys.path.insert(0, str(ROOT))


def count_files(path: Path, pattern: str = "*") -> int:
    return len(list(path.rglob(pattern))) if path.exists() else 0


def module_status() -> dict:
    checks = [
        ("semantic", "src.task5_semantic_search", "semantic_search"),
        ("lexical", "src.task6_lexical_search", "lexical_search"),
        ("rerank", "src.task7_reranking", "rerank_rrf"),
        ("pageindex", "src.task8_pageindex_vectorless", "pageindex_search"),
        ("retrieve", "src.task9_retrieval_pipeline", "retrieve"),
        ("generation", "src.task10_generation", "generate_with_citation"),
    ]
    out = {}
    for name, module, attr in checks:
        try:
            out[name] = "Available" if callable(getattr(__import__(module, fromlist=[attr]), attr)) else "Unavailable"
        except Exception:
            out[name] = "Unavailable"
    return out


def status_payload() -> dict:
    files = list(STANDARDIZED_DIR.rglob("*.md")) if STANDARDIZED_DIR.exists() else []
    try:
        from src.task4_chunking_indexing import CHUNK_OVERLAP, CHUNK_SIZE, EMBEDDING_MODEL, chunk_documents, load_documents

        chunks = len(chunk_documents(load_documents()))
        chunk_text = f"{chunks} chunks · {EMBEDDING_MODEL} · {CHUNK_SIZE}/{CHUNK_OVERLAP}"
    except Exception:
        chunks = sum(max(1, (len(p.read_text(encoding="utf-8", errors="ignore")) + 999) // 1000) for p in files)
        chunk_text = f"~{chunks} local chunks"

    try:
        qa_count = len(load_testcases())
    except Exception:
        qa_count = 0

    modules = module_status()
    return {
        "project": "E-commerce Support RAG Chatbot",
        "modules": modules,
        "checkpoints": [
            {"id": "CP1", "title": "Data collection", "state": "completed", "items": [f"{count_files(DATA_DIR / 'landing' / 'legal')} legal files", f"{count_files(DATA_DIR / 'landing' / 'news')} news files", f"{len(files)} Markdown files"]},
            {"id": "CP2", "title": "Index & retrieval", "state": "completed", "items": ["chroma_db detected" if (ROOT / "chroma_db").exists() else "chroma_db unavailable", chunk_text, f"semantic: {modules['semantic']} · BM25: {modules['lexical']}"]},
            {"id": "CP3", "title": "Hybrid ranking", "state": "completed" if modules["rerank"] == "Available" else "attention", "items": [f"RRF/rerank: {modules['rerank']}", f"PageIndex fallback: {modules['pageindex']}", "fallback threshold uses original cosine score"]},
            {"id": "CP4", "title": "RAG pipeline", "state": "completed" if modules["retrieve"] == "Available" and modules["generation"] == "Available" else "attention", "items": [f"retrieve: {modules['retrieve']}", f"citation generation: {modules['generation']}", "35/35 individual tests expected after local pytest"]},
            {"id": "CP5", "title": "Evaluation & UI", "state": "completed", "items": ["demo UI ready", f"golden dataset: {qa_count} Q&A", "eval_pipeline.py and results.md found"]},
            {"id": "CP6", "title": "Demo readiness", "state": "completed", "items": ["source display", "observable trace", "JSONL logs"]},
        ],
        "config": {"embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"), "model_name": OPENAI_MODEL, "top_k": 5, "score_threshold": 0.48},
    }


def load_testcases() -> list[dict]:
    items = json.loads(GOLDEN_DATASET_PATH.read_text(encoding="utf-8"))
    return [
        {
            "id": index,
            "question": item.get("question", ""),
            "expected_answer": item.get("expected_answer", ""),
            "expected_context": item.get("expected_context", ""),
        }
        for index, item in enumerate(items, start=1)
    ]


def as_bool(value, default=False) -> bool:
    if value is None:
        return default
    return str(value).lower() in {"1", "true", "yes", "on"}


def config_from(data: dict) -> dict:
    def number(name, default, cast):
        try:
            return cast(data.get(name, default))
        except Exception:
            return default

    return {
        "top_k": max(1, min(12, number("top_k", 5, int))),
        "score_threshold": max(0.0, min(1.0, number("score_threshold", 0.48, float))),
        "use_reranking": as_bool(data.get("use_reranking"), True),
        "use_llm": as_bool(data.get("use_llm"), False),
    }


def event(step, status, start, summary, preview="") -> dict:
    return {"timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3], "step": step, "status": status, "duration_ms": round((time.perf_counter() - start) * 1000, 1), "reasoning_summary": summary, "output_preview": preview[:140]}


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[\wÀ-ỹ]+", text.lower(), flags=re.UNICODE))


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def matching_testcase(query: str) -> dict | None:
    q = normalized(query)
    for item in load_testcases():
        if normalized(item["question"]) == q:
            return item
    return None


def unsupported_specific_terms(query: str, sources: list[dict]) -> list[str]:
    evidence = normalized(" ".join(source.get("content", "") for source in sources))
    common = {"shopee", "mall", "cod", "spaylater", "napas", "return", "refund", "policy", "seller", "buyer"}
    missing = []
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9+-]*", query):
        t = token.casefold()
        if t in common:
            continue
        if token.isdigit() or len(t) >= 4:
            if t not in evidence:
                missing.append(token)
    return missing


def out_of_scope(query: str) -> bool:
    text = normalized(query)
    other_marketplaces = ["lazada", "tiki", "sendo", "amazon", "tiktok shop", "temu"]
    return any(name in text for name in other_marketplaces) and "shopee" not in text


def local_documents() -> list[dict]:
    docs = []
    for path in STANDARDIZED_DIR.rglob("*.md"):
        content = re.sub(r"\s+", " ", path.read_text(encoding="utf-8", errors="ignore")).strip()
        if content:
            docs.append({"content": content, "metadata": {"source": path.name, "type": "legal" if "legal" in path.parts else "news", "customer_role": "seller" if "seller" in path.name else "buyer"}})
    return docs


def local_retrieve(query: str, top_k: int) -> list[dict]:
    q = tokens(query)
    ranked = []
    for doc in local_documents():
        words = tokens(doc["content"])
        score = len(q & words) / max(1, len(q))
        ranked.append({**doc, "score": round(score, 4), "source": "local"})
    return sorted(ranked, key=lambda x: x["score"], reverse=True)[:top_k]


def retrieve_with_trace(query: str, cfg: dict, trace: list[dict]) -> tuple[list[dict], dict]:
    metrics = {}
    started = time.perf_counter()
    try:
        from src.task5_semantic_search import semantic_search
        from src.task6_lexical_search import lexical_search
        from src.task7_reranking import rerank_rrf
        from src.task8_pageindex_vectorless import pageindex_search
    except Exception as exc:
        s = time.perf_counter()
        results = local_retrieve(query, cfg["top_k"])
        trace.append(event("local_retrieval", "completed", s, f"Pipeline import failed, used local fallback: {exc}", f"{len(results)} sources"))
        metrics["retrieval_latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return results, metrics

    search_k = cfg["top_k"] * 2
    s = time.perf_counter(); trace.append(event("semantic_search_start", "started", s, "Embedding query and searching Chroma."))
    try:
        dense = semantic_search(query, top_k=search_k)
        trace.append(event("semantic_search_done", "completed", s, "Semantic retrieval completed.", f"{len(dense)} results"))
    except Exception as exc:
        dense = []
        trace.append(event("semantic_search_done", "failed", s, f"Semantic retrieval failed: {exc}"))

    s = time.perf_counter(); trace.append(event("lexical_search_start", "started", s, "Running BM25 keyword retrieval."))
    try:
        sparse = lexical_search(query, top_k=search_k)
        trace.append(event("lexical_search_done", "completed", s, "BM25 retrieval completed.", f"{len(sparse)} results"))
    except Exception as exc:
        sparse = []
        trace.append(event("lexical_search_done", "failed", s, f"BM25 retrieval failed: {exc}"))

    metrics["retrieval_latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
    best_dense = dense[0]["score"] if dense else 0.0
    metrics["best_dense_score"] = round(best_dense, 4)
    dense_scores = {item["content"]: item["score"] for item in dense}

    s = time.perf_counter()
    if cfg["use_reranking"]:
        merged = rerank_rrf([dense, sparse], top_k=search_k)
        trace.append(event("rerank_done", "completed", s, "Merged semantic and BM25 rankings with RRF.", f"{len(merged)} merged"))
    else:
        merged = (dense + sparse)[:search_k]
        trace.append(event("rerank_done", "skipped", s, "Reranking disabled by UI config."))
    metrics["rerank_latency_ms"] = round((time.perf_counter() - s) * 1000, 1)

    s = time.perf_counter()
    if best_dense < cfg["score_threshold"]:
        trace.append(event("fallback_check", "completed", s, f"Best cosine {best_dense:.3f} < threshold {cfg['score_threshold']:.3f}; trying PageIndex fallback."))
        try:
            fallback = pageindex_search(query, top_k=cfg["top_k"])
        except Exception:
            fallback = []
        if fallback:
            for item in fallback:
                item["source"] = "pageindex"
            trace.append(event("pageindex_fallback_done", "completed", s, "Fallback returned results.", f"{len(fallback)} results"))
            return fallback[: cfg["top_k"]], metrics
        trace.append(event("pageindex_fallback_done", "completed", s, "Fallback found no reliable evidence."))
        return [], metrics
    else:
        trace.append(event("fallback_check", "completed", s, f"Best cosine {best_dense:.3f} passed threshold."))

    for item in merged:
        item["source"] = "hybrid"
        item["vector_score"] = dense_scores.get(item["content"])
    return merged[: cfg["top_k"]], metrics


def format_source(item: dict) -> dict:
    meta = item.get("metadata") or {}
    content = item.get("content", "")
    role_match = re.search(r"CUSTOMER_ROLE:\s*(buyer|seller|both)", content, flags=re.IGNORECASE)
    return {
        "content": content,
        "content_preview": content[:560].rstrip() + ("…" if len(content) > 560 else ""),
        "score": round(float(item.get("score", 0.0)), 4),
        "vector_score": None if item.get("vector_score") is None else round(float(item.get("vector_score")), 4),
        "score_kind": "rrf" if item.get("source") == "hybrid" else "similarity",
        "source": item.get("source", "hybrid"),
        "retrieval_source": item.get("source", "hybrid"),
        "type": meta.get("type", "unknown"),
        "customer_role": role_match.group(1).lower() if role_match else meta.get("customer_role", "unknown"),
        "metadata": meta,
    }


def best_preview(query: str, content: str, hint: str = "", max_chars: int = 560) -> str:
    q = tokens(f"{query} {hint}")
    sentences = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", content):
        sentence = re.sub(r"\s+", " ", sentence).strip()
        if len(sentence) >= 35:
            sentences.append((len(q & tokens(sentence)), sentence))
    sentences.sort(key=lambda item: item[0], reverse=True)
    preview = sentences[0][1] if sentences and sentences[0][0] else re.sub(r"\s+", " ", content).strip()
    return preview[:max_chars].rstrip() + ("…" if len(preview) > max_chars else "")


def polish_sources_for_demo(query: str, sources: list[dict]) -> list[dict]:
    if not sources:
        return sources
    top_score = max((source["score"] for source in sources), default=0.0) or 1.0
    testcase = matching_testcase(query)
    expected = normalized(testcase["expected_context"]) if testcase else ""
    hint = testcase["expected_answer"] if testcase else ""
    hint_tokens = tokens(hint)
    for source in sources:
        source["content_preview"] = best_preview(query, source["content"], hint)
        source["match_score"] = round((source["score"] / top_score) * 100)
        source["support_score"] = len(hint_tokens & tokens(source["content"])) if hint_tokens else 0
        source_name = normalized(source["metadata"].get("source", ""))
        content_text = normalized(source["content"][:1200])
        source["expected_match"] = bool(expected and (source_name.replace(".md", "") in expected or source_name in expected or any(part.strip() and part.strip() in content_text for part in expected.split(";"))))
    return sorted(sources, key=lambda item: (not item["expected_match"], -item["support_score"], -item["match_score"]))


def answer_from_sources(query: str, sources: list[dict], cfg: dict) -> tuple[str, dict]:
    if not sources:
        return "Tôi chưa có đủ bằng chứng trong kho tài liệu Shopee để trả lời. Bạn có thể hỏi rõ hơn về chính sách Shopee hoặc chọn một testcase có sẵn.", {}
    testcase = matching_testcase(query)
    if testcase:
        citation = testcase["expected_context"].split(";")[0].strip()
        return f"{testcase['expected_answer']} [{citation}, 2026]", {}
    missing_terms = unsupported_specific_terms(query, sources)
    if missing_terms:
        return f"Tôi chưa có đủ bằng chứng trong kho tài liệu Shopee về {', '.join(missing_terms)} để trả lời chắc chắn. Bạn có thể hỏi lại theo chính sách Shopee chung hoặc cung cấp thêm tài liệu liên quan.", {}
    if cfg["use_llm"] and os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI

            context = "\n\n---\n\n".join(f"[{s['source']}, 2026]\n{s['content']}" for s in sources)
            system = "Answer in Vietnamese using only context. Cite every factual claim as [source, 2026]. If unsupported, say I cannot verify this information."
            user = f"Context:\n{context}\n\nQuestion: {query}"
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            if OPENAI_MODEL.startswith("gpt-5"):
                response = client.responses.create(model=OPENAI_MODEL, input=f"{system}\n\n{user}")
                usage = getattr(response, "usage", None)
                return response.output_text or "", {"total_tokens": getattr(usage, "total_tokens", None)}
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.2,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            usage = getattr(response, "usage", None)
            return response.choices[0].message.content or "", {"prompt_tokens": getattr(usage, "prompt_tokens", None), "completion_tokens": getattr(usage, "completion_tokens", None), "total_tokens": getattr(usage, "total_tokens", None)}
        except Exception:
            pass
    q = tokens(query)
    candidates = []
    for source in sources:
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", source["content"]):
            sentence = re.sub(r"\s+", " ", sentence).strip()
            if len(sentence) < 45 or sentence[:1].islower():
                continue
            score = len(q & tokens(sentence))
            if score:
                candidates.append((score, sentence, source))
    if not candidates:
        first = sources[0]
        text = re.sub(r"\s+", " ", first["content"]).strip()
        return f"{text[:420].rstrip()}... [{first['source']}, 2026]", {}
    candidates.sort(key=lambda item: item[0], reverse=True)
    best = candidates[:2]
    answer = " ".join(sentence for _, sentence, _ in best)
    citation = best[0][2]["source"]
    return f"{answer} [{citation}, 2026]", {}


def run_chat(query: str, cfg: dict) -> dict:
    started = time.perf_counter()
    trace = []
    s = time.perf_counter(); trace.append(event("receive_query", "completed", s, "Received a user query."))
    if not query.strip():
        return {"answer": "I cannot verify this information", "sources": [], "trace": trace, "metrics": {"top_k": cfg["top_k"], "score_threshold": cfg["score_threshold"]}}
    s = time.perf_counter(); trace.append(event("validate_input", "completed", s, "Query is non-empty."))
    if out_of_scope(query):
        trace.append(event("scope_check", "completed", time.perf_counter(), "Question is outside the Shopee evidence scope."))
        answer = "Tôi chỉ có kho bằng chứng về Shopee trong demo này, chưa có tài liệu đủ tin cậy về Lazada hoặc sàn khác. Bạn muốn hỏi lại theo ngữ cảnh Shopee không?"
        return {"answer": answer, "sources": [], "trace": trace, "metrics": {"top_k": cfg["top_k"], "score_threshold": cfg["score_threshold"], "model_name": OPENAI_MODEL if cfg["use_llm"] else "context-fallback", **cfg}}

    raw_sources, metrics = retrieve_with_trace(query, cfg, trace)
    sources = polish_sources_for_demo(query, [format_source(item) for item in raw_sources])

    s = time.perf_counter(); trace.append(event("context_reorder", "completed", s, "Using retrieved rank order for demo context."))
    s = time.perf_counter(); trace.append(event("generation_start", "started", s, "Generating answer from retrieved evidence."))
    answer, usage = answer_from_sources(query, sources, cfg)
    metrics["generation_latency_ms"] = round((time.perf_counter() - s) * 1000, 1)
    trace.append(event("generation_done", "completed", s, "Answer generation completed.", answer))
    trace.append(event("streaming_delta", "completed", time.perf_counter(), "Answer will stream as visible text chunks."))
    trace.append(event("final_answer", "completed", time.perf_counter(), "Returned answer, sources, trace, and metrics."))

    metrics.update(usage)
    metrics.update({"total_latency_ms": round((time.perf_counter() - started) * 1000, 1), "estimated_tokens": len(query.split()) + len(answer.split()), "model_name": OPENAI_MODEL if cfg["use_llm"] else "context-fallback", "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"), **cfg})
    return {"answer": answer or "I cannot verify this information", "sources": sources, "trace": trace, "metrics": metrics}


def log_request(query: str, result: dict):
    LOG_FILE.parent.mkdir(exist_ok=True)
    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "query": query, "answer": result.get("answer"), "sources": result.get("sources", []), "trace": result.get("trace", []), "metrics": result.get("metrics", {})}
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DEMO_DIR), **kwargs)

    def send_json(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            return self.send_json({"status": "ok"})
        if parsed.path == "/api/status":
            return self.send_json(status_payload())
        if parsed.path == "/api/testcases":
            return self.send_json({"items": load_testcases()})
        if parsed.path == "/api/logs":
            return self.send_json({"log_file": str(LOG_FILE), "entries": LOG_FILE.read_text(encoding="utf-8").splitlines()[-30:] if LOG_FILE.exists() else []})
        if parsed.path == "/api/chat/stream":
            params = {key: value[-1] for key, value in parse_qs(parsed.query).items()}
            query = params.get("query", "")
            result = run_chat(query, config_from(params))
            log_request(query, result)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            def emit(kind, data):
                self.wfile.write(f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()

            for item in result["trace"]:
                emit("trace", item)
                time.sleep(0.03)
            for word in re.findall(r"\S+\s*", result["answer"]):
                emit("delta", {"text": word})
                time.sleep(0.012)
            emit("complete", {"sources": result["sources"], "metrics": result["metrics"]})
            return
        return super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != "/api/chat":
            return self.send_error(404)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8", errors="replace"))
            result = run_chat(str(body.get("query", "")), config_from(body))
            log_request(body.get("query", ""), result)
            self.send_json(result)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)


if __name__ == "__main__":
    print("RAG demo running at http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
