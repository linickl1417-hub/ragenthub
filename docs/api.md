# API Documentation

> Python AI Service Base URL: `http://localhost:8000`
> Java Primary Service Base URL: `http://localhost:8080` (Basic Auth, default `admin / admin123`)

Swagger UI: http://localhost:8000/docs

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
| domain | string | Yes | Domain name: `finance` / `gov` / `medical` |
| user_id | string | Yes | User identifier for audit |

### Response

```json
{
  "answer": "Based on 2 retrieved chunks (Mock mode)...",
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
    "llm_provider": "mock",
    "reflection_rounds": 0,
    "rewritten_query": null,
    "top_score": 0.8234
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
| `llm_provider` | Which LLM was used: `mock` / `openai` |
| `reflection_rounds` | Number of reflection loop rounds (0 = no reflection triggered) |
| `rewritten_query` | The rewritten query if reflection was triggered, otherwise `null` |
| `top_score` | Cosine similarity of the top-1 retrieved chunk |

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

Read the conversation history for one user in one domain — used by the web console to restore sessions after reload.

| Param | Type | Required | Description |
|---|---|---|---|
| user_id | string | Yes | User identifier |
| domain | string | Yes | Domain name |
| limit | int | No (50) | Max records, capped at 200 |

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
| limit | int | 20 | Max number of records (max 100) |

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
  "database": "up"
}
```

Returns `status: "degraded"` and `database: "down"` when the database is unreachable.

---

## Error Format

Validation errors return HTTP 422:

```json
{
  "error": "validation_error",
  "detail": [ ... pydantic error entries ... ],
  "path": "/api/v1/domains"
}
```

Unhandled failures return HTTP 500 with a generic message so internal details are not leaked:

```json
{
  "error": "internal_error",
  "detail": "Internal server error",
  "path": "/api/v1/chat"
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
- reflection-loop indicator on assistant answers
