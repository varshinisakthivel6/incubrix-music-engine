
from pathlib import Path
import json
import subprocess
import tempfile
import shutil

import numpy as np
import soundfile as sf


def get_ffmpeg_exe():
    """Find FFmpeg on Windows or Linux."""
    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg:
        return ffmpeg

    raise FileNotFoundError(
        "FFmpeg executable not found. "
        "Please install FFmpeg and add it to PATH."
    )


def read_mono(path: Path):
    """Read audio as mono float32."""
    audio, sr = sf.read(
        path,
        dtype="float32",
        always_2d=False,
    )
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    return audio, sr


def read_audio(path: Path):
    """Read audio as a 2D float32 array."""
    audio, sr = sf.read(
        path,
        dtype="float32",
        always_2d=True,
    )
    return audio, sr


def write_audio(path: Path, audio: np.ndarray, sr: int):
    """Write a 24-bit PCM WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, sr, subtype="PCM_24")


def align_audio(
    source: Path,
    target_n: int,
    sample_rate: int,
    work_dir: Path,
):
    """Resample audio if necessary, then align it to target_n samples."""
    audio, sr = read_audio(source)

    if sr != sample_rate:
        work_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=work_dir) as temp_dir:
            temp_path = Path(temp_dir) / "resampled.wav"

            subprocess.run(
                [
                    get_ffmpeg_exe(),
                    "-y",
                    "-loglevel", "error",
                    "-i", str(source),
                    "-ar", str(sample_rate),
                    "-c:a", "pcm_f32le",
                    str(temp_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            audio, sr = read_audio(temp_path)

    if sr != sample_rate:
        raise ValueError(
            f"Expected {sample_rate} Hz, received {sr} Hz."
        )

    if len(audio) < target_n:
        audio = np.pad(
            audio,
            ((0, target_n - len(audio)), (0, 0)),
        )
    else:
        audio = audio[:target_n]

    return audio.astype(np.float32, copy=False)


def apply_fades(audio: np.ndarray, sample_rate: int):
    """Apply short start/end fades."""
    audio = audio.copy()
    n = len(audio)
    fade_n = min(int(0.15 * sample_rate), n // 2)

    if fade_n > 0:
        audio[:fade_n] *= np.linspace(
            0, 1, fade_n, dtype=np.float32
        )[:, None]

        audio[-fade_n:] *= np.linspace(
            1, 0, fade_n, dtype=np.float32
        )[:, None]

    return audio


def _measure_lufs(audio: np.ndarray, sample_rate: int):
    """Return integrated LUFS when pyloudnorm can measure it."""
    try:
        import pyloudnorm as pyln

        mono = audio.mean(axis=1) if audio.ndim == 2 else audio
        value = float(pyln.Meter(sample_rate).integrated_loudness(mono))

        if np.isfinite(value):
            return value

    except (ImportError, ValueError, ZeroDivisionError):
        pass

    return None


def normalize_audio(
    audio: np.ndarray,
    sample_rate: int,
    target_lufs: float,
):
    """
    Apply common gain while respecting a -1 dBFS sample-peak ceiling.
    This is linear gain control, not a limiter.
    """
    audio = audio.astype(np.float32, copy=False)

    if audio.size == 0:
        return audio.copy(), 1.0, None

    peak = float(np.max(np.abs(audio)))

    if peak <= 1e-8:
        return audio.copy(), 1.0, _measure_lufs(audio, sample_rate)

    measured_lufs = _measure_lufs(audio, sample_rate)
    gain = 1.0

    if measured_lufs is not None:
        gain = 10 ** ((target_lufs - measured_lufs) / 20.0)

    peak_ceiling = 10 ** (-1.0 / 20.0)
    gain = min(gain, peak_ceiling / peak)

    result = (audio * gain).astype(np.float32)
    return result, float(gain), measured_lufs


def export_mp3(mix_wav: Path, mp3_path: Path):
    """Export the WAV mix to MP3."""
    mp3_path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            get_ffmpeg_exe(),
            "-y",
            "-loglevel", "error",
            "-i", str(mix_wav),
            "-codec:a", "libmp3lame",
            "-q:a", "2",
            str(mp3_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def export_mix(
    audio: np.ndarray,
    out_dir: Path,
    sample_rate: int,
    target_lufs: float,
    formats: list[str],
):
    """Export a single mix."""
    out_dir.mkdir(parents=True, exist_ok=True)

    audio = apply_fades(audio, sample_rate)
    audio, gain, _ = normalize_audio(
        audio, sample_rate, target_lufs
    )

    mix_wav = out_dir / "mix.wav"
    write_audio(mix_wav, audio, sample_rate)

    result = {
        "mix_wav": mix_wav,
        "stems": {},
        "stem_gains": {},
        "mix": audio,
        "audio_source_type": "single_mix",
        "mix_gain": gain,
    }

    if "mp3" in formats:
        mp3_path = out_dir / "mix.mp3"
        export_mp3(mix_wav, mp3_path)
        result["mix_mp3"] = mp3_path

    return result


def process_single_mix(
    source: Path,
    out_dir: Path,
    duration_s: float,
    sample_rate: int,
    target_lufs: float,
    formats: list[str],
):
    """Align and export a generated full mix."""
    target_n = round(duration_s * sample_rate)

    if target_n <= 0:
        raise ValueError("duration_s must be greater than zero.")

    audio = align_audio(
        source,
        target_n,
        sample_rate,
        out_dir / ".work",
    )

    result = export_mix(
        audio,
        out_dir,
        sample_rate,
        target_lufs,
        formats,
    )

    result["stems"] = {}
    result["stem_gains"] = {}
    return result


def process_stems(
    stem_paths: dict[str, Path],
    out_dir: Path,
    duration_s: float,
    sample_rate: int,
    target_lufs: float,
    formats: list[str],
):
    """Align stems and apply a common gain."""
    if not stem_paths:
        raise ValueError("No audio stems were provided.")

    if "mix" in stem_paths:
        raise ValueError(
            "A full mix cannot be treated as an instrument stem."
        )

    target_n = round(duration_s * sample_rate)
    if target_n <= 0:
        raise ValueError("duration_s must be greater than zero.")

    out_dir.mkdir(parents=True, exist_ok=True)
    stems_dir = out_dir / "stems"
    stems_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / ".work"

    aligned = {}

    for name, source in stem_paths.items():
        audio = align_audio(
            source,
            target_n,
            sample_rate,
            work_dir,
        )

        if audio.shape[1] > 1:
            audio = audio.mean(axis=1, keepdims=True)

        aligned[name] = apply_fades(audio, sample_rate)

    mix_before_gain = np.sum(
        np.stack(list(aligned.values()), axis=0),
        axis=0,
        dtype=np.float32,
    )

    _, gain, _ = normalize_audio(
        mix_before_gain,
        sample_rate,
        target_lufs,
    )

    processed_stems = {}

    for name, audio in aligned.items():
        processed = (audio * gain).astype(np.float32)
        processed_stems[name] = processed

        write_audio(
            stems_dir / f"{name}.wav",
            processed,
            sample_rate,
        )

    mix = np.sum(
        np.stack(list(processed_stems.values()), axis=0),
        axis=0,
        dtype=np.float32,
    )

    mix_wav = out_dir / "mix.wav"
    write_audio(mix_wav, mix, sample_rate)

    result = {
        "mix_wav": mix_wav,
        "stems": {
            name: stems_dir / f"{name}.wav"
            for name in processed_stems
        },
        "stem_gains": {
            name: float(gain) for name in processed_stems
        },
        "mix": mix,
        "audio_source_type": "separate_stems",
    }

    if "mp3" in formats:
        mp3_path = out_dir / "mix.mp3"
        export_mp3(mix_wav, mp3_path)
        result["mix_mp3"] = mp3_path

    return result


def audio_metrics(mix_path: Path, target_lufs: float):
    """Measure duration, sample peak, integrated LUFS and true peak."""
    audio, sr = read_mono(mix_path)

    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    peak_dbfs = 20 * np.log10(max(peak, 1e-12))
    duration_s = len(audio) / sr

    lufs = None
    true_peak_dbtp = None

    command = [
        get_ffmpeg_exe(),
        "-hide_banner",
        "-nostats",
        "-i", str(mix_path),
        "-af",
        (
            f"loudnorm=I={target_lufs}:"
            "TP=-1.0:LRA=11:print_format=json"
        ),
        "-f", "null",
        "-",
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        if completed.returncode == 0:
            stderr = completed.stderr
            start = stderr.rfind("{")
            end = stderr.rfind("}")

            if start >= 0 and end > start:
                data = json.loads(stderr[start:end + 1])

                measured_lufs = float(data["input_i"])
                measured_tp = float(data["input_tp"])

                if np.isfinite(measured_lufs):
                    lufs = measured_lufs

                if np.isfinite(measured_tp):
                    true_peak_dbtp = measured_tp

    except (
        FileNotFoundError,
        subprocess.SubprocessError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ):
        pass

    return {
        "sample_rate_hz": sr,
        "duration_s": duration_s,
        "sample_peak_dbfs": peak_dbfs,
        "integrated_lufs": lufs,
        "target_lufs": target_lufs,
        "loudness_target_verified": (
            lufs is not None
            and abs(lufs - target_lufs) <= 1.0
        ),
        "true_peak_dbtp": true_peak_dbtp,
        "true_peak_verified": (
            true_peak_dbtp is not None
            and true_peak_dbtp <= -1.0
        ),
    }
