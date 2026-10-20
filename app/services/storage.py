from pathlib import Path
from app.config import settings

def local_job_dir(job_id: str) -> Path:
    base = Path(settings.storage_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / job_id

def public_file_url(job_id: str, filename: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/api/v1/jobs/{job_id}/files/{filename}"
