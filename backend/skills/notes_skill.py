"""Simple notes: add and list, persisted to a local JSON file."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from skills.base_skill import BaseSkill

logger = logging.getLogger("jarvis.skills.notes")
NOTES_PATH = Path(__file__).resolve().parent.parent / "data" / "notes.json"


def _load() -> list[dict]:
    if not NOTES_PATH.exists():
        return []
    try:
        return json.loads(NOTES_PATH.read_text())
    except json.JSONDecodeError:
        logger.warning("notes.json was corrupt; starting fresh.")
        return []


def _save(notes: list[dict]) -> None:
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTES_PATH.write_text(json.dumps(notes, indent=2))


class AddNoteSkill(BaseSkill):
    name = "add_note"
    description = "Save a short note for later."
    parameters = {
        "text": {"type": "string", "description": "The note content", "required": True},
    }

    async def run(self, text: str) -> str:
        notes = _load()
        notes.append({"text": text, "created_at": datetime.now().isoformat(timespec="seconds")})
        _save(notes)
        return "Noted."


class ListNotesSkill(BaseSkill):
    name = "list_notes"
    description = "List all saved notes."
    parameters = {}

    async def run(self) -> str:
        notes = _load()
        if not notes:
            return "You don't have any notes saved."
        lines = [f"{i+1}. {n['text']}" for i, n in enumerate(notes)]
        return "Your notes:\n" + "\n".join(lines)
