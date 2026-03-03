from __future__ import annotations

import argparse
import os
import requests


def main() -> None:
    p = argparse.ArgumentParser(
        description="Obtain refresh token using username/password (one-time bootstrap)."
    )
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    p.add_argument(
        "--base",
        default=None,
        help="API base URL (default from LOCALITATI_API_BASE_URL or API_BASE_URL)",
    )
    p.add_argument(
        "--only-refresh",
        action="store_true",
        help="Print only the refresh token (useful for scripting)",
    )
    args = p.parse_args()

    base = (
        args.base
        or os.environ.get("LOCALITATI_API_BASE_URL")
        or os.environ.get("API_BASE_URL")
        or "http://127.0.0.1:8080"
    ).rstrip("/")

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

    if args.only_refresh:
        print(refresh)
        return

    print("Access token (short-lived):", access)
    print("Refresh token (store securely, e.g. as LOCALITATI_REFRESH_TOKEN env var):")
    print(refresh)


if __name__ == "__main__":
    main()
