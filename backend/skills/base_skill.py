"""
Every skill is a small plugin that:
  1. declares a `name` (the function-call name the LLM will use)
  2. declares a `description` (tells the LLM when to use it)
  3. declares `parameters` (JSON-schema-ish dict of args)
  4. implements async `run(**kwargs) -> str`

Drop a new file in this folder defining a subclass of BaseSkill and
llm_brain.py's `discover_skills()` will pick it up automatically —
no registration step required.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseSkill(ABC):
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    @abstractmethod
    async def run(self, **kwargs) -> str:
        """Execute the skill and return a short natural-language result."""
        raise NotImplementedError

    def to_tool_schema(self) -> dict:
        """Anthropic tool-use / OpenAI function-calling compatible schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    key: {
                        "type": spec.get("type", "string"),
                        "description": spec.get("description", ""),
                    }
                    for key, spec in self.parameters.items()
                },
                "required": [
                    key for key, spec in self.parameters.items() if spec.get("required", True)
                ],
            },
        }
