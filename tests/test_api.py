from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    assert client.get("/health").status_code == 200

def test_ready():
    assert client.get("/ready").json()["status"] == "ready"

def test_invalid_duration():
    response = client.post("/api/v1/music/jobs", json={"prompt": "calm", "duration_s": 2})
    assert response.status_code == 422

def test_create_job_and_idempotency():
    payload = {"prompt": "gentle instrumental test", "duration_s": 5,
               "output": {"sample_rate": 48000, "target_lufs": -16, "formats": ["wav"]}}
    r1 = client.post("/api/v1/music/jobs", json=payload, headers={"Idempotency-Key": "test-key-1"})
    assert r1.status_code == 202
    r2 = client.post("/api/v1/music/jobs", json=payload, headers={"Idempotency-Key": "test-key-1"})
    assert r2.status_code == 200
    assert r1.json()["job_id"] == r2.json()["job_id"]
