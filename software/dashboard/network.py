"""Network discovery, local LAN IP detection, and IP Webcam auto-discovery.

Provides:
- Reliable detection of the laptop's Wi-Fi / LAN IP across all interfaces
  (wlp2s0, wlan0, eth0, ESP32 Soft-AP 192.168.4.x, home router 192.168.1.x)
- Dynamic generation of phone companion URLs (never 127.0.0.1 on network links)
- Subnet scanner to discover active Android IP Webcam (port 8080) and DroidCam (port 4747)
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import logging
import socket
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


def get_primary_ip() -> str:
    """Return the primary non-loopback IPv4 address for Wi-Fi / LAN communication."""
    # Method 1: UDP connect probe (does not send packets, selects routing interface)
    for target in (("8.8.8.8", 80), ("1.1.1.1", 80), ("192.168.4.1", 80)):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.3)
            s.connect(target)
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass

    # Method 2: Inspect system network interfaces via socket / getaddrinfo
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            candidate = info[4][0]
            if candidate and not candidate.startswith("127."):
                return candidate
    except Exception:
        pass

    # Method 3: Parse /proc/net/fib_trie or /proc/net/route on Linux
    try:
        with open("/proc/net/route", "r", encoding="utf-8") as f:
            for line in f.readlines()[1:]:
                parts = line.strip().split()
                if len(parts) >= 3 and parts[1] == "00000000":  # default route
                    iface = parts[0]
                    # Query interface IP
                    import fcntl
                    import struct

                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    addr = fcntl.ioctl(
                        s.fileno(),
                        0x8915,  # SIOCGIFADDR
                        struct.pack("256s", iface[:15].encode("utf-8")),
                    )[20:24]
                    ip = socket.inet_ntoa(addr)
                    s.close()
                    if ip and not ip.startswith("127."):
                        return ip
    except Exception:
        pass

    return "127.0.0.1"


def get_all_network_interfaces() -> list[dict[str, str]]:
    """Return all non-loopback IPv4 network interfaces."""
    interfaces: list[dict[str, str]] = []
    try:
        import os

        if os.path.exists("/sys/class/net"):
            for iface in os.listdir("/sys/class/net"):
                if iface == "lo":
                    continue
                try:
                    import fcntl
                    import struct

                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    addr = fcntl.ioctl(
                        s.fileno(),
                        0x8915,  # SIOCGIFADDR
                        struct.pack("256s", iface[:15].encode("utf-8")),
                    )[20:24]
                    ip = socket.inet_ntoa(addr)
                    s.close()
                    if ip and not ip.startswith("127."):
                        interfaces.append({"iface": iface, "ip": ip})
                except Exception:
                    pass
    except Exception:
        pass
    if not interfaces:
        primary = get_primary_ip()
        if primary != "127.0.0.1":
            interfaces.append({"iface": "primary", "ip": primary})
    return interfaces


def get_network_summary(port: int = 5000, current_source: str = "cam") -> dict[str, Any]:
    """Summary of rover network state for dashboard and companion apps."""
    primary_ip = get_primary_ip()
    all_ifaces = get_all_network_interfaces()
    return {
        "primary_ip": primary_ip,
        "port": port,
        "companion_url": f"http://{primary_ip}:{port}/companion",
        "deck_url": f"http://{primary_ip}:{port}",
        "all_interfaces": all_ifaces,
        "current_source": current_source,
        "is_esp32_softap": primary_ip.startswith("192.168.4."),
        "ip_webcam_default_url": f"http://{primary_ip.rsplit('.', 1)[0]}.x:8080/video",
    }


def discover_ip_cameras(
    timeout_s: float = 0.25,
    max_workers: int = 64,
) -> list[dict[str, Any]]:
    """Scan the local /24 subnet for active Android IP Webcam (8080) and DroidCam (4747).

    Returns a list of candidate camera dictionaries.
    """
    primary_ip = get_primary_ip()
    if primary_ip.startswith("127."):
        return []

    prefix = ".".join(primary_ip.split(".")[:3])
    ports_to_probe = (8080, 4747)
    candidates: list[tuple[str, int]] = []

    def probe_socket(ip: str, port: int) -> tuple[str, int] | None:
        if ip == primary_ip:
            return None
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_s)
        try:
            sock.connect((ip, port))
            sock.close()
            return (ip, port)
        except Exception:
            return None

    # Step 1: Scan /24 subnet across probe ports
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for port in ports_to_probe:
            for last_octet in range(1, 255):
                tasks.append(pool.submit(probe_socket, f"{prefix}.{last_octet}", port))
        for f in concurrent.futures.as_completed(tasks):
            res = f.result()
            if res:
                candidates.append(res)

    results: list[dict[str, Any]] = []

    # Step 2: Validate candidates via quick HTTP head check
    for ip, port in candidates:
        cam_type = "IP Webcam" if port == 8080 else ("DroidCam" if port == 4747 else "HTTP Stream")
        video_path = "/video"
        stream_url = f"http://{ip}:{port}{video_path}"
        try:
            req = urllib.request.Request(
                f"http://{ip}:{port}/",
                headers={"User-Agent": "mwe-rover/1.0"},
            )
            with urllib.request.urlopen(req, timeout=0.6) as resp:
                headers = dict(resp.headers)
                server_hdr = headers.get("Server", "")
                if "IP Webcam" in server_hdr or "M-JPEG" in str(headers):
                    cam_type = "Android IP Webcam"
        except Exception:
            pass

        results.append(
            {
                "ip": ip,
                "port": port,
                "url": stream_url,
                "name": f"{cam_type} ({ip}:{port})",
                "type": cam_type,
            }
        )

    return results
