from __future__ import annotations

import asyncio
import math
import os
import struct
import wave
from pathlib import Path
from typing import Any

from ..core.config import DATA_DIR
from .base import BaseProvider


class MockProvider(BaseProvider):
    provider = "mock"

    def __init__(self, kind: str, model: str | None = None) -> None:
        self.kind = kind
        self.model = model or f"mock-{kind}"

    async def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(float(os.environ.get("SHORT_DRAMA_DEMO_DELAY", "2.2")))
        if self.kind == "image":
            allow_mock_media = os.environ.get("SHORT_DRAMA_ALLOW_MOCK_GENERATION", "").strip().lower() in {"1", "true", "yes", "on"}
            if not allow_mock_media:
                raise RuntimeError("未配置真实的图片生成 API，任务未生成。请在设置中填写可访问的 POST 生成接口和 API Key。")
            parameters = payload.get("parameters") or {}
            is_character = payload.get("target_type") == "character_reference" or payload.get("asset_type") == "characters" or parameters.get("asset_type") in {"characters", "character_reference"}
            output = "/assets/shot-hero.png" if is_character else "/assets/shot-wide.png"
        elif self.kind == "video":
            allow_mock_media = os.environ.get("SHORT_DRAMA_ALLOW_MOCK_GENERATION", "").strip().lower() in {"1", "true", "yes", "on"}
            if not allow_mock_media:
                raise RuntimeError("未配置真实的视频生成 API，任务未生成。请在设置中填写可访问的 POST 生成接口和 API Key。")
            output = "/assets/shot-wide.png"
        elif self.kind == "audio":
            output, duration_ms = self._write_wav(payload)
        else:
            output, duration_ms = None, None
        return {"status": "Success", "provider_task_id": f"mock-{payload.get('task_id', 'task')}", "output_url": output, "duration_ms": locals().get("duration_ms"), "cost": await self.estimate_cost(payload)}

    def _write_wav(self, payload: dict[str, Any]) -> tuple[str, int]:
        parameters = payload.get("parameters") or {}
        target = int(parameters.get("target_duration_ms") or 1800)
        ratio = parameters.get("mock_duration_ratio")
        if ratio is not None:
            try:
                target = max(120, int(target * float(ratio)))
            except (TypeError, ValueError):
                pass
        target = max(120, min(target, 30000))
        task_id = str(payload.get("task_id") or "audio").replace("/", "-")
        output_dir = DATA_DIR / "generated-audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{task_id}.wav"
        path = output_dir / filename
        sample_rate = 16000
        frame_count = round(sample_rate * target / 1000)
        frequency = 220 + (abs(hash(parameters.get("text", ""))) % 140)
        frames = bytearray()
        for index in range(frame_count):
            envelope = min(1.0, index / max(1, sample_rate * 0.04))
            envelope *= min(1.0, (frame_count - index) / max(1, sample_rate * 0.06))
            sample = int(9000 * envelope * math.sin(2 * math.pi * frequency * index / sample_rate))
            frames.extend(struct.pack("<h", sample))
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(sample_rate)
            audio.writeframes(frames)
        return f"/generated-media/{filename}", target

    async def status(self, provider_task_id: str, status_url: str | None = None) -> dict[str, Any]:
        return {"status": "Success", "provider_task_id": provider_task_id}

    async def estimate_cost(self, payload: dict[str, Any]) -> float:
        return {"text": 0.02, "image": 0.18, "video": 0.73, "voice": 0.08, "audio": 0.08}.get(self.kind, 0.1)
