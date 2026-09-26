from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from typing import Any

from .base import BaseProvider


class HttpProvider(BaseProvider):
    """Generic async adapter for a configured external provider."""

    def __init__(self, kind: str, url: str, provider_name: str, model: str, api_key: str | None) -> None:
        self.kind = kind
        self.url = url
        self.provider = provider_name
        self.model = model
        self.api_key = api_key
        self.auth_header = os.environ.get("SHORT_DRAMA_PROVIDER_AUTH_HEADER", "Authorization")
        self.auth_prefix = os.environ.get("SHORT_DRAMA_PROVIDER_AUTH_PREFIX", "Bearer")

    def _request(self, url: str, payload: dict[str, Any] | None = None, method: str | None = None) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers[self.auth_header] = f"{self.auth_prefix} {self.api_key}".strip()
        request = urllib.request.Request(url, data=json.dumps(payload or {}).encode("utf-8") if payload is not None else None, headers=headers, method=method or ("POST" if payload is not None else "GET"))
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))

    async def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._request, self.url, {**payload, "model": self.model, "type": self.kind})

    async def status(self, provider_task_id: str, status_url: str | None = None) -> dict[str, Any]:
        return await asyncio.to_thread(self._request, status_url or provider_task_id)

    async def cancel(self, provider_task_id: str, cancel_url: str | None = None) -> dict[str, Any]:
        return await asyncio.to_thread(self._request, cancel_url or provider_task_id, {"status": "cancelled"}, "POST")

    async def estimate_cost(self, payload: dict[str, Any]) -> float:
        return float(os.environ.get("SHORT_DRAMA_ESTIMATED_COST", "0.73"))
