"""
System control: volume, brightness, and launching applications.

Implementations are OS-specific and best-effort — each shells out to the
native tool for the current platform and reports a clear message if that
tool isn't available rather than crashing the assistant.
"""
from __future__ import annotations

import logging
import platform
import shutil
import subprocess

from skills.base_skill import BaseSkill

logger = logging.getLogger("jarvis.skills.system")
OS_NAME = platform.system()  # "Windows" | "Darwin" | "Linux"


class SetVolumeSkill(BaseSkill):
    name = "set_volume"
    description = "Set the system output volume to a percentage (0-100)."
    parameters = {
        "level": {"type": "number", "description": "Volume percentage, 0-100", "required": True},
    }

    async def run(self, level: float) -> str:
        level = max(0, min(100, int(level)))
        try:
            if OS_NAME == "Darwin":
                subprocess.run(
                    ["osascript", "-e", f"set volume output volume {level}"], check=True
                )
            elif OS_NAME == "Windows":
                # Requires nircmd or pycaw in a full build; this is a best-effort stub.
                logger.info("Windows volume control requires pycaw — see skills docs.")
                return (
                    f"I'd set volume to {level}%, but Windows volume control needs the "
                    f"pycaw package wired in — it's stubbed out in this build."
                )
            elif OS_NAME == "Linux":
                if shutil.which("amixer"):
                    subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"], check=True)
                else:
                    return "amixer isn't installed, so I can't change the volume."
            else:
                return f"Volume control isn't supported on {OS_NAME}."
            return f"Volume set to {level}%."
        except subprocess.CalledProcessError as exc:
            logger.warning("Volume control failed: %s", exc)
            return "I hit an error trying to change the volume."


class SetBrightnessSkill(BaseSkill):
    name = "set_brightness"
    description = "Set the screen brightness to a percentage (0-100)."
    parameters = {
        "level": {"type": "number", "description": "Brightness percentage, 0-100", "required": True},
    }

    async def run(self, level: float) -> str:
        level = max(0, min(100, int(level)))
        try:
            if OS_NAME == "Darwin":
                # macOS has no first-party CLI; requires 'brightness' (brew install brightness).
                if shutil.which("brightness"):
                    subprocess.run(["brightness", str(level / 100)], check=True)
                else:
                    return "Install the 'brightness' CLI (`brew install brightness`) to enable this."
            elif OS_NAME == "Linux" and shutil.which("brightnessctl"):
                subprocess.run(["brightnessctl", "set", f"{level}%"], check=True)
            elif OS_NAME == "Windows":
                logger.info("Windows brightness control requires WMI — see skills docs.")
                return (
                    f"I'd set brightness to {level}%, but Windows brightness control needs "
                    f"the WMI bridge wired in — it's stubbed out in this build."
                )
            else:
                return f"Brightness control isn't available on this system for {OS_NAME}."
            return f"Brightness set to {level}%."
        except subprocess.CalledProcessError as exc:
            logger.warning("Brightness control failed: %s", exc)
            return "I hit an error trying to change the brightness."


class OpenAppSkill(BaseSkill):
    name = "open_app"
    description = "Open a desktop application by name (e.g. 'Spotify', 'Calculator')."
    parameters = {
        "app_name": {"type": "string", "description": "Name of the app to open", "required": True},
    }

    async def run(self, app_name: str) -> str:
        try:
            if OS_NAME == "Darwin":
                subprocess.run(["open", "-a", app_name], check=True)
            elif OS_NAME == "Windows":
                subprocess.run(["cmd", "/c", "start", "", app_name], check=True, shell=False)
            elif OS_NAME == "Linux":
                subprocess.run([app_name.lower()], check=True)
            else:
                return f"Opening apps isn't supported on {OS_NAME}."
            return f"Opening {app_name}."
        except (subprocess.CalledProcessError, FileNotFoundError):
            return f"I couldn't find or open '{app_name}'."
