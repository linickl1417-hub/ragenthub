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

Upload a document (multipart/form-data) — automatically parsed, chunked, and ingested into vector store.

| Field | Type | Required | Description |
|---|---|---|---|
| file | file | Yes | `.md` / `.txt` / `.pdf` |
| domain | string | Yes | Domain name: `finance` / `gov` / `medical` |

### Response

```json
{
  "filename": "product-manual.md",
  "domain": "finance",
  "chunks": 12,
  "status": "ingested"
}
```

---

## 3. GET `/api/v1/documents`

List all ingested documents.

### Response

```json
[
  {
    "id": 1,
    "filename": "product-manual.md",
    "domain": "finance",
    "chunk_count": 12,
    "created_at": "2026-11-04T12:00:00"
  }
]
```

---

## 4. GET `/api/v1/audit/recent`

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

## 5. GET `/health`

Health check.

```json
{
  "status": "ok",
  "service": "ai-service"
}
```

---

## Java Primary Service Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/chat` | Proxy to Python service, also writes audit log (dual-write) |
| GET | `/api/audit/recent` | Recent audit logs (Java-side view) |
| GET | `/api/health` | Java service health check |
