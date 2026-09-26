from __future__ import annotations

import asyncio
import os
from typing import Any

from .base import BaseProvider


class MockProvider(BaseProvider):
    provider = "mock"

    def __init__(self, kind: str, model: str | None = None) -> None:
        self.kind = kind
        self.model = model or f"mock-{kind}"

    async def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(float(os.environ.get("SHORT_DRAMA_DEMO_DELAY", "2.2")))
        if self.kind == "image":
            output = "/assets/shot-hero.png" if payload.get("asset_type") == "characters" else "/assets/shot-wide.png"
        else:
            output = "/assets/shot-wide.png" if self.kind == "video" else None
        return {"status": "Success", "provider_task_id": f"mock-{payload.get('task_id', 'task')}", "output_url": output, "cost": await self.estimate_cost(payload)}

    async def status(self, provider_task_id: str, status_url: str | None = None) -> dict[str, Any]:
        return {"status": "Success", "provider_task_id": provider_task_id}

    async def estimate_cost(self, payload: dict[str, Any]) -> float:
        return {"text": 0.02, "image": 0.18, "video": 0.73, "voice": 0.08}.get(self.kind, 0.1)
