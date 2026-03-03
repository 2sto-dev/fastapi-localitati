"""
Client-side TokenManager for FastAPI API using refresh tokens only.
- Stores refresh token in client .env (CLIENT_REFRESH_TOKEN)
- Obtains access tokens via POST /token/refresh
- Caches access token in memory with expiry and auto-refresh on 401/near-expiry

No username/password stored in client.
"""
from __future__ import annotations

import base64
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

import requests


ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")


def load_client_env(env_path: str = ENV_PATH) -> None:
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def save_refresh_token(refresh_token: str, env_path: str = ENV_PATH) -> None:
    # update or append CLIENT_REFRESH_TOKEN in env file
    lines = []
    found = False
    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("CLIENT_REFRESH_TOKEN="):
                    lines.append(f"CLIENT_REFRESH_TOKEN={refresh_token}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"CLIENT_REFRESH_TOKEN={refresh_token}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _jwt_exp(token: str) -> Optional[int]:
    # decode JWT payload without verifying signature to extract exp
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        # add padding
        padding = '=' * (-len(payload_b64) % 4)
        payload = base64.urlsafe_b64decode(payload_b64 + padding)
        data = json.loads(payload)
        return int(data.get("exp")) if isinstance(data.get("exp"), (int, float)) else None
    except Exception:
        return None


@dataclass
class TokenCache:
    access_token: Optional[str] = None
    access_exp: Optional[int] = None  # epoch seconds
    refresh_token: Optional[str] = None


class TokenManager:
    def __init__(self, base_url: Optional[str] = None, refresh_token: Optional[str] = None, env_path: str = ENV_PATH):
        load_client_env(env_path)
        self.base_url = (base_url or os.environ.get("API_BASE_URL") or "http://127.0.0.1:8080").rstrip("/")
        self.env_path = env_path
        self._lock = threading.RLock()
        self._cache = TokenCache(refresh_token=(refresh_token or os.environ.get("CLIENT_REFRESH_TOKEN")))
        if not self._cache.refresh_token:
            raise RuntimeError("CLIENT_REFRESH_TOKEN missing. Run bootstrap_refresh_token.py to obtain one.")

    def _refresh(self) -> None:
        url = f"{self.base_url}/token/refresh"
        body = {"refresh_token": self._cache.refresh_token}
        r = requests.post(url, json=body, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Failed to refresh token: {r.status_code} {r.text}")
        data = r.json()
        access = data.get("access_token")
        refresh = data.get("refresh_token")
        if not access or not refresh:
            raise RuntimeError("Invalid refresh response")
        self._cache.access_token = access
        self._cache.access_exp = _jwt_exp(access)
        # rotate refresh in cache and persist to .env
        self._cache.refresh_token = refresh
        save_refresh_token(refresh, self.env_path)

    def get_access_token(self) -> str:
        with self._lock:
            now = int(time.time())
            # If token missing or expiring in <30s, refresh
            if not self._cache.access_token or not self._cache.access_exp or self._cache.access_exp - now < 30:
                self._refresh()
            return self._cache.access_token  # type: ignore[return-value]

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {}) or {}
        # first attempt
        token = self.get_access_token()
        headers["Authorization"] = f"Bearer {token}"
        r = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        if r.status_code in (401, 403):
            # try refresh and retry once
            with self._lock:
                self._refresh()
                headers["Authorization"] = f"Bearer {self._cache.access_token}"
                r = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        return r
