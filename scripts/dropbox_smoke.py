#!/usr/bin/env python3
"""M0 Dropbox app-folder upload smoke script.

Uploads a deterministic tiny payload and verifies it can be read back.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import requests


class SmokeError(RuntimeError):
    """Expected smoke-path exception."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dropbox smoke: upload deterministic payload to app-folder and verify"
    )
    parser.add_argument(
        "--api-token",
        default="",
        help="Dropbox API token (optional; falls back to env)",
    )
    parser.add_argument(
        "--api-token-env",
        default="DROPBOX_ACCESS_TOKEN",
        help="Environment variable containing Dropbox API token (default: DROPBOX_ACCESS_TOKEN)",
    )
    parser.add_argument(
        "--target-path",
        default="/smoke/m0-delivery-smoke.txt",
        help="App-folder target path for upload (default: /smoke/m0-delivery-smoke.txt)",
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


def _resolve_token(args: argparse.Namespace) -> str:
    token = args.api_token.strip()
    if token:
        return token
    env_value = os.getenv(args.api_token_env, "").strip()
    if env_value:
        return env_value
    raise SmokeError(f"Missing Dropbox API token. Provide --api-token or set {args.api_token_env}.")


def _build_payload() -> bytes:
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = f"M0-D-DELIVERY-SMOKE\nsource=dropbox\ncreated_at={now_iso}\n".encode("utf-8")
    return payload


def _api_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
    }


def _upload(*, token: str, target_path: str, payload: bytes, timeout: float) -> dict:
    url = "https://content.dropboxapi.com/2/files/upload"
    headers = {
        **_api_headers(token),
        "Content-Type": "application/octet-stream",
        "Dropbox-API-Arg": json.dumps(
            {
                "path": target_path,
                "mode": "overwrite",
                "autorename": False,
                "mute": True,
                "strict_conflict": False,
            }
        ),
    }
    response = requests.post(url, headers=headers, data=payload, timeout=timeout)
    if response.status_code in (401, 403):
        raise SmokeError(f"Authentication/authorization failed: HTTP {response.status_code}")
    if response.status_code >= 400:
        raise SmokeError(f"Dropbox upload failed: HTTP {response.status_code} body={response.text[:400]}")
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise SmokeError(f"Upload response is not valid JSON: {exc}") from exc


def _download(*, token: str, target_path: str, timeout: float) -> bytes:
    url = "https://content.dropboxapi.com/2/files/download"
    headers = {
        **_api_headers(token),
        "Dropbox-API-Arg": json.dumps({"path": target_path}),
    }
    response = requests.post(url, headers=headers, timeout=timeout)
    if response.status_code >= 400:
        raise SmokeError(f"Dropbox download verify failed: HTTP {response.status_code} body={response.text[:400]}")
    return response.content


def _delete(*, token: str, target_path: str, timeout: float) -> None:
    url = "https://api.dropboxapi.com/2/files/delete_v2"
    headers = {
        **_api_headers(token),
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, json={"path": target_path}, timeout=timeout)
    if response.status_code >= 400:
        raise SmokeError(f"Dropbox cleanup failed: HTTP {response.status_code} body={response.text[:400]}")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(token: str, target_path: str, timeout: float) -> dict:
    payload = _build_payload()
    payload_sha = _sha256(payload)
    upload_meta = _upload(token=token, target_path=target_path, payload=payload, timeout=timeout)
    downloaded = _download(token=token, target_path=target_path, timeout=timeout)
    downloaded_sha = _sha256(downloaded)
    if downloaded_sha != payload_sha:
        raise SmokeError("Uploaded payload hash does not match downloaded payload hash")

    _delete(token=token, target_path=target_path, timeout=timeout)

    return {
        "status": "ok",
        "source": "dropbox",
        "checks": {
            "auth": "ok",
            "upload": "ok",
            "download_verify": "ok",
            "cleanup": "ok",
        },
        "target_path": target_path,
        "payload": {
            "bytes": len(payload),
            "sha256": payload_sha,
        },
        "upload": {
            "name": upload_meta.get("name"),
            "path_display": upload_meta.get("path_display"),
            "id": upload_meta.get("id"),
            "server_modified": upload_meta.get("server_modified"),
        },
        "message": None,
    }


def _print_human(report: dict) -> None:
    print(f"Dropbox smoke status: {report['status']}")
    print(f"Target path: {report['target_path']}")
    print(f"Payload sha256: {report['payload']['sha256']}")
    print("\nJSON summary:")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> int:
    args = parse_args()
    try:
        token = _resolve_token(args)
        report = _run(token=token, target_path=args.target_path, timeout=args.timeout)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            _print_human(report)
        return 0
    except requests.exceptions.RequestException as exc:
        print(f"ERROR: Network/HTTP failure while contacting Dropbox endpoint: {exc}", file=sys.stderr)
        return 3
    except SmokeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
