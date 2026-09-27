from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from ..core.config import DATA_DIR
from .base import BaseProvider


class VoiceHttpProvider(BaseProvider):
    """Provider-neutral audio adapter; the TTS runtime stays outside Manju."""

    def __init__(self, provider: str, url: str, model: str, api_key: str | None = None) -> None:
        self.provider = provider
        self.url = url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.kind = "audio"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json, audio/wav, audio/x-wav"}
        if self.api_key:
            headers[os.environ.get("SHORT_DRAMA_PROVIDER_AUTH_HEADER", "Authorization")] = f"Bearer {self.api_key}"
        return headers

    def _canonical(self, payload: dict[str, Any]) -> dict[str, Any]:
        parameters = payload.get("parameters") or {}
        voice = parameters.get("voice") or {}
        performance = parameters.get("performance") or {}
        return {"text": parameters.get("text") or payload.get("prompt", ""), "voice": voice, "performance": performance, "target_duration_ms": parameters.get("target_duration_ms"), "model": payload.get("model") or self.model, "task_id": payload.get("task_id")}

    def _provider_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        canonical = self._canonical(payload)
        if self.provider == "gpt-sovits":
            voice = canonical["voice"]
            performance = canonical["performance"]
            return {
                "text": canonical["text"],
                "text_lang": voice.get("language", "zh"),
                "ref_audio_path": voice.get("referenceAudioUrl") or voice.get("referenceAudioAssetId") or "",
                "prompt_lang": voice.get("language", "zh"),
                "prompt_text": voice.get("referenceText", ""),
                "speed_factor": performance.get("speed", 1.0),
                "streaming_mode": False,
                "media_type": "wav",
            }
        if self.provider == "chatterbox":
            intensity = float(canonical["performance"].get("emotionIntensity", 0.5))
            return {"text": canonical["text"], "audio_prompt_path": canonical["voice"].get("referenceAudioUrl") or "", "exaggeration": round(0.3 + 0.7 * intensity, 3), "cfg_weight": round(0.35 + 0.4 * intensity, 3), "model": canonical["model"]}
        return {**canonical, "provider": "cosyvoice" if self.provider == "cosyvoice" else self.provider}

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(self.url, data=json.dumps(self._provider_payload(payload), ensure_ascii=False).encode("utf-8"), headers=self._headers(), method="POST")
        with urlopen(request, timeout=120) as response:
            content = response.read()
            content_type = response.headers.get("Content-Type", "")
        if "audio" in content_type or content[:4] == b"RIFF":
            output_dir = DATA_DIR / "generated-audio"
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = f"remote-{payload.get('task_id', 'audio')}.wav"
            (output_dir / filename).write_bytes(content)
            return {"status": "Success", "provider_task_id": f"{self.provider}-{payload.get('task_id')}", "output_url": f"/generated-media/{filename}"}
        data = json.loads(content.decode("utf-8")) if content else {}
        return data if isinstance(data, dict) else {"status": "Success"}

    async def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._request, payload)

    async def status(self, provider_task_id: str, status_url: str | None = None) -> dict[str, Any]:
        return {"status": "Success", "provider_task_id": provider_task_id}

    async def estimate_cost(self, payload: dict[str, Any]) -> float:
        return float(os.environ.get("SHORT_DRAMA_VOICE_ESTIMATED_COST", "0.08"))
