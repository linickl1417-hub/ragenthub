# Architecture Design

## 1. Design Goals

1. **Job Capability Mapping**: Covers backend architecture, microservices, databases, APIs, data governance, data security, RAG, agents, LLM, and model deployment keywords.
2. **Multi-Domain Adaptation**: Same codebase switches industry corpus and prompts via `domain.yaml`, no business logic rewrite needed.
3. **Zero-Dependency Local Run**: Default SQLite + embedded Chroma for local dev; production-ready switches to PostgreSQL + Redis + Kafka + Milvus.
4. **Demo-Ready**: Swagger UI interactive, audit trace visible, sample corpus included.

## 2. Service Decomposition

| Service | Tech Stack | Responsibilities |
|---|---|---|
| `backend-java` | Spring Boot 3, Spring Security, Spring Data JPA, PostgreSQL | User/role/document metadata/permissions/audit/external REST API |
| `ai-service` | FastAPI, LangChain, ChromaDB, PostgreSQL | Document chunking, vector ingestion, RAG retrieval, multi-agent orchestration, LLM calls |
| `web-console` | React + Vite | Knowledge base management UI + chat demo interface |

Services are decoupled via HTTP. Java side uses `RestClient` to call Python.

## 3. Multi-Agent Pipeline

```
User Question
   │
   ▼
RetrieverAgent  ── Vector retrieval (Chroma, cosine similarity)
   │
   ├─ top-1 score < threshold? ── yes ──► Rewrite query (synonym expansion) ──► Retry retrieval
   │                                         │
   ├─ no ────────────────────────────────────┘
   │
   ▼
GuardianAgent   ── Sensitive word check / PII masking / denial decision
   │ pass
   ▼
GeneratorAgent  ── Build prompt, call LLM, generate answer + citations
   │
   ▼
AuditorAgent    ── Persist audit log (user, question, citations, tokens, latency)
   │
   ▼
Return to user
```

### Reflection Loop Detail

When top-1 retrieval similarity drops below 0.35, the RetrieverAgent automatically triggers a reflection loop:
- **English**: Expands wh-word questions with related terms (e.g. "what is X" → "what is X define explain")
- **Chinese**: Matches question patterns (e.g. "什么是 X" → "什么是 X 定义 解释 概述")
- Merges results and keeps top-k by relevance score

## 4. Data Governance & Security

- **Authentication**: API-key (`X-API-Key` or `Authorization: Bearer`) with a
  constant-time comparison. Disabled only when `API_KEY` is empty, and
  `/health` reports the mode so misconfiguration is visible to probes.
- **Rate limiting**: fixed one-minute window per API key / client IP, counted
  in the shared cache — Redis makes the budget hold across replicas.
- **Domain isolation**: documents, vectors and conversations are namespaced by
  the `domain` field; a document can only be listed or deleted inside its domain.
- **PII Masking**: GuardianAgent masks phone numbers, ID cards and bank card
  numbers on both the input and the output side.
- **Audit Log**: every Q&A writes to `audit_log` with user_id, question,
  answer, guard_action, latency_ms and the resolved LLM provider.
- **Configurable Denial**: the `deny_topics` list in `domain.yaml` (or the
  custom domain record) triggers an automatic refusal before generation.
- **Conversation retention**: `chat_history` keeps the dialogue so sessions
  survive a reload and multi-turn context can be rebuilt; `DELETE
  /api/v1/chat/history` is the data-subject erasure path.

## 4.1 Multi-Turn Context

```
question ──► RetrieverAgent ──► Guardian ──► Generator ──► Auditor
             ▲
             │ last N turns from chat_history
             │ (pronoun follow-up + previous question)
```

Two distinct uses of history, with different failure modes if conflated:

| Use | Where | Why |
|---|---|---|
| Retrieval disambiguation | `RetrieverAgent._effective_query` | A short follow-up such as "它是什么" has nothing to embed on its own, so the previous user question is prepended before the vector search. Surfaced as `contextualized_query`. |
| Answer generation | `GeneratorAgent._build_messages` | The previous turns are sent as native `user`/`assistant` messages, so the model resolves references without a second lookup. |

Both are bounded: `CHAT_CONTEXT_TURNS` (default 3) and
`CHAT_CONTEXT_MAX_CHARS` (default 500) cap what can reach the prompt.

## 5. Production-Ready Switching

| Component | Local Default | Production Switch |
|---|---|---|
| Business DB | SQLite | PostgreSQL 16 (switch `DB_BACKEND=postgres`) |
| Vector Store | Chroma embedded | pgvector / Milvus (switch `VECTOR_BACKEND=pgvector`) |
| Cache | None | Redis (hot query embedding cache, switch `CACHE_BACKEND=redis`) |
| Async Chunking | Sync | Kafka (document upload → event → worker consumes, switch `EVENT_BUS=kafka`) |
| LLM | Mock / Ollama local | OpenAI / Qwen / DeepSeek (switch `LLM_PROVIDER=openai`) |

## 5.1 Persistence and Offline Model Bootstrap

Container recreation must not lose data, and cold starts must not depend on
network access to the model CDN.

| Volume | Mount point | Holds |
|---|---|---|
| `pg_data` | `/var/lib/postgresql/data` | PostgreSQL business data (`audit_log`, `document_meta`, `domain_config`, `chat_history`) |
| `ai_data` | `/data` | Chroma persistent vector store (`RAGENTHUB_DATA_DIR=/data`) |
| `onnx_cache` | `/root/.cache/chroma/onnx_models` | ONNX embedding model cache |
| host bind (ro) | `/models/minilm` | Local `all-MiniLM-L6-v2` directory |

`ai-service/docker-entrypoint.sh` runs before the service starts. Chroma only
treats the embedding model as installed when **all six** files
(`config.json`, `model.onnx`, `special_tokens_map.json`, `tokenizer_config.json`,
`tokenizer.json`, `vocab.txt`) are present under
`all-MiniLM-L6-v2/onnx/`. The entrypoint copies them from the read-only bind
mount, deletes any partially downloaded archive, and only then lets the
process start — so the ingest worker and the HTTP worker never race on the
same download.

## 6. Directory Structure

```
RAGentHub/
├── backend-java/               # Spring Boot 3 primary service
├── ai-service/
│   ├── app/
│   │   ├── agents/             # Retriever / Guardian / Generator / Auditor
│   │   ├── api/                # chat, documents, domains, history, audit
│   │   └── core/               # db, vectorstore, cache, llm
│   ├── tests/                  # pytest contract tests
│   └── docker-entrypoint.sh    # ONNX cache seeding
├── web-console/                # React + Vite management console
├── web/                        # Built-in chat + admin SPA served by ai-service
├── config/
│   └── domain.yaml             # Multi-domain reskin config
├── examples/                   # Sample corpus (finance/gov/medical)
├── docs/                       # Documentation
└── scripts/                    # Dev helper scripts (e2e smoke, evaluation)
```

