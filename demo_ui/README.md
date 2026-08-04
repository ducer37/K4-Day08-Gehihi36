# E-commerce Support RAG Chatbot Demo

Standalone, dependency-free dashboard for presenting the CP1–CP6 RAG workflow. It does not modify `src/` or `app.py`.

## Run

From the project root:

```powershell
python demo_ui/server.py
```

Open http://127.0.0.1:8765 in a browser.

The backend safely detects the original modules. When unfinished modules are unavailable, it displays that state and uses a lightweight, local lexical evidence fallback over `data/standardized/`. This keeps the demo operational without API keys or heavyweight dependencies. Answers without sufficient evidence return exactly `I cannot verify this information`.

## Endpoints

- `GET /health`
- `GET /api/status`
- `POST /api/chat` with `{"query":"..."}`
- `GET /api/chat/stream?query=...` (SSE)
- `GET /api/logs`

## Smoke test

Start the server in one terminal, then run:

```powershell
python demo_ui/smoke_test.py
```

Request logs are appended to `demo_ui/logs/rag_demo_logs.jsonl`. The Export Logs icon in the UI opens the latest entries.
