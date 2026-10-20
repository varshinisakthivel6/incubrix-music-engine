"""Run JSON requests against the API. Usage: python scripts/batch_runner.py test_inputs --out test_outputs"""
import argparse, json, time
from pathlib import Path
import requests

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="JSON file or directory containing JSON request files")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--out", default="test_outputs")
    args = parser.parse_args()
    src = Path(args.input)
    paths = [src] if src.is_file() else sorted(src.glob("*.json"))
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    summary = []
    for path in paths:
        req = json.loads(path.read_text(encoding="utf-8"))
        key = f"batch-{path.stem}"
        resp = requests.post(f"{args.base_url}/api/v1/music/jobs", json=req,
                             headers={"Idempotency-Key": key}, timeout=30)
        record = {"input": str(path), "submit_status": resp.status_code, "response": resp.json()}
        if resp.status_code == 202:
            job_id = resp.json()["job_id"]
            for _ in range(600):
                status = requests.get(f"{args.base_url}/api/v1/jobs/{job_id}", timeout=15).json()
                if status["status"] in ("succeeded", "failed"):
                    record["final"] = status
                    break
                time.sleep(1)
        (out / f"{path.stem}_result.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        summary.append(record)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Finished {len(paths)} request(s). Results: {out.resolve()}")

if __name__ == "__main__":
    main()
