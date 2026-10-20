from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

class MusicProvider(ABC):
    name = "base"
    version = "unknown"

    @abstractmethod
    def generate_stems(self, prompt: str, duration_s: float, sample_rate: int,
                       seed: int, tempo_bpm: float | None, output_dir: Path) -> dict[str, Path]:
        """Return separate instrument files. Implementations must document actual rights."""
        raise NotImplementedError

    def rights(self) -> dict[str, Any]:
        return {
            "status": "UNVERIFIED",
            "commercial_use": False,
            "notes": "Provider rights have not been verified. Do not use this output for commercial release."
        }
