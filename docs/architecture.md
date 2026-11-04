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

## 6. Directory Structure

```
RAGentHub/
├── backend-java/          # Spring Boot 3 primary service
├── ai-service/            # FastAPI + LangChain AI service
├── web-console/           # React + Vite management console
├── config/
│   └── domain.yaml        # Multi-domain reskin config
├── examples/               # Sample corpus (finance/gov/medical)
├── docs/                   # Documentation
└── scripts/                # Dev helper scripts
```
