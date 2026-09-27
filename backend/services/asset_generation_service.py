from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from ..domain.repository import create_asset, create_target_generation_task, complete_generation_task, loads, project_to_dict


PENDING_STATUSES = {"queued", "retrying", "running", "processing", "pending"}


def _asset_payload(asset_type: str, payload: dict[str, Any], image: str | None = None, status: str = "生成中") -> dict[str, Any]:
    prompt = payload.get("prompt") or payload.get("description") or "生成一张短剧制作参考图"
    result = {
        "name": payload.get("name") or ("新人物" if asset_type == "characters" else "新场景"),
        "meta": payload.get("meta") or ("人物参考" if asset_type == "characters" else "场景参考"),
        "description": payload.get("description") or prompt,
        "image": image or ("/assets/shot-hero.png" if asset_type == "characters" else "/assets/shot-wide.png"),
        "prompt": prompt,
        "status": status,
    }
    if asset_type == "characters":
        result.update({"age": payload.get("age", ""), "gender": payload.get("gender", ""), "role": payload.get("role", ""), "personality": payload.get("personality", "")})
    return result


def _task_payload(project_id: str, asset_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "assetType": asset_type,
        "name": payload.get("name"),
        "description": payload.get("description"),
        "prompt": payload.get("prompt") or payload.get("description") or "生成一张短剧制作参考图",
        "style": payload.get("style", "电影感写实"),
        "negativePrompt": payload.get("negativePrompt", ""),
        "parameters": payload.get("parameters", {}),
        "projectId": project_id,
    }


async def generate_asset_image(project_id: str, payload: dict[str, Any], registry: Any) -> dict[str, Any]:
    """Queue image generation so asset work uses the same durable task center."""
    asset_type = payload.get("assetType") or payload.get("asset_type")
    if asset_type not in {"characters", "locations"}:
        raise KeyError("只支持生成人物图或场景图")
    summary = registry.summary()
    provider_name = payload.get("provider") or summary["provider"]
    model = payload.get("model") or (registry.external_model if summary["mode"] == "remote" else "mock-image")
    asset_id = create_asset(project_id, asset_type, _asset_payload(asset_type, payload))
    task_id = create_target_generation_task(
        project_id, "asset", asset_id,
        payload.get("prompt") or payload.get("description") or "生成一张短剧制作参考图",
        provider_name, model, estimated_cost=float(payload.get("estimatedCost", 0.18)),
        parameters=_task_payload(project_id, asset_type, payload), task_type="图片",
    )
    asset = next(item for item in project_to_dict(project_id)["assets"][asset_type] if item["id"] == asset_id)
    return {"projectId": project_id, "asset": asset, "assetType": asset_type, "provider": provider_name, "model": model, "cost": float(payload.get("estimatedCost", 0.18)), "taskId": task_id, "queued": True}


async def run_asset_task(task: dict[str, Any], registry: Any) -> None:
    parameters = loads(task.get("parameters_json"), {})
    provider = registry.resolve("image", task.get("provider"), task.get("model"))
    response = await provider.submit({
        "task_id": task["id"], "project_id": task["project_id"], "asset_type": parameters.get("assetType"),
        "name": parameters.get("name"), "prompt": parameters.get("prompt") or task.get("prompt", ""),
        "style": parameters.get("style", "电影感写实"), "negative_prompt": parameters.get("negativePrompt", ""),
        "parameters": parameters.get("parameters", {}),
    }) or {}
    provider_task_id = response.get("provider_task_id") or response.get("task_id") or response.get("id")
    status_url = response.get("status_url") or response.get("statusUrl")
    status = str(response.get("status") or "Success")
    deadline = time.monotonic() + float(os.environ.get("SHORT_DRAMA_ASSET_TIMEOUT", "900"))
    while status.lower() in PENDING_STATUSES:
        if time.monotonic() > deadline:
            raise TimeoutError("图片生成等待平台结果超时")
        await asyncio.sleep(float(os.environ.get("SHORT_DRAMA_POLL_INTERVAL", "2")))
        response = await provider.status(provider_task_id or status_url or "", status_url) or {}
        status = str(response.get("status") or "Success")
    if status.lower() in {"failed", "error"}:
        raise RuntimeError(response.get("error") or response.get("message") or "图片生成失败")
    if status.lower() in {"cancelled", "canceled"}:
        raise RuntimeError("图片生成已取消")
    complete_generation_task(task["id"], {
        "output_url": response.get("output_url") or response.get("outputUrl") or response.get("image_url") or response.get("imageUrl") or response.get("url"),
        "cost": response.get("cost"), "qc_score": response.get("qc_score") or response.get("qcScore") or 91,
    })
