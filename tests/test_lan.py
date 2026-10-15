from pathlib import Path

import pytest

from newspaper.lan import (
    MDNS_V4,
    MDNS_V6,
    UPSTREAM_DOWN_STATUS,
    read_status_port,
    render_caddy,
    render_nftables,
    sync_commands,
    sync_lan,
    write_status_port,
)


def test_caddy_proxies_localhost_and_a_dead_upstream_is_502():
    text = render_caddy(["newspaper.local", "192.168.1.20"], None)
    assert "tls internal" in text
    assert "reverse_proxy 127.0.0.1:8080" in text
    assert "handle_errors" not in text
    assert UPSTREAM_DOWN_STATUS == 502
    assert "192.168.1.20" in text
    assert "8.8.8.8" not in render_caddy(["newspaper.local", "8.8.8.8", "2001:db8::1"], None)


def test_status_port_site_serves_only_status():
    text = render_caddy(["newspaper.local"], 9090)
    assert "http://:9090 {" in text
    assert "path /status" in text
    assert 'respond "" 403' in text
    assert text.count("reverse_proxy 127.0.0.1:8080") == 2
    closed = render_caddy(["newspaper.local"], None)
    assert "http://:" not in closed
    assert ":9090" not in closed


def test_nftables_lan_rules_without_a_status_port():
    text = render_nftables(None)
    assert text.startswith("flush ruleset\n")
    assert "10.0.0.0/8" in text
    assert "172.16.0.0/12" in text
    assert "192.168.0.0/16" in text
    assert "169.254.0.0/16" in text
    assert "fc00::/7" in text
    assert "fe80::/10" in text
    assert 'policy drop' in text
    assert "ct state established,related accept" in text
    assert 'iif "lo" accept' in text
    assert "ip saddr @lan4 tcp dport { 22, 443 } accept" in text
    assert "ip6 saddr @lan6 tcp dport { 22, 443 } accept" in text
    assert f"udp dport 5353 ip daddr {MDNS_V4} accept" in text
    assert f"udp dport 5353 ip6 daddr {MDNS_V6} accept" in text
    assert "udp sport 67 udp dport 68 accept" in text
    assert "udp sport 547 udp dport 546 accept" in text
    assert "icmp type destination-unreachable accept" in text
    assert "nd-router-advert" in text
    assert "packet-too-big" in text
    assert "policy accept" in text
    assert "631" not in text
    assert "dport 9090" not in text
    assert "0.0.0.0/0" not in text


def test_nftables_opens_the_status_port_only_after_it_is_set():
    text = render_nftables(9090)
    assert "ip saddr @lan4 tcp dport 9090 accept" in text
    assert "ip6 saddr @lan6 tcp dport 9090 accept" in text
    assert "631" not in text


def test_status_port_file_is_an_integer_or_empty(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    write_status_port(data, 9090)
    assert (data / "status-http.port").read_text(encoding="utf-8") == "9090\n"
    assert read_status_port(data) == 9090
    write_status_port(data, None)
    assert (data / "status-http.port").read_text(encoding="utf-8") == ""
    assert read_status_port(data) is None
    (data / "status-http.port").write_text("9090; echo hi\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_status_port(data)


def test_sync_writes_files_and_reloads_with_fixed_commands(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    write_status_port(data, 9090)
    caddy = tmp_path / "Caddyfile"
    nft = tmp_path / "nftables.conf"
    calls = []

    def run(command, check=False):
        calls.append(command)

    sync_lan(
        data,
        caddy_path=caddy,
        nft_path=nft,
        addresses=["newspaper.local", "192.168.1.20", "8.8.8.8"],
        run=run,
    )
    site = caddy.read_text(encoding="utf-8")
    rules = nft.read_text(encoding="utf-8")
    assert "reverse_proxy 127.0.0.1:8080" in site
    assert "192.168.1.20" in site
    assert "8.8.8.8" not in site
    assert "tcp dport 9090 accept" in rules
    assert calls == sync_commands(nft)
    assert calls == [
        ["nft", "-f", str(nft)],
        ["systemctl", "reload-or-restart", "caddy"],
    ]
    assert all("9090" not in part for command in calls for part in command)


def test_a_bad_port_file_is_not_applied(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "status-http.port").write_text("nope\n", encoding="utf-8")
    caddy = tmp_path / "Caddyfile"
    nft = tmp_path / "nftables.conf"
    with pytest.raises(ValueError):
        sync_lan(data, caddy_path=caddy, nft_path=nft, addresses=["newspaper.local"], run=lambda *args, **kwargs: None)
    assert not caddy.exists()
    assert not nft.exists()


def test_install_enables_avahi_and_security_updates_without_editing_sshd():
    script = Path("deploy/install.sh").read_text(encoding="utf-8")
    assert "systemctl enable --now avahi-daemon" in script
    assert "systemctl enable --now unattended-upgrades" in script
    assert "sshd" not in script
    assert "/etc/ssh" not in script
    web = Path("deploy/newspaper-web.service").read_text(encoding="utf-8")
    assert "Restart=always" in web
    assert "0.0.0.0" not in web
    path_unit = Path("deploy/newspaper-lan-sync.path").read_text(encoding="utf-8")
    assert "PathChanged=__DATA__/status-http.port" in path_unit
    assert "Unit=newspaper-lan-sync.service" in path_unit
    sync = Path("deploy/newspaper-lan-sync.service").read_text(encoding="utf-8")
    assert "newspaper-lan-sync" in sync
    assert "Before=" not in sync
    assert "sshd" not in sync
    assert script.index('"$ROOT/.venv/bin/newspaper-lan-sync"') < script.index("apt-get install -y caddy")
    upgrades = Path("deploy/apt/50unattended-upgrades").read_text(encoding="utf-8")
    assert "security" in upgrades
    assert Path("deploy/avahi/newspaper.service").is_file()
