#!/usr/bin/env python3
"""Upload a small file to the Dropbox app folder."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import requests

API_RPC = "https://api.dropboxapi.com/2"
API_CONTENT = "https://content.dropboxapi.com/2"


def _token() -> str:
    access = os.environ.get("DROPBOX_ACCESS_TOKEN", "").strip()
    if access:
        return access

    refresh = os.environ.get("DROPBOX_REFRESH_TOKEN", "").strip()
    app_key = os.environ.get("DROPBOX_APP_KEY", "").strip()
    app_secret = os.environ.get("DROPBOX_APP_SECRET", "").strip()
    if not (refresh and app_key and app_secret):
        print(
            "FAIL set DROPBOX_ACCESS_TOKEN or DROPBOX_REFRESH_TOKEN + APP_KEY + APP_SECRET",
            file=sys.stderr,
        )
        sys.exit(1)

    resp = requests.post(
        "https://api.dropbox.com/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": app_key,
            "client_secret": app_secret,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"FAIL token refresh HTTP {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
        sys.exit(1)
    return resp.json()["access_token"]


def main() -> int:
    token = _token()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = f"/smoke-{stamp}.txt"
    body = f"Your Nickname Times milestone 0 smoke upload {stamp}\n".encode()

    print("== Dropbox app folder ==")
    print(f"Path: {path}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Dropbox-API-Arg": json_dumps({"path": path, "mode": "add", "autorename": True}),
    }
    resp = requests.post(
        f"{API_CONTENT}/files/upload",
        headers=headers,
        data=body,
        timeout=60,
    )
    if resp.status_code != 200:
        body = resp.text[:500]
        if "missing_scope" in body and "files.content.write" in body:
            print(
                "FAIL Dropbox token lacks files.content.write; enable it in the app "
                "permissions, re-authorize, and set DROPBOX_ACCESS_TOKEN or "
                "DROPBOX_REFRESH_TOKEN in smoke.local.env",
                file=sys.stderr,
            )
        else:
            print(f"FAIL upload HTTP {resp.status_code}: {body}", file=sys.stderr)
        return 1

    meta = resp.json()
    print(f"Uploaded: {meta.get('path_display', path)} ({meta.get('size', len(body))} bytes)")
    print("PASS check_dropbox — confirm the file in the app folder")
    print(f"Record this path in keys-for-1.3.local.md: {meta.get('path_display', path)}")
    return 0


def json_dumps(obj: dict) -> str:
    import json

    return json.dumps(obj, separators=(",", ":"))


if __name__ == "__main__":
    raise SystemExit(main())
