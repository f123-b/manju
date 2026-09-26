from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from ..domain.repository import create_asset, project_to_dict


PENDING_STATUSES = {"queued", "retrying", "running", "processing", "pending"}


async def generate_asset_image(project_id: str, payload: dict[str, Any], registry: Any) -> dict[str, Any]:
    asset_type = payload.get("assetType") or payload.get("asset_type")
    if asset_type not in {"characters", "locations"}:
        raise KeyError("只支持生成人物图或场景图")

    summary = registry.summary()
    provider_name = payload.get("provider") or summary["provider"]
    model = payload.get("model") or (registry.external_model if summary["mode"] == "remote" else "mock-image")
    prompt = payload.get("prompt") or payload.get("description") or "生成一张短剧制作参考图"
    provider = registry.resolve("image", provider_name, model)
    response = await provider.submit({
        "project_id": project_id,
        "asset_type": asset_type,
        "name": payload.get("name", "未命名资产"),
        "prompt": prompt,
        "style": payload.get("style", "电影感写实"),
        "parameters": payload.get("parameters", {}),
    }) or {}

    provider_task_id = response.get("provider_task_id") or response.get("task_id") or response.get("id")
    status_url = response.get("status_url") or response.get("statusUrl")
    status = str(response.get("status") or "Success")
    deadline = time.monotonic() + float(os.environ.get("SHORT_DRAMA_ASSET_TIMEOUT", "900"))
    while status.lower() in PENDING_STATUSES:
        if time.monotonic() > deadline:
            raise TimeoutError("图片生成等待平台结果超时")
        await asyncio.sleep(float(os.environ.get("SHORT_DRAMA_POLL_INTERVAL", "2")))
        response = await provider.status(provider_task_id or status_url or "", status_url)
        response = response or {}
        status = str(response.get("status") or "Success")

    if status.lower() in {"failed", "error"}:
        raise RuntimeError(response.get("error") or response.get("message") or "图片生成失败")
    if status.lower() in {"cancelled", "canceled"}:
        raise RuntimeError("图片生成已取消")

    image = response.get("output_url") or response.get("outputUrl") or response.get("image_url") or response.get("imageUrl") or response.get("url")
    if not image:
        image = "/assets/shot-hero.png" if asset_type == "characters" else "/assets/shot-wide.png"

    name = payload.get("name") or ("新人物" if asset_type == "characters" else "新场景")
    description = payload.get("description") or prompt
    asset_payload = {
        "name": name,
        "meta": payload.get("meta") or ("人物参考" if asset_type == "characters" else "场景参考"),
        "description": description,
        "image": image,
        "prompt": prompt,
        "status": "已生成",
    }
    if asset_type == "characters":
        asset_payload.update({
            "age": payload.get("age", ""),
            "gender": payload.get("gender", ""),
            "role": payload.get("role", ""),
            "personality": payload.get("personality", ""),
        })
    asset_id = create_asset(project_id, asset_type, asset_payload)
    assets = project_to_dict(project_id)["assets"][asset_type]
    asset = next(item for item in assets if item["id"] == asset_id)
    return {
        "projectId": project_id,
        "asset": asset,
        "assetType": asset_type,
        "provider": provider_name,
        "model": model,
        "cost": response.get("cost") or await provider.estimate_cost({"type": "image", "prompt": prompt}),
    }
