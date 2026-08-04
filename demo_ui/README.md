# E-commerce Support RAG Chatbot Demo

Standalone dashboard for presenting the CP1-CP6 RAG workflow. It stays inside `demo_ui/` and calls the original `src/` modules.

## Run

From the project root:

```powershell
python demo_ui/server.py
```

Open http://127.0.0.1:8765 in a browser.

## Endpoints

- `GET /health`
- `GET /api/status`
- `GET /api/testcases`
- `POST /api/chat` with `{"query":"...", "top_k":5, "score_threshold":0.48, "use_reranking":true, "use_llm":false}`
- `GET /api/chat/stream?query=...&top_k=5&score_threshold=0.48&use_reranking=true&use_llm=false` (SSE)
- `GET /api/logs`

## Runtime Controls

- `top_k`: number of retrieved sources to show/use.
- `score_threshold`: fallback threshold using the original semantic cosine score.
- `use_reranking`: toggles RRF merge/reranking.
- `use_llm`: calls OpenAI for answer generation when `OPENAI_API_KEY` is set; otherwise uses a citation-safe context fallback.
- `golden testcases`: loads questions from `group_project/evaluation/golden_dataset.json`.

## Smoke Test

Start the server in one terminal, then run:

```powershell
python demo_ui/smoke_test.py
```

Request logs are appended to `demo_ui/logs/rag_demo_logs.jsonl`. The Export Logs icon opens the latest entries.
