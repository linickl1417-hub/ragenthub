"""全局配置：读环境变量 + domain.yaml"""
from __future__ import annotations
import os
from pathlib import Path
import yaml
from pydantic_settings import BaseSettings

# 本地开发：config.py 在 <root>/ai-service/app/config.py，parents[2]=<root>
# Docker：config.py 在 /app/app/config.py，parents[2]=/，config 通过 RAGENTHUB_CONFIG_DIR 指定
_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_DIR = Path(os.getenv("RAGENTHUB_CONFIG_DIR", _ROOT / "config"))
CONFIG_PATH = _CONFIG_DIR / "domain.yaml"
ROOT = _ROOT


class Settings(BaseSettings):
    app_name: str = "RAGentHub AI Service"
    env: str = os.getenv("ENV", "dev")

    # 数据路径
    data_dir: Path = ROOT / "data"
    sqlite_path: Path = ROOT / "data" / "ragenthub.sqlite3"
    chroma_dir: Path = ROOT / "data" / "chroma"

    # 业务库：sqlite | mysql | postgres
    db_backend: str = os.getenv("DB_BACKEND", "sqlite")
    database_url: str = os.getenv("DATABASE_URL", "")

    # 向量库：chroma | pgvector
    vector_backend: str = os.getenv("VECTOR_BACKEND", "chroma")

    # 缓存：memory | redis
    cache_backend: str = os.getenv("CACHE_BACKEND", "memory")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # 事件总线：sync | kafka
    event_bus: str = os.getenv("EVENT_BUS", "sync")
    kafka_bootstrap: str = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

    # LLM：默认 Mock（无 key 也能跑）
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    model_config = {"env_file": ".env"}


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)


def load_domain_config(domain: str = "medical") -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    defaults = cfg.get("defaults", {})
    domains = cfg.get("domains", {})
    if domain not in domains:
        raise ValueError(f"未知 domain: {domain}，可选: {list(domains.keys())}")
    merged = {**defaults, **domains[domain]}
    # corpus_dir：本地 <root>/examples/...；容器 /examples/...
    merged["corpus_dir"] = str(ROOT / merged["corpus_dir"])
    return merged
