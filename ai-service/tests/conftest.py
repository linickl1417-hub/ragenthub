"""Pytest bootstrap: isolate the test database from local development data."""
import os
import shutil
from pathlib import Path

_TEST_DATA_DIR = Path(__file__).resolve().parent / ".pytest_data"
shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)
_TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("DB_BACKEND", "sqlite")
os.environ["RAGENTHUB_DATA_DIR"] = str(_TEST_DATA_DIR)
os.environ.setdefault("VECTOR_BACKEND", "chroma")
os.environ.setdefault("CACHE_BACKEND", "memory")
os.environ.setdefault("EVENT_BUS", "sync")
os.environ.setdefault("LLM_PROVIDER", "mock")
