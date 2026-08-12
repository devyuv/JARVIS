"""
"Hey Jarvis" wake word detection, built on openWakeWord.

Runs a continuous listen loop and calls `on_wake()` whenever the wake
word is detected. If no microphone is available, `available` is set
to False and `listen_forever()` becomes a no-op — main.py checks this
flag and shows a "voice offline" state to the HUD instead of crashing.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

import numpy as np

from config import settings

logger = logging.getLogger("jarvis.wake_word")

CHUNK_SAMPLES = 1280  # openWakeWord expects 80ms chunks @ 16kHz
SAMPLE_RATE = 16000


class WakeWordListener:
    def __init__(self, on_wake: Callable[[], Awaitable[None]]):
        self.on_wake = on_wake
        self.available = False
        self._model = None
        self._stream = None
        self._init_hardware_and_model()

    def _init_hardware_and_model(self) -> None:
        try:
            import sounddevice as sd
            from openwakeword.model import Model

            devices = sd.query_devices()
            if not any(d["max_input_channels"] > 0 for d in devices):
                logger.warning("No input (microphone) device found. Wake word disabled.")
                return

            self._model = Model(
                wakeword_models=[settings.wake_word],
                inference_framework="onnx",
            )
            self._sd = sd
            self.available = True
            logger.info("Wake word model '%s' loaded.", settings.wake_word)
        except Exception as exc:  # pragma: no cover - hardware/env dependent
            logger.warning("Wake word init failed (%s). Wake word disabled.", exc)
            self.available = False

    async def listen_forever(self) -> None:
        """Continuously poll the mic and fire on_wake() on detection."""
        if not self.available:
            logger.info("Wake word listener not available; skipping.")
            return

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[np.ndarray] = asyncio.Queue()

        def _callback(indata, frames, time_info, status):
            if status:
                logger.debug("Audio status: %s", status)
            loop.call_soon_threadsafe(queue.put_nowait, indata.copy())

        with self._sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK_SAMPLES,
            callback=_callback,
        ):
            logger.info("Listening for wake word '%s'...", settings.wake_word)
            while True:
                chunk = await queue.get()
                scores = self._model.predict(chunk.flatten())
                score = scores.get(settings.wake_word, 0.0)
                if score >= settings.wake_word_sensitivity:
                    logger.info("Wake word detected (score=%.2f)", score)
                    await self.on_wake()
                    # brief cooldown to avoid re-triggering on the same utterance
                    await asyncio.sleep(1.5)
