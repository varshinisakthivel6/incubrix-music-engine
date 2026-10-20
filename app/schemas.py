from typing import Optional, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

class Section(BaseModel):
    start_s: float = Field(ge=0)
    mood: str = Field(min_length=1, max_length=200)

class OutputOptions(BaseModel):
    sample_rate: int = Field(default=48000, ge=8000, le=192000)
    target_lufs: float = Field(default=-16.0, ge=-36, le=-5)
    formats: list[Literal["wav", "mp3"]] = Field(default_factory=lambda: ["wav", "mp3"])

class MusicJobRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    duration_s: float = Field(ge=5, le=300)
    sections: list[Section] = Field(default_factory=list)
    tempo_bpm: Optional[float] = Field(default=None, ge=30, le=240)
    key: Optional[str] = None
    loopable: bool = False
    narration_url: Optional[HttpUrl] = None
    seed: Optional[int] = 42
    output: OutputOptions = Field(default_factory=OutputOptions)

    @field_validator("prompt")
    @classmethod
    def strip_prompt(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("prompt must not be blank")
        return value

class JobResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    status_url: str
