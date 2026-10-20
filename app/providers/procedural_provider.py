
from pathlib import Path

import numpy as np
import soundfile as sf


class ProceduralProvider:
    """Generate prompt-influenced instrumental music stems."""

    name = "procedural"
    version = "3.0"

    def __init__(self):
        self.sample_rate = 24000
        self.ai_generated = False

    def rights(self):
        return {
            "status": "procedurally_generated",
            "commercial_use": "verify_before_claiming",
            "notes": (
                "Procedurally synthesized audio, not an AI music model "
                "or realistic instrument recording."
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
    ):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        duration = float(duration_s)
        sr = int(sample_rate)
        text = str(prompt or "").lower()
        rng = np.random.default_rng(seed)
        count = int(round(duration * sr))

        if duration <= 0 or sr <= 0 or count <= 0:
            raise ValueError("Duration and sample rate must be positive.")

        # Detect the intended musical mood.
        energetic_words = [
            "energetic", "upbeat", "fast", "action", "workout",
            "mass", "kuthu", "dance", "tamil", "folk",
            "festival", "celebration", "dappankuthu",
            "parai", "thavil", "party",
        ]
        emotional_words = [
            "sad", "emotional", "slow", "heartfelt",
            "dramatic", "romantic",
        ]
        chill_words = [
            "calm", "peaceful", "relaxing", "meditation",
            "nature", "dreamy", "chill", "lofi", "lo-fi",
            "night drive",
        ]
        suspense_words = [
            "suspense", "dark", "mystery", "thriller",
        ]

        tempo = int(tempo_bpm or 96)
        mood = "chill"

        if any(word in text for word in energetic_words):
            tempo = int(tempo_bpm or 124)
            mood = "energetic"
        elif any(word in text for word in emotional_words):
            tempo = int(tempo_bpm or 82)
            mood = "emotional"
        elif any(word in text for word in chill_words):
            tempo = int(tempo_bpm or 88)
            mood = "chill"
        elif any(word in text for word in suspense_words):
            tempo = int(tempo_bpm or 96)
            mood = "suspense"

        tempo = max(55, min(160, tempo))
        beat = 60.0 / tempo
        bar_length = beat * 4

        def hz(midi):
            return 440.0 * (2.0 ** ((midi - 69) / 12.0))

        progressions = {
            "chill": [
                (60, 64, 67), (55, 59, 62),
                (57, 60, 64), (53, 57, 60),
            ],
            "energetic": [
                (60, 64, 67), (65, 69, 72),
                (57, 60, 64), (67, 71, 74),
            ],
            "emotional": [
                (57, 60, 64), (53, 57, 60),
                (60, 64, 67), (55, 59, 62),
            ],
            "suspense": [
                (48, 51, 55), (49, 52, 56),
                (48, 51, 55), (46, 50, 53),
            ],
        }

        scales = {
            "chill": [60, 62, 64, 67, 69, 72, 74, 76],
            "energetic": [60, 62, 64, 67, 69, 72, 76, 79],
            "emotional": [57, 60, 62, 64, 67, 69, 72, 76],
            "suspense": [58, 60, 63, 65, 66, 70, 72, 75],
        }

        progression = progressions[mood]
        scale = scales[mood]

        chords = np.zeros(count, dtype=np.float32)
        bass = np.zeros(count, dtype=np.float32)
        melody = np.zeros(count, dtype=np.float32)
        percussion = np.zeros(count, dtype=np.float32)

        def add_tone(
            buffer,
            freq,
            start,
            length,
            volume,
            kind="soft",
        ):
            if start < 0 or length <= 0 or start >= duration:
                return

            first = max(0, int(start * sr))
            last = min(count, int((start + length) * sr))

            if last <= first:
                return

            t = np.arange(last - first, dtype=np.float32) / sr
            note_len = max(length, 1.0 / sr)

            attack_time = 0.008 if kind == "pluck" else 0.018
            release_time = 0.06 if kind != "pad" else 0.18

            attack = np.minimum(t / attack_time, 1.0)
            release = np.clip(
                (note_len - t) / release_time,
                0.0,
                1.0,
            )
            env = attack * release

            fundamental = np.sin(2 * np.pi * freq * t)

            if kind == "pluck":
                wave = (
                    fundamental
                    + 0.42 * np.sin(2 * np.pi * freq * 2 * t)
                    + 0.16 * np.sin(2 * np.pi * freq * 3 * t)
                )
                env *= np.exp(-3.0 * t / note_len)

            elif kind == "pad":
                wave = (
                    fundamental
                    + 0.24 * np.sin(2 * np.pi * freq * 2 * t)
                    + 0.10 * np.sin(2 * np.pi * freq * 0.5 * t)
                )

            elif kind == "bass":
                wave = (
                    fundamental
                    + 0.12 * np.sin(2 * np.pi * freq * 2 * t)
                )

            else:
                wave = (
                    fundamental
                    + 0.22 * np.sin(2 * np.pi * freq * 2 * t)
                )

            buffer[first:last] += (
                volume * wave * env
            ).astype(np.float32)

        # Punchier synthesized kick drum.
        def add_kick(start, volume):
            if start < 0 or start >= duration:
                return

            length = min(0.28, duration - start)
            first = max(0, int(start * sr))
            last = min(count, first + int(length * sr))

            if last <= first:
                return

            t = np.arange(last - first, dtype=np.float32) / sr

            freq = 135.0 * np.exp(-12.0 * t) + 42.0
            phase = 2 * np.pi * np.cumsum(freq) / sr

            body = np.sin(phase) * np.exp(-13.0 * t)
            click = (
                np.sin(2 * np.pi * 1800.0 * t)
                * np.exp(-100.0 * t)
            )

            percussion[first:last] += (
                volume * (body + 0.12 * click)
            ).astype(np.float32)

        # Sharper synthesized snare.
        def add_snare(start, volume):
            if start < 0 or start >= duration:
                return

            length = min(0.17, duration - start)
            first = max(0, int(start * sr))
            last = min(count, first + int(length * sr))

            if last <= first:
                return

            t = np.arange(last - first, dtype=np.float32) / sr

            noise = rng.normal(
                0.0, 1.0, last - first
            ).astype(np.float32)

            noise_env = np.exp(-28.0 * t)
            tone_env = np.exp(-32.0 * t)

            tone_part = (
                np.sin(2 * np.pi * 190.0 * t) * tone_env
            )

            snap = (
                np.sin(2 * np.pi * 2400.0 * t)
                * np.exp(-85.0 * t)
            )

            sound = (
                0.72 * noise * noise_env
                + 0.23 * tone_part
                + 0.12 * snap
            )

            percussion[first:last] += (
                volume * sound
            ).astype(np.float32)

        # Short high-frequency percussion.
        def add_hat(start, volume):
            if start < 0 or start >= duration:
                return

            length = min(0.045, duration - start)
            first = max(0, int(start * sr))
            last = min(count, first + int(length * sr))

            if last <= first:
                return

            noise = rng.normal(
                0.0, 1.0, last - first
            ).astype(np.float32)

            t = np.arange(last - first, dtype=np.float32) / sr

            percussion[first:last] += (
                volume * noise * np.exp(-75.0 * t)
            ).astype(np.float32)

        # Melodic phrases.
        phrase = [
            0, 2, 4, 3, 2, 1, 4, 2,
            0, 2, 5, 4, 3, 2, 1, 0,
        ]

        if mood == "emotional":
            phrase = [
                0, 2, 4, 5, 4, 2, 1, 2,
                0, 2, 4, 3, 2, 1, 0, 1,
            ]
        elif mood == "energetic":
            phrase = [
                0, 2, 4, 6, 4, 2, 5, 4,
                0, 2, 4, 7, 6, 4, 2, 1,
            ]
        elif mood == "suspense":
            phrase = [
                0, 1, 3, 2, 0, 2, 4, 3,
                1, 0, 3, 2, 1, 3, 2, 0,
            ]

        bars = int(np.ceil(duration / bar_length))

        for bar in range(bars):
            start = bar * bar_length

            if start >= duration:
                break

            bar_duration = min(bar_length, duration - start)
            chord = progression[bar % len(progression)]

            # Chords stay softer so the beat can lead.
            pad_volume = 0.026 if mood == "chill" else 0.028

            for index, note in enumerate(chord):
                add_tone(
                    chords,
                    hz(note + 12),
                    start + index * 0.012,
                    bar_duration,
                    pad_volume,
                    "pad",
                )

                if mood in ("chill", "energetic") and index == 1:
                    add_tone(
                        chords,
                        hz(note + 24),
                        start,
                        bar_duration,
                        0.007,
                        "pad",
                    )

            # More rhythmic bass notes for energetic tracks.
            bass_volume = 0.14 if mood == "suspense" else 0.12

            if mood == "energetic":
                bass_pattern = [
                    (0.0, 0, 1.35),
                    (1.0, 2, 0.85),
                    (2.0, 0, 1.10),
                    (2.5, 2, 0.65),
                    (3.0, 1, 0.80),
                ]

                for beat_offset, note_index, strength in bass_pattern:
                    note_start = start + beat_offset * beat

                    if note_start < duration:
                        note_midi = chord[note_index]

                        add_tone(
                            bass,
                            hz(note_midi - 12),
                            note_start,
                            min(
                                beat * 0.72,
                                duration - note_start,
                            ),
                            bass_volume * strength,
                            "bass",
                        )
            else:
                add_tone(
                    bass,
                    hz(chord[0] - 12),
                    start,
                    min(beat * 1.65, bar_duration),
                    bass_volume,
                    "bass",
                )

                second_start = start + beat * 2

                if second_start < duration:
                    add_tone(
                        bass,
                        hz(chord[2] - 12),
                        second_start,
                        min(
                            beat * 1.35,
                            duration - second_start,
                        ),
                        bass_volume * 0.8,
                        "bass",
                    )

            # Melody.
            step_beats = 0.5 if mood == "energetic" else 1.0
            steps_per_bar = int(4 / step_beats)

            for step in range(steps_per_bar):
                note_start = start + step * beat * step_beats

                if note_start >= duration:
                    break

                phrase_index = (bar % 4) * 4 + min(step, 3)
                scale_index = phrase[
                    phrase_index % len(phrase)
                ]
                note_midi = scale[scale_index % len(scale)]

                if (
                    bar % 4 == 3
                    and step == steps_per_bar - 1
                    and mood in ("chill", "energetic")
                ):
                    note_midi += 12

                note_len = min(
                    beat * step_beats * 0.72,
                    duration - note_start,
                )

                melody_volume = (
                    0.055 if mood == "energetic"
                    else 0.052 if mood == "chill"
                    else 0.062
                )

                add_tone(
                    melody,
                    hz(note_midi),
                    note_start,
                    note_len,
                    melody_volume,
                    "pluck",
                )

            # Drum patterns.
            for beat_index in range(4):
                hit = start + beat_index * beat

                if hit >= duration:
                    break

                if mood == "energetic":
                    kick_vol = 0.23
                    snare_vol = 0.105
                    hat_vol = 0.030

                    # Main kick pulse.
                    if beat_index in (0, 2):
                        add_kick(hit, kick_vol)

                    # Backbeat.
                    if beat_index in (1, 3):
                        add_snare(hit, snare_vol)

                    # Busy dance subdivisions.
                    add_hat(hit + beat * 0.5, hat_vol)
                    add_hat(hit + beat * 0.75, hat_vol * 0.85)

                    # Extra offbeat kicks for dance energy.
                    if beat_index in (1, 2):
                        add_kick(
                            hit + beat * 0.5,
                            kick_vol * 0.58,
                        )

                    # Short fill near the end of each bar.
                    if beat_index == 3:
                        add_snare(
                            hit + beat * 0.5,
                            snare_vol * 0.55,
                        )
                        add_hat(
                            hit + beat * 0.75,
                            hat_vol * 1.1,
                        )

                    # Occasional extra accents, not every bar.
                    if bar % 4 == 3 and beat_index in (2, 3):
                        add_hat(
                            hit + beat * 0.25,
                            hat_vol * 0.75,
                        )

                else:
                    if mood == "chill":
                        kick_vol, snare_vol, hat_vol = (
                            0.12, 0.045, 0.012
                        )
                    elif mood == "emotional":
                        kick_vol, snare_vol, hat_vol = (
                            0.105, 0.035, 0.010
                        )
                    else:
                        kick_vol, snare_vol, hat_vol = (
                            0.10, 0.025, 0.009
                        )

                    if beat_index in (0, 2):
                        add_kick(hit, kick_vol)

                    if beat_index in (1, 3):
                        add_snare(hit, snare_vol)

                    add_hat(hit + beat * 0.5, hat_vol)

        # Fade the end smoothly.
        fade_len = min(int(1.5 * sr), count)

        if fade_len > 0:
            fade = np.linspace(
                1.0, 0.0, fade_len, dtype=np.float32
            )

            for stem in (chords, bass, melody, percussion):
                stem[-fade_len:] *= fade

        stems = {
            "chords": chords,
            "bass": bass,
            "melody": melody,
            "percussion": percussion,
        }

        # Save each stem as a WAV file.
        paths = {}

        for stem_name, audio in stems.items():
            peak = float(np.max(np.abs(audio)))

            if peak > 0.8:
                audio = audio * (0.8 / peak)

            path = output_dir / f"{stem_name}.wav"
            sf.write(path, audio, sr, subtype="PCM_16")
            paths[stem_name] = path

        return paths
