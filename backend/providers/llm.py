from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.request import Request, urlopen


class LLMNotConfigured(RuntimeError):
    pass


class LLMProvider:
    """Small OpenAI-compatible JSON adapter used by the Agent runner."""

    def __init__(self, settings: dict[str, Any]) -> None:
        self.url = str(settings.get("llmProviderUrl") or "").rstrip("/")
        self.provider = settings.get("llmProviderName") or "OpenAI Compatible"
        self.model = settings.get("llmModel") or "gpt-4o-mini"
        self.api_key = settings.get("llmApiKey") or ""

    @property
    def configured(self) -> bool:
        return bool(self.url)

    def _endpoint(self) -> str:
        if self.url.endswith("/chat/completions"):
            return self.url
        return f"{self.url}/chat/completions"

    def _request(self, system: str, user: str) -> dict[str, Any]:
        if not self.configured:
            raise LLMNotConfigured("请先在设置中填写 LLM Provider 地址")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
        }
        request = Request(self._endpoint(), data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
        with urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content")
        if isinstance(content, list):
            content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
        if not content:
            content = payload.get("output") or payload.get("content") or payload
        if isinstance(content, dict):
            return content
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(content).strip())
        result = json.loads(cleaned)
        return result if isinstance(result, dict) else {"data": result}

    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._request, system, user)
