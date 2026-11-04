"""全局配置：读环境变量 + domain.yaml"""
from __future__ import annotations
import os
from pathlib import Path
import yaml
from pydantic_settings import BaseSettings

ROOT = Path(__file__).resolve().parents[2]   # RAGentHub/
CONFIG_PATH = ROOT / "config" / "domain.yaml"


class Settings(BaseSettings):
    app_name: str = "RAGentHub AI Service"
    env: str = os.getenv("ENV", "dev")

    # 数据路径
    data_dir: Path = ROOT / "data"
    sqlite_path: Path = ROOT / "data" / "ragenthub.sqlite3"
    chroma_dir: Path = ROOT / "data" / "chroma"

    # LLM：默认 Mock（无 key 也能跑）
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")  # mock | openai
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    class Config:
        env_file = ".env"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)


def load_domain_config(domain: str = "medical") -> dict:
    """读取 config/domain.yaml 中某个 domain 的配置"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    defaults = cfg.get("defaults", {})
    domains = cfg.get("domains", {})
    if domain not in domains:
        raise ValueError(f"未知 domain: {domain}，可选: {list(domains.keys())}")
    merged = {**defaults, **domains[domain]}
    merged["corpus_dir"] = str(ROOT / merged["corpus_dir"])
    return merged
