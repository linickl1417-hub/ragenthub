# API Documentation

> Python AI Service Base URL: `http://localhost:8000`
> Java Primary Service Base URL: `http://localhost:8080` (Basic Auth, default `admin / admin123`)

Swagger UI: http://localhost:8000/docs

---

## 0. Authentication and Rate Limiting

### API key

Every `/api/v1/*` endpoint requires an API key when `API_KEY` is configured.
Send it as `X-API-Key` or as a bearer token:

```
X-API-Key: <your key>
Authorization: Bearer <your key>
```

Missing/invalid key → `401`:

```json
{ "detail": "Invalid or missing API key" }
```

`/health`, `/docs`, `/redoc`, `/openapi.json` and `/web` never require a key.
When `API_KEY` is empty the service runs in development mode with no
authentication — `/health` reports `"auth": "disabled"` in that case.

### Rate limiting

`RATE_LIMIT_PER_MINUTE` (default `120`, `0` disables) caps requests per API
key (or per client IP when unauthenticated) in a fixed one-minute window.
The counter lives in the shared cache, so with `CACHE_BACKEND=redis` the
budget is enforced across replicas.

Over budget → `429` with `Retry-After`:

```json
{ "error": "rate_limit_exceeded", "detail": "Too many requests, retry in 37s" }
```

---

## 1. POST `/api/v1/chat`

Main Q&A endpoint — runs the full 4-agent pipeline (Retriever → Guardian → Generator → Auditor).

### Request

```json
{
  "question": "What is the PCLT20K dataset used for?",
  "domain": "medical",
  "user_id": "zhangsan"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| question | string | Yes | User's question |
| domain | string | Yes | Domain name: `finance` / `gov` / `medical` / any custom domain |
| user_id | string | Yes | User identifier for audit and conversation context |

### Response

```json
{
  "answer": "PCLT20K is used for liver pathology image segmentation.",
  "citations": [
    {
      "content": "PCLF (PET/CT Reliability Fusion)...",
      "source": "datasets-and-models.md",
      "score": 0.8234
    }
  ],
  "agent_trace": {
    "guard_action": "pass",
    "retrieved": 2,
    "llm_provider": "openai",
    "reflection_rounds": 1,
    "rewritten_query": "What is the PCLT20K dataset used for? define explain",
    "top_score": 0.8234,
    "context_turns": 2,
    "contextualized_query": "PCLT20K 数据集 它用于什么任务",
    "cache_hit": false
  },
  "audit_id": 12,
  "latency_ms": 230
}
```

### Agent Trace Fields

| Field | Description |
|---|---|
| `guard_action` | `pass` / `denied` — whether GuardianAgent blocked the question |
| `retrieved` | Number of chunks retrieved by RetrieverAgent |
| `llm_provider` | `mock` / `openai` / `mock(fallback)` when the LLM call failed |
| `reflection_rounds` | Number of reflection loop rounds (0 = no reflection triggered) |
| `rewritten_query` | The rewritten query if reflection was triggered, otherwise `null` |
| `top_score` | Cosine similarity of the top-1 retrieved chunk |
| `context_turns` | Previous user turns injected into the prompt (0 = first question) |
| `contextualized_query` | Retrieval query after folding in the previous turn, `null` when unused |
| `cache_hit` | Whether the retrieval result came from the embedding cache |

### Multi-turn behaviour

The last `CHAT_CONTEXT_TURNS` (default `3`) exchanges for this
`user_id` + `domain` are loaded from `chat_history` and sent to the LLM as
proper `user`/`assistant` messages, so follow-ups work without repeating
context. Short pronoun-style follow-ups (`它是什么`, `this one?`) are expanded
with the previous question **before retrieval** and surfaced as
`contextualized_query`.

---

## 2. POST `/api/v1/documents`

Upload a document (multipart/form-data) — automatically parsed, chunked, and ingested into the vector store.

| Field | Type | Required | Description |
|---|---|---|---|
| file | file | Yes | `.md` / `.txt` / `.pdf`, max 50 MB |
| domain | string | Yes | Domain name, e.g. `finance` / `gov` / `medical` |

### Response

```json
{
  "file": "product-manual.md",
  "chunks": 12,
  "domain": "finance"
}
```

### Errors

| Status | Meaning |
|---|---|
| 400 | Unsupported file type, empty file, or missing filename |
| 413 | File exceeds the 50 MB limit |
| 500 | Ingestion failed |

---

## 3. GET `/api/v1/documents`

List ingested documents, optionally filtered by domain.

### Query Params

| Param | Type | Default | Description |
|---|---|---|---|
| domain | string | — | Filter by domain |
| limit | int | 100 | Page size, 1–500 |
| offset | int | 0 | Rows to skip |

The total number of matching rows is returned in the `X-Total-Count` response
header, so a client can paginate without a second query.

### Response

```json
[
  {
    "id": 1,
    "filename": "product-manual.md",
    "domain": "finance",
    "chunk_count": 12,
    "uploaded_at": "2026-11-04T12:00:00"
  }
]
```

---

## 4. DELETE `/api/v1/documents/{filename}`

Delete one document from both the vector store and the metadata table.

### Query Params

| Param | Type | Required | Description |
|---|---|---|---|
| domain | string | Yes | Domain the document belongs to |

### Response

```json
{
  "filename": "product-manual.md",
  "domain": "finance",
  "chunks_deleted": 12
}
```

---

## 5. Domain Management

### GET `/api/v1/domains`

List all domains — built-in (from `config/domain.yaml`) plus user-created (from the database).

```json
[
  { "id": "medical", "name": "Medical", "is_custom": false },
  { "id": "legal", "name": "Legal Department", "is_custom": true }
]
```

### POST `/api/v1/domains`

Create a custom domain. Persisted in PostgreSQL, survives restarts.

```json
{
  "id": "legal",
  "name": "Legal Department",
  "system_prompt": "You are a legal support assistant.",
  "deny_topics": ["contract_breach", "litigation_advice"]
}
```

Rules: `id` must match `^[a-z][a-z0-9_-]{1,63}$`; built-in domain IDs cannot be redefined (409).

### GET `/api/v1/domains/{domain_id}`

Get the full configuration of a domain (built-in or custom).

### PUT `/api/v1/domains/{domain_id}`

Update a custom domain's `name`, `system_prompt` and `deny_topics`. Built-in domains are read-only.

### DELETE `/api/v1/domains/{domain_id}`

Delete a custom domain.

---

## 6. Chat History

### GET `/api/v1/chat/history`

Read the conversation history for one user in one domain — used by the web console to restore sessions after reload. Messages are returned oldest-first.

| Param | Type | Required | Description |
|---|---|---|---|
| user_id | string | Yes | User identifier |
| domain | string | Yes | Domain name |
| limit | int | No (50) | Page size, 1–200 — the **most recent** N messages |
| before_id | int | No | Return messages older than this id (load previous page) |

```json
[
  {
    "id": 1,
    "role": "user",
    "content": "What is the PCLT20K dataset?",
    "citations": "[]",
    "reflection_rounds": 0,
    "created_at": "2026-11-04T12:00:00"
  },
  {
    "id": 2,
    "role": "assistant",
    "content": "PCLT20K is ...",
    "citations": "[{\"source\": \"datasets.md\", \"score\": 0.82}]",
    "reflection_rounds": 1,
    "created_at": "2026-11-04T12:00:01"
  }
]
```

### DELETE `/api/v1/chat/history`

Clear the conversation history for one user in one domain.

```json
{ "deleted": 6 }
```

---

## 7. GET `/api/v1/audit/recent`

Get recent audit logs (Python-side view).

### Query Params

| Param | Type | Default | Description |
|---|---|---|---|
| limit | int | 20 | Page size, 1–100 |
| offset | int | 0 | Rows to skip |

### Response

```json
[
  {
    "id": 12,
    "user_id": "zhangsan",
    "domain": "medical",
    "question": "What is the PCLT20K dataset?",
    "guard_action": "pass",
    "latency_ms": 230,
    "created_at": "2026-11-04T12:00:00"
  }
]
```

---

## 8. GET `/health`

Liveness/readiness probe — also verifies database connectivity.

```json
{
  "status": "ok",
  "service": "ai-service",
  "database": "up",
  "auth": "enabled",
  "llm_provider": "openai"
}
```

Returns `status: "degraded"` and `database: "down"` when the database is
unreachable. `auth` is `enabled` when `API_KEY` is set, `disabled` in
development mode. This endpoint never requires an API key — it is the
container health probe.

---

## Error Format

| Status | Body | Cause |
|---|---|---|
| 401 | `{"detail": "Invalid or missing API key"}` | `API_KEY` configured, key missing/wrong |
| 413 | `{"detail": "File exceeds 50 MB limit"}` | Upload too large |
| 422 | `{"error": "validation_error", "detail": [...], "path": ...}` | Body/query validation failed |
| 429 | `{"error": "rate_limit_exceeded", ...}` + `Retry-After` | Rate limit exceeded |
| 500 | `{"error": "internal_error", "detail": "Internal server error", "path": ...}` | Unhandled failure — internal details are never leaked |

```json
{
  "error": "validation_error",
  "detail": [ ... pydantic error entries ... ],
  "path": "/api/v1/domains"
}
```

---

## Java Primary Service Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/chat` | Proxy to Python service, also writes audit log (dual-write) |
| GET | `/api/audit/recent` | Recent audit logs (Java-side view) |
| GET | `/api/health` | Java service health check |

---

## Web Console

The built-in UI is served by the AI service at `http://localhost:8000/web/index.html`:

- domain switching and custom domain creation
- per-domain document upload / delete
- conversation history restored from the database on reload
- reflection-loop and multi-turn context indicators on assistant answers
- API key entry (stored in `localStorage`, prompted automatically on `401`)
