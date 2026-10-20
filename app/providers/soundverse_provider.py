
import os
from pathlib import Path
from typing import Any

import requests

from .base import MusicProvider


class SoundverseProvider(MusicProvider):
    name = "soundverse"
    version = "v1"

    BASE_URL = "https://apiv2.soundverse.ai"

    def __init__(self):
        self.api_key = os.getenv("SOUNDVERSE_API_KEY")
        if not self.api_key:
            raise RuntimeError("SOUNDVERSE_API_KEY is not configured")

    def rights(self) -> dict[str, Any]:
        return {
            "status": "VERIFY_REQUIRED",
            "commercial_use": False,
            "notes": (
                "Verify the selected Soundverse license and usage rights "
                "before commercial publication."
            ),
        }

    def generate_stems(
        self,
        prompt,
        duration_s,
        sample_rate,
        seed,
        tempo_bpm,
        output_dir,
    ) -> dict[str, Path]:
        raise NotImplementedError(
            "Soundverse generation and stem-separation workflow "
            "must be implemented and tested before use."
        )
