"""HTTP client for the ESP32 gateway (stdlib only, no requests dependency).

Every call is defensive: the rover must not hang because the Wi-Fi hiccuped.
A failed command returns ``False`` and updates :attr:`RoverClient.stats`; it
never raises unless you ask it to with ``strict=True``.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from .protocol import DEFAULT_SPEED, Packet, ProtocolError, encode_command

DEFAULT_BASE_URL = "http://192.168.4.1"


@dataclass
class ClientStats:
    sent: int = 0
    ok: int = 0
    failed: int = 0
    skipped: int = 0
    last_error: str = ""
    last_latency_ms: float = 0.0
    last_cmd: str = ""
    last_code: int = 0

    def as_dict(self) -> dict:
        return {
            "sent": self.sent,
            "ok": self.ok,
            "failed": self.failed,
            "skipped": self.skipped,
            "last_error": self.last_error,
            "last_latency_ms": round(self.last_latency_ms, 1),
            "last_cmd": self.last_cmd,
            "last_code": self.last_code,
        }


@dataclass
class RoverStatus:
    uptime_ms: int = 0
    forwarded: int = 0
    rejected: int = 0
    clients: int = 0
    last_cmd: str = ""
    last_cmd_age_ms: int = 0
    camera: str = ""
    fw: str = ""
    ip: str = ""
    free_heap: int = 0
    uno: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    # --- Uno health convenience accessors --------------------------------
    @property
    def uno_alive(self) -> bool:
        return bool(self.uno.get("alive"))

    @property
    def uno_fault(self) -> bool:
        return bool(self.uno.get("fault_pin"))

    @property
    def rover_state(self) -> str:
        return str(self.uno.get("state", ""))

    @property
    def battery_v(self) -> float:
        try:
            return int(self.uno.get("battery_mv") or 0) / 1000.0
        except (TypeError, ValueError):
            return 0.0

    @property
    def telemetry_age_ms(self) -> int:
        try:
            return int(self.uno.get("telemetry_age_ms", -1))
        except (TypeError, ValueError):
            return -1

    @classmethod
    def from_payload(cls, payload: dict) -> "RoverStatus":
        def as_int(key: str) -> int:
            try:
                return int(payload.get(key, 0) or 0)
            except (TypeError, ValueError):
                return 0

        return cls(
            uptime_ms=as_int("uptime_ms"),
            forwarded=as_int("forwarded"),
            rejected=as_int("rejected"),
            clients=as_int("clients"),
            last_cmd=str(payload.get("last_cmd", "") or ""),
            last_cmd_age_ms=as_int("last_cmd_age_ms"),
            camera=str(payload.get("camera", "") or ""),
            fw=str(payload.get("fw", "") or ""),
            ip=str(payload.get("ip", "") or ""),
            free_heap=as_int("free_heap"),
            uno=dict(payload.get("uno") or {}),
            raw=dict(payload),
        )


class RoverClient:
    """Thin, thread-safe, fail-soft gateway client.

    >>> RoverClient("http://192.168.4.1").send("F", 180)   # doctest: +SKIP
    True
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 0.4,
        min_interval: float = 0.0,
        token: str | None = None,
        clock=time.monotonic,
        sleep=time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)
        self.token = token if token is not None else os.environ.get("ROVER_TOKEN", "")
        self.min_interval = float(min_interval)
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last_send: float | None = None
        self.stats = ClientStats()
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # -- low level ---------------------------------------------------------
    def _with_token(self, path: str) -> str:
        if not self.token:
            return path
        separator = "&" if "?" in path else "?"
        return f"{path}{separator}k={urllib.parse.quote(self.token)}"

    def _request(self, path: str, timeout: float | None = None) -> tuple[int, bytes]:
        url = f"{self.base_url}{self._with_token(path)}"
        req = urllib.request.Request(url, headers={"Cache-Control": "no-store"})
        try:
            with self._opener.open(req, timeout=timeout or self.timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:  # 4xx/5xx still carries a body
            return exc.code, exc.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ConnectionError(str(exc)) from exc

    def _get_json(self, path: str, timeout: float | None = None) -> dict:
        status, body = self._request(path, timeout=timeout)
        if status >= 400:
            raise ConnectionError(f"HTTP {status} for {path}")
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectionError(f"bad JSON from {path}") from exc

    # -- commands ----------------------------------------------------------
    def send(self, cmd: str, speed: int | None = None, strict: bool = False) -> bool:
        """Send one command. Returns True on HTTP 200."""
        try:
            packet = Packet(cmd, speed)
            encode_command(packet.cmd, packet.speed)  # validate before the network
        except ProtocolError:
            if strict:
                raise
            self.stats.failed += 1
            self.stats.last_error = f"invalid command {cmd!r}"
            return False

        with self._lock:
            if self.min_interval > 0 and not packet.is_stop and self._last_send is not None:
                wait = self.min_interval - (self._clock() - self._last_send)
                if wait > 0:
                    self._sleep(wait)
            query = urllib.parse.urlencode({"c": packet.cmd + ("" if packet.speed is None else str(packet.speed))})
            path = f"/cmd?{query}"
            started = self._clock()
            try:
                status, _ = self._request(path)
                self.stats.last_code = status
                ok = status == 200
                if ok:
                    self.stats.ok += 1
                else:
                    self.stats.failed += 1
                    self.stats.last_error = f"HTTP {status}"
            except ConnectionError as exc:
                ok = False
                self.stats.last_code = 0
                self.stats.failed += 1
                self.stats.last_error = str(exc)
                if strict:
                    raise
            finally:
                self.stats.sent += 1
                self.stats.last_cmd = packet.cmd
                self.stats.last_latency_ms = (self._clock() - started) * 1000.0
                self._last_send = self._clock()
        return ok

    def stop(self, attempts: int = 3) -> bool:
        """Emergency stop: never throttled, retried, always resolves."""
        ok = False
        for attempt in range(max(1, attempts)):
            ok = self.send("S")
            if ok:
                return True
            if attempt + 1 < attempts:
                self._sleep(0.05)
        return ok

    # -- gateway API -------------------------------------------------------
    def status(self) -> RoverStatus | None:
        try:
            return RoverStatus.from_payload(self._get_json("/status"))
        except ConnectionError:
            return None

    def health(self) -> bool:
        try:
            status, body = self._request("/health", timeout=min(self.timeout, 0.3))
            return status == 200 and body.strip().lower() == b"ok"
        except ConnectionError:
            return False

    def camera_url(self) -> str | None:
        try:
            payload = self._get_json("/cam")
        except ConnectionError:
            return None
        value = payload.get("camera")
        return str(value) if value else None

    def set_camera_url(self, url: str) -> bool:
        if not url.startswith(("http://", "https://")):
            raise ProtocolError("camera URL must start with http:// or https://")
        try:
            payload = self._get_json("/cam?" + urllib.parse.urlencode({"u": url}))
        except ConnectionError:
            return False
        return bool(payload.get("ok"))

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        try:
            self._opener.close()  # type: ignore[attr-defined]
        except Exception:
            pass

    def __enter__(self) -> "RoverClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.stop(attempts=2)
        self.close()

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"RoverClient({self.base_url!r}, sent={self.stats.sent}, ok={self.stats.ok})"
