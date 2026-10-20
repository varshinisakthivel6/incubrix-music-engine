
import json
import time
import traceback
import hashlib
from uuid import uuid4
from threading import Lock

from app.config import settings
from app.providers.mock_provider import MockProvider
from app.services.storage import local_job_dir, public_file_url
from app.services.audio_pipeline import (
    process_stems,
    process_single_mix,
    audio_metrics,
)

JOBS = {}
IDEMPOTENCY = {}
LOCK = Lock()


def provider_for_job():
    if settings.provider == "mock":
        return MockProvider()

    if settings.provider == "procedural":
        from app.providers.procedural_provider import ProceduralProvider
        return ProceduralProvider()

    if settings.provider == "stable_audio":
        from app.providers.stable_audio_provider import StableAudioProvider
        return StableAudioProvider()

    raise RuntimeError(
        f"Unsupported MUSIC_PROVIDER={settings.provider!r}"
    )


def create_job(
    payload: dict,
    idempotency_key: str | None,
    correlation_id: str,
):
    payload_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()

    with LOCK:
        if idempotency_key and idempotency_key in IDEMPOTENCY:
            old_id, old_hash = IDEMPOTENCY[idempotency_key]

            if old_hash != payload_hash:
                raise ValueError(
                    "IDEMPOTENCY_KEY_PAYLOAD_MISMATCH"
                )

            return JOBS[old_id], False

        job_id = str(uuid4())

        job = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0,
            "created_at": time.time(),
            "correlation_id": correlation_id,
            "request": payload,
            "result": None,
            "error": None,
        }

        JOBS[job_id] = job

        if idempotency_key:
            IDEMPOTENCY[idempotency_key] = (
                job_id,
                payload_hash,
            )

        return job, True


def run_job(job_id: str):
    job = JOBS[job_id]
    req = job["request"]

    job["status"] = "running"
    job["progress"] = 10

    total_start = time.perf_counter()

    try:
        provider = provider_for_job()

        job_dir = local_job_dir(job_id)
        generated_dir = job_dir / "generated"
        output_dir = job_dir / "result"

        opts = req.get("output", {})
        sample_rate = int(
            opts.get("sample_rate", settings.default_sample_rate)
        )
        target_lufs = float(
            opts.get("target_lufs", settings.default_target_lufs)
        )
        duration_s = float(req["duration_s"])
        formats = opts.get("formats", ["wav", "mp3"])

        # 1. Measure music generation time
        generation_start = time.perf_counter()

        generated = provider.generate_stems(
            req["prompt"],
            duration_s,
            sample_rate,
            int(req.get("seed") or uuid4().int % (2**32)),
            req.get("tempo_bpm"),
            generated_dir,
        )

        generation_seconds = round(
            time.perf_counter() - generation_start, 3
        )

        if not generated:
            raise RuntimeError(
                "The music provider returned no audio files."
            )

        job["progress"] = 55

        # 2. Measure mixing, normalization and audio export time
        processing_start = time.perf_counter()

        # A single full mix is not the same as separate instrument stems.
        if set(generated.keys()) == {"mix"}:
            processed = process_single_mix(
                generated["mix"],
                output_dir,
                duration_s,
                sample_rate,
                target_lufs,
                formats,
            )
            audio_source_type = "single_mix"

        else:
            if "mix" in generated:
                raise RuntimeError(
                    "Provider output cannot mix a full track with "
                    "individual stems."
                )

            processed = process_stems(
                generated,
                output_dir,
                duration_s,
                sample_rate,
                target_lufs,
                formats,
            )
            audio_source_type = "separate_stems"

        metrics = audio_metrics(
            processed["mix_wav"],
            target_lufs,
        )

        processing_seconds = round(
            time.perf_counter() - processing_start, 3
        )

        job["progress"] = 85

        result_files = {
            "mix.wav": public_file_url(job_id, "mix.wav")
        }

        if "mix_mp3" in processed:
            result_files["mix.mp3"] = public_file_url(
                job_id, "mix.mp3"
            )

        for name in processed["stems"]:
            result_files[f"stems/{name}.wav"] = public_file_url(
                job_id, f"stems/{name}.wav"
            )

        warnings = []

        if audio_source_type == "single_mix":
            warnings.append(
                "The provider supplied one complete music mix. "
                "Separate instrument stems were not generated."
            )

        if provider.name.startswith("mock"):
            warnings.append(
                "Mock output is synthetic test audio, not "
                "publishable music."
            )

        rights = provider.rights()

        if not rights.get("commercial_use", False):
            warnings.append(
                "Commercial-use rights are not verified. "
                "Check the model and output license before release."
            )

        total_seconds = round(
            time.perf_counter() - total_start, 3
        )

        manifest = {
            "job_id": job_id,
            "ai_generated": getattr(provider, "ai_generated", False),
            "audio_source_type": audio_source_type,
            "prompt": req["prompt"],
            "duration_s_requested": duration_s,
            "duration_s_actual": metrics["duration_s"],
            "tempo_bpm": req.get("tempo_bpm"),
            "key": req.get("key"),
            "sections": req.get("sections", []),
            "seed": req.get("seed"),
            "sample_rate_hz": sample_rate,
            "target_lufs": target_lufs,
            "stem_gains": processed["stem_gains"],
            "provider": {
                "name": provider.name,
                "version": provider.version,
            },
            "rights": rights,
            "audio_metrics": metrics,
            "timings": {
                "generation_seconds": generation_seconds,
                "processing_seconds": processing_seconds,
                "total_seconds": total_seconds,
            },
            "estimated_cost_usd": None,
            "warnings": warnings,
            "loopable_requested": req.get("loopable", False),
            "sections_applied": False,
            "narration_ducking_applied": False,
        }

        output_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = output_dir / "music_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

        result_files["music_manifest.json"] = public_file_url(
            job_id, "music_manifest.json"
        )

        job["result"] = {
            "files": result_files,
            "manifest": manifest,
        }
        job["status"] = "succeeded"
        job["progress"] = 100

    except Exception as exc:
        job["status"] = "failed"
        job["progress"] = 100
        job["error"] = {
            "code": "MUSIC_GENERATION_FAILED",
            "message": str(exc),
            "retryable": True,
            "details": {
                "trace": traceback.format_exc(limit=3)
            },
        }
