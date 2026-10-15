"""Caddy and nftables for the LAN. The app stays on 127.0.0.1:8080."""

from __future__ import annotations

import argparse
import ipaddress
import json
import subprocess
from pathlib import Path

# Caddy returns 502 when the reverse_proxy dial fails and the site sets no handle_errors.
UPSTREAM_DOWN_STATUS = 502
MDNS_V4 = "224.0.0.251"
MDNS_V6 = "ff02::fb"


def write_status_port(data_dir: Path, port: int | None) -> None:
    path = Path(data_dir) / "status-http.port"
    if port is None:
        path.write_text("", encoding="utf-8")
        return
    number = _port(port)
    path.write_text(f"{number}\n", encoding="utf-8")


def read_status_port(data_dir: Path) -> int | None:
    path = Path(data_dir) / "status-http.port"
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    return _port(raw)


def render_caddy(addresses: list[str], status_port: int | None) -> str:
    hosts = ", ".join(_site_hosts(addresses))
    lines = [
        f"{hosts} {{",
        "\ttls internal",
        "\treverse_proxy 127.0.0.1:8080",
        "}",
        "",
    ]
    if status_port is not None:
        port = _port(status_port)
        lines.extend(
            [
                f"http://:{port} {{",
                "\t@status path /status",
                "\thandle @status {",
                "\t\treverse_proxy 127.0.0.1:8080",
                "\t}",
                "\thandle {",
                '\t\trespond "" 403',
                "\t}",
                "}",
                "",
            ]
        )
    return "\n".join(lines)


def render_nftables(status_port: int | None) -> str:
    lines = [
        "flush ruleset",
        "table inet newspaper {",
        "\tset lan4 {",
        "\t\ttype ipv4_addr",
        "\t\tflags interval",
        "\t\telements = { 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16 }",
        "\t}",
        "",
        "\tset lan6 {",
        "\t\ttype ipv6_addr",
        "\t\tflags interval",
        "\t\telements = { fc00::/7, fe80::/10 }",
        "\t}",
        "",
        "\tchain input {",
        "\t\ttype filter hook input priority 0; policy drop;",
        "\t\tct state established,related accept",
        '\t\tiif "lo" accept',
        "\t\tip saddr @lan4 tcp dport { 22, 443 } accept",
        "\t\tip6 saddr @lan6 tcp dport { 22, 443 } accept",
        f"\t\tip saddr @lan4 udp dport 5353 ip daddr {MDNS_V4} accept",
        f"\t\tip6 saddr @lan6 udp dport 5353 ip6 daddr {MDNS_V6} accept",
        "\t\tip saddr @lan4 udp sport 67 udp dport 68 accept",
        "\t\tip6 saddr @lan6 udp sport 547 udp dport 546 accept",
        "\t\ticmp type destination-unreachable accept",
        "\t\ticmpv6 type { nd-router-advert, nd-neighbor-solicit, nd-neighbor-advert, packet-too-big } accept",
    ]
    if status_port is not None:
        port = _port(status_port)
        lines.append(f"\t\tip saddr @lan4 tcp dport {port} accept")
        lines.append(f"\t\tip6 saddr @lan6 tcp dport {port} accept")
    lines.extend(
        [
            "\t}",
            "",
            "\tchain forward {",
            "\t\ttype filter hook forward priority 0; policy drop;",
            "\t}",
            "",
            "\tchain output {",
            "\t\ttype filter hook output priority 0; policy accept;",
            "\t}",
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def sync_commands(nft_path: Path) -> list[list[str]]:
    return [
        ["nft", "-f", str(nft_path)],
        ["systemctl", "reload-or-restart", "caddy"],
    ]


def sync_lan(
    data_dir: Path,
    *,
    caddy_path: Path,
    nft_path: Path,
    addresses: list[str],
    run=None,
) -> None:
    port = read_status_port(data_dir)
    caddy_text = render_caddy(addresses, port)
    nft_text = render_nftables(port)
    caddy_path.write_text(caddy_text, encoding="utf-8")
    nft_path.write_text(nft_text, encoding="utf-8")
    runner = run or subprocess.run
    for command in sync_commands(nft_path):
        runner(command, check=False)


def local_addresses() -> list[str]:
    try:
        result = subprocess.run(["ip", "-j", "addr"], capture_output=True, text=True, check=False)
        rows = json.loads(result.stdout or "[]")
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    if not isinstance(rows, list):
        return []
    found: list[str] = []
    for link in rows:
        if not isinstance(link, dict):
            continue
        for item in link.get("addr_info") or []:
            if not isinstance(item, dict):
                continue
            local = str(item.get("local") or "")
            if _certificate_address(local) and local not in found:
                found.append(local)
    return found


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write the Caddy site and nftables rules from the status port file.")
    parser.add_argument("--data-dir", default="/var/lib/newspaper")
    parser.add_argument("--caddy", default="/etc/caddy/Caddyfile")
    parser.add_argument("--nft", default="/etc/nftables.conf")
    args = parser.parse_args(argv)
    sync_lan(
        Path(args.data_dir),
        caddy_path=Path(args.caddy),
        nft_path=Path(args.nft),
        addresses=["newspaper.local", *local_addresses()],
    )


def _port(value: object) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError("status port")
    if isinstance(value, int):
        number = value
    else:
        text = str(value).strip()
        if not text.isascii() or not text.isdigit():
            raise ValueError("status port")
        number = int(text)
    if number < 1 or number > 65535:
        raise ValueError("status port")
    return number


def _site_hosts(addresses: list[str]) -> list[str]:
    hosts = ["newspaper.local"]
    for raw in addresses:
        if raw == "newspaper.local" or not _certificate_address(raw):
            continue
        ip = ipaddress.ip_address(raw)
        text = f"[{ip}]" if isinstance(ip, ipaddress.IPv6Address) else str(ip)
        if text not in hosts:
            hosts.append(text)
    return hosts


def _certificate_address(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return False
    return bool(ip.is_private)
