# IncuBrix AI Background Music Engine

A FastAPI prototype that generates procedural instrumental music with separate synthesized stems for chords, bass, melody, and percussion. It supports WAV/MP3 output, job tracking, audio mixing, and Docker deployment.

**Current limitation:** The active procedural provider is not a trained AI music-generation model. The stems are synthesized audio, and commercial-use rights have not been independently verified.

## Features

- FastAPI music-generation job endpoint
- Procedural instrumental synthesis with four separate stems
- Prompt-keyword-based mood and tempo selection
- WAV and MP3 export paths
- Job status, file downloads, and idempotency support
- Health and readiness endpoints
- Docker image and Docker Compose deployment
- Automated tests for implemented functionality

## Requirements

- Python version compatible with `requirements.txt`
- Docker Desktop for containerized deployment
- FFmpeg available for audio conversion and readiness checks

## Run locally on Windows

Open PowerShell in the project folder.

1. Create and activate the virtual environment if needed:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Ensure `.env` contains the appropriate local settings. Do not commit secrets.

4. Start the API:

   ```powershell
   uvicorn app.main:app --reload
   ```

5. Open the API documentation at http://127.0.0.1:8000/docs.

6. Run the tests in a separate terminal:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests -q
   ```

## Run with Docker

Build the image from the project directory:

```powershell
docker build --network=host -t incubrix-api .
```

Start the service:

```powershell
docker compose up -d
```

Check the container status:

```powershell
docker compose ps
```

Open http://localhost:8000/docs to explore the API and http://localhost:8000/health to check service health.

Stop the service:

```powershell
docker compose down
```

Rebuild the image after changing application code or dependencies, then run `docker compose up -d` again.

## API endpoints

- `GET /health` — service health
- `GET /ready` — readiness check
- `POST /api/v1/music/jobs` — submit a music-generation job
- `GET /api/v1/jobs/{job_id}` — retrieve job status and result
- `GET /api/v1/jobs/{job_id}/final-video` — final-video endpoint
- `GET /api/v1/jobs/{job_id}/files/{file_path}` — download a generated file

For exact request and response schemas, refer to `openapi.yaml` and the running API documentation.

## Batch runner

With the API running and the required dependencies installed:

```powershell
python scripts/batch_runner.py test_inputs --out test_outputs
```

Check the script's arguments and the contents of `test_inputs` before running a full batch.

## Configuration

The application reads settings from environment variables, including:

- `APP_NAME`
- `MUSIC_PROVIDER`
- `STORAGE_DIR`
- `MAX_DURATION_S`
- `DEFAULT_SAMPLE_RATE`
- `DEFAULT_TARGET_LUFS`
- `PUBLIC_BASE_URL`

The current Docker configuration uses the procedural provider and local filesystem storage. Persistent distributed job execution and production-grade object storage require further implementation and verification.

## Testing and evidence

Save test logs, generated audio, manifests, measurements, and demonstration evidence. Report actual test results and clearly mark incomplete assessment requirements as Partial or Not Implemented.

## Known limitations and future work

- Integrate and verify a suitable licensed music-generation system if required.
- Validate exact-duration output and musical endings across a range of prompts.
- Measure loudness and true peak on final outputs.
- Verify that individual stems reconstruct the mix correctly.
- Evaluate audio quality and prompt matching.
- Implement and test advanced composition, narration ducking, seamless looping, and single-stem regeneration.
- Verify persistent job processing, storage, structured errors, logging, and deployment requirements.
- Document music-source licences and permitted commercial uses before making commercial-use claims.

See `REPORT.md`, `SOURCES.md`, `AI_USE.md`, and `openapi.yaml` for additional project documentation.
