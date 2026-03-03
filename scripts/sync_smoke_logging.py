"""
Smoke check for sync loop logging correctness and duplication.
- Runs sync for a small subset of counties (configurable).
- Writes to a unique log file via ANAF_SYNC_LOG_FILE env var.
- Asserts each county start and commit lines match and appear once.

Usage (PowerShell):
  $env:ANAF_SYNC_LOG_FILE="logs\\smoke_sync_$(Get-Date -Format yyyyMMdd_HHmmss_ffff)_$PID.log"; \
  python -m scripts.sync_smoke_logging --only 11,12
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
from typing import List

from fastapi_localitati.database import async_session_maker
from fastapi_localitati.scripts.sync_anaf import sync_all


def parse_only(arg: str | None) -> List[int] | None:
    if not arg:
        return None
    out: List[int] = []
    for p in arg.split(","):
        p = p.strip()
        if p.isdigit():
            out.append(int(p))
    return out or None


async def run(only: List[int] | None) -> str:
    logfile = os.environ.get("ANAF_SYNC_LOG_FILE")
    if not logfile:
        raise SystemExit("ANAF_SYNC_LOG_FILE must be set to a unique path for this smoke test")

    async with async_session_maker() as session:
        await sync_all(session, only_judete=only)

    return logfile


def assert_logs(logfile: str) -> None:
    with open(logfile, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]

    start_re = re.compile(r"Județ: (?P<name>.+?) \(cod (?P<code>\d+)\)")
    commit_re = re.compile(r"Commit reușit pentru (?P<name>.+?) ")

    starts: List[tuple[str, str]] = []  # (code, name)
    commits: List[str] = []  # names

    for ln in lines:
        m1 = start_re.search(ln)
        if m1:
            starts.append((m1.group("code"), m1.group("name")))
            continue
        m2 = commit_re.search(ln)
        if m2:
            commits.append(m2.group("name"))

    if not starts:
        raise AssertionError("No county start lines found in logs")

    # Assert each start has exactly one matching commit by name
    for code, name in starts:
        if commits.count(name) != 1:
            raise AssertionError(f"County {name} (cod {code}) commit count = {commits.count(name)}; expected 1")

    # Optionally ensure no duplicates in starts for same code
    seen_codes: set[str] = set()
    for code, name in starts:
        if code in seen_codes:
            raise AssertionError(f"Duplicate processing detected for code {code} ({name})")
        seen_codes.add(code)

    print("✅ Smoke assertions passed: unique counties and matching commit logs.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--only", help="Comma-separated county codes to sync (e.g., 11,12)")
    args = p.parse_args()
    only = parse_only(args.only)

    logfile = asyncio.run(run(only))
    assert_logs(logfile)


if __name__ == "__main__":
    main()
