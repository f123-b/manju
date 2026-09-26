from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    provider = "base"
    kind = "unknown"

    @abstractmethod
    async def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def status(self, provider_task_id: str, status_url: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    async def cancel(self, provider_task_id: str, cancel_url: str | None = None) -> dict[str, Any]:
        return {"status": "Cancelled", "provider_task_id": provider_task_id}

    async def estimate_cost(self, payload: dict[str, Any]) -> float:
        return 0.73

    async def get_result(self, provider_task_id: str, status_url: str | None = None) -> dict[str, Any]:
        return await self.status(provider_task_id, status_url)
