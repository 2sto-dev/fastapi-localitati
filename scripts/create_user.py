"""
Dev-only helper to create an initial user with a hashed password.
Usage (Windows PowerShell):
  python -m scripts.create_user --username admin --password "Str0ngP@ss!"

NEVER use this in production automation without secure input handling.
"""
from __future__ import annotations

import argparse
import asyncio

from fastapi_localitati.database import async_session_maker
from fastapi_localitati import models
from fastapi_localitati.auth import get_password_hash
from sqlalchemy import select


async def create_user(username: str, password: str, is_active: bool = True) -> None:
    async with async_session_maker() as session:
        res = await session.execute(select(models.User).where(models.User.username == username))
        if res.scalars().first():
            print(f"User '{username}' already exists")
            return
        user = models.User(username=username, hashed_password=get_password_hash(password), is_active=is_active)
        session.add(user)
        await session.commit()
        print(f"✅ Created user '{username}'")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--inactive", action="store_true")
    args = parser.parse_args()
    asyncio.run(create_user(args.username, args.password, not args.inactive))


if __name__ == "__main__":
    main()
