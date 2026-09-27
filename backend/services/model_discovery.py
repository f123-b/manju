from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..domain.repository import upsert_discovered_models


CATEGORY_LABELS = {
    "text": "文本 / LLM",
    "vision": "视觉理解",
    "image": "图片生成",
    "video": "视频生成",
    "audio": "音频 / 语音",
    "embedding": "向量 / 重排",
    "workflow": "工作流",
    "unknown": "未识别",
}

_SUFFIXES = (
    "/chat/completions",
    "/responses",
    "/completions",
    "/generate",
    "/models",
)


class ModelDiscoveryError(RuntimeError):
    pass


def _clean_endpoint(value: str) -> str:
    endpoint = str(value or "").strip().rstrip("/")
    lowered = endpoint.lower()
    for suffix in _SUFFIXES:
        if lowered.endswith(suffix):
            return endpoint[: -len(suffix)].rstrip("/")
    return endpoint


def _candidate_model_urls(value: str) -> list[str]:
    base = _clean_endpoint(value)
    if not base:
        return []
    if base.lower().endswith("/v1"):
        return [f"{base}/models"]
    return [f"{base}/models", f"{base}/v1/models"]


def _request_json(url: str, api_key: str | None) -> dict[str, Any] | list[Any]:
    headers = {"Accept": "application/json"}
    if api_key and api_key != "••••••••":
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=float(os.environ.get("SHORT_DRAMA_MODEL_DISCOVERY_TIMEOUT", "8"))) as response:
        return json.loads(response.read().decode("utf-8"))


def _records(body: dict[str, Any] | list[Any]) -> list[Any]:
    if isinstance(body, list):
        return body
    for key in ("data", "models", "items", "results"):
        value = body.get(key)
        if isinstance(value, list):
            return value
    return []


def _truthy_capabilities(raw: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for key in ("capabilities", "modalities", "supported_modalities", "input_modalities", "output_modalities"):
        value = raw.get(key)
        if isinstance(value, dict):
            values.update(str(item).lower() for item, enabled in value.items() if enabled)
        elif isinstance(value, list):
            values.update(str(item).lower() for item in value)
        elif isinstance(value, str):
            values.update(part.strip().lower() for part in value.replace(",", " ").split())
    return values


def _classify(raw: Any, requested_kind: str) -> dict[str, Any] | None:
    if isinstance(raw, str):
        model_id = raw
        data: dict[str, Any] = {}
    elif isinstance(raw, dict):
        data = raw
        model_id = str(raw.get("id") or raw.get("model") or raw.get("model_id") or raw.get("name") or "").strip()
    else:
        return None
    if not model_id:
        return None

    display_name = str(data.get("display_name") or data.get("displayName") or data.get("name") or model_id)
    capabilities = _truthy_capabilities(data)
    haystack = f"{model_id} {display_name} {json.dumps(data, ensure_ascii=False, default=str)}".lower()
    categories: list[str] = []

    def add(category: str) -> None:
        if category not in categories:
            categories.append(category)

    if any(token in haystack for token in ("embedding", "embed", "rerank", "bge-m3", "e5-") ):
        add("embedding")
    if any(token in haystack for token in ("tts", "text-to-speech", "speech", "audio", "whisper", "voice", "cosyvoice", "gpt-sovits")) or capabilities & {"audio", "speech", "tts"}:
        add("audio")
    if any(token in haystack for token in ("video", "text-to-video", "image-to-video", "kling", "seedance", "wan2", "wan-", "vidu", "runway", "luma", "hailuo", "cogvideo")) or capabilities & {"video"}:
        add("video")
    if any(token in haystack for token in ("gpt-image", "image-2", "flux", "stable-diffusion", "sdxl", "sd3", "dall-e", "image-generation", "text-to-image", "qwen-image", "kolors", "midjourney", "playground", "comfy")) or capabilities & {"image", "image_generation"}:
        add("image")
    if any(token in haystack for token in ("vision", "-vl", "_vl", "multimodal", "omni", "llava", "pixtral", "minicpm-v", "gpt-4o", "gemini")) or capabilities & {"vision", "image_input", "image understanding"}:
        add("vision")

    if not categories:
        text_model_markers = ("gpt-", "claude", "deepseek", "minimax", "llama", "qwen", "mistral", "gemma", "phi-")
        if requested_kind in {"llm", "agent"} or any(token in haystack for token in text_model_markers):
            add("text")
        elif requested_kind in {"image", "video", "audio"}:
            add(requested_kind)
        else:
            add("unknown")
    if "vision" in categories or "text" in categories or requested_kind in {"llm", "agent"}:
        add("text")

    primary = next((item for item in ("video", "image", "audio", "vision", "embedding", "text") if item in categories), "unknown")
    capabilities_result = {
        "text": "text" in categories,
        "vision": "vision" in categories,
        "imageInput": "vision" in categories,
        "imageOutput": "image" in categories,
        "videoOutput": "video" in categories,
        "audioOutput": "audio" in categories,
    }
    return {
        "provider": "",
        "modelId": model_id,
        "displayName": display_name,
        "type": primary,
        "typeLabel": CATEGORY_LABELS[primary],
        "categories": categories,
        "categoryLabels": [CATEGORY_LABELS[item] for item in categories],
        "capabilities": capabilities_result,
        "raw": data,
    }


def _group_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for model in models:
        grouped.setdefault(model["type"], []).append(model)
    return [{"type": key, "label": CATEGORY_LABELS.get(key, key), "count": len(items), "models": items} for key, items in grouped.items()]


def discover_models(url: str, api_key: str | None = None, provider_name: str | None = None, requested_kind: str = "llm") -> dict[str, Any]:
    urls = _candidate_model_urls(url)
    if not urls:
        raise ModelDiscoveryError("请先填写 API 地址")
    last_error: Exception | None = None
    body: dict[str, Any] | list[Any] | None = None
    selected_url = urls[0]
    for candidate in urls:
        try:
            body = _request_json(candidate, api_key)
            selected_url = candidate
            break
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            last_error = error
    if body is None:
        if isinstance(last_error, HTTPError):
            raise ModelDiscoveryError(f"模型列表接口返回 HTTP {last_error.code}") from last_error
        raise ModelDiscoveryError(f"无法读取模型列表：{last_error}") from last_error

    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in _records(body):
        model = _classify(record, requested_kind)
        if not model or model["modelId"] in seen:
            continue
        seen.add(model["modelId"])
        model["provider"] = provider_name or urlparse(url).netloc or "Discovered Provider"
        model.pop("raw", None)
        models.append(model)
    if not models:
        raise ModelDiscoveryError("接口可访问，但响应中没有识别到模型。支持 OpenAI-compatible /models、models 或 data 数组格式。")

    upsert_discovered_models(models)
    recommended = {}
    for category in ("image", "video", "audio", "vision", "text"):
        candidate = next((model["modelId"] for model in models if category in model["categories"]), None)
        if candidate:
            recommended[category] = candidate
    return {
        "provider": provider_name or urlparse(url).netloc or "Discovered Provider",
        "endpoint": selected_url,
        "models": models,
        "groups": _group_models(models),
        "recommended": recommended,
        "count": len(models),
    }
