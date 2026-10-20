import logging
import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Header,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.schemas import MusicJobRequest
from app.services.job_service import JOBS, create_job, run_job
from app.services.storage import local_job_dir


logger = logging.getLogger(__name__)

app = FastAPI(
    title="IncuBrix AI Background Music Engine",
    version="1.0.0",
)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "Frontend"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Local development only
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500 MB


def error_response(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def find_ffmpeg() -> str:
    executable = shutil.which("ffmpeg")

    if not executable:
        raise HTTPException(
            status_code=500,
            detail=error_response(
                "FFMPEG_NOT_FOUND",
                "FFmpeg is not installed or is not on PATH.",
            ),
        )

    return executable


@app.get("/")
def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    ffmpeg_available = shutil.which("ffmpeg") is not None
    return {
        "status": "ready" if ffmpeg_available else "degraded",
        "ffmpeg_available": ffmpeg_available,
    }


@app.post("/api/v1/music/jobs", status_code=202)
def create_music_job(
    request: MusicJobRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
):
    try:
        correlation_id = str(uuid.uuid4())
        payload = request.model_dump(mode="json")
        job, created = create_job(
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        job_id = job["job_id"]
        if created:
            background_tasks.add_task(run_job, job_id)
        return JSONResponse(
            status_code=202 if created else 200,
            content={
                "job_id": job_id,
                "status": job["status"],
                "status_url": f"/api/v1/jobs/{job_id}",
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not create music-generation job")
        raise HTTPException(
            status_code=500,
            detail=error_response("JOB_CREATION_FAILED", str(exc)),
        ) from exc


@app.get("/api/v1/jobs/{job_id}")
def get_job_status(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=error_response("JOB_NOT_FOUND", "The requested job was not found."),
        )
    return job


@app.post("/api/v1/jobs/{job_id}/final-video")
async def create_final_video(
    job_id: str,
    video: UploadFile = File(...),
):
    filename = Path(video.filename or "").name
    extension = Path(filename).suffix.lower()
    if extension not in VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "UNSUPPORTED_VIDEO_FORMAT",
                "Upload an MP4, MOV, MKV, or WEBM video.",
            ),
        )

    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=error_response("JOB_NOT_FOUND", "The music-generation job was not found."),
        )
    if job.get("status") != "succeeded":
        raise HTTPException(
            status_code=409,
            detail=error_response("MUSIC_NOT_READY", "Wait until music generation has completed."),
        )

    job_dir = Path(local_job_dir(job_id)).resolve()
    result_dir = (job_dir / "result").resolve()
    result_dir.mkdir(parents=True, exist_ok=True)
    music_path = result_dir / "mix.wav"
    if not music_path.is_file():
        music_path = result_dir / "mix.mp3"
    if not music_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=error_response(
                "MUSIC_FILE_NOT_FOUND",
                "The generated mix.wav or mix.mp3 file is missing.",
            ),
        )

    video_path = job_dir / f"uploaded_video_{uuid.uuid4().hex}{extension}"
    output_path = result_dir / "final_video.mp4"
    try:
        size = 0
        with video_path.open("wb") as destination:
            while True:
                chunk = await video.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_VIDEO_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=error_response("VIDEO_TOO_LARGE", "The maximum video size is 500 MB."),
                    )
                destination.write(chunk)

        if size == 0:
            raise HTTPException(
                status_code=400,
                detail=error_response("EMPTY_VIDEO", "The uploaded video is empty."),
            )

        command = [
            find_ffmpeg(),
            "-y",
            "-i", str(video_path),
            "-i", str(music_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-threads", "1",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-af", "apad",
            "-shortest",
            "-movflags", "+faststart",
            str(output_path),
        ]
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if process.returncode != 0 or not output_path.is_file():
            logger.error(
                "FFmpeg merge failed for job %s: %s",
                job_id,
                process.stderr[-3000:],
            )
            raise HTTPException(
                status_code=500,
                detail=error_response(
                    "VIDEO_MERGE_FAILED",
                    "FFmpeg could not combine the video and music.",
                ),
            )

        return {
            "job_id": job_id,
            "status": "succeeded",
            "filename": "final_video.mp4",
            "preview_url": f"/api/v1/jobs/{job_id}/files/final_video.mp4",
            "download_url": f"/api/v1/jobs/{job_id}/files/final_video.mp4",
        }
    except subprocess.TimeoutExpired as exc:
        output_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=504,
            detail=error_response("VIDEO_MERGE_TIMEOUT", "Video processing took too long."),
        ) from exc
    finally:
        await video.close()
        video_path.unlink(missing_ok=True)


@app.get("/api/v1/jobs/{job_id}/files/{file_path:path}")
def download_job_file(job_id: str, file_path: str):
    job_dir = Path(local_job_dir(job_id)).resolve()
    result_dir = (job_dir / "result").resolve()
    requested_path = (result_dir / file_path).resolve()
    if not requested_path.is_relative_to(result_dir):
        raise HTTPException(
            status_code=400,
            detail=error_response("INVALID_FILE_PATH", "The requested file path is invalid."),
        )
    if not requested_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=error_response("FILE_NOT_FOUND", "The requested file was not found."),
        )
    return FileResponse(requested_path)
