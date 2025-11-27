# Development Guide — back_end

This guide provides concrete, copy-paste steps to get the `back_end` service running locally, how to test key endpoints, and common troubleshooting tips.

Scope: assumes you're working from the `back_end/` folder in this repository.

---

## Prerequisites

- Python 3.10+ (3.11 recommended)
- Git
- A Supabase project (if you use Supabase features) and/or Pinecone account (if using vector store)
- An OpenAI API key
- Optional: Redis (for Celery) if you plan to run background workers

---

## Files to check

- `main.py` — FastAPI app and most of the routes
- `routes/agent.py` — vector search + agent endpoint
- `routes/documents.py` — document upload and ingest
- `services/` — helpers for embeddings, Pinecone, Supabase, file parsing
- `middleware/auth.py` — Supabase auth middleware
- `.env` — local environment variables (create from your secrets)

---

## Recommended environment variables

Create `back_end/.env` with the variables your project needs. At minimum:

```
OPENAI_API_KEY=sk_xxx
SUPABASE_URL=https://your-supabase-url
SUPABASE_ANON_KEY=your_anon_key
EMBEDDING_MODEL=text-embedding-3-small
EMBED_BATCH_SIZE=64
PINECONE_API_KEY=xxx
PINECONE_ENV=us-west1-gcp
TOP_K=5
CELERY_BROKER_URL=redis://localhost:6379/0
```

Check `services/*.py` for any extra variables used by your code.

---

## Quick local setup (Windows PowerShell)

```powershell
cd back_end
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# create .env and populate as shown above
```

---

## Run the API server

```powershell
# from back_end/
& .\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

- The app will be available at `http://127.0.0.1:8001`
- If you run the frontend on a different host or via Vercel, set `NEXT_PUBLIC_FASTAPI_URL` in the frontend to this URL for dev.

---

## Run Celery workers (optional)

If you use the Celery workers in `workers/`:

```powershell
# start Redis (or ensure your broker is running)
# example: using redis-server installed locally
redis-server
# in a separate terminal (with venv active)
cd back_end
& .\.venv\Scripts\Activate.ps1
celery -A workers.celery_app worker --loglevel=info
```

Adjust `CELERY_BROKER_URL` in `.env` if needed.

---

## Test endpoints (examples)

Use PowerShell `Invoke-RestMethod` or `curl`.

ChatKit session (create):

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/chatkit/session" -Method Post
```

ChatKit message:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/chatkit/message" -Method Post -ContentType 'application/json' -Body '{"session_id":"abc","content":"Hello"}'
```

Agent / vector query:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8001/agent/answer" -Method Post -ContentType 'application/json' -Body '{"session_id":"s1","user_id":"user_ns","content":"Find invoice 1234"}'
```

Document upload (multipart form): use a tool like Postman or curl:

```bash
curl -X POST "http://127.0.0.1:8001/documents/upload" \
  -F "file=@/path/to/file.pdf" \
  -F "user_id=your_user_namespace"
```

---

## Quick smoke test script (Python)

Save the snippet below as `back_end/tests/smoke_test.py` and run it with the venv. It runs a minimal check for session and message endpoints.

```python
import requests

BASE = "http://127.0.0.1:8001"

print('session...')
resp = requests.post(BASE + '/api/chatkit/session')
print(resp.status_code, resp.text)

print('message...')
resp = requests.post(BASE + '/api/chatkit/message', json={
    'session_id': 'local-test',
    'content': 'Hello from smoke test'
})
print(resp.status_code, resp.text)
```

Run:

```powershell
& .\.venv\Scripts\python.exe back_end\tests\smoke_test.py
```

---

## Frontend integration notes (debug 405)

If the frontend receives `405 Method Not Allowed` from `/api/chatkit/session`:

- Confirm the frontend environment variable `NEXT_PUBLIC_FASTAPI_URL` points to your backend (e.g., `http://localhost:8001`).
- In development the frontend may attempt a relative call (`/api/chatkit/session`) which hits the frontend host — ensure your client code uses the backend URL or that you proxy requests properly.
- Example check in the Next.js project: `nca/lib/chatkit-client.ts` should build `backendUrl = process.env.NEXT_PUBLIC_FASTAPI_URL || 'http://localhost:8000'` and call `${backendUrl}/api/chatkit/session`.

---

## Common issues & debugging

- 422 Unprocessable Entity: usually missing the expected JSON shape. The message endpoints expect `session_id` + `content`. The `/chat` endpoint expects either `input_as_text` or `messages`.

- OpenAI SDK errors: check `OPENAI_API_KEY` and SDK versions. The code uses both `openai.chat.completions.create(...)` and (in other places) the newer Responses/Agents APIs; ensure the installed `openai` package version supports the methods you call.

- Missing packages / wrong Python interpreter: make sure the venv is activated before running `uvicorn` so the app imports packages installed into `.venv`.

- Latency: add logging in `main.py` at route start and end (or use middleware) to measure time spent inside handlers.

- Pinecone / embeddings: when uploading documents, the code names vector `namespace=user_id`. If you don't see results, confirm data is upserted into the expected Pinecone namespace.

---

## Logging

- The app configures `logging.basicConfig(level=logging.DEBUG)` in `main.py`. Tail logs in the terminal where you run `uvicorn` to see inbound requests and stack traces.
- Add `logging.info()` calls to routes for timing information.

---

## Code quality & running tests

- Use `black` / `ruff` / `flake8` locally if desired. There is no pre-configured formatter in this repo by default.
- Add `pytest` tests under `back_end/tests/` and run with the venv Python.

---

## Useful commands

```powershell
# Start server
& .\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8001

# Run smoke test
& .\.venv\Scripts\python.exe back_end\tests\smoke_test.py

# Run Celery worker (if configured)
celery -A workers.celery_app worker --loglevel=info
```

---

## Where to look next

- `main.py` — routes and middleware
- `routes/agent.py` — vector search + LLM prompt
- `routes/documents.py` — file upload, text extraction, embed + upsert
- `services/embeddings.py` — embedding client and batching
- `services/file_processing.py` — PDF/DOCX/CSV text extractors

---



---

Last updated: 2025-11-27
