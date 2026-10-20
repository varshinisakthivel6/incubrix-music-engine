
"""Optional manual Soundverse API test.

Run explicitly only when an API key and credits are available.
This file must not run automatically during pytest collection.
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv


def main():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(env_path)

    api_key = os.getenv("SOUNDVERSE_API_KEY")
    if not api_key:
        print("Soundverse test skipped: no API key configured.")
        return

    response = requests.post(
        "https://apiv2.soundverse.ai/v7/generate/music",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "prompt": "Warm lo-fi instrumental background music",
            "parameters": {"versions": 1},
        },
        timeout=60,
    )

    print("HTTP status:", response.status_code)
    print(response.text)
    response.raise_for_status()


if __name__ == "__main__":
    main()
