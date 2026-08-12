"""Current weather for a city, via OpenWeatherMap."""
from __future__ import annotations

import logging

import requests

from config import settings
from skills.base_skill import BaseSkill

logger = logging.getLogger("jarvis.skills.weather")


class WeatherSkill(BaseSkill):
    name = "get_weather"
    description = "Get the current weather conditions for a named city."
    parameters = {
        "city": {"type": "string", "description": "City name, e.g. 'Austin'", "required": True},
    }

    async def run(self, city: str) -> str:
        if not settings.weather_api_key:
            return (
                "I don't have a weather API key configured, so I can't check "
                "the weather right now. Set WEATHER_API_KEY in .env to enable this."
            )
        try:
            resp = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "q": city,
                    "appid": settings.weather_api_key,
                    "units": "imperial",
                },
                timeout=6,
            )
            resp.raise_for_status()
            data = resp.json()
            desc = data["weather"][0]["description"]
            temp = data["main"]["temp"]
            feels = data["main"]["feels_like"]
            return f"It's {temp:.0f}°F in {city} ({desc}), feels like {feels:.0f}°F."
        except requests.exceptions.RequestException as exc:
            logger.warning("Weather lookup failed: %s", exc)
            return f"I couldn't reach the weather service to check {city} right now."
        except (KeyError, IndexError):
            return f"I couldn't find weather data for '{city}'. Check the spelling?"
