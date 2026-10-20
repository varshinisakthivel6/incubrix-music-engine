import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "IncuBrix AI Background Music Engine")
    storage_dir: str = os.getenv("STORAGE_DIR", "/app/storage")
    provider: str = os.getenv("MUSIC_PROVIDER", "stable_audio")
    max_duration_s: float = float(os.getenv("MAX_DURATION_S", "300"))
    default_sample_rate: int = int(os.getenv("DEFAULT_SAMPLE_RATE", "48000"))
    default_target_lufs: float = float(os.getenv("DEFAULT_TARGET_LUFS", "-16"))
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "minio:9000")
    minio_access_key: str = os.getenv("MINIO_ROOT_USER", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "music-results")

settings = Settings()
