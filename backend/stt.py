"""
Speech-to-text. Two backends, chosen via STT_ENGINE:

  - "whisper-local": faster-whisper running fully offline
  - "google":        SpeechRecognition + Google's free web API (needs network)

Both expose the same async `transcribe_from_mic(timeout, phrase_time_limit)`
coroutine so main.py doesn't need to know which one is active.
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
import wave
from pathlib import Path

from config import settings

logger = logging.getLogger("jarvis.stt")


class SpeechToText:
    def __init__(self):
        self.available = False
        self.engine = settings.stt_engine
        self._whisper_model = None
        self._recognizer = None
        self._mic = None
        self._init()

    def _init(self) -> None:
        try:
            import sounddevice as sd  # noqa: F401 - probes mic availability

            devices = sd.query_devices()
            if not any(d["max_input_channels"] > 0 for d in devices):
                logger.warning("No microphone found. STT disabled.")
                return
        except Exception as exc:
            logger.warning("Audio subsystem unavailable (%s). STT disabled.", exc)
            return

        if self.engine == "whisper-local":
            try:
                from faster_whisper import WhisperModel

                self._whisper_model = WhisperModel(
                    settings.whisper_model_size, device="cpu", compute_type="int8"
                )
                self.available = True
                logger.info("Loaded local Whisper model '%s'.", settings.whisper_model_size)
            except Exception as exc:
                logger.warning("Failed to load local Whisper model (%s).", exc)
        else:  # google
            try:
                import speech_recognition as sr

                self._recognizer = sr.Recognizer()
                self._mic = sr.Microphone()
                self.available = True
                logger.info("Using Google speech recognition (requires network).")
            except Exception as exc:
                logger.warning("Failed to init Google STT (%s).", exc)

    async def transcribe_from_mic(
        self, timeout: float = 6.0, phrase_time_limit: float = 12.0
    ) -> str | None:
        """Record one utterance from the mic and return its transcript."""
        if not self.available:
            return None

        loop = asyncio.get_event_loop()
        try:
            if self.engine == "whisper-local":
                return await loop.run_in_executor(
                    None, self._record_and_transcribe_whisper, timeout, phrase_time_limit
                )
            return await loop.run_in_executor(
                None, self._record_and_transcribe_google, timeout, phrase_time_limit
            )
        except Exception as exc:
            logger.error("Transcription failed: %s", exc)
            return None

    # -- whisper path -----------------------------------------------------
    def _record_and_transcribe_whisper(self, timeout: float, phrase_time_limit: float) -> str:
        import sounddevice as sd
        import numpy as np

        sample_rate = 16000
        logger.info("Recording (up to %.0fs)...", phrase_time_limit)
        audio = sd.rec(
            int(phrase_time_limit * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())

        segments, _ = self._whisper_model.transcribe(str(path), language="en")
        text = " ".join(seg.text.strip() for seg in segments).strip()
        path.unlink(missing_ok=True)
        return text

    # -- google path --------------------------------------------------------
    def _record_and_transcribe_google(self, timeout: float, phrase_time_limit: float) -> str:
        import speech_recognition as sr

        with self._mic as source:
            self._recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = self._recognizer.listen(
                source, timeout=timeout, phrase_time_limit=phrase_time_limit
            )
        return self._recognizer.recognize_google(audio)
