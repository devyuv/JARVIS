"""
The reasoning layer. Discovers every BaseSkill subclass in backend/skills/,
exposes them to the LLM as tools, and runs the tool-calling loop.

Supports Anthropic (Claude) and OpenAI, chosen via LLM_PROVIDER. If no
API key is configured for the active provider, `available` is False and
`think()` returns a friendly degraded-mode message instead of raising —
main.py can still route simple commands directly to skills in that case.
"""
from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import Any

from config import settings
from skills.base_skill import BaseSkill

logger = logging.getLogger("jarvis.llm_brain")

SYSTEM_PROMPT = (
    "You are JARVIS, a concise, capable AI desktop assistant speaking out loud "
    "to your user. Keep replies short and conversational — this is text that "
    "will be spoken aloud via TTS, not read on a screen. Use the tools "
    "available to you to actually perform actions (opening apps, checking "
    "weather, searching the web, controlling volume/brightness, taking notes) "
    "rather than just describing what you would do."
)


def discover_skills() -> list[BaseSkill]:
    """Import every module in backend/skills/ and instantiate each BaseSkill subclass found."""
    import skills as skills_pkg

    discovered: list[BaseSkill] = []
    for _, module_name, _ in pkgutil.iter_modules(skills_pkg.__path__):
        if module_name in ("base_skill",):
            continue
        module = importlib.import_module(f"skills.{module_name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseSkill) and obj is not BaseSkill:
                try:
                    discovered.append(obj())
                except Exception as exc:
                    logger.warning("Failed to instantiate skill %s: %s", obj.__name__, exc)
    logger.info("Discovered %d skills: %s", len(discovered), [s.name for s in discovered])
    return discovered


class LLMBrain:
    def __init__(self):
        self.skills: dict[str, BaseSkill] = {s.name: s for s in discover_skills()}
        self.provider = settings.llm_provider
        self.available = False
        self._client = None
        self._history: list[dict[str, Any]] = []
        self._init_client()

    def _init_client(self) -> None:
        try:
            if self.provider == "anthropic" and settings.anthropic_api_key:
                import anthropic

                self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                self.available = True
            elif self.provider == "openai" and settings.openai_api_key:
                import openai

                self._client = openai.OpenAI(api_key=settings.openai_api_key)
                self.available = True
            else:
                logger.warning(
                    "No API key for provider '%s'. LLM brain running in degraded mode.",
                    self.provider,
                )
        except Exception as exc:
            logger.warning("LLM client init failed (%s). Degraded mode.", exc)

    async def think(self, user_text: str) -> str:
        """Take a user utterance, run the tool-calling loop, return the final reply text."""
        if not self.available:
            return (
                "I can't reach my reasoning engine right now — no LLM API key is "
                "configured — but local skills like timers and volume control "
                "still work if you name them directly."
            )
        if self.provider == "anthropic":
            return await self._think_anthropic(user_text)
        return await self._think_openai(user_text)

    # -- Anthropic ----------------------------------------------------------
    async def _think_anthropic(self, user_text: str) -> str:
        tools = [s.to_tool_schema() for s in self.skills.values()]
        self._history.append({"role": "user", "content": user_text})

        for _ in range(5):  # cap tool-call round trips
            response = self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=self._history,
            )
            self._history.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                return "".join(
                    block.text for block in response.content if block.type == "text"
                ).strip()

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                skill = self.skills.get(block.name)
                result = (
                    await skill.run(**block.input)
                    if skill
                    else f"Unknown tool '{block.name}'."
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
            self._history.append({"role": "user", "content": tool_results})

        return "Sorry, that took more steps than I expected — could you rephrase?"

    # -- OpenAI ---------------------------------------------------------------
    async def _think_openai(self, user_text: str) -> str:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": s.to_tool_schema()["input_schema"],
                },
            }
            for s in self.skills.values()
        ]
        if not self._history:
            self._history.append({"role": "system", "content": SYSTEM_PROMPT})
        self._history.append({"role": "user", "content": user_text})

        for _ in range(5):
            response = self._client.chat.completions.create(
                model=settings.openai_model,
                messages=self._history,
                tools=tools,
            )
            message = response.choices[0].message
            self._history.append(message.model_dump())

            if not message.tool_calls:
                return message.content or ""

            for call in message.tool_calls:
                import json

                skill = self.skills.get(call.function.name)
                args = json.loads(call.function.arguments or "{}")
                result = await skill.run(**args) if skill else "Unknown tool."
                self._history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result,
                    }
                )

        return "Sorry, that took more steps than I expected — could you rephrase?"
