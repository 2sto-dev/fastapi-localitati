"""
Thin API client using TokenManager.
"""
from __future__ import annotations

from typing import Any, List

from .token_manager import TokenManager


def get_judete(tm: TokenManager) -> List[dict]:
    r = tm.request("GET", "/api/judete")
    r.raise_for_status()
    return r.json()


def get_localitati(tm: TokenManager, cod_judet: int) -> List[dict]:
    r = tm.request("GET", f"/api/localitati/{cod_judet}")
    r.raise_for_status()
    return r.json()


def get_strazi(tm: TokenManager, cod_judet: int, cod_localitate: int) -> List[dict]:
    r = tm.request("GET", f"/api/strazi/{cod_judet}/{cod_localitate}")
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    # Example usage
    tm = TokenManager()
    print("Judete:", len(get_judete(tm)))
