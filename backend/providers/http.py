from __future__ import annotations

import asyncio
import json
import os
from urllib.error import HTTPError, URLError
import urllib.request
from typing import Any

from .base import BaseProvider


class HttpProvider(BaseProvider):
    """Generic async adapter for a configured external provider."""

    def __init__(self, kind: str, url: str, provider_name: str, model: str, api_key: str | None, status_url_template: str | None = None) -> None:
        self.kind = kind
        self.url = url.rstrip("/")
        self.provider = provider_name
        self.model = model
        self.api_key = api_key
        self.status_url_template = status_url_template or ""
        self.auth_header = os.environ.get("SHORT_DRAMA_PROVIDER_AUTH_HEADER", "Authorization")
        self.auth_prefix = os.environ.get("SHORT_DRAMA_PROVIDER_AUTH_PREFIX", "Bearer")

    def _request(self, url: str, payload: dict[str, Any] | None = None, method: str | None = None) -> dict[str, Any] | list[Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers[self.auth_header] = f"{self.auth_prefix} {self.api_key}".strip()
        request = urllib.request.Request(url, data=json.dumps(payload or {}).encode("utf-8") if payload is not None else None, headers=headers, method=method or ("POST" if payload is not None else "GET"))
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except HTTPError as error:
            raise RuntimeError(f"{self.provider} 返回 HTTP {error.code}，请检查 API 地址、Key 和模型权限") from error
        except (URLError, TimeoutError, OSError) as error:
            raise RuntimeError(f"无法连接 {self.provider}：{error}") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError(f"{self.provider} 返回的不是 JSON，当前地址可能是网页地址而不是生成 API") from error

    @staticmethod
    def _status(value: Any) -> str:
        normalized = str(value or "").strip().lower()
        return {"queued": "Queued", "pending": "Pending", "created": "Queued", "submitted": "Queued", "running": "Running", "processing": "Processing", "success": "Success", "succeeded": "Success", "completed": "Success", "complete": "Success", "failed": "Failed", "error": "Failed", "cancelled": "Cancelled", "canceled": "Cancelled"}.get(normalized, str(value or ""))

    @staticmethod
    def _containers(body: dict[str, Any] | list[Any]) -> list[Any]:
        containers: list[Any] = [body]
        if isinstance(body, dict):
            for key in ("data", "result", "output", "outputs", "results"):
                value = body.get(key)
                if isinstance(value, (dict, list)):
                    containers.append(value)
        return containers

    def _normalize(self, body: dict[str, Any] | list[Any]) -> dict[str, Any]:
        containers = self._containers(body)
        output_url = None
        provider_task_id = None
        status_url = None
        error = None
        status_value = None
        progress = None
        results: list[Any] = []
        for container in containers:
            records = container if isinstance(container, list) else [container]
            for item in records:
                if not isinstance(item, dict):
                    if isinstance(item, str) and not output_url and item.startswith(("http://", "https://", "/")):
                        output_url = item
                    continue
                output_url = output_url or item.get("output_url") or item.get("outputUrl") or item.get("image_url") or item.get("imageUrl") or item.get("video_url") or item.get("videoUrl") or item.get("audio_url") or item.get("audioUrl") or item.get("url") or item.get("file_url") or item.get("fileUrl")
                provider_task_id = provider_task_id or item.get("provider_task_id") or item.get("providerTaskId") or item.get("task_id") or item.get("taskId") or item.get("request_id") or item.get("requestId")
                status_url = status_url or item.get("status_url") or item.get("statusUrl") or item.get("result_url") or item.get("resultUrl")
                status_value = status_value or item.get("status") or item.get("state") or item.get("task_status") or item.get("taskStatus")
                progress = progress if progress is not None else item.get("progress") or item.get("percent")
                error = error or item.get("error") or item.get("errorMessage") or item.get("message") if str(item.get("status") or "").lower() in {"failed", "error"} else error
                if isinstance(item.get("data"), list):
                    results.extend(item["data"])
                elif item is not body and item not in results:
                    results.append(item)
        status = self._status(status_value)
        if not status:
            status = "Success" if output_url else "Running" if provider_task_id else "Failed"
        if not output_url and not provider_task_id and status == "Success":
            status = "Failed"
            error = error or "接口返回成功，但没有找到图片/视频输出地址"
        return {"status": status, "provider_task_id": provider_task_id, "status_url": status_url, "output_url": output_url, "results": results, "progress": progress, "error": error, "raw": body}

    def _submit_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.kind == "image" and any(token in self.url.lower() for token in ("/images/generations", "/image/generations")):
            parameters = payload.get("parameters") or {}
            return {"model": self.model, "prompt": payload.get("prompt", ""), "n": int(parameters.get("n") or 1), "size": parameters.get("size") or "1024x1024", "response_format": parameters.get("response_format") or "url"}
        return {**payload, "model": self.model, "type": self.kind}

    async def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = await asyncio.to_thread(self._request, self.url, self._submit_payload(payload))
        return self._normalize(body)

    async def status(self, provider_task_id: str, status_url: str | None = None) -> dict[str, Any]:
        endpoint = status_url or (self.status_url_template.replace("{task_id}", provider_task_id) if self.status_url_template else provider_task_id)
        if not endpoint or not endpoint.startswith(("http://", "https://", "/")):
            raise RuntimeError(f"{self.provider} 返回了异步任务，但没有 status_url；请配置异步状态 URL")
        body = await asyncio.to_thread(self._request, endpoint)
        return self._normalize(body)

    async def cancel(self, provider_task_id: str, cancel_url: str | None = None) -> dict[str, Any]:
        endpoint = cancel_url or (self.status_url_template.replace("{task_id}", provider_task_id) if self.status_url_template else provider_task_id)
        if not endpoint or not endpoint.startswith(("http://", "https://", "/")):
            return {"status": "Cancelled", "provider_task_id": provider_task_id}
        body = await asyncio.to_thread(self._request, endpoint, {"status": "cancelled"}, "POST")
        return self._normalize(body)

    async def estimate_cost(self, payload: dict[str, Any]) -> float:
        return float(os.environ.get("SHORT_DRAMA_ESTIMATED_COST", "0.73"))
