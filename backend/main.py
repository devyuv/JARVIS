"""
Entrypoint. Wires every subsystem together as concurrent asyncio tasks:

  - WebSocket server: always runs, broadcasts to the HUD
  - Gesture tracker:  runs if a webcam is available, streams gestures to the HUD
  - Wake word:        runs if a mic is available, triggers the listen/respond cycle
  - LLM brain + STT/TTS: invoked per-conversation-turn after a wake

Run with:
    cd backend && python main.py
"""
from __future__ import annotations

import asyncio
import logging

from config import settings
from gesture_tracker import GestureTracker
from llm_brain import LLMBrain
from stt import SpeechToText
from tts import TextToSpeech
from wake_word import WakeWordListener
from websocket_server import HUDBroadcaster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("jarvis.main")


class JarvisAssistant:
    def __init__(self):
        self.hud = HUDBroadcaster()
        self.brain = LLMBrain()
        self.stt = SpeechToText()
        self.tts = TextToSpeech(on_speaking_change=self._on_speaking_change)
        self.gestures = GestureTracker(
            on_gesture=self.hud.gesture,
            camera_index=settings.camera_index,
            fps_target=settings.gesture_fps_target,
        )
        self.wake_word = WakeWordListener(on_wake=self._on_wake)

    async def _on_speaking_change(self, speaking: bool) -> None:
        await self.hud.status("speaking" if speaking else "idle")

    async def _on_wake(self) -> None:
        """Full conversation turn: listen -> transcribe -> think -> speak."""
        await self.hud.status("listening")
        text = await self.stt.transcribe_from_mic()
        if not text:
            await self.hud.status("idle")
            return

        logger.info("Heard: %s", text)
        await self.hud.transcript("user", text)

        await self.hud.status("thinking")
        reply = await self.brain.think(text)
        logger.info("Reply: %s", reply)
        await self.hud.transcript("assistant", reply)

        await self.tts.speak(reply)  # flips status to "speaking" via callback, then back to "idle"

    async def run(self) -> None:
        for warning in settings.validate():
            logger.warning(warning)

        await self.hud.start()
        await self.hud.hardware(mic=self.stt.available, camera=self.gestures.available)

        logger.info(
            "Subsystem status — wake word: %s | STT: %s | TTS: %s | gestures: %s | LLM: %s",
            self.wake_word.available,
            self.stt.available,
            self.tts.available,
            self.gestures.available,
            self.brain.available,
        )

        await self.hud.status("idle")

        tasks = [
            asyncio.create_task(self.wake_word.listen_forever(), name="wake_word"),
            asyncio.create_task(self.gestures.track_forever(), name="gestures"),
        ]
        # keep the process alive even if both hardware-dependent tasks are no-ops
        await asyncio.gather(*tasks, asyncio.sleep(float("inf")), return_exceptions=True)


async def main() -> None:
    assistant = JarvisAssistant()
    await assistant.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down.")
