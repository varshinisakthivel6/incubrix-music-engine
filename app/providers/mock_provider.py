"""Deterministic test-only audio provider. It is NOT an AI music generator."""
from pathlib import Path
import numpy as np
import soundfile as sf
from .base import MusicProvider

class MockProvider(MusicProvider):
    name = "mock-test-tone"
    version = "1.0"

    def generate_stems(self, prompt, duration_s, sample_rate, seed, tempo_bpm, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        n = max(1, round(duration_s * sample_rate))
        t = np.arange(n, dtype=np.float32) / sample_rate
        rng = np.random.default_rng(seed or 42)

        # Synthetic, deliberately simple test signals, not publishable music.
        bass = (0.30 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)
        melody = (0.07 * np.sin(2 * np.pi * 440 * t) * (0.5 + 0.5*np.sin(2*np.pi*0.25*t))).astype(np.float32)
        beat_period = 60.0 / (tempo_bpm or 100.0)
        drums = np.zeros(n, dtype=np.float32)
        step = max(1, int(beat_period * sample_rate))
        click_len = max(1, int(0.04 * sample_rate))
        for start in range(0, n, step):
            end = min(n, start + click_len)
            m = end - start
            drums[start:end] += (0.15 * np.exp(-np.arange(m)/(0.008*sample_rate)) *
                                 rng.choice([-1.0, 1.0], size=m)).astype(np.float32)

        # Intentional fade so test audio does not hard-cut.
        fade_n = min(int(0.08 * sample_rate), n // 2)
        if fade_n:
            fade = np.linspace(0, 1, fade_n, dtype=np.float32)
            for arr in (bass, melody, drums):
                arr[:fade_n] *= fade
                arr[-fade_n:] *= fade[::-1]

        paths = {}
        for name, arr in {"bass": bass, "melody": melody, "drums": drums}.items():
            path = output_dir / f"{name}.wav"
            sf.write(path, arr, sample_rate, subtype="PCM_24")
            paths[name] = path
        return paths

    def rights(self):
        return {
            "status": "TEST_ONLY",
            "commercial_use": False,
            "notes": "Synthetic test tones only; not real generated music and not for commercial publication."
        }
