"""Load, switch, and list Yumii's personalities from prompt files."""

import os
from typing import Dict

from yumii.core.global_config import load_global_config
from yumii.core.types import PERSONALITY_TYPE

PERSONALITY_DESCRIPTIONS: Dict[PERSONALITY_TYPE, str] = {
    "caring": "Warm, empathetic, and supportive",
    "tsundere": "Playful teasing with a soft heart",
    "genki": "Energetic and cheerful",
    "kuudere": "Cool, calm, and rational",
    "yandere": "Intensely devoted and loving",
    "dandere": "Shy and introverted",
}


class PersonalityManager:
    """Manages personality prompt loading and switching."""

    def __init__(self) -> None:
        """Set up personality prompt paths and cache."""
        # Resolve prompts relative to this file (works installed or from a dev checkout).
        from pathlib import Path
        self._prompts_dir: str = str(
            Path(__file__).parent.parent / "assets" / "prompts"
        )
        self._cache: Dict[PERSONALITY_TYPE, str] = {}

    def load_core_prompt(self) -> str:
        """Load the shared companion core prompt (_core.txt), cached."""
        if "_core" in self._cache:
            return self._cache["_core"]
        core_path = os.path.join(self._prompts_dir, "_core.txt")
        with open(core_path, "r", encoding="utf-8") as f:
            prompt = f.read()
        self._cache["_core"] = prompt
        return prompt

    def load_personality(self, personality: PERSONALITY_TYPE) -> str:
        """Load a personality prompt from file, with caching."""
        if personality in self._cache:
            return self._cache[personality]

        prompt_path = os.path.join(self._prompts_dir, f"{personality}.txt")
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f"Personality file not found: {prompt_path}")

        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt = f.read()

        self._cache[personality] = prompt
        return prompt

    def get_current_personality(self) -> PERSONALITY_TYPE:
        """Get the currently selected personality from global config."""
        config = load_global_config()
        personality = config.get("PERSONALITY", "caring")

        if personality not in PERSONALITY_DESCRIPTIONS:
            personality = "caring"

        return personality

    def get_current_personality_prompt(self) -> str:
        """Get the prompt for the currently selected personality."""
        personality = self.get_current_personality()
        return self.load_personality(personality)

    def list_personalities(self) -> Dict[PERSONALITY_TYPE, str]:
        """Get list of available personalities with descriptions."""
        return PERSONALITY_DESCRIPTIONS.copy()


# Global instance.
personality_manager = PersonalityManager()
