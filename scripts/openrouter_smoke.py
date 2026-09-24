#!/usr/bin/env python3
"""M0 OpenRouter smoke script.

Validates that an OpenRouter test call path returns a structured response.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests


class SmokeError(RuntimeError):
    """Expected smoke-path exception."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OpenRouter smoke: send a minimal chat completion request and print health summary"
    )
    parser.add_argument(
        "--endpoint",
        default="https://openrouter.ai/api/v1/chat/completions",
        help="OpenRouter chat completions endpoint",
    )
    parser.add_argument(
        "--model",
        default="openrouter/auto",
        help="Model name to request (default: openrouter/auto)",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="OpenRouter API key (optional; falls back to env)",
    )
    parser.add_argument(
        "--api-key-env",
        default="OPENROUTER_API_KEY",
        help="Environment variable containing OpenRouter API key (default: OPENROUTER_API_KEY)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds (default: 20)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON-only output",
    )
    return parser.parse_args()


def _resolve_api_key(args: argparse.Namespace) -> str:
    key = args.api_key.strip()
    if key:
        return key
    env_value = os.getenv(args.api_key_env, "").strip()
    if env_value:
        return env_value
    raise SmokeError(f"Missing OpenRouter API key. Provide --api-key or set {args.api_key_env}.")


def _call_openrouter(
    *,
    endpoint: str,
    api_key: str,
    model: str,
    timeout: float,
) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yournicknametimes.local/smoke",
        "X-Title": "YourNicknameTimes M0 Smoke",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "temperature": 0,
        "max_tokens": 16,
    }
    response = requests.post(
        endpoint,
        headers=headers,
        json=payload,
        timeout=timeout,
    )

    if response.status_code in (401, 403):
        raise SmokeError(f"Authentication/authorization failed: HTTP {response.status_code}")
    if response.status_code >= 400:
        raise SmokeError(f"OpenRouter request failed: HTTP {response.status_code} body={response.text[:400]}")

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise SmokeError(f"Invalid JSON response: {exc}") from exc

    choices = data.get("choices") or []
    if not choices:
        raise SmokeError("Response missing choices[]")

    content = _extract_choice_content(choices[0])
    if not content:
        content = "<non-text response>"

    provider = data.get("provider") or {}
    usage = data.get("usage") or {}

    return {
        "status": "ok",
        "source": "openrouter",
        "checks": {
            "auth": "ok",
            "http": "ok",
            "response_shape": "ok",
        },
        "request": {
            "endpoint": endpoint,
            "model": model,
            "timeout_seconds": timeout,
        },
        "response": {
            "id": data.get("id"),
            "model": data.get("model"),
            "provider": provider,
            "usage": usage,
            "preview": content.strip()[:120],
        },
        "message": None,
    }


def _extract_choice_content(choice: Any) -> str:
    if not isinstance(choice, dict):
        return ""

    message = choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
                elif isinstance(part, str) and part.strip():
                    parts.append(part.strip())
            joined = "\n".join(parts).strip()
            if joined:
                return joined

        reasoning = message.get("reasoning")
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning.strip()

        reasoning_details = message.get("reasoning_details")
        if isinstance(reasoning_details, list):
            parts: list[str] = []
            for part in reasoning_details:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            joined = "\n".join(parts).strip()
            if joined:
                return joined

    text_field = choice.get("text")
    if isinstance(text_field, str) and text_field.strip():
        return text_field.strip()

    return ""


def _print_human(report: dict) -> None:
    print(f"OpenRouter smoke status: {report['status']}")
    print(f"Model requested: {report['request']['model']}")
    print(f"Model served: {report['response'].get('model')}")
    print(f"Preview: {report['response'].get('preview')}")
    print("\nJSON summary:")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> int:
    args = parse_args()
    try:
        api_key = _resolve_api_key(args)
        report = _call_openrouter(
            endpoint=args.endpoint,
            api_key=api_key,
            model=args.model,
            timeout=args.timeout,
        )
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            _print_human(report)
        return 0
    except requests.exceptions.RequestException as exc:
        print(f"ERROR: Network/HTTP failure while contacting OpenRouter endpoint: {exc}", file=sys.stderr)
        return 3
    except SmokeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
