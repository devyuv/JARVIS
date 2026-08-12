"""
Thin broadcast layer between the backend subsystems (gesture tracker,
wake word, STT/TTS) and the React/Three.js HUD.

Every message is a small JSON envelope:
    {"type": "<event-type>", "data": {...}, "ts": <epoch-ms>}

Event types the frontend listens for:
    gesture            - a single classified gesture (see gesture_tracker.py)
    status             - {"state": "idle" | "listening" | "thinking" | "speaking"}
    transcript_partial - live STT text as the user talks (not implemented for
                          local Whisper batch mode, reserved for streaming STT)
    transcript_final    - {"role": "user" | "assistant", "text": "..."}
    hardware            - {"mic": bool, "camera": bool} on startup
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import websockets
from websockets.server import WebSocketServerProtocol

from config import settings

logger = logging.getLogger("jarvis.ws")


class HUDBroadcaster:
    def __init__(self):
        self._clients: set[WebSocketServerProtocol] = set()
        self._server = None

    async def start(self) -> None:
        self._server = await websockets.serve(
            self._handle_client, settings.ws_host, settings.ws_port
        )
        logger.info("WebSocket server listening on ws://%s:%d", settings.ws_host, settings.ws_port)

    async def _handle_client(self, ws: WebSocketServerProtocol) -> None:
        self._clients.add(ws)
        logger.info("HUD client connected (%d total).", len(self._clients))
        try:
            async for _ in ws:
                pass  # this server is broadcast-only; inbound messages are ignored for now
        except websockets.ConnectionClosed:
            pass
        finally:
            self._clients.discard(ws)
            logger.info("HUD client disconnected (%d total).", len(self._clients))

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        if not self._clients:
            return
        payload = json.dumps({"type": event_type, "data": data, "ts": int(time.time() * 1000)})
        await asyncio.gather(
            *(self._safe_send(ws, payload) for ws in list(self._clients)),
            return_exceptions=True,
        )

    async def _safe_send(self, ws: WebSocketServerProtocol, payload: str) -> None:
        try:
            await ws.send(payload)
        except websockets.ConnectionClosed:
            self._clients.discard(ws)

    # convenience wrappers used throughout main.py
    async def gesture(self, event: dict) -> None:
        await self.broadcast("gesture", event)

    async def status(self, state: str) -> None:
        await self.broadcast("status", {"state": state})

    async def transcript(self, role: str, text: str) -> None:
        await self.broadcast("transcript_final", {"role": role, "text": text})

    async def hardware(self, mic: bool, camera: bool) -> None:
        await self.broadcast("hardware", {"mic": mic, "camera": camera})
