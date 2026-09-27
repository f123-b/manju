from __future__ import annotations

import os
from urllib.parse import urlparse
from typing import Any

from .base import BaseProvider
from .http import HttpProvider
from .mock import MockProvider
from .runninghub import RunningHubProvider
from .voice import VoiceHttpProvider


def _is_placeholder_url(value: str | None) -> bool:
    hostname = (urlparse(str(value or "")).hostname or "").lower().rstrip(".")
    return hostname in {"blankapi.com", "example.com", "api.example.com"} or hostname.endswith(".example.com")


class ProviderRegistry:
    def __init__(self) -> None:
        self.apply_settings({
            "providerUrl": os.environ.get("SHORT_DRAMA_PROVIDER_URL", ""),
            "providerName": os.environ.get("SHORT_DRAMA_PROVIDER_NAME", "External Video API"),
            "providerModel": os.environ.get("SHORT_DRAMA_PROVIDER_MODEL", "video-default"),
            "providerStatusUrl": os.environ.get("SHORT_DRAMA_PROVIDER_STATUS_URL", ""),
            "providerApiKey": os.environ.get("SHORT_DRAMA_PROVIDER_API_KEY", ""),
            "voiceProvider": os.environ.get("SHORT_DRAMA_VOICE_PROVIDER", "mock"),
            "voiceModel": os.environ.get("SHORT_DRAMA_VOICE_PROVIDER_MODEL", "voice-default"),
            "cosyvoiceUrl": os.environ.get("SHORT_DRAMA_COSYVOICE_URL") or os.environ.get("SHORT_DRAMA_VOICE_PROVIDER_URL", ""),
            "chatterboxUrl": os.environ.get("SHORT_DRAMA_CHATTERBOX_URL", ""),
            "gptSovitsUrl": os.environ.get("SHORT_DRAMA_GPTSOVITS_URL", ""),
            "llmProviderUrl": os.environ.get("SHORT_DRAMA_LLM_PROVIDER_URL", ""),
            "llmProviderName": os.environ.get("SHORT_DRAMA_LLM_PROVIDER_NAME", "OpenAI Compatible"),
            "llmModel": os.environ.get("SHORT_DRAMA_LLM_MODEL", "gpt-4o-mini"),
            "llmVisionModel": os.environ.get("SHORT_DRAMA_LLM_VISION_MODEL", ""),
            "runninghubBaseUrl": os.environ.get("SHORT_DRAMA_RUNNINGHUB_BASE_URL", "https://www.runninghub.cn"),
            "runninghubApiKey": os.environ.get("SHORT_DRAMA_RUNNINGHUB_API_KEY", ""),
        })

    def apply_settings(self, settings: dict[str, Any]) -> None:
        configured_url = settings.get("providerUrl") or None
        self.external_url = None if _is_placeholder_url(configured_url) else configured_url
        self.external_name = settings.get("providerName") or "External Video API"
        self.external_model = settings.get("providerModel") or "video-default"
        self.image_model = settings.get("providerImageModel") or self.external_model
        self.video_model = settings.get("providerVideoModel") or self.external_model
        self.external_status_url = settings.get("providerStatusUrl") or None
        self.api_key = settings.get("providerApiKey") or None
        self.voice_provider = (settings.get("voiceProvider") or "mock").lower()
        self.voice_endpoints = {
            "cosyvoice": settings.get("cosyvoiceUrl") or None,
            "chatterbox": settings.get("chatterboxUrl") or None,
            "gpt-sovits": settings.get("gptSovitsUrl") or None,
        }
        self.voice_model = settings.get("voiceModel") or "voice-default"
        self.llm_url = settings.get("llmProviderUrl") or None
        self.llm_name = settings.get("llmProviderName") or "OpenAI Compatible"
        self.llm_model = settings.get("llmModel") or "gpt-4o-mini"
        self.runninghub_url = settings.get("runninghubBaseUrl") or "https://www.runninghub.cn"
        self.runninghub_api_key = settings.get("runninghubApiKey") or None

    def reload(self) -> None:
        from ..services.runtime_settings import _raw_settings

        self.apply_settings(_raw_settings())

    def resolve(self, kind: str, provider: str | None = None, model: str | None = None) -> BaseProvider:
        if kind == "workflow" and (not provider or provider == "RunningHub"):
            return RunningHubProvider(self.runninghub_url, self.runninghub_api_key, model or "workflow")
        if kind in {"image", "video"} and self.external_url and (not provider or provider == self.external_name):
            selected_model = model or (self.image_model if kind == "image" else self.video_model)
            return HttpProvider(kind, self.external_url, self.external_name, selected_model, self.api_key, self.external_status_url)
        if kind == "audio":
            provider_key = (provider or self.voice_provider or "mock").lower()
            endpoint = self.voice_endpoints.get(provider_key)
            if endpoint:
                return VoiceHttpProvider(provider_key, endpoint, model or self.voice_model, self.api_key)
        return MockProvider(kind, model)

    def summary(self) -> dict[str, Any]:
        image_video_provider = self.external_name if self.external_url else "Local Demo"
        image_video_model = self.image_model if self.external_url else "mock-image/video"
        audio_provider = self.voice_provider if any(self.voice_endpoints.values()) else "Local Demo"
        return {
            "mode": "remote" if self.external_url or any(self.voice_endpoints.values()) else "demo",
            "provider": self.external_name if self.external_url else (self.voice_provider if any(self.voice_endpoints.values()) else "Local Demo"),
            "configured": bool(self.external_url or any(self.voice_endpoints.values())),
            "types": ["text", "image", "video", "audio"],
            "voiceProviders": {key: bool(value) for key, value in self.voice_endpoints.items()},
            "providers": {
                "image": {"provider": image_video_provider, "model": image_video_model, "configured": bool(self.external_url)},
                "video": {"provider": image_video_provider, "model": self.video_model if self.external_url else "mock-video", "configured": bool(self.external_url)},
                "audio": {"provider": audio_provider, "model": self.voice_model, "configured": bool(any(self.voice_endpoints.values()))},
                "llm": {"provider": self.llm_name if self.llm_url else "Local Agent", "model": self.llm_model, "configured": bool(self.llm_url)},
                "workflow": {"provider": "RunningHub", "model": "workflow", "configured": bool(self.runninghub_api_key)},
            },
        }
