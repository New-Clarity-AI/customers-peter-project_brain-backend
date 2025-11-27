This document explains the structure and operation of the `back_end/` service so a new developer can get up to speed quickly.

**TL;DR**
- FastAPI backend used by the Next.js frontend.
- Integrates with OpenAI (Responses / Agents), Supabase (auth + storage), and Pinecone (vector index) for embeddings.
- Run locally with a Python virtual environment and `uvicorn main:app`.
## Repository layout (back_end)

```
back_end/
├── __init__.py
├── .env                # local environment variables (not checked into git)
├── main.py             # FastAPI app, middleware, and core API routes
├── requirements.txt
├── middleware/         # middleware utilities (e.g., SupabaseAuthMiddleware)
├── routes/             # grouped route modules
│   ├── agent.py        # /agent/* routes (e.g., /agent/answer)
│   └── documents.py    # /documents/* routes (file upload + ingest)
├── services/           # core service helpers (embeddings, pinecone, supabase, file processing)
├── workers/            # Celery worker config for background tasks
└── README.md
```
The backend exposes HTTP endpoints used by the frontend and external clients. Major responsibilities:

- Normalize incoming chat requests and call OpenAI (direct Responses API or an Agents/Workflow runner).
- Provide ChatKit helper endpoints used by the frontend to create sessions and proxy messages to the OpenAI Chat/ChatKit APIs.
- Accept document uploads, extract text, create embeddings, and upsert vectors to Pinecone (namespaced by user).
- Offer utilities for Supabase storage/auth integration and background processing via Celery.
- `main.py` — FastAPI application, middleware, and core routes.
  - Middleware: `SupabaseAuthMiddleware` is applied (see `middleware/auth.py`) and a Supabase client instance is created using `SUPABASE_URL` and `SUPABASE_ANON_KEY`.
  - Routes included from `routes/` (documents, agent) via `app.include_router(...)`.
  - Important built-in endpoints:
    - `POST /api/chatkit/message` — accepts `Message` body: `{"session_id": "...", "content": <string|dict|list>, "user_id": "..."}`. The code normalizes `content` to a text string and calls the OpenAI chat completion API (in current code it uses `openai.chat.completions.create(model="gpt-4.1", ...)`). Returns `{ "message": "..." }`.
    - `POST /api/chatkit/session` — creates a ChatKit session with OpenAI SDK using a `workflow` (current code passes a `workflow` object with an `id` property) and returns `{ "client_secret": ... }`.

  - Note: `main.py` is the place to add other global endpoints and route-level logging / error handling.
- `workflow.py` (if present) — contains orchestration helpers that call into the `agents` Runner/RunConfig to execute multi-step agent workflows and normalize outputs.
- `services/` directory
  - `supabase_client.py` / `supabase_storage.py` — helpers for Supabase auth and storage upload.
  - `embeddings.py` — wraps the OpenAI embeddings client and batching logic (`embed_text`, `embed_texts`, helper chunking functions using `tiktoken`). Environment variable `EMBEDDING_MODEL` is used.
  - `pinecone_client.py` / `pinecone_adapter.py` — Pinecone initialization and index operations (`upsert`, `query`). The app stores vectors under a `namespace` equal to the `user_id` when ingesting documents.
  - `file_processing.py` — document text extraction for PDF, DOCX, CSV, and plaintext (helpers used by the upload route).
  - `chunker.py` — chunking utilities used to split long texts before embedding.
Place a `.env` at `back_end/.env` (not committed). Important environment variables used by the app include:

- `OPENAI_API_KEY` — required for the OpenAI SDK (Responses / Embeddings / ChatKit calls).
- `SUPABASE_URL` and `SUPABASE_ANON_KEY` — required to construct the Supabase client used by the app and routes.
- `EMBEDDING_MODEL` — model name used for embeddings (e.g., `text-embedding-3-small` or project-specific value).
- `EMBED_BATCH_SIZE` — batch size used by `services/embeddings.embed_texts` (default 64).
- `PINECONE_API_KEY`, `PINECONE_ENV` — if Pinecone is used for vector storage.
- `TOP_K` — integer used by the agent route to control how many vectors to retrieve for context (example usage in `routes/agent.py`).
- `CELERY_BROKER_URL` — broker URL for Celery workers (if used)

Check `services/*.py` for any additional environment variables used in your environment.
1. Create and activate a Python virtual environment from the `back_end` directory:

```powershell
cd back_end
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
3. Run the FastAPI app locally:

```powershell
# from back_end/
& .\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8001
```
4. Test endpoints using `curl` / PowerShell `Invoke-RestMethod` or Postman. Example payloads for major routes:

- ChatKit message (backend route):

```json
POST /api/chatkit/message
Content-Type: application/json

{ "session_id": "<session-id>", "content": "Hello, what's the weather in London?" }
```

- ChatKit session create:

```json
POST /api/chatkit/session
```

Response: `{ "client_secret": "..." }` (used by frontend to initialize ChatKit client)

- Agent answer (vector search + LLM):

```json
POST /agent/answer
Content-Type: application/json

{ "session_id": "<session-id>", "content": "Find the invoice details for order 1234.", "user_id": "<user-namespace>" }
```

Response: `{ "session_id": "...", "message": "..." }`

- Upload document (multipart/form-data):

`POST /documents/upload` with a `file` form field and `user_id` form field (string). The route will extract text from the file, chunk it, embed chunks, and upsert vectors into Pinecone under the provided `user_id` namespace.
The Next.js frontend expects specific JSON shapes (see `nca/lib/chatkit-client.ts` and frontend components):

- Chatkit message endpoint: `POST /api/chatkit/message` — `{ session_id: string, content: string }` → returns `{ message: string }`.
- Chatkit session: `POST /api/chatkit/session` — returns `{ client_secret: string }`.
- Agent endpoint: `POST /agent/answer` — `{ session_id, content, user_id }`.

If you change payload shapes update both frontend and backend accordingly and ensure `NEXT_PUBLIC_FASTAPI_URL` in the frontend points to the running backend.
- 405 / Method Not Allowed on session endpoint:
  - If you see a 405 when calling `/api/chatkit/session` from the browser, confirm the frontend is calling the backend URL (not the frontend host). The frontend environment variable `NEXT_PUBLIC_FASTAPI_URL` should point to your backend (for dev typically `http://localhost:8001`).

 - Example: `nca/lib/chatkit-client.ts` uses `process.env.NEXT_PUBLIC_FASTAPI_URL || 'http://localhost:8000'`. Update that env var in the Next.js app if it points to the wrong domain.
There are no unit tests included by default. For a production-ready project, add tests for:
  - Request/response contract for each route (using `pytest` + `httpx.AsyncClient` for FastAPI).
  - Service functions (embeddings, chunker, pinecone adapter).

Note: There are small implementation issues and TODOs in the codebase (for example some functions reference variables that aren't defined in the snippet or may raise exceptions on edge cases). When extending the backend, add small unit tests for services and route handlers to catch regressions early.
# Agent Backend — README

This document explains the structure and operation of the `back_end/` service so a new developer can get up to speed quickly.

**TL;DR**
- It's a FastAPI application that exposes several endpoints used by the Next.js frontend.
- It integrates with OpenAI (and an `openai-agents` workflow), Supabase auth/storage, and (optionally) Pinecone for embeddings.
- Run locally with a Python virtual environment and `uvicorn main:app`.

---

## Repository layout (back_end)

```
back_end/
├── __init__.py
├── .env                # local environment variables (not checked into git)
├── main.py             # FastAPI app + most API routes
├── requirements.txt
├── middleware/
│   └── auth.py         # auth helpers/middleware
├── routes/
│   ├── agent.py        # route handlers for agent-specific API (if present)
│   └── documents.py    # document related routes
├── services/           # core service helpers
│   ├── agent_tools.py
│   ├── chunker.py
│   ├── embeddings.py
│   ├── file_processing.py
│   ├── pinecone_adapter.py
│   ├── pinecone_client.py
│   ├── supabase_client.py
│   └── supabase_storage.py
├── workers/
│   └── celery_app.py   # background worker config (Celery)
└── workers/__init__.py
```

> Files may vary slightly — see the folder for exact names.

---

## Purpose and high-level flow

- The backend exposes HTTP endpoints the frontend calls 
(e.g., `/agent/answer`, `/api/chatkit/session`, `/api/chatkit/message`, `/documents/upload`).
- Incoming chat requests are normalized and passed into the `agents`/`workflow` runner (`workflow.run_workflow`) which uses the OpenAI Agents SDK.
- Some routes act as adapters for ChatKit (session creation and message sending), proxying to OpenAI ChatKit or the Agents runner as required.
- Services in `services/` provide utilities for embeddings, file handling, Pinecone/Supabase integration, and other shared logic.
- Background tasks (long running or heavy processing) can be performed via Celery workers configured in `workers/celery_app.py`.

---

## Main files of interest

- `main.py`
  - FastAPI application factory and route definitions.
  - Important endpoints:
    - `POST /chat` — accepts either `{"input_as_text":"..."}` or `{"messages": [...]}`.
      - Normalizes `messages` where content can be `string`, `dict`, or `list`.
      - Calls `workflow.run_workflow(WorkflowInput(...))` and returns `{"message": "..."}`.
    - `POST /api/chat` — alias forwarding to `/chat` for backward compatibility.
    - `POST /api/chatkit/session` — creates a ChatKit session via OpenAI SDK and returns `{"client_secret": ...}`.
    - `POST /api/chatkit/message` — accepts `{"session_id":..., "content":...}` and calls the OpenAI `chat.completions.create(...)` or ChatKit APIs.

- `workflow.py` (used from `main.py`)
  - Contains `run_workflow` and `WorkflowInput` that wrap the Agents runner.
  - Imports from the `agents` package (e.g., `Runner`, `RunConfig`) and returns a normalized `output_text`.

- `services/` directory
  - `supabase_client.py`/`supabase_storage.py` — interaction with Supabase (auth, storage, file uploads).
  - `embeddings.py` / `pinecone_*` — compute embeddings and optionally store them in Pinecone.
  - `file_processing.py` / `chunker.py` — helpers to chunk long documents for embeddings.

- `workers/celery_app.py`
  - Celery configuration for offloading heavy tasks (embedding generation, large file processing).

---

## Environment & secrets

Place a `.env` at `back_end/.env` (not committed). Important environment variables used by the app include:

- `OPENAI_API_KEY` — required. OpenAI API key for all OpenAI SDK calls.
- `SUPABASE_URL` — Supabase project URL (if using Supabase services).
- `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_ANON_KEY` — Supabase keys as needed.
- `PINECONE_API_KEY`, `PINECONE_ENV` — Pinecone credentials (if used).
- `CELERY_BROKER_URL` — e.g., Redis `redis://localhost:6379/0` for Celery.
- Any other service credentials referenced in `services/*.py` (check those files for exact names).

Example `.env` snippet:

```
OPENAI_API_KEY=sk_xxx
SUPABASE_URL=https://xyz.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
PINECONE_API_KEY=...
CELERY_BROKER_URL=redis://localhost:6379/0
```

---

## Setup & local development

1. Create and activate a Python virtual environment from the `back_end` directory:

```powershell
cd back_end
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Create a `.env` file with the required environment variables (see previous section).

3. Run the FastAPI app locally:

```powershell
# from back_end/
& .\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

4. Test endpoints using `curl` / PowerShell `Invoke-RestMethod` or Postman. Example payloads for `/api/chat`:

```json
{ "input_as_text": "Hello, summarize the latest news." }

{ "messages": [{ "role": "user", "content": "What's the weather?" }] }
```

---

## Frontend integration notes

- The Next.js frontend expects specific JSON shapes. Two important contracts:
  - `POST /api/chat` (or `/chat`) → body either `{ input_as_text: string }` or `{ messages: [...] }`. Response: `{ message: string }`.
  - ChatKit flows:
    - `POST /api/chatkit/session` → returns `{ client_secret: string }` (frontend uses this to initialize the ChatKit client).
    - `POST /api/chatkit/message` → body `{ session_id: string, content: string }`, response `{ message: string }`.

- If you change any payload shapes, update `nca/lib/chatkit-client.ts` and the frontend components consuming these endpoints.

---

## Common debugging tips

- 405 / Method Not Allowed on session endpoint:
  - Ensure the frontend `NEXT_PUBLIC_FASTAPI_URL` points to the backend (e.g., `http://localhost:8001`) and the frontend code uses that base URL when calling backend endpoints.

- 422 Unprocessable Entity for `/api/chat`:
  - Backend validates that either `input_as_text` or `messages` is present. Use one of the valid shapes shown above.

- OpenAI errors (BadRequest, invalid workflow type):
  - Check SDK versions (OpenAI SDK and `openai-agents`), and confirm the payload you send to the SDK matches the SDK's expected types (object vs string).

- Packages and venv mismatch:
  - Activate the project venv before running `uvicorn` so Python imports the correct packages installed into `.venv`.

- To trace latency/delays:
  - Add logging in `main.py` (request start/end) and inspect the frontend Network tab to compare request timing.

---

## Extending & modifying

- Add new API routes under `routes/` or directly in `main.py` for quick changes.
- Put shared logic in `services/` and keep route handlers thin.
- For heavy tasks (embeddings, long-running file processing), add Celery tasks in `workers/` and call them from route handlers as needed.

---

## Tests

- There are no unit tests included by default. For a production-ready project, add tests for:
  - Request/response contract for each route (using `pytest` + `httpx.AsyncClient` for FastAPI).
  - Service functions (embeddings, chunker, pinecone adapter).

---

## Where to look next

- `main.py` — entrypoint and most critical route logic.
- `workflow.py` — agents/workflow orchestration.
- `services/supabase_client.py` — Supabase authentication and storage interactions.
- `services/embeddings.py` & `services/pinecone_*` — embedding generation and vector storage.



---

Last updated: 2025-11-27
