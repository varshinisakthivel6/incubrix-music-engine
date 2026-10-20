
"""Stable Audio 3 provider using its separate virtual environment."""

import os
import subprocess
from pathlib import Path


class StableAudioProvider:
    name = "stable_audio_3_huggingface"
    version = "3.0-small-music"
    ai_generated = True

    def __init__(self):
        self.model_name = os.getenv("STABLE_AUDIO3_MODEL", "small-music")
        self.steps = int(os.getenv("STABLE_AUDIO3_STEPS", "8"))
        self.max_native_duration = 300

        self.project_root = Path(__file__).resolve().parents[2]
        self.model_project = (
            self.project_root
            / "stable-audio-3"
            / "stable-audio-3-main"
            / "stable-audio-3-main"
        )

        scripts_dir = self.model_project / ".venv" / "Scripts"
        self.python_exe = scripts_dir / "python.exe"
        self.cli_exe = scripts_dir / "stable-audio.exe"

    def rights(self):
        return {
            "status": "license_review_required",
            "commercial_use": False,
            "notes": (
                "Review the Stability AI Community License and "
                "Hugging Face model terms before commercial distribution."
            ),
            "model_id": "stabilityai/stable-audio-3-small-music",
        }

    def _generate(self, prompt, duration_s, seed, output_path):
        duration_s = float(duration_s)

        if not 0 < duration_s <= self.max_native_duration:
            raise ValueError(
                "Duration must be greater than 0 and at most 120 seconds."
            )

        if not self.model_project.is_dir():
            raise RuntimeError(
                f"Stable Audio project directory not found: {self.model_project}"
            )

        if not self.python_exe.is_file():
            raise RuntimeError(
                f"Stable Audio Python executable not found: {self.python_exe}"
            )

        if self.cli_exe.is_file():
            command = [str(self.cli_exe)]
        else:
            command = [str(self.python_exe), "-m", "stable_audio_3"]

        # Resolve the output path before changing the subprocess working directory.
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        command += [
            "--model", self.model_name,
            "--prompt", str(prompt),
            "--duration", str(duration_s),
            "--steps", str(self.steps),
            "--seed", str(int(seed)),
            "--output", str(output_path),
        ]

        try:
            completed = subprocess.run(
                command,
                cwd=str(self.model_project),
                capture_output=True,
                text=True,
                timeout=max(300, int(duration_s * 30)),
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Could not launch Stable Audio. "
                f"Executable: {command[0]}. "
                f"Working directory: {self.model_project}. "
                f"Details: {exc}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Stable Audio timed out after {exc.timeout} seconds."
            ) from exc

        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(
                f"Stable Audio exited with code {completed.returncode}.\n"
                f"Command: {command[0]}\n"
                f"Details:\n{details[-4000:]}"
            )

        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError(
                "Stable Audio finished but the expected WAV file was not created: "
                f"{output_path}\n"
                f"CLI output:\n{completed.stdout[-2000:]}"
            )

    def generate_stems(
        self, prompt, duration_s, sample_rate, seed, tempo_bpm, output_dir
    ):
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        duration_s = float(duration_s)
        if not 0 < duration_s <= self.max_native_duration:
            raise ValueError(
                "duration_s must be greater than 0 and at most 300."
            )

        base_prompt = str(prompt or "").strip()
        if not base_prompt:
            raise ValueError("A non-empty music prompt is required.")

        tempo = f", {int(tempo_bpm)} BPM" if tempo_bpm else ""
        common = (
            f"{base_prompt}{tempo}. Instrumental background music for video, "
            "no intelligible vocals, polished production, clear ending."
        )

        tracks = {
            "drums": (
                "TrackType: Instrument. Isolated drum kit and percussion. "
                f"{common}"
            ),
            "bass": (
                "TrackType: Instrument. Isolated bass guitar or synth bass. "
                f"{common}"
            ),
            "harmony": (
                "TrackType: Instrument. Isolated piano and harmonic pads. "
                f"{common}"
            ),
            "melody": (
                "TrackType: Instrument. Isolated melodic lead instrument. "
                f"{common}"
            ),
        }

        results = {}

        for offset, (name, track_prompt) in enumerate(tracks.items()):
            path = output_dir / f"{name}.wav"

            self._generate(
                prompt=track_prompt,
                duration_s=duration_s,
                seed=int(seed) + offset * 104729,
                output_path=path,
            )

            results[name] = path

        # These are independently generated instrument tracks,
        # not source-separated stems.
        return results
