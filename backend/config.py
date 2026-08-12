"""
Centralized settings, loaded once from .env at import time.

Every other module imports `settings` from here rather than reading
os.environ directly, so there's a single source of truth and a single
place to add validation later.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


@dataclass
class Settings:
    # LLM
    llm_provider: str = os.getenv("LLM_PROVIDER", "anthropic")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # STT
    stt_engine: str = os.getenv("STT_ENGINE", "whisper-local")
    whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "base")
    google_stt_api_key: str = os.getenv("GOOGLE_STT_API_KEY", "")

    # TTS
    tts_engine: str = os.getenv("TTS_ENGINE", "pyttsx3")
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "")

    # Wake word
    wake_word: str = os.getenv("WAKE_WORD", "hey_jarvis")
    wake_word_sensitivity: float = field(
        default_factory=lambda: _get_float("WAKE_WORD_SENSITIVITY", 0.5)
    )

    # Skills
    weather_api_key: str = os.getenv("WEATHER_API_KEY", "")

    # WebSocket
    ws_host: str = os.getenv("WS_HOST", "localhost")
    ws_port: int = field(default_factory=lambda: _get_int("WS_PORT", 8765))

    # Gesture tracking
    camera_index: int = field(default_factory=lambda: _get_int("CAMERA_INDEX", 0))
    gesture_fps_target: int = field(
        default_factory=lambda: _get_int("GESTURE_FPS_TARGET", 30)
    )

    def validate(self) -> list[str]:
        """Return a list of human-readable warnings (never raises)."""
        warnings = []
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            warnings.append(
                "ANTHROPIC_API_KEY is not set — the LLM brain will run in "
                "degraded mode (local skills only, no conversation)."
            )
        if self.llm_provider == "openai" and not self.openai_api_key:
            warnings.append("OPENAI_API_KEY is not set — LLM brain degraded.")
        if self.tts_engine == "elevenlabs" and not self.elevenlabs_api_key:
            warnings.append("TTS_ENGINE=elevenlabs but ELEVENLABS_API_KEY is missing.")
        return warnings


settings = Settings()
