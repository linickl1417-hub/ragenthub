"""
RAGAS 评估脚本

用法：
  # 1. 先启动 ai-service（uvicorn app.main:app --port 8000）
  # 2. 跑评估
  cd ai-service
  python -m evals.eval_ragas

需要 OPENAI_API_KEY 才能跑真实 RAGAS 指标；
未配置时会自动降级为 keyword-overlap baseline。
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

import httpx

API = os.getenv("EVAL_API", "http://localhost:8000")
DOMAIN = os.getenv("EVAL_DOMAIN", "medical")
ROOT = Path(__file__).resolve().parent
GOLDEN = ROOT / "golden_qa.jsonl"
OUTPUT = ROOT / "ragas_report.json"


def load_golden() -> list[dict]:
    rows = []
    for line in GOLDEN.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def run_query(question: str) -> dict:
    r = httpx.post(
        f"{API}/api/v1/chat",
        json={"question": question, "domain": DOMAIN, "user_id": "ragas-eval"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def keyword_overlap(pred: str, truth: str) -> float:
    """无 LLM 时的 baseline：基于字符级 bigram 相似度"""
    def bigrams(s: str) -> set:
        s = "".join(ch for ch in s if ch.strip())
        return {s[i:i+2] for i in range(len(s)-1)}
    a, b = bigrams(pred), bigrams(truth)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def main():
    golden = load_golden()
    print(f"[eval] 共 {len(golden)} 条 golden QA，domain={DOMAIN}")

    samples = []
    for i, item in enumerate(golden):
        print(f"  [{i+1}/{len(golden)}] {item['question']}")
        t0 = time.time()
        resp = run_query(item["question"])
        latency = int((time.time() - t0) * 1000)

        pred = resp["answer"]
        truth = item["ground_truth"]
        samples.append({
            "question": item["question"],
            "ground_truth": truth,
            "answer": pred,
            "contexts": [c["content"] for c in resp["citations"]],
            "latency_ms": latency,
            "keyword_overlap": round(keyword_overlap(pred, truth), 4),
        })

    # 尝试真实 RAGAS；无 key 时降级
    metrics = {"baseline_keyword_overlap": round(
        sum(s["keyword_overlap"] for s in samples) / len(samples), 4
    )}

    if os.getenv("OPENAI_API_KEY"):
        try:
            from ragas import evaluate
            from ragas.metrics import faithfulness, answer_relevancy, context_precision
            from datasets import Dataset
            ds = Dataset.from_dict({
                "question": [s["question"] for s in samples],
                "answer": [s["answer"] for s in samples],
                "contexts": [s["contexts"] for s in samples],
                "ground_truth": [s["ground_truth"] for s in samples],
            })
            result = evaluate(ds, metrics=[faithfulness, answer_relevancy, context_precision])
            metrics.update({k: float(v) for k, v in result.items()})
            print("[eval] RAGAS 真实指标已计算")
        except Exception as e:  # noqa: BLE001
            print(f"[eval] RAGAS 调用失败，已保留 baseline: {e}")
    else:
        print("[eval] 未配置 OPENAI_API_KEY，仅输出 keyword-overlap baseline")

    report = {"domain": DOMAIN, "metrics": metrics, "samples": samples}
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[eval] 报告已写入 {OUTPUT}")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT.parent))
    main()
