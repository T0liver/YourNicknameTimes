#!/usr/bin/env python3
"""M0 CalDAV smoke script.

Lists discovered CalDAV collections and classifies them as event calendars
and/or task lists based on supported components (VEVENT/VTODO).
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth


NS = {
    "d": "DAV:",
    "cs": "http://calendarserver.org/ns/",
    "cal": "urn:ietf:params:xml:ns:caldav",
}


PROPFIND_BODY = """<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:displayname />
    <d:resourcetype />
    <cal:supported-calendar-component-set />
  </d:prop>
</d:propfind>
"""

DISCOVERY_BODY = """<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
    <d:prop>
        <d:current-user-principal />
        <d:principal-URL />
        <cal:calendar-home-set />
    </d:prop>
</d:propfind>
"""


@dataclass(frozen=True)
class Collection:
    href: str
    name: str
    is_calendar: bool
    components: tuple[str, ...]

    @property
    def has_events(self) -> bool:
        return "VEVENT" in self.components

    @property
    def has_tasks(self) -> bool:
        return "VTODO" in self.components


class SmokeError(RuntimeError):
    """Expected smoke-path exception."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CalDAV smoke: discover calendars/task lists and print health summary"
    )
    parser.add_argument("--url", required=True, help="CalDAV base URL (Baikal endpoint)")
    parser.add_argument("--username", required=True, help="CalDAV username")
    parser.add_argument("--password", required=True, help="CalDAV password")
    parser.add_argument(
        "--auth",
        choices=("auto", "basic", "digest"),
        default="auto",
        help="Authentication mode (default: auto)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP timeout in seconds (default: 15)",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON-only output",
    )
    return parser.parse_args()


def _auth(mode: str, username: str, password: str):
    if mode == "basic":
        return HTTPBasicAuth(username, password)
    if mode == "digest":
        return HTTPDigestAuth(username, password)
    return None


def _request_propfind(
    url: str,
    username: str,
    password: str,
    timeout: float,
    insecure: bool,
    mode: str,
    body: str,
    depth: str,
) -> requests.Response:
    headers = {
        "Depth": depth,
        "Content-Type": "application/xml; charset=utf-8",
    }

    def do_request(auth_mode: str | None, request_url: str) -> requests.Response:
        auth_obj = _auth(auth_mode, username, password) if auth_mode else None
        return requests.request(
            method="PROPFIND",
            url=request_url,
            headers=headers,
            data=body.encode("utf-8"),
            auth=auth_obj,
            timeout=timeout,
            verify=not insecure,
            allow_redirects=False,
        )

    def follow_redirects(auth_mode: str | None) -> requests.Response:
        current = url
        for _ in range(6):
            response = do_request(auth_mode, current)
            if response.status_code not in (301, 302, 303, 307, 308):
                return response

            location = response.headers.get("Location")
            if not location:
                return response
            current = urljoin(current, location)
        return response

    if mode in {"basic", "digest"}:
        response = follow_redirects(mode)
    else:
        response = follow_redirects("basic")
        if response.status_code == 401:
            response = follow_redirects("digest")

    return response


def _text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def _parse_collections(xml_text: str, request_url: str) -> list[Collection]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SmokeError(f"Invalid XML response: {exc}") from exc

    collections: list[Collection] = []
    for resp in root.findall("d:response", NS):
        href = _text(resp.find("d:href", NS))
        if not href:
            continue

        prop = resp.find("d:propstat/d:prop", NS)
        if prop is None:
            continue

        rtype = prop.find("d:resourcetype", NS)
        is_calendar = False
        if rtype is not None:
            is_calendar = rtype.find("cal:calendar", NS) is not None

        if not is_calendar:
            continue

        name = _text(prop.find("d:displayname", NS)) or href.rstrip("/").split("/")[-1]

        components: list[str] = []
        comp_set = prop.find("cal:supported-calendar-component-set", NS)
        if comp_set is not None:
            for comp in comp_set.findall("cal:comp", NS):
                component = (comp.attrib.get("name") or "").strip().upper()
                if component:
                    components.append(component)

        if not components:
            components = ["UNKNOWN"]

        collections.append(
            Collection(
                href=urljoin(request_url, href),
                name=name,
                is_calendar=True,
                components=tuple(sorted(set(components))),
            )
        )

    if not collections:
        return []
    return collections


def _discover_home_url(xml_text: str, request_url: str) -> str | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    prop_paths = (
        "d:propstat/d:prop/cal:calendar-home-set/d:href",
        "d:propstat/d:prop/d:current-user-principal/d:href",
        "d:propstat/d:prop/d:principal-URL/d:href",
    )

    for resp in root.findall("d:response", NS):
        for path in prop_paths:
            href_node = resp.find(path, NS)
            href = _text(href_node)
            if href:
                return urljoin(request_url, href)
    return None


def _summary(collections: Iterable[Collection]) -> dict:
    coll_list = list(collections)
    event_count = sum(1 for c in coll_list if c.has_events)
    task_count = sum(1 for c in coll_list if c.has_tasks)

    status = "ok" if event_count or task_count else "degraded"
    message = None if status == "ok" else "Collections discovered but component types unknown"

    return {
        "source": "caldav",
        "status": status,
        "checks": {
            "auth": "ok",
            "discovery": "ok",
            "classification": "ok" if status == "ok" else "degraded",
        },
        "counts": {
            "collections": len(coll_list),
            "event_calendars": event_count,
            "task_lists": task_count,
        },
        "message": message,
        "collections": [
            {
                "name": c.name,
                "url": c.href,
                "components": list(c.components),
                "is_event_calendar": c.has_events,
                "is_task_list": c.has_tasks,
            }
            for c in coll_list
        ],
    }


def _print_human(report: dict) -> None:
    print(f"CalDAV smoke status: {report['status']}")
    print(
        "Discovered collections: "
        f"{report['counts']['collections']} "
        f"(event calendars: {report['counts']['event_calendars']}, "
        f"task lists: {report['counts']['task_lists']})"
    )

    print("\nCollections:")
    for col in report["collections"]:
        tags = []
        if col["is_event_calendar"]:
            tags.append("VEVENT")
        if col["is_task_list"]:
            tags.append("VTODO")
        if not tags:
            tags = col["components"]
        print(f"- {col['name']} | components={','.join(tags)} | {col['url']}")

    if report["message"]:
        print(f"\nNote: {report['message']}")


def main() -> int:
    args = parse_args()
    try:
        response = _request_propfind(
            url=args.url,
            username=args.username,
            password=args.password,
            timeout=args.timeout,
            insecure=args.insecure,
            mode=args.auth,
            body=PROPFIND_BODY,
            depth="1",
        )

        if response.status_code in (401, 403):
            raise SmokeError(f"Authentication failed: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise SmokeError(f"CalDAV endpoint request failed: HTTP {response.status_code}")

        collections = _parse_collections(response.text, args.url)

        if not collections:
            discovery = _request_propfind(
                url=args.url,
                username=args.username,
                password=args.password,
                timeout=args.timeout,
                insecure=args.insecure,
                mode=args.auth,
                body=DISCOVERY_BODY,
                depth="0",
            )
            if discovery.status_code < 400:
                home_or_principal = _discover_home_url(discovery.text, args.url)
                if home_or_principal:
                    second = _request_propfind(
                        url=home_or_principal,
                        username=args.username,
                        password=args.password,
                        timeout=args.timeout,
                        insecure=args.insecure,
                        mode=args.auth,
                        body=DISCOVERY_BODY,
                        depth="0",
                    )
                    if second.status_code < 400:
                        home = _discover_home_url(second.text, home_or_principal) or home_or_principal
                    else:
                        home = home_or_principal

                    third = _request_propfind(
                        url=home,
                        username=args.username,
                        password=args.password,
                        timeout=args.timeout,
                        insecure=args.insecure,
                        mode=args.auth,
                        body=PROPFIND_BODY,
                        depth="1",
                    )
                    if third.status_code < 400:
                        collections = _parse_collections(third.text, home)

        if not collections:
            raise SmokeError("No CalDAV calendar collections discovered")
        report = _summary(collections)

        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            _print_human(report)
            print("\nJSON summary:")
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "ok" else 10

    except requests.exceptions.RequestException as exc:
        print(f"ERROR: Network/HTTP failure while contacting CalDAV endpoint: {exc}", file=sys.stderr)
        return 3
    except SmokeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())