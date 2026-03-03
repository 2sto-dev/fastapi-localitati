"""
Minimal smoke test against a running local server.
Requires the app to be running, e.g.:
  uvicorn fastapi_localitati.main:app --reload --host 127.0.0.1 --port 8080

Then run:
  python -m scripts.smoke_test --base http://127.0.0.1:8080 --username admin --password admin
"""
from __future__ import annotations

import argparse
import requests


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://127.0.0.1:8080")
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    args = p.parse_args()

    base = args.base.rstrip("/")
    s = requests.Session()

    # Login
    r = s.post(
        f"{base}/token",
        data={"username": args.username, "password": args.password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    r.raise_for_status()
    data = r.json()
    access = data["access_token"]
    refresh = data.get("refresh_token")
    print("✅ Login OK")

    # Call protected endpoint
    r2 = s.get(f"{base}/api/judete", headers={"Authorization": f"Bearer {access}"})
    r2.raise_for_status()
    print("✅ Protected endpoint OK, items:", len(r2.json()))

    # Refresh
    r3 = s.post(f"{base}/token/refresh", json={"refresh_token": refresh})
    r3.raise_for_status()
    data2 = r3.json()
    access2 = data2["access_token"]
    print("✅ Refresh OK")

    # Call again with rotated token
    r4 = s.get(f"{base}/api/judete", headers={"Authorization": f"Bearer {access2}"})
    r4.raise_for_status()
    print("✅ Protected endpoint OK after refresh")


if __name__ == "__main__":
    main()
