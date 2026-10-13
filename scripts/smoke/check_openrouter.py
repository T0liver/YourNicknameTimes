#!/usr/bin/env python3
"""Minimal OpenRouter chat completion smoke test."""
from __future__ import annotations

import json
import os
import sys

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"


def main() -> int:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        print("FAIL missing OPENROUTER_API_KEY", file=sys.stderr)
        return 1

    model = os.environ.get("OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free"

    print("== OpenRouter ==")
    print(f"Model: {model}")

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Reply with exactly one word: ok",
            }
        ],
        "max_tokens": 16,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/local/yournicknametimes-smoke",
        "X-Title": "Your Nickname Times smoke test",
    }

    resp = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        print(f"FAIL HTTP {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        return 1

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        print(f"FAIL unexpected response: {json.dumps(data)[:500]}", file=sys.stderr)
        return 1

    used_model = data.get("model", model)
    print(f"Reply: {content.strip()!r}")
    print(f"Model used: {used_model}")
    print("PASS check_openrouter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
