"""CLI：python -m app.scripts.ingest --domain medical"""
from __future__ import annotations
import argparse
from app.config import load_domain_config
from app.core.db import init_db
from app.pipelines.ingest import ingest_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", default="medical", help="finance / gov / medical")
    args = parser.parse_args()

    init_db()
    cfg = load_domain_config(args.domain)
    n = ingest_dir(cfg["corpus_dir"], args.domain)
    print(f"[ok] domain={args.domain} 灌入片段 {n} 个，来源目录: {cfg['corpus_dir']}")


if __name__ == "__main__":
    main()
