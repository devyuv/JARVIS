"""
Text-to-speech. Three backends, chosen via TTS_ENGINE:

  - "pyttsx3":    fully offline, robotic-ish but zero dependencies on network
  - "edge-tts":   free, natural-sounding, needs network (Microsoft Edge voices)
  - "elevenlabs": premium natural voice, needs ELEVENLABS_API_KEY + network

All expose the same async `speak(text)` coroutine.
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from config import settings

logger = logging.getLogger("jarvis.tts")


class TextToSpeech:
    def __init__(self, on_speaking_change=None):
        """
        on_speaking_change: optional async callback(bool) fired when
        speech starts/stops, so the HUD can animate the waveform.
        """
        self.engine = settings.tts_engine
        self.available = False
        self._on_speaking_change = on_speaking_change
        self._pyttsx3_engine = None
        self._init()

    def _init(self) -> None:
        if self.engine == "pyttsx3":
            try:
                import pyttsx3

                self._pyttsx3_engine = pyttsx3.init()
                self.available = True
            except Exception as exc:
                logger.warning("pyttsx3 init failed (%s). TTS disabled.", exc)
        elif self.engine == "edge-tts":
            self.available = True  # checked lazily on first use (network dependent)
        elif self.engine == "elevenlabs":
            self.available = bool(settings.elevenlabs_api_key)
            if not self.available:
                logger.warning("ELEVENLABS_API_KEY missing. TTS disabled.")
        else:
            logger.warning("Unknown TTS_ENGINE '%s'. TTS disabled.", self.engine)

    async def speak(self, text: str) -> None:
        if not self.available or not text:
            return
        if self._on_speaking_change:
            await self._on_speaking_change(True)
        try:
            if self.engine == "pyttsx3":
                await self._speak_pyttsx3(text)
            elif self.engine == "edge-tts":
                await self._speak_edge(text)
            elif self.engine == "elevenlabs":
                await self._speak_elevenlabs(text)
        except Exception as exc:
            logger.error("TTS playback failed (%s). Falling back to text-only.", exc)
        finally:
            if self._on_speaking_change:
                await self._on_speaking_change(False)

    async def _speak_pyttsx3(self, text: str) -> None:
        loop = asyncio.get_event_loop()

        def _run():
            self._pyttsx3_engine.say(text)
            self._pyttsx3_engine.runAndWait()

        await loop.run_in_executor(None, _run)

    async def _speak_edge(self, text: str) -> None:
        import edge_tts

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            path = Path(f.name)
        communicate = edge_tts.Communicate(text, voice="en-US-GuyNeural")
        await communicate.save(str(path))
        await self._play_audio_file(path)
        path.unlink(missing_ok=True)

    async def _speak_elevenlabs(self, text: str) -> None:
        from elevenlabs.client import ElevenLabs

        client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        loop = asyncio.get_event_loop()

        def _generate_and_save() -> Path:
            audio = client.generate(
                text=text,
                voice=settings.elevenlabs_voice_id or "Adam",
                model="eleven_turbo_v2",
            )
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                for chunk in audio:
                    f.write(chunk)
                return Path(f.name)

        path = await loop.run_in_executor(None, _generate_and_save)
        await self._play_audio_file(path)
        path.unlink(missing_ok=True)

    async def _play_audio_file(self, path: Path) -> None:
        """Cross-platform-ish playback without extra native deps."""
        loop = asyncio.get_event_loop()

        def _play():
            try:
                from playsound import playsound

                playsound(str(path))
            except Exception:
                logger.warning("No audio player available; skipping playback of %s", path)

        await loop.run_in_executor(None, _play)
