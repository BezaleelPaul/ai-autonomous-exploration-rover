"""WebSocket real-time bridge for zero-latency direct telemetry and control."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any

import websockets

logger = logging.getLogger(__name__)


class WebSocketBridge:
    """Provides a persistent, bi-directional WebSocket channel.

    Avoids HTTP poll request overhead:
    * Browser sends commands directly over the open socket: {"cmd": "F"}
    * Browser sends camera stream switch: {"url": "http://192.168.1.10:8080/video"}
    * Server pushes real-time telemetry (link, feed, decision) at 10 Hz.
    """

    def __init__(
        self,
        feed=None,
        link=None,
        pilot=None,
        host: str = "0.0.0.0",
        port: int = 8765,
    ):
        self.feed = feed
        self.link = link
        self.pilot = pilot
        self.host = host
        self.port = port
        self.clients: set[Any] = set()
        self._running = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run_server(self) -> None:
        asyncio.run(self._main())

    async def _handler(self, websocket: Any) -> None:
        self.clients.add(websocket)
        logger.info("WebSocket client connected from %s", websocket.remote_address)
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except Exception:
                    data = {"cmd": str(message).strip()}

                # Direct command execution
                cmd = data.get("cmd")
                if cmd and self.link is not None:
                    try:
                        from software.dashboard.controls import validate_command

                        valid_cmd = validate_command(str(cmd).strip())
                        self.link.send(valid_cmd)
                    except Exception as e:
                        logger.warning("WS command error: %s", e)

                # Direct camera stream repointing
                url = data.get("url")
                if url and self.feed is not None:
                    set_source = getattr(self.feed, "set_source", None)
                    if callable(set_source):
                        try:
                            new_src = set_source(str(url).strip())
                            await websocket.send(
                                json.dumps({"type": "stream_ack", "ok": True, "source": new_src})
                            )
                        except Exception as e:
                            await websocket.send(
                                json.dumps({"type": "stream_ack", "ok": False, "error": str(e)})
                            )

                # Direct mode change
                mode = data.get("mode")
                if mode and self.pilot is not None:
                    set_mode = getattr(self.pilot, "set_mode", None)
                    if callable(set_mode):
                        try:
                            set_mode(str(mode).strip())
                        except Exception:
                            pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)

    async def _broadcast_loop(self) -> None:
        while self._running:
            if self.clients:
                state_data: dict[str, Any] = {}
                try:
                    if self.link is not None:
                        state_data["link"] = self.link.telemetry()
                except Exception:
                    pass

                try:
                    if self.feed is not None:
                        state_data["feed"] = self.feed.state()
                except Exception:
                    pass

                try:
                    if self.pilot is not None:
                        state_data["decision"] = self.pilot.status()
                except Exception:
                    pass

                if state_data:
                    msg = json.dumps({"type": "telemetry", **state_data})
                    dead = []
                    for ws in list(self.clients):
                        try:
                            await ws.send(msg)
                        except Exception:
                            dead.append(ws)
                    for d in dead:
                        self.clients.discard(d)

            await asyncio.sleep(0.10)  # 10 Hz telemetry rate

    async def _main(self) -> None:
        async with websockets.serve(self._handler, self.host, self.port):
            await self._broadcast_loop()
