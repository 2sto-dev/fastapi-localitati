"""
One-time script to obtain a refresh token using username/password.
After running, copy the refresh token into client_app/.env as CLIENT_REFRESH_TOKEN=...

PowerShell example:
  $env:API_BASE_URL="http://127.0.0.1:8080"; \
  python -m client_app.bootstrap_refresh_token --username admin --password "Str0ngP@ss!"
"""
from __future__ import annotations

import argparse
import os
import requests


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--base", default=None, help="API base URL (default from API_BASE_URL env)")
    args = p.parse_args()

    base = (args.base or os.environ.get("API_BASE_URL") or "http://127.0.0.1:8080").rstrip("/")

    r = requests.post(
        f"{base}/token",
        data={"username": args.username, "password": args.password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if r.status_code != 200:
        raise SystemExit(f"Login failed: {r.status_code} {r.text}")

    data = r.json()
    refresh = data.get("refresh_token")
    access = data.get("access_token")
    if not refresh:
        raise SystemExit("No refresh_token returned")

    print("Access token (short-lived):", access)
    print("Refresh token (store this in client_app/.env as CLIENT_REFRESH_TOKEN=...):")
    print(refresh)


if __name__ == "__main__":
    main()
