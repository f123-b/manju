from __future__ import annotations

import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..core.database import session
from ..domain.repository import now_text


SETTING_ENV = {
    "providerUrl": "SHORT_DRAMA_PROVIDER_URL",
    "providerName": "SHORT_DRAMA_PROVIDER_NAME",
    "providerModel": "SHORT_DRAMA_PROVIDER_MODEL",
    "providerApiKey": "SHORT_DRAMA_PROVIDER_API_KEY",
    "voiceProvider": "SHORT_DRAMA_VOICE_PROVIDER",
    "voiceModel": "SHORT_DRAMA_VOICE_PROVIDER_MODEL",
    "cosyvoiceUrl": "SHORT_DRAMA_COSYVOICE_URL",
    "chatterboxUrl": "SHORT_DRAMA_CHATTERBOX_URL",
    "gptSovitsUrl": "SHORT_DRAMA_GPTSOVITS_URL",
}

DEFAULTS = {
    "providerUrl": "",
    "providerName": "External Video API",
    "providerModel": "video-default",
    "providerApiKey": "",
    "voiceProvider": "mock",
    "voiceModel": "voice-default",
    "cosyvoiceUrl": "",
    "chatterboxUrl": "",
    "gptSovitsUrl": "",
}


def _raw_settings() -> dict[str, str]:
    values = {}
    with session() as connection:
        rows = connection.execute("SELECT key, value FROM runtime_settings").fetchall()
        values.update({row["key"]: row["value"] for row in rows})
    for key, env_key in SETTING_ENV.items():
        if key not in values:
            values[key] = os.environ.get(env_key, DEFAULTS[key])
    return {**DEFAULTS, **values}


def public_provider_settings() -> dict[str, Any]:
    values = _raw_settings()
    has_key = bool(values.get("providerApiKey"))
    return {
        **{key: value for key, value in values.items() if key != "providerApiKey"},
        "providerApiKey": "",
        "providerApiKeyMasked": "••••••••" if has_key else "",
        "apiKeySet": has_key,
    }


def save_provider_settings(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = set(SETTING_ENV)
    with session() as connection:
        for key in allowed:
            if key not in payload:
                continue
            value = payload.get(key)
            if key == "providerApiKey" and value in {None, "", "••••••••"}:
                continue
            if value == "__CLEAR__":
                value = ""
            connection.execute(
                "INSERT INTO runtime_settings(key, value, is_secret, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, is_secret = excluded.is_secret, updated_at = excluded.updated_at",
                (key, str(value or ""), int(key == "providerApiKey"), now_text()),
            )
    return public_provider_settings()


def test_provider_connection(payload: dict[str, Any]) -> dict[str, Any]:
    provider_kind = payload.get("kind", "video")
    if provider_kind == "audio":
        provider = str(payload.get("voiceProvider") or "mock").lower()
        endpoint = {"cosyvoice": payload.get("cosyvoiceUrl"), "chatterbox": payload.get("chatterboxUrl"), "gpt-sovits": payload.get("gptSovitsUrl")}.get(provider)
        label = provider
    else:
        endpoint = payload.get("providerUrl")
        label = payload.get("providerName") or "通用生成接口"
    if not endpoint:
        return {"ok": False, "status": "not_configured", "message": "请先填写接口地址"}
    if not str(endpoint).startswith(("http://", "https://")):
        return {"ok": False, "status": "invalid", "message": "接口地址必须以 http:// 或 https:// 开头"}
    headers = {"Accept": "application/json, audio/wav"}
    if payload.get("providerApiKey"):
        headers["Authorization"] = f"Bearer {payload['providerApiKey']}"
    try:
        request = Request(str(endpoint), headers=headers, method="GET")
        with urlopen(request, timeout=5) as response:
            return {"ok": True, "status": "reachable", "message": f"{label} 已连接（HTTP {response.status}）", "endpoint": str(endpoint)}
    except HTTPError as error:
        # A synthesis endpoint commonly rejects GET but is still reachable.
        if error.code in {400, 401, 403, 404, 405, 422}:
            return {"ok": True, "status": "reachable", "message": f"{label} 可访问（HTTP {error.code}，生成接口需 POST）", "endpoint": str(endpoint)}
        return {"ok": False, "status": "http_error", "message": f"接口返回 HTTP {error.code}", "endpoint": str(endpoint)}
    except (URLError, TimeoutError, OSError) as error:
        return {"ok": False, "status": "unreachable", "message": f"连接失败：{error}", "endpoint": str(endpoint)}
