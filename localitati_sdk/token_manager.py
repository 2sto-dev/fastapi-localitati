from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass
from typing import Optional, Callable, Any, Dict

import requests

from .errors import AuthError


def _jwt_exp(token: str) -> Optional[int]:
    """Decode JWT payload (no signature verify) to extract exp."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        padding = "=" * (-len(payload_b64) % 4)
        payload = base64.urlsafe_b64decode(payload_b64 + padding)
        data = json.loads(payload)
        exp = data.get("exp")
        return int(exp) if isinstance(exp, (int, float)) else None
    except Exception:
        return None


@dataclass
class TokenCache:
    access_token: Optional[str] = None
    access_exp: Optional[int] = None
    refresh_token: Optional[str] = None


class TokenManager:
    """
    Production TokenManager:
    - does NOT read/write .env
    - needs base_url + refresh_token
    - refresh rotation supported via callback
    """

    def __init__(
        self,
        *,
        base_url: str,
        refresh_token: str,
        timeout: float = 30.0,
        refresh_skew_seconds: int = 30,
        session: Optional[requests.Session] = None,
        on_refresh_token_rotated: Optional[Callable[[str], None]] = None,
    ):
        if not base_url:
            raise ValueError("base_url is required")
        if not refresh_token:
            raise ValueError("refresh_token is required")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.refresh_skew_seconds = refresh_skew_seconds
        self._lock = threading.RLock()
        self._cache = TokenCache(refresh_token=refresh_token)
        self._session = session or requests.Session()
        self._on_rotated = on_refresh_token_rotated

    def _refresh(self) -> None:
        url = f"{self.base_url}/token/refresh"
        body = {"refresh_token": self._cache.refresh_token}

        r = self._session.post(url, json=body, timeout=self.timeout)
        if r.status_code != 200:
            raise AuthError(f"Failed to refresh token: {r.status_code} {r.text}")

        data = r.json()
        access = data.get("access_token")
        refresh = data.get("refresh_token")
        if not access or not refresh:
            raise AuthError(
                "Invalid refresh response (missing access_token/refresh_token)"
            )

        self._cache.access_token = access
        self._cache.access_exp = _jwt_exp(access)
        self._cache.refresh_token = refresh

        if self._on_rotated:
            self._on_rotated(refresh)

    def get_access_token(self) -> str:
        with self._lock:
            now = int(time.time())
            if (
                not self._cache.access_token
                or not self._cache.access_exp
                or (self._cache.access_exp - now) < self.refresh_skew_seconds
            ):
                self._refresh()
            return self._cache.access_token  # type: ignore[return-value]

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        headers: Dict[str, Any] = dict(kwargs.pop("headers", {}) or {})

        token = self.get_access_token()
        headers["Authorization"] = f"Bearer {token}"

        r = self._session.request(
            method, url, headers=headers, timeout=self.timeout, **kwargs
        )
        if r.status_code in (401, 403):
            with self._lock:
                self._refresh()
                headers["Authorization"] = f"Bearer {self._cache.access_token}"
                r = self._session.request(
                    method, url, headers=headers, timeout=self.timeout, **kwargs
                )

        return r
