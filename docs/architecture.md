# 架构设计

## 1. 设计目标

1. **岗位能力映射**：完整覆盖后端架构、微服务、数据库、接口、数据治理、数据安全、RAG、Agent、大模型、模型部署等关键词。
2. **多场景适配**：同一套代码通过 `domain.yaml` 切换行业语料与 prompt，不重新写业务逻辑。
3. **本地零依赖可跑**：默认 SQLite + Chroma，生产可切换 MySQL + Redis + Kafka + Milvus。
4. **可演示性**：Swagger 直接可点、有审计 trace、有示例语料。

## 2. 服务划分

| 服务 | 技术栈 | 职责 |
|---|---|---|
| `backend-java` | Spring Boot 3, Spring Security, Spring Data JPA, MySQL Driver | 用户/角色/文档元数据/权限/审计/对外 REST |
| `ai-service` | FastAPI, LangChain, ChromaDB, SQLite | 文档切分、向量入库、RAG 检索、多 Agent 编排、LLM 调用 |
| `web` | 原生 HTML + Fetch | 极简知识库问答界面 |

服务间通过 HTTP 解耦，Java 侧用 `RestClient` 或 `WebClient` 调用 Python。

## 3. 多 Agent 协作流程

```
用户提问
   │
   ▼
RetrieverAgent  ── 混合检索（向量 + BM25）取回 top-k 片段
   │
   ▼
GuardianAgent   ── 敏感词过滤 / 越权检查 / 拒答判定
   │ 通过
   ▼
GeneratorAgent  ── 拼装 prompt，调用 LLM 生成答案 + 引用
   │
   ▼
AuditorAgent    ── 落审计日志（用户、问题、引用、token、耗时）
   │
   ▼
返回给用户
```

## 4. 数据治理与安全

- **RBAC**：`admin / editor / viewer` 三角色，文档按 `domain` 字段隔离。
- **脱敏**：GuardianAgent 在输入输出两侧做手机号、身份证、银行卡号正则脱敏。
- **审计**：每次问答落 `audit_log` 表，含 user_id、question、retrieved_chunk_ids、answer、latency_ms、llm_tokens。
- **配置化拒答**：`domain.yaml` 中 `deny_topics` 列表命中即拒答并记录。

## 5. 生产化切换

| 组件 | 本地默认 | 生产切换 |
|---|---|---|
| 业务库 | SQLite | MySQL 8（改 `application.yml` datasource） |
| 向量库 | Chroma 嵌入式 | Milvus / pgvector |
| 缓存 | 无 | Redis（热门问题 embedding 缓存） |
| 异步切分 | 同步 | Kafka（文档上传后发事件，worker 消费） |
| LLM | Ollama 本地 / Mock | OpenAI / 通义 / DeepSeek |
