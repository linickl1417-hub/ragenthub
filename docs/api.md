# API 文档

> Base URL（Python AI 服务）：`http://localhost:8000`
> Base URL（Java 主服务）：`http://localhost:8080`（Basic Auth，默认 `admin / admin123`）

Swagger UI：启动后访问 http://localhost:8000/docs

---

## 1. POST `/api/v1/chat`

问答主入口（走完整 4-Agent 链路）。

**Request**
```json
{
  "question": "PCLT20K 是什么数据集？",
  "domain": "medical",
  "user_id": "zhangsan",
  "top_k": 5
}
```

**Response**
```json
{
  "answer": "……",
  "citations": [
    {"content": "……", "source": "数据集与模型.md", "score": 0.83}
  ],
  "agent_trace": {
    "guard_action": "pass",
    "retrieved": 3,
    "llm_provider": "mock"
  },
  "audit_id": 12,
  "latency_ms": 230
}
```

## 2. POST `/api/v1/documents`

上传文档（multipart/form-data），自动切分入库。

| 字段 | 类型 | 说明 |
|---|---|---|
| file | file | md / txt / pdf |
| domain | string | finance / gov / medical |

## 3. GET `/health`

健康检查。

---

## Java 主服务侧

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/chat` | 透传到 Python 服务，并在 H2 落审计 |
| GET  | `/api/audit/recent` | 最近 50 条审计（Java 侧视角） |
| GET  | `/h2` | H2 控制台（dev 用） |
