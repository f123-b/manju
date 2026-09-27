from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class LLMNotConfigured(RuntimeError):
    pass


class LLMProvider:
    """Small OpenAI-compatible JSON adapter used by the Agent runner."""

    def __init__(self, settings: dict[str, Any]) -> None:
        self.url = str(settings.get("llmProviderUrl") or "").rstrip("/")
        self.provider = settings.get("llmProviderName") or "OpenAI Compatible"
        self.model = settings.get("llmModel") or "gpt-4o-mini"
        self.vision_model = settings.get("llmVisionModel") or self.model
        self.api_key = settings.get("llmApiKey") or ""

    @property
    def configured(self) -> bool:
        return bool(self.url)

    def _endpoint(self) -> str:
        if self.url.endswith("/chat/completions"):
            return self.url
        return f"{self.url}/chat/completions"

    def _request_messages(self, messages: list[dict[str, Any]], model: str | None = None) -> dict[str, Any]:
        if not self.configured:
            raise LLMNotConfigured("请先在设置中填写 LLM Provider 地址")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": model or self.model,
            "temperature": 0.2,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }

        def send(request_body: dict[str, Any]) -> dict[str, Any]:
            request = Request(self._endpoint(), data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
            with urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            payload = send(body)
        except HTTPError as error:
            # Some local OpenAI-compatible runtimes (including older vLLM
            # builds) do not implement response_format. Retry once with the
            # same prompt so MiniMax can still return structured JSON.
            if error.code not in {400, 422}:
                raise
            payload = send({key: value for key, value in body.items() if key != "response_format"})

        message = ((payload.get("choices") or [{}])[0].get("message") or {})
        content = message.get("content")
        if not content:
            # Reasoning models may put their visible answer in a separate
            # field. Prefer content, but keep this compatible with local
            # MiniMax gateways that expose only reasoning_content.
            content = message.get("reasoning_content")
        if isinstance(content, list):
            content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
        if not content:
            content = payload.get("output") or payload.get("content") or payload
        if isinstance(content, dict):
            return content

        cleaned = str(content).strip()
        # MiniMax reasoning models can wrap the JSON answer in a <think>
        # block or Markdown fences. Remove those wrappers before parsing.
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE).strip()
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            # Be tolerant of a short natural-language prefix/suffix while
            # preserving the structured object returned by the model.
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start < 0 or end <= start:
                raise
            result = json.loads(cleaned[start:end + 1])
        return result if isinstance(result, dict) else {"data": result}

    def _request(self, system: str, user: str) -> dict[str, Any]:
        return self._request_messages([{"role": "system", "content": system}, {"role": "user", "content": user}])

    @staticmethod
    def _image_reference(image: str | Path) -> str:
        """Turn a local image into a data URL; remote URLs stay remote.

        The QC service only passes paths inside the application data/public
        directories, so the provider does not need to expose a new file route
        merely to let a remote vision model inspect a generated frame.
        """
        value = str(image)
        if value.startswith(("http://", "https://", "data:")):
            return value
        path = Path(value)
        if not path.is_file():
            raise FileNotFoundError(f"视觉检查图片不存在：{path}")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _request_vision(self, system: str, user: str, image: str | Path) -> dict[str, Any]:
        image_url = self._image_reference(image)
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ]
        return self._request_messages(messages, self.vision_model)

    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._request, system, user)

    def complete_vision_json_sync(self, system: str, user: str, image: str | Path) -> dict[str, Any]:
        """Synchronous vision call for the synchronous QC transaction."""
        return self._request_vision(system, user, image)

    async def complete_vision_json(self, system: str, user: str, image: str | Path) -> dict[str, Any]:
        return await asyncio.to_thread(self._request_vision, system, user, image)
