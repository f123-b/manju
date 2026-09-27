from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import uuid
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .base import BaseProvider


class RunningHubProvider(BaseProvider):
    """RunningHub workflow adapter using the documented OpenAPI task flow."""

    provider = "RunningHub"

    def __init__(self, base_url: str, api_key: str | None, model: str = "workflow") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.model = model or "workflow"

    def _headers(self, content_type: str | None = "application/json") -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None,
            headers=self._headers(),
            method="POST" if payload is not None else "GET",
        )
        with urlopen(request, timeout=float(os.environ.get("SHORT_DRAMA_RUNNINGHUB_TIMEOUT", "45"))) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _status(value: Any) -> str:
        normalized = str(value or "RUNNING").upper()
        return {"QUEUED": "Queued", "PENDING": "Pending", "RUNNING": "Running", "PROCESSING": "Processing", "SUCCESS": "Success", "FAILED": "Failed", "ERROR": "Failed", "CANCELLED": "Cancelled", "CANCELED": "Cancelled"}.get(normalized, normalized.title())

    def _normalize(self, body: dict[str, Any]) -> dict[str, Any]:
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        results = body.get("results") if isinstance(body.get("results"), list) else data.get("results", []) if isinstance(data, dict) else []
        output_url = None
        if results:
            first = results[0] if isinstance(results[0], dict) else {}
            output_url = first.get("url") or first.get("fileUrl")
        task_id = data.get("taskId") if isinstance(data, dict) else body.get("taskId")
        status = self._status((data or {}).get("taskStatus") if isinstance(data, dict) else None)
        status = self._status(body.get("status") or status)
        return {
            "status": status,
            "provider_task_id": task_id,
            "output_url": output_url,
            "results": results,
            "cost": (data or {}).get("consumeMoney") if isinstance(data, dict) else body.get("consumeMoney"),
            "error": body.get("errorMessage") or body.get("msg") if body.get("code") not in (None, 0) else None,
            "raw": body,
        }

    async def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        workflow_id = payload.get("workflow_id") or payload.get("workflowId")
        if not workflow_id:
            raise ValueError("RunningHub 工作流需要 workflowId")
        request_payload: dict[str, Any] = {"apiKey": self.api_key, "workflowId": str(workflow_id)}
        node_info_list = payload.get("nodeInfoList") or payload.get("node_info_list")
        if node_info_list:
            request_payload["nodeInfoList"] = node_info_list
        for key in ("accessPassword", "retainSeconds", "webhookUrl"):
            if payload.get(key) is not None:
                request_payload[key] = payload[key]
        body = await asyncio.to_thread(self._request, "/task/openapi/create", request_payload)
        return self._normalize(body)

    async def status(self, provider_task_id: str, status_url: str | None = None) -> dict[str, Any]:
        body = await asyncio.to_thread(self._request, "/openapi/v2/query", {"taskId": provider_task_id})
        return self._normalize(body)

    async def cancel(self, provider_task_id: str, cancel_url: str | None = None) -> dict[str, Any]:
        return {"status": "Cancelled", "provider_task_id": provider_task_id}

    async def estimate_cost(self, payload: dict[str, Any]) -> float:
        return float(payload.get("estimatedCost") or os.environ.get("SHORT_DRAMA_RUNNINGHUB_ESTIMATED_COST", "0.73"))

    async def upload(self, filename: str, content: bytes, content_type: str | None = None) -> dict[str, Any]:
        mime = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        boundary = f"----ShortDramaOS{uuid.uuid4().hex}"
        body = b"--" + boundary.encode() + b"\r\n"
        body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode("utf-8")
        body += content + b"\r\n--" + boundary.encode() + b"--\r\n"
        request = Request(f"{self.base_url}/openapi/v2/media/upload/binary", data=body, headers=self._headers(f"multipart/form-data; boundary={boundary}"), method="POST")
        with urlopen(request, timeout=float(os.environ.get("SHORT_DRAMA_RUNNINGHUB_TIMEOUT", "45"))) as response:
            result = json.loads(response.read().decode("utf-8"))
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        return {"ok": result.get("code", 0) in (0, 200), "data": data, "raw": result}
