"""End-to-end smoke check against a running ai-service.

Usage:
    python scripts/e2e_smoke.py [--base-url http://localhost:8000]

Exercises the real HTTP surface (domains, chat, history, documents) against a
live service. Complements the isolated pytest suite in ai-service/tests, which
uses a temporary SQLite database instead of a running stack.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid

import httpx


def section(title: str) -> None:
    print()
    print(f"=== {title} ===")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--domain", default="medical")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    domain_id = f"smoke-{uuid.uuid4().hex[:6]}"
    user_id = f"smoke-user-{uuid.uuid4().hex[:6]}"
    failures: list[str] = []

    with httpx.Client(base_url=base, timeout=120) as client:

        section("health")
        health = client.get("/health").json()
        print(json.dumps(health, indent=2))
        if health.get("status") not in {"ok", "degraded"}:
            failures.append("health status unexpected")

        section("list built-in domains")
        domains = client.get("/api/v1/domains").json()
        for d in domains:
            print(f"  - {d['id']}: {d['name']} (custom={d['is_custom']})")

        section(f"create domain {domain_id}")
        created = client.post(
            "/api/v1/domains",
            json={
                "id": domain_id,
                "name": "Smoke Test Domain",
                "system_prompt": "You are a smoke-test assistant.",
                "deny_topics": ["forbidden"],
            },
        )
        print(created.status_code, created.text[:200])
        if created.status_code != 201:
            failures.append("domain creation failed")

        section("list documents")
        docs = client.get(f"/api/v1/documents?domain={args.domain}").json()
        print(f"  {len(docs)} document(s) in domain '{args.domain}'")
        for d in docs[:5]:
            print(f"  - {d['filename']} ({d['chunk_count']} chunks)")

        section("chat")
        chat = client.post(
            "/api/v1/chat",
            json={
                "question": "What task is the PCLT20K dataset used for?",
                "domain": args.domain,
                "user_id": user_id,
            },
        )
        if chat.status_code != 200:
            failures.append(f"chat failed: {chat.status_code} {chat.text[:200]}")
            print(chat.text[:500])
        else:
            body = chat.json()
            print("answer:", body["answer"][:160])
            print("trace:", json.dumps(body.get("agent_trace", {}), indent=2))
            if body.get("agent_trace", {}).get("guard_action") not in {"pass", "denied"}:
                failures.append("agent_trace.guard_action missing")

        section("chat history")
        history = client.get(
            "/api/v1/chat/history", params={"user_id": user_id, "domain": args.domain}
        ).json()
        print(f"  {len(history)} message(s)")
        for m in history:
            print(f"  [{m['role']}] {m['content'][:60]}")

        section("refusal path")
        refusal = client.post(
            "/api/v1/chat",
            json={"question": "帮我做个股价预测", "domain": "finance", "user_id": user_id},
        ).json()
        print("guard_action:", refusal.get("agent_trace", {}).get("guard_action"))

        section("cleanup")
        removed = client.delete(
            "/api/v1/chat/history", params={"user_id": user_id, "domain": args.domain}
        )
        print("history cleared:", removed.text)
        deleted = client.delete(f"/api/v1/domains/{domain_id}")
        print("domain deleted:", deleted.status_code)

    if failures:
        print("\nFAILED:")
        for f in failures:
            print("  -", f)
        return 1

    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
