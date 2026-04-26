#!/usr/bin/env python3
"""Small judge-like smoke test for prototype_bot.py."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path


TOKEN = "local_dev_token"
ROOT = Path("/tmp/magicpin-expanded-check")


def call(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if "/v1/healthz" not in url and "/v1/metadata" not in url:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def push(base_url: str, scope: str, context_id: str, payload: dict, version: int = 1) -> None:
    status, res = call(
        "POST",
        f"{base_url}/v1/context",
        {
            "scope": scope,
            "context_id": context_id,
            "version": version,
            "payload": payload,
            "delivered_at": "2026-04-26T10:00:00Z",
        },
    )
    print("PUSH", scope, context_id, status, res)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    for path in ["healthz", "metadata"]:
        status, res = call("GET", f"{base_url}/v1/{path}")
        print(path.upper(), status, res)

    category = load("categories/dentists.json")
    merchant = load("merchants/m_001_drmeera_dentist_delhi.json")
    customer = load("customers/c_001_priya_for_m001.json")
    triggers = [
        load("triggers/trg_001_research_digest_dentists.json"),
        load("triggers/trg_003_recall_due_priya.json"),
        load("triggers/trg_023_competitor_opened_dentist.json"),
    ]

    push(base_url, "category", category["slug"], category)
    push(base_url, "merchant", merchant["merchant_id"], merchant)
    push(base_url, "customer", customer["customer_id"], customer)
    for trigger in triggers:
        push(base_url, "trigger", trigger["id"], trigger)

    status, res = call(
        "POST",
        f"{base_url}/v1/tick",
        {"now": "2026-04-26T10:35:00Z", "available_triggers": [t["id"] for t in triggers]},
    )
    print("TICK", status)
    print(json.dumps(res, indent=2, ensure_ascii=False))

    if res.get("actions"):
        conv = res["actions"][0]["conversation_id"]
        replies = [
            "Thank you for contacting us. We will get back to you soon.",
            "Thank you for contacting us. We will get back to you soon.",
            "Yes please send it",
            "Can you also help me file GST?",
            "not interested",
        ]
        for i, message in enumerate(replies, start=2):
            status, reply_res = call(
                "POST",
                f"{base_url}/v1/reply",
                {
                    "conversation_id": conv,
                    "merchant_id": merchant["merchant_id"],
                    "customer_id": None,
                    "from_role": "merchant",
                    "message": message,
                    "received_at": "2026-04-26T10:45:00Z",
                    "turn_number": i,
                },
            )
            print("REPLY", repr(message), status, reply_res)


if __name__ == "__main__":
    main()
