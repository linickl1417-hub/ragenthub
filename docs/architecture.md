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

- **RBAC**: `admin / editor / viewer` three roles, documents isolated by `domain` field.
- **PII Masking**: GuardianAgent masks phone numbers, ID cards, bank card numbers on both input and output sides.
- **Audit Log**: Every Q&A writes to `audit_log` table with user_id, question, retrieved_chunk_ids, answer, latency_ms, llm_provider.
- **Configurable Denial**: `deny_topics` list in `domain.yaml` triggers automatic refusal when matched.

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

