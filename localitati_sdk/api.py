from __future__ import annotations

from typing import Any, List

from .errors import APIError
from .token_manager import TokenManager


def _json_or_error(resp):
    if resp.status_code >= 400:
        raise APIError(resp.status_code, resp.text)
    return resp.json()


def get_judete(tm: TokenManager) -> List[Any]:
    r = tm.request("GET", "/api/judete")
    return _json_or_error(r)


def get_localitati(tm: TokenManager, cod_judet: int) -> List[Any]:
    r = tm.request("GET", f"/api/localitati/{cod_judet}")
    return _json_or_error(r)


def get_strazi(tm: TokenManager, cod_judet: int, cod_localitate: int) -> List[Any]:
    r = tm.request("GET", f"/api/strazi/{cod_judet}/{cod_localitate}")
    return _json_or_error(r)
