from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..core.database import session
from ..domain.repository import now_text
from ..providers.http import resolve_generation_url
from .secret_store import is_protected, protect_secret, storage_status, unprotect_secret


SETTING_ENV = {
    "providerUrl": "SHORT_DRAMA_PROVIDER_URL",
    "providerName": "SHORT_DRAMA_PROVIDER_NAME",
    "providerModel": "SHORT_DRAMA_PROVIDER_MODEL",
    "providerImageModel": "SHORT_DRAMA_PROVIDER_IMAGE_MODEL",
    "providerVideoModel": "SHORT_DRAMA_PROVIDER_VIDEO_MODEL",
    "providerStatusUrl": "SHORT_DRAMA_PROVIDER_STATUS_URL",
    "providerApiKey": "SHORT_DRAMA_PROVIDER_API_KEY",
    "voiceProvider": "SHORT_DRAMA_VOICE_PROVIDER",
    "voiceModel": "SHORT_DRAMA_VOICE_PROVIDER_MODEL",
    "cosyvoiceUrl": "SHORT_DRAMA_COSYVOICE_URL",
    "chatterboxUrl": "SHORT_DRAMA_CHATTERBOX_URL",
    "gptSovitsUrl": "SHORT_DRAMA_GPTSOVITS_URL",
    "llmProviderUrl": "SHORT_DRAMA_LLM_PROVIDER_URL",
    "llmProviderName": "SHORT_DRAMA_LLM_PROVIDER_NAME",
    "llmModel": "SHORT_DRAMA_LLM_MODEL",
    "llmVisionModel": "SHORT_DRAMA_LLM_VISION_MODEL",
    "llmApiKey": "SHORT_DRAMA_LLM_API_KEY",
    "runninghubBaseUrl": "SHORT_DRAMA_RUNNINGHUB_BASE_URL",
    "runninghubApiKey": "SHORT_DRAMA_RUNNINGHUB_API_KEY",
}

DEFAULTS = {
    "providerUrl": "",
    "providerName": "External Video API",
    "providerModel": "video-default",
    "providerImageModel": "",
    "providerVideoModel": "",
    "providerStatusUrl": "",
    "providerApiKey": "",
    "voiceProvider": "mock",
    "voiceModel": "voice-default",
    "cosyvoiceUrl": "",
    "chatterboxUrl": "",
    "gptSovitsUrl": "",
    "llmProviderUrl": "",
    "llmProviderName": "OpenAI Compatible",
    "llmModel": "gpt-4o-mini",
    "llmVisionModel": "",
    "llmApiKey": "",
    "runninghubBaseUrl": "https://www.runninghub.cn",
    "runninghubApiKey": "",
}

SECRET_KEYS = {"providerApiKey", "llmApiKey", "runninghubApiKey"}


def _llm_models_endpoint(endpoint: str) -> str:
    """Normalize an OpenAI-compatible LLM URL to its model discovery route."""
    value = endpoint.rstrip("/")
    if value.endswith("/chat/completions"):
        return value[: -len("/chat/completions")] + "/models"
    if value.endswith("/models"):
        return value
    return f"{value}/models"


def _is_placeholder_url(value: str | None) -> bool:
    from urllib.parse import urlparse

    hostname = (urlparse(str(value or "")).hostname or "").lower().rstrip(".")
    return hostname in {"example.com", "api.example.com"} or hostname.endswith(".example.com")


def _raw_settings() -> dict[str, str]:
    values = {}
    with session() as connection:
        rows = connection.execute("SELECT key, value FROM runtime_settings").fetchall()
        for row in rows:
            key = row["key"]
            stored = row["value"]
            if key in SECRET_KEYS:
                value = unprotect_secret(stored)
                # Migrate V1 plaintext values as soon as the settings store is
                # read, while keeping old installations usable.
                if value and not is_protected(stored):
                    connection.execute("UPDATE runtime_settings SET value = ?, is_secret = 1, updated_at = ? WHERE key = ?", (protect_secret(value), now_text(), key))
                values[key] = value
            else:
                values[key] = stored
    for key, env_key in SETTING_ENV.items():
        if key not in values:
            values[key] = os.environ.get(env_key, DEFAULTS[key])
    return {**DEFAULTS, **values}


def public_provider_settings() -> dict[str, Any]:
    values = _raw_settings()
    # The old demo endpoint must not look like a usable provider in the UI.
    if _is_placeholder_url(values.get("providerUrl")):
        values["providerUrl"] = ""
    if _is_placeholder_url(values.get("llmProviderUrl")):
        values["llmProviderUrl"] = ""
    has_key = bool(values.get("providerApiKey"))
    has_llm_key = bool(values.get("llmApiKey"))
    has_runninghub_key = bool(values.get("runninghubApiKey"))
    return {
        **{key: value for key, value in values.items() if key not in SECRET_KEYS},
        "providerApiKey": "",
        "providerApiKeyMasked": "••••••••" if has_key else "",
        "apiKeySet": has_key,
        "llmApiKey": "",
        "llmApiKeyMasked": "••••••••" if has_llm_key else "",
        "llmApiKeySet": has_llm_key,
        "runninghubApiKey": "",
        "runninghubApiKeyMasked": "••••••••" if has_runninghub_key else "",
        "runninghubApiKeySet": has_runninghub_key,
        "secretStorage": storage_status(),
    }


def save_provider_settings(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("providerUrl", "llmProviderUrl"):
        value = payload.get(key)
        if value and _is_placeholder_url(str(value)):
            raise ValueError("这是示例占位地址，不能保存。请替换为真实可访问的 API 地址。")
    allowed = set(SETTING_ENV)
    with session() as connection:
        for key in allowed:
            if key not in payload:
                continue
            value = payload.get(key)
            if key in SECRET_KEYS and value in {None, "", "••••••••"}:
                continue
            if value == "__CLEAR__":
                value = ""
            if key in SECRET_KEYS and value:
                value = protect_secret(str(value))
            connection.execute(
                "INSERT INTO runtime_settings(key, value, is_secret, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, is_secret = excluded.is_secret, updated_at = excluded.updated_at",
                (key, str(value or ""), int(key in SECRET_KEYS), now_text()),
            )
    return public_provider_settings()


def test_provider_connection(payload: dict[str, Any]) -> dict[str, Any]:
    provider_kind = payload.get("kind", "video")
    if provider_kind == "runninghub":
        endpoint = payload.get("runninghubBaseUrl") or DEFAULTS["runninghubBaseUrl"]
        label = "RunningHub"
        api_key = payload.get("runninghubApiKey")
        if not endpoint:
            return {"ok": False, "status": "not_configured", "message": "请先填写 RunningHub 地址"}
        if not str(endpoint).startswith(("http://", "https://")):
            return {"ok": False, "status": "invalid", "message": "RunningHub 地址必须以 http:// 或 https:// 开头"}
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            request = Request(str(endpoint).rstrip("/") + "/", headers=headers, method="GET")
            with urlopen(request, timeout=20) as response:
                return {"ok": True, "status": "reachable", "message": f"{label} 已连接（HTTP {response.status}）", "endpoint": str(endpoint)}
        except HTTPError as error:
            if error.code in {401, 403, 404, 405}:
                return {"ok": True, "status": "reachable", "message": f"{label} 可访问（HTTP {error.code}）", "endpoint": str(endpoint)}
            return {"ok": False, "status": "http_error", "message": f"RunningHub 返回 HTTP {error.code}", "endpoint": str(endpoint)}
        except (URLError, TimeoutError, OSError) as error:
            return {"ok": False, "status": "unreachable", "message": f"连接失败：{error}", "endpoint": str(endpoint)}
    if provider_kind == "audio":
        provider = str(payload.get("voiceProvider") or "mock").lower()
        endpoint = {"cosyvoice": payload.get("cosyvoiceUrl"), "chatterbox": payload.get("chatterboxUrl"), "gpt-sovits": payload.get("gptSovitsUrl")}.get(provider)
        label = provider
    elif provider_kind == "llm":
        endpoint = payload.get("llmProviderUrl")
        label = payload.get("llmProviderName") or "LLM Provider"
    else:
        endpoint = payload.get("providerUrl")
        label = payload.get("providerName") or "通用生成接口"
    if not endpoint:
        return {"ok": False, "status": "not_configured", "message": "请先填写接口地址"}
    if not str(endpoint).startswith(("http://", "https://")):
        return {"ok": False, "status": "invalid", "message": "接口地址必须以 http:// 或 https:// 开头"}
    if _is_placeholder_url(str(endpoint)):
        return {"ok": False, "status": "invalid", "message": "当前是示例占位地址，请替换成真实 API 地址"}
    requested_endpoint = str(endpoint)
    if provider_kind == "llm":
        endpoint = _llm_models_endpoint(requested_endpoint)
    elif provider_kind not in {"audio", "runninghub"}:
        endpoint = resolve_generation_url(requested_endpoint, "image", payload.get("providerModel"))
    headers = {"Accept": "application/json, audio/wav"}
    api_key = payload.get("llmApiKey") if provider_kind == "llm" else payload.get("providerApiKey")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        request = Request(str(endpoint), headers=headers, method="GET")
        with urlopen(request, timeout=5) as response:
            result: dict[str, Any] = {"ok": True, "status": "reachable", "message": f"{label} 已连接（HTTP {response.status}）", "endpoint": str(endpoint), "requestedEndpoint": requested_endpoint}
            if provider_kind == "llm":
                try:
                    body = json.loads(response.read().decode("utf-8"))
                    models = [item.get("id") for item in body.get("data", []) if isinstance(item, dict) and item.get("id")]
                    if models:
                        result["models"] = models[:20]
                        result["message"] = f"{label} 已连接，发现 {len(models)} 个模型"
                except (ValueError, TypeError):
                    pass
            return result
    except HTTPError as error:
        # A synthesis endpoint commonly rejects GET but is still reachable.
        if error.code in {400, 401, 403, 404, 405, 422}:
            return {"ok": True, "status": "reachable", "message": f"{label} 可访问（HTTP {error.code}，生成接口需 POST）", "endpoint": str(endpoint), "requestedEndpoint": requested_endpoint}
        return {"ok": False, "status": "http_error", "message": f"接口返回 HTTP {error.code}", "endpoint": str(endpoint), "requestedEndpoint": requested_endpoint}
    except (URLError, TimeoutError, OSError) as error:
        return {"ok": False, "status": "unreachable", "message": f"连接失败：{error}", "endpoint": str(endpoint), "requestedEndpoint": requested_endpoint}
