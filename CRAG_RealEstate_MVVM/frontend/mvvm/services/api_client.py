from __future__ import annotations

import os
import requests
from typing import Any


class ApiClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout_s: int = 30):
        self.base_url = (base_url or os.getenv("API_BASE_URL", "http://localhost:8000")).rstrip("/")
        self.token = token
        self.timeout_s = timeout_s

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get(self, path: str) -> Any:
        r = requests.get(self.base_url + path, headers=self._headers(), timeout=self.timeout_s)
        self._raise(r)
        return r.json()

    def post(self, path: str, payload: dict) -> Any:
        r = requests.post(self.base_url + path, json=payload, headers=self._headers(), timeout=self.timeout_s)
        self._raise(r)
        return r.json()

    def put(self, path: str, payload: dict) -> Any:
        r = requests.put(self.base_url + path, json=payload, headers=self._headers(), timeout=self.timeout_s)
        self._raise(r)
        return r.json()

    def delete(self, path: str) -> Any:
        r = requests.delete(self.base_url + path, headers=self._headers(), timeout=self.timeout_s)
        self._raise(r)
        return r.json() if r.text else {"status": "ok"}

    @staticmethod
    def _raise(r: requests.Response) -> None:
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail")
            except Exception:
                detail = r.text
            raise RuntimeError(f"{r.status_code}: {detail}")
