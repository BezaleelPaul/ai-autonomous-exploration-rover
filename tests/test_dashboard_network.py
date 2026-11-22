"""Tests for dashboard network detection and camera discovery."""

from __future__ import annotations

from software.dashboard.network import (
    discover_ip_cameras,
    get_all_network_interfaces,
    get_network_summary,
    get_primary_ip,
)
from software.perception_node.stream import validate_stream_url


def test_get_primary_ip():
    ip = get_primary_ip()
    assert isinstance(ip, str)
    assert len(ip) >= 7
    # In Linux test environments, should be a valid IPv4
    octets = ip.split(".")
    assert len(octets) == 4
    for o in octets:
        assert 0 <= int(o) <= 255


def test_get_all_network_interfaces():
    ifaces = get_all_network_interfaces()
    assert isinstance(ifaces, list)
    for iface in ifaces:
        assert "iface" in iface
        assert "ip" in iface
        assert not iface["ip"].startswith("127.")


def test_get_network_summary():
    summary = get_network_summary(port=5000, current_source="cam:0")
    assert isinstance(summary, dict)
    assert "primary_ip" in summary
    assert summary["port"] == 5000
    assert summary["companion_url"].startswith("http://")
    assert summary["companion_url"].endswith(":5000/companion")
    assert summary["current_source"] == "cam:0"
    assert "all_interfaces" in summary


def test_validate_stream_url_normalization():
    # Bare IP
    assert validate_stream_url("192.168.1.50") == "http://192.168.1.50:8080/video"
    # Bare IP with port
    assert validate_stream_url("192.168.1.50:8080") == "http://192.168.1.50:8080/video"
    # Standard URL with port
    assert validate_stream_url("http://192.168.1.50:8080") == "http://192.168.1.50:8080/video"
    # Full URL
    assert validate_stream_url("http://192.168.1.50:8080/video") == "http://192.168.1.50:8080/video"
    # DroidCam
    assert validate_stream_url("http://192.168.1.50:4747/video") == "http://192.168.1.50:4747/video"


def test_discover_ip_cameras_runs():
    # Subnet scan should complete without throwing exceptions
    cams = discover_ip_cameras(timeout_s=0.05, max_workers=16)
    assert isinstance(cams, list)
