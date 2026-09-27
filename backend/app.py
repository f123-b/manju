from __future__ import annotations

import asyncio
import json
import os
from urllib.parse import quote
from typing import Any, Optional

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .core.config import DATA_DIR, DB_PATH, DIST_DIR, PROJECT_ID
from .core.database import init_database, session
from .domain.repository import (
    activate_version,
    affected_shots,
    cancel_generation_task,
    create_canvas_edge,
    create_canvas_node,
    create_target_generation_task,
    create_episode,
    create_asset,
    create_generation_task,
    create_project,
    create_scene,
    create_shot,
    delete_shot,
    delete_canvas_edge,
    delete_canvas_node,
    episode_dict,
    generation_task,
    list_costs,
    list_canvas,
    list_runninghub_workflows,
    list_models,
    list_projects,
    list_qc,
    list_scenes,
    list_shots_for_scene,
    list_versions,
    patch_asset,
    patch_canvas_node,
    patch_episode,
    patch_project,
    patch_runninghub_workflow,
    patch_scene,
    patch_shot,
    patch_story_bible,
    project_to_dict,
    create_runninghub_workflow,
    delete_project,
    delete_runninghub_workflow,
    retry_generation_task,
)
from .domain.character_assets import (
    affected_shots_for_character,
    bind_shot_characters,
    create_character,
    create_look,
    create_reference,
    extract_identity_anchors,
    generate_character_candidates,
    generate_master_sheet,
    get_character,
    get_shot_characters,
    list_characters,
    list_looks,
    list_references,
    lock_character,
    patch_character,
    patch_look,
    review_reference,
    set_canonical_reference,
    shot_generation_context,
    unlock_character,
)
from .domain.seed import seed_legacy_project
from .domain.audio_engine import (
    activate_take,
    audio_status,
    create_audio_clip,
    create_dialogue_line,
    create_voice_profile,
    direct_performance,
    extract_dialogue_lines,
    generate_dialogue_line,
    generate_episode_dialogue,
    list_audio_clips,
    list_dialogue_lines,
    list_takes,
    list_voice_profiles,
    lock_voice_profile,
    mixdown_episode,
    patch_audio_clip,
    delete_audio_clip,
    patch_dialogue_line,
    patch_voice_profile,
    provider_definitions,
    run_qc,
    test_voice_profile,
    unlock_voice_profile,
)
from .domain.video_engine import create_video_clip, delete_video_clip, list_video_clips, patch_video_clip
from .providers.registry import ProviderRegistry
from .services.export_service import export_project_package
from .services.asset_generation_service import generate_asset_image
from .services.script_service import generate_episode_matrix_ai, generate_scene_script_ai, generate_shot_breakdown_ai
from .services.task_engine import task_engine
from .services.runtime_settings import _raw_settings, public_provider_settings, save_provider_settings, test_provider_connection
from .services.model_discovery import ModelDiscoveryError, discover_models
from .services.agent_service import cancel_agent_run, create_agent_run, get_agent_run, list_agent_runs, resume_agent_run
from .services.qc_service import run_project_continuity_check, run_project_qc, run_shot_visual_qc
from .services.render_service import list_render_jobs, render_episode_mp4
from .services.workspace_service import list_audit_events, record_audit, session_descriptor


app = FastAPI(title="Short Drama OS API", version="1.0.0")
registry = ProviderRegistry()


def not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


def project_response(project_id: str) -> dict[str, Any]:
    try:
        return project_to_dict(project_id)
    except KeyError as error:
        raise not_found(str(error)) from error


def task_response(task_id: str) -> dict[str, Any]:
    try:
        return generation_task(task_id)
    except KeyError as error:
        raise not_found(str(error)) from error


def find_shot(shot_id: str) -> dict[str, Any]:
    for item in list_projects():
        for shot in project_response(item["id"]).get("shots", []):
            if shot["id"] == shot_id:
                return shot
    raise not_found("镜头不存在")


@app.on_event("startup")
async def startup() -> None:
    init_database()
    registry.reload()
    task_engine.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    task_engine.stop()


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "database": str(DB_PATH), "schemaVersion": 2, **registry.summary()}


@app.get("/api/session")
async def get_session_descriptor() -> dict[str, Any]:
    return session_descriptor()


@app.get("/api/audit-events")
async def get_audit_events(limit: int = 50) -> dict[str, Any]:
    return {"items": list_audit_events(limit)}


@app.get("/api/settings/providers")
async def get_provider_settings() -> dict[str, Any]:
    return {"settings": public_provider_settings()}


@app.patch("/api/settings/providers")
async def patch_provider_settings(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    settings = save_provider_settings(payload)
    registry.reload()
    changed_keys = [key for key, value in payload.items() if key not in {"providerApiKey", "llmApiKey"} or value not in (None, "", "••••••••")]
    record_audit("settings.updated", "runtime_settings", metadata={"keys": sorted(changed_keys)})
    return {"settings": settings, "provider": registry.summary()}


@app.post("/api/settings/providers/test")
async def post_provider_settings_test(payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    settings = _raw_settings()
    for key, value in (payload or {}).items():
        if key in {"providerApiKey", "llmApiKey"} and not value:
            continue
        settings[key] = value
    return await asyncio.to_thread(test_provider_connection, settings)


@app.post("/api/settings/providers/discover-models")
async def post_provider_model_discovery(payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    requested = payload or {}
    kind = str(requested.get("kind") or "llm").lower()
    settings = _raw_settings()
    if kind in {"llm", "agent", "vision"}:
        url = requested.get("url") or requested.get("llmProviderUrl") or settings.get("llmProviderUrl")
        api_key = requested.get("apiKey") or requested.get("llmApiKey") or settings.get("llmApiKey")
        provider_name = requested.get("providerName") or requested.get("llmProviderName") or settings.get("llmProviderName")
    else:
        url = requested.get("url") or requested.get("providerUrl") or settings.get("providerUrl")
        api_key = requested.get("apiKey") or requested.get("providerApiKey") or settings.get("providerApiKey")
        provider_name = requested.get("providerName") or settings.get("providerName")
    if kind == "runninghub":
        return {"provider": "RunningHub", "models": [], "groups": [{"type": "workflow", "label": "工作流", "count": 0, "models": []}], "count": 0, "warning": "RunningHub 以 workflowId 管理工作流，不提供通用模型列表。"}
    try:
        result = await asyncio.to_thread(discover_models, str(url or ""), api_key, provider_name, kind)
        record_audit("models.discovered", "model_definitions", metadata={"provider": result["provider"], "count": result["count"], "kind": kind})
        return result
    except ModelDiscoveryError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/agent/runs")
async def post_agent_run(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        run = create_agent_run(payload.get("projectId", PROJECT_ID), payload.get("episodeId") or project_response(payload.get("projectId", PROJECT_ID))["currentEpisodeId"], payload.get("goal", ""))
        record_audit("agent.started", "agent_run", run["id"], {"episodeId": run["episodeId"]})
        task_engine.wake()
        return {"run": run}
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/agent/runs/{run_id}")
async def get_agent_run_resource(run_id: str) -> dict[str, Any]:
    try:
        return {"run": get_agent_run(run_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/projects/{project_id}/agent/runs")
async def list_agent_run_resources(project_id: str, episodeId: Optional[str] = None) -> dict[str, Any]:
    project_response(project_id)
    return {"items": list_agent_runs(project_id, episodeId)}


@app.post("/api/agent/runs/{run_id}/resume")
async def resume_agent_run_resource(run_id: str) -> dict[str, Any]:
    try:
        run = resume_agent_run(run_id)
        record_audit("agent.resumed", "agent_run", run_id, {"episodeId": run["episodeId"]})
        task_engine.wake()
        return {"run": run}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/agent/runs/{run_id}/cancel")
async def cancel_agent_run_resource(run_id: str) -> dict[str, Any]:
    try:
        return {"run": cancel_agent_run(run_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/projects")
async def get_projects() -> dict[str, Any]:
    return {"items": list_projects()}


@app.post("/api/projects")
async def post_project(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return project_response(create_project(payload))
    except Exception as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{project_id}")
async def get_project_resource(project_id: str) -> dict[str, Any]:
    return project_response(project_id)


@app.delete("/api/projects/{project_id}")
async def delete_project_resource(project_id: str) -> dict[str, Any]:
    try:
        delete_project(project_id)
        return {"ok": True, "projectId": project_id}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/projects/{project_id}/tasks")
async def get_project_tasks(project_id: str, status: Optional[str] = None, targetType: Optional[str] = None, limit: int = 100) -> dict[str, Any]:
    tasks = project_response(project_id)["tasks"]
    if status:
        tasks = [item for item in tasks if item["status"] == status]
    if targetType:
        tasks = [item for item in tasks if item["targetType"] == targetType]
    return {"items": tasks[:max(1, min(int(limit), 500))]}


@app.get("/api/projects/{project_id}/canvas")
async def get_project_canvas(project_id: str) -> dict[str, Any]:
    try:
        return list_canvas(project_id)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/projects/{project_id}/canvas/nodes")
async def post_canvas_node(project_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        node = create_canvas_node(project_id, payload)
        record_audit("canvas.node.created", "canvas_node", node["id"], {"type": node["type"]})
        return {"node": node}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.patch("/api/canvas-nodes/{node_id}")
async def patch_canvas_node_resource(node_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        project_id, node = patch_canvas_node(node_id, payload)
        record_audit("canvas.node.updated", "canvas_node", node_id, {"keys": sorted(payload)})
        return {"projectId": project_id, "node": node}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/canvas-nodes/{node_id}")
async def delete_canvas_node_resource(node_id: str) -> dict[str, Any]:
    try:
        project_id = delete_canvas_node(node_id)
        record_audit("canvas.node.deleted", "canvas_node", node_id)
        return {"ok": True, "projectId": project_id}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/projects/{project_id}/canvas/edges")
async def post_canvas_edge(project_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        edge = create_canvas_edge(project_id, str(payload.get("source") or payload.get("sourceNodeId")), str(payload.get("target") or payload.get("targetNodeId")), str(payload.get("label") or ""))
        record_audit("canvas.edge.created", "canvas_edge", edge["id"], {"source": edge["source"], "target": edge["target"]})
        return {"edge": edge}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/canvas-edges/{edge_id}")
async def delete_canvas_edge_resource(edge_id: str) -> dict[str, Any]:
    try:
        project_id = delete_canvas_edge(edge_id)
        record_audit("canvas.edge.deleted", "canvas_edge", edge_id)
        return {"ok": True, "projectId": project_id}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/canvas-nodes/{node_id}/run")
async def run_canvas_node(node_id: str, payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    with session() as connection:
        row = connection.execute("SELECT * FROM canvas_nodes WHERE id = ?", (node_id,)).fetchone()
    if not row:
        raise not_found(f"canvas node {node_id} not found")
    node = {
        "id": row["id"],
        "projectId": row["project_id"],
        "type": row["node_type"],
        "title": row["title"],
        "data": json.loads(row["data_json"] or "{}"),
    }
    data = {**node["data"], **(payload.get("data") or {})}
    prompt = str(payload.get("prompt") or data.get("prompt") or data.get("content") or node["title"])
    try:
        if node["type"] == "agent":
            episode_id = data.get("episodeId") or project_response(node["projectId"])["currentEpisodeId"]
            run = create_agent_run(node["projectId"], episode_id, prompt)
            patch_canvas_node(node_id, {"status": "queued", "data": data})
            task_engine.wake()
            return {"kind": "agent", "run": run}
        if node["type"] == "image":
            if not data.get("assetType") or not data.get("assetId"):
                raise ValueError("图片节点需要在右侧绑定 assetType 和 assetId")
            provider = registry.summary()["providers"]["image"]
            task_id = create_target_generation_task(node["projectId"], str(data["assetType"]), str(data["assetId"]), prompt, provider["provider"], provider["model"], float(payload.get("estimatedCost") or 0.18), {"assetType": data["assetType"], "canvasNodeId": node_id}, "图片")
        elif node["type"] == "video":
            shot_id = data.get("shotId")
            if not shot_id:
                raise ValueError("视频节点需要在右侧绑定 shotId")
            provider = registry.summary()["providers"]["video"]
            _project_id, task_id = create_generation_task(str(shot_id), prompt, provider["provider"], provider["model"], float(payload.get("estimatedCost") or 0.73), {"canvasNodeId": node_id}, "视频")
        else:
            raise ValueError("当前可执行节点为 Agent、图片和视频；文本与音频节点先作为工作流输入")
        patch_canvas_node(node_id, {"status": "queued", "data": data})
        task_engine.wake()
        return {"kind": "task", "task": task_response(task_id)}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/projects/{project_id}/runninghub/workflows")
async def get_runninghub_workflows(project_id: str) -> dict[str, Any]:
    try:
        return {"items": list_runninghub_workflows(project_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/projects/{project_id}/runninghub/workflows")
async def post_runninghub_workflow(project_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        workflow = create_runninghub_workflow(project_id, payload)
        record_audit("runninghub.workflow.created", "runninghub_workflow", workflow["id"], {"workflowId": workflow["workflowId"]})
        return {"workflow": workflow}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.patch("/api/runninghub/workflows/{workflow_record_id}")
async def patch_runninghub_workflow_resource(workflow_record_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        project_id, workflow = patch_runninghub_workflow(workflow_record_id, payload)
        record_audit("runninghub.workflow.updated", "runninghub_workflow", workflow_record_id, {"keys": sorted(payload)})
        return {"projectId": project_id, "workflow": workflow}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/runninghub/workflows/{workflow_record_id}")
async def delete_runninghub_workflow_resource(workflow_record_id: str) -> dict[str, Any]:
    try:
        project_id = delete_runninghub_workflow(workflow_record_id)
        record_audit("runninghub.workflow.deleted", "runninghub_workflow", workflow_record_id)
        return {"ok": True, "projectId": project_id}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/runninghub/workflows/{workflow_record_id}/run")
async def run_runninghub_workflow(workflow_record_id: str, payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    with session() as connection:
        row = connection.execute("SELECT * FROM runninghub_workflows WHERE id = ?", (workflow_record_id,)).fetchone()
    if not row:
        raise not_found(f"runninghub workflow {workflow_record_id} not found")
    if not registry.summary()["providers"]["workflow"]["configured"]:
        raise HTTPException(status_code=422, detail="请先在设置中配置 RunningHub API Key")
    api_json = json.loads(row["api_json"] or "{}")
    node_info_list = payload.get("nodeInfoList") or []
    task_id = create_target_generation_task(
        row["project_id"],
        "runninghub_workflow",
        workflow_record_id,
        str(payload.get("prompt") or row["name"]),
        "RunningHub",
        "workflow",
        float(payload.get("estimatedCost") or 0.73),
        {"workflowId": row["workflow_id"], "nodeInfoList": node_info_list, "apiJson": api_json, "retainSeconds": payload.get("retainSeconds")},
        "工作流",
    )
    record_audit("runninghub.workflow.run", "runninghub_workflow", workflow_record_id, {"taskId": task_id})
    task_engine.wake()
    return {"queued": True, "task": task_response(task_id)}


@app.post("/api/runninghub/upload")
async def upload_runninghub_file(request: Request) -> dict[str, Any]:
    if not registry.summary()["providers"]["workflow"]["configured"]:
        raise HTTPException(status_code=422, detail="请先在设置中配置 RunningHub API Key")
    raw_content_type = request.headers.get("content-type", "")
    boundary_marker = "boundary="
    if boundary_marker not in raw_content_type:
        raise HTTPException(status_code=400, detail="上传请求缺少 multipart boundary")
    boundary = raw_content_type.split(boundary_marker, 1)[1].strip().strip('"')
    body = await request.body()
    chunks = body.split(f"--{boundary}".encode("utf-8"))
    file_name = "upload.bin"
    file_content = b""
    for chunk in chunks:
        if b"filename=" not in chunk or b"\r\n\r\n" not in chunk:
            continue
        headers, file_content = chunk.split(b"\r\n\r\n", 1)
        disposition = headers.decode("utf-8", errors="ignore")
        marker = "filename=\""
        if marker in disposition:
            file_name = disposition.split(marker, 1)[1].split("\"", 1)[0]
        file_content = file_content.rstrip(b"\r\n-")
        break
    if not file_content:
        raise HTTPException(status_code=400, detail="未收到上传文件")
    provider = registry.resolve("workflow", "RunningHub", "workflow")
    try:
        return await provider.upload(file_name, file_content, None)
    except Exception as error:  # noqa: BLE001 - surface provider failure as API error
        raise HTTPException(status_code=502, detail=f"RunningHub 文件上传失败：{error}") from error


@app.patch("/api/projects/{project_id}")
async def patch_project_resource(project_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return patch_project(project_id, payload)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/projects/{project_id}/story-bible")
async def get_story_bible(project_id: str) -> dict[str, Any]:
    return project_response(project_id)["storyBible"]


@app.patch("/api/projects/{project_id}/story-bible")
async def patch_story_bible_resource(project_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return patch_story_bible(project_id, payload)["storyBible"]
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/projects/{project_id}/episodes")
async def get_episodes(project_id: str) -> dict[str, Any]:
    project = project_response(project_id)
    return {"items": project["episodes"]}


@app.post("/api/projects/{project_id}/episodes")
async def post_episode(project_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return episode_dict(create_episode(project_id, payload))
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/episodes/{episode_id}")
async def get_episode(episode_id: str) -> dict[str, Any]:
    try:
        return episode_dict(episode_id)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.patch("/api/episodes/{episode_id}")
async def patch_episode_resource(episode_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        project_id = patch_episode(episode_id, payload)
        return next(item for item in project_response(project_id)["episodes"] if item["id"] == episode_id)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/episodes/{episode_id}/scenes")
async def get_scenes(episode_id: str) -> dict[str, Any]:
    return {"items": list_scenes(episode_id)}


@app.post("/api/episodes/{episode_id}/scenes")
async def post_scene(episode_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        scene_id = create_scene(episode_id, payload)
        return next(item for item in list_scenes(episode_id) if item["id"] == scene_id)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/scenes/{scene_id}")
async def get_scene(scene_id: str) -> dict[str, Any]:
    from .core.database import session

    with session() as connection:
        row = connection.execute("SELECT episode_id FROM scenes WHERE id = ? AND archived = 0", (scene_id,)).fetchone()
    if not row:
        raise not_found("场景不存在")
    try:
        return next(item for item in list_scenes(row["episode_id"]) if item["id"] == scene_id)
    except StopIteration as error:
        raise not_found("场景不存在") from error


@app.patch("/api/scenes/{scene_id}")
async def patch_scene_resource(scene_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        project_id = patch_scene(scene_id, payload)
        return {"projectId": project_id, **await get_scene(scene_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/scenes/{scene_id}/shots")
async def get_scene_shots(scene_id: str) -> dict[str, Any]:
    return {"items": list_shots_for_scene(scene_id)}


@app.post("/api/scenes/{scene_id}/shots")
async def post_scene_shot(scene_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        project_id, _ = create_shot(scene_id, payload)
        shot = list_shots_for_scene(scene_id)[-1]
        return {"projectId": project_id, "shot": shot}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/shots/{shot_id}")
async def get_shot(shot_id: str) -> dict[str, Any]:
    return find_shot(shot_id)


@app.patch("/api/shots/{shot_id}")
async def patch_shot_resource(shot_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        project = patch_shot(shot_id, payload)
        return next(item for item in project["shots"] if item["id"] == shot_id)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.delete("/api/shots/{shot_id}")
async def delete_shot_resource(shot_id: str) -> dict[str, Any]:
    try:
        project_id = delete_shot(shot_id)
        return {"ok": True, "projectId": project_id}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/shots/{shot_id}/qc")
async def post_shot_qc(shot_id: str) -> dict[str, Any]:
    try:
        return {"result": run_shot_visual_qc(shot_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/projects/{project_id}/qc")
async def post_project_qc(project_id: str) -> dict[str, Any]:
    project_response(project_id)
    return {"result": run_project_qc(project_id)}


@app.post("/api/projects/{project_id}/continuity-check")
async def post_project_continuity_check(project_id: str) -> dict[str, Any]:
    project_response(project_id)
    return {"result": run_project_continuity_check(project_id)}


@app.get("/api/projects/{project_id}/assets")
async def get_assets(project_id: str) -> dict[str, Any]:
    return project_response(project_id)["assets"]


@app.post("/api/projects/{project_id}/export")
async def export_project(project_id: str) -> Response:
    try:
        filename, content = export_project_package(project_id)
        encoded = quote(filename)
        return Response(content=content, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="short-drama-project-package.zip"; filename*=UTF-8\'\'{encoded}'})
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/projects/{project_id}/audio-clips")
async def get_project_audio_clips(project_id: str, episodeId: Optional[str] = None) -> dict[str, Any]:
    return {"items": list_audio_clips(project_id, episodeId)}


@app.post("/api/projects/{project_id}/audio-clips")
async def post_project_audio_clip(project_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return {"clip": create_audio_clip(project_id, payload)}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.patch("/api/audio-clips/{clip_id}")
async def patch_audio_clip_resource(clip_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return {"clip": patch_audio_clip(clip_id, payload)}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/audio-clips/{clip_id}")
async def delete_audio_clip_resource(clip_id: str) -> dict[str, Any]:
    try:
        return delete_audio_clip(clip_id)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/projects/{project_id}/video-clips")
async def get_project_video_clips(project_id: str, episodeId: Optional[str] = None) -> dict[str, Any]:
    project_response(project_id)
    return {"items": list_video_clips(project_id, episodeId)}


@app.post("/api/projects/{project_id}/video-clips")
async def post_project_video_clip(project_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return {"clip": create_video_clip(project_id, payload)}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.patch("/api/video-clips/{clip_id}")
async def patch_video_clip_resource(clip_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return {"clip": patch_video_clip(clip_id, payload)}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/video-clips/{clip_id}")
async def delete_video_clip_resource(clip_id: str) -> dict[str, Any]:
    try:
        return delete_video_clip(clip_id)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/projects/{project_id}/{asset_type}")
async def post_asset(project_id: str, asset_type: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    if asset_type not in {"characters", "locations", "props"}:
        raise not_found("资产类型不存在")
    try:
        asset_id = create_asset(project_id, asset_type, payload)
        asset = next(item for item in project_response(project_id)["assets"][asset_type] if item["id"] == asset_id)
        return {"projectId": project_id, "asset": asset}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/projects/{project_id}/assets/generate")
async def generate_asset(project_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        result = await generate_asset_image(project_id, payload or {}, registry)
        record_audit("asset.generation_queued", "asset", result["asset"]["id"], {"taskId": result["taskId"], "assetType": result["assetType"]})
        return result
    except KeyError as error:
        raise not_found(str(error)) from error
    except (RuntimeError, TimeoutError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


# Audio Engine -----------------------------------------------------------
@app.get("/api/characters/{character_id}/voice-profiles")
async def get_voice_profiles(character_id: str) -> dict[str, Any]:
    try:
        return {"items": list_voice_profiles(character_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/characters/{character_id}/voice-profiles")
async def post_voice_profile(character_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return {"profile": create_voice_profile(character_id, payload)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.patch("/api/voice-profiles/{profile_id}")
async def patch_voice_profile_resource(profile_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return {"profile": patch_voice_profile(profile_id, payload)}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/voice-profiles/{profile_id}/lock")
async def post_voice_profile_lock(profile_id: str) -> dict[str, Any]:
    try:
        return {"profile": lock_voice_profile(profile_id)}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/voice-profiles/{profile_id}/unlock")
async def post_voice_profile_unlock(profile_id: str) -> dict[str, Any]:
    try:
        return {"profile": unlock_voice_profile(profile_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/voice-profiles/{profile_id}/test")
async def post_voice_profile_test(profile_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        result = test_voice_profile(profile_id, payload or {})
        task_engine.wake()
        return {**result, "task": task_response(result["taskId"])}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/scenes/{scene_id}/dialogue-lines")
async def get_scene_dialogue_lines(scene_id: str) -> dict[str, Any]:
    try:
        return {"items": list_dialogue_lines(scene_id=scene_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/scenes/{scene_id}/dialogue-lines/extract")
async def post_scene_dialogue_extract(scene_id: str) -> dict[str, Any]:
    try:
        return {"items": extract_dialogue_lines(scene_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/scenes/{scene_id}/dialogue-lines")
async def post_scene_dialogue_line(scene_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return {"line": create_dialogue_line(scene_id, payload)}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/episodes/{episode_id}/dialogue-lines")
async def get_episode_dialogue_lines(episode_id: str) -> dict[str, Any]:
    return {"items": list_dialogue_lines(episode_id=episode_id)}


@app.post("/api/episodes/{episode_id}/generate-dialogue")
async def post_episode_generate_dialogue(episode_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        result = generate_episode_dialogue(episode_id, payload or {})
        task_engine.wake()
        return {**result, "tasks": [task_response(item["taskId"]) for item in result["created"]]}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/episodes/{episode_id}/audio-status")
async def get_episode_audio_status(episode_id: str) -> dict[str, Any]:
    return audio_status(episode_id)


@app.patch("/api/dialogue-lines/{line_id}")
async def patch_dialogue_line_resource(line_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return {"line": patch_dialogue_line(line_id, payload)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/dialogue-lines/{line_id}/direct-performance")
async def post_direct_performance(line_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        return {"performance": direct_performance(line_id, payload or {})}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/dialogue-lines/{line_id}/generate")
async def post_dialogue_generate(line_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        result = generate_dialogue_line(line_id, payload or {})
        task_engine.wake()
        return {**result, "task": task_response(result["taskId"])}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/dialogue-lines/{line_id}/takes")
async def get_dialogue_takes(line_id: str) -> dict[str, Any]:
    try:
        return {"items": list_takes(line_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/voice-takes/{take_id}/activate")
async def post_take_activate(take_id: str) -> dict[str, Any]:
    try:
        return {"take": activate_take(take_id)}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/voice-takes/{take_id}/run-qc")
async def post_take_qc(take_id: str) -> dict[str, Any]:
    try:
        return run_qc(take_id)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/voice-providers")
async def get_voice_providers() -> dict[str, Any]:
    return {"items": provider_definitions(), "provider": registry.summary()}


@app.post("/api/episodes/{episode_id}/mixdown")
async def post_episode_mixdown(episode_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        return {"mixdown": mixdown_episode(episode_id, payload or {})}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/episodes/{episode_id}/render")
async def post_episode_render(episode_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        render = await asyncio.to_thread(render_episode_mp4, episode_id, payload or {})
        record_audit("timeline.rendered", "render_job", render["id"], {"episodeId": episode_id, "status": render["status"]})
        return {"render": render}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/episodes/{episode_id}/renders")
async def get_episode_renders(episode_id: str) -> dict[str, Any]:
    return {"items": list_render_jobs(episode_id)}


@app.get("/generated-media/{filename}")
async def get_generated_media(filename: str):
    from fastapi.responses import FileResponse

    candidates = [(DATA_DIR / "generated-audio" / filename).resolve(), (DATA_DIR / "generated-video" / filename).resolve()]
    candidate = next((item for item in candidates if item.is_file()), candidates[0])
    if DATA_DIR.resolve() not in candidate.parents or not candidate.is_file():
        raise not_found("音频文件不存在")
    return FileResponse(candidate)


# Character Asset Engine -------------------------------------------------
@app.get("/api/projects/{project_id}/characters")
async def get_project_characters(project_id: str) -> dict[str, Any]:
    project_response(project_id)
    return {"items": list_characters(project_id)}


@app.post("/api/projects/{project_id}/characters")
async def post_project_character(project_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return {"character": create_character(project_id, payload)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/characters/{character_id}")
async def get_character_resource(character_id: str) -> dict[str, Any]:
    try:
        return get_character(character_id)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.patch("/api/characters/{character_id}")
async def patch_character_resource(character_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return patch_character(character_id, payload)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/characters/{character_id}/extract-anchors")
async def post_character_anchors(character_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        return {"characterId": character_id, "identityAnchors": extract_identity_anchors(character_id, payload or {})}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/characters/{character_id}/generate-candidates")
async def post_character_candidates(character_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        result = generate_character_candidates(character_id, payload or {})
        task_engine.wake()
        return {**result, "character": get_character(character_id), "tasks": [task_response(task_id) for task_id in result["taskIds"]]}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/characters/{character_id}/generate-master-sheet")
async def post_character_master_sheet(character_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        result = generate_master_sheet(character_id, payload or {})
        task_engine.wake()
        return {**result, "task": task_response(result["taskId"])}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/characters/{character_id}/canonical")
async def post_character_canonical(character_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return set_canonical_reference(character_id, payload.get("referenceId") or payload.get("reference_id", ""))
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/characters/{character_id}/lock")
async def post_character_lock(character_id: str) -> dict[str, Any]:
    try:
        return lock_character(character_id)
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/characters/{character_id}/unlock")
async def post_character_unlock(character_id: str) -> dict[str, Any]:
    try:
        return unlock_character(character_id)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/characters/{character_id}/looks")
async def get_character_looks(character_id: str) -> dict[str, Any]:
    try:
        return {"items": list_looks(character_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/characters/{character_id}/looks")
async def post_character_look(character_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return {"look": create_look(character_id, payload)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.patch("/api/character-looks/{look_id}")
async def patch_character_look(look_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return patch_look(look_id, payload)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/characters/{character_id}/references")
async def get_character_references(character_id: str) -> dict[str, Any]:
    try:
        return {"items": list_references(character_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/characters/{character_id}/references")
async def post_character_reference(character_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return {"reference": create_reference(character_id, payload)}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/character-references/{reference_id}/approve")
async def approve_character_reference(reference_id: str) -> dict[str, Any]:
    try:
        return {"reference": review_reference(reference_id, "approved")}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/character-references/{reference_id}/reject")
async def reject_character_reference(reference_id: str) -> dict[str, Any]:
    try:
        return {"reference": review_reference(reference_id, "rejected")}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/characters/{character_id}/affected-shots")
async def get_character_affected_shots(character_id: str, look_id: Optional[str] = None) -> dict[str, Any]:
    try:
        return affected_shots_for_character(character_id, look_id)
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/character-looks/{look_id}/affected-shots")
async def get_look_affected_shots(look_id: str) -> dict[str, Any]:
    from .core.database import session

    with session() as connection:
        row = connection.execute("SELECT character_id FROM character_looks WHERE id = ?", (look_id,)).fetchone()
    if not row:
        raise not_found("look not found")
    return affected_shots_for_character(row["character_id"], look_id)


@app.get("/api/shots/{shot_id}/characters")
async def get_shot_character_bindings(shot_id: str) -> dict[str, Any]:
    try:
        return {"items": get_shot_characters(shot_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.put("/api/shots/{shot_id}/characters")
async def put_shot_character_bindings(shot_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    bindings = payload.get("items") if isinstance(payload, dict) else payload
    try:
        return {"items": bind_shot_characters(shot_id, bindings or [])}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.patch("/api/assets/{asset_id}")
async def patch_asset_resource(asset_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        project_id = patch_asset(asset_id, payload)
        return {"projectId": project_id, "assets": project_response(project_id)["assets"]}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/assets/{asset_id}/affected-shots")
async def get_affected_shots(asset_id: str) -> dict[str, Any]:
    return {"assetId": asset_id, "shotIds": affected_shots(asset_id)}


@app.post("/api/shots/{shot_id}/generate")
async def generate_shot(shot_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    payload = payload or {}
    shot = await get_shot(shot_id)
    summary = registry.summary()
    provider = payload.get("provider") or summary["provider"]
    model = payload.get("model") or (registry.video_model if summary["mode"] == "remote" else "mock-video")
    estimated_cost = float(payload.get("estimatedCost") or (0.73 if summary["mode"] == "demo" else os.environ.get("SHORT_DRAMA_ESTIMATED_COST", "0.73")))
    reference_context = shot_generation_context(shot_id)
    try:
        project_id, task_id = create_generation_task(shot_id, payload.get("prompt") or shot.get("prompt", ""), provider, model, estimated_cost, {"references": reference_context["references"]})
    except KeyError as error:
        raise not_found(str(error)) from error
    task_engine.wake()
    return {"task": task_response(task_id), "project": project_response(project_id), "provider": provider, "references": reference_context["references"]}


@app.get("/api/generation-tasks/{task_id}")
async def get_generation_task(task_id: str) -> dict[str, Any]:
    return task_response(task_id)


@app.post("/api/generation-tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> dict[str, Any]:
    try:
        project_id = cancel_generation_task(task_id)
        task_engine.wake()
        return {"task": task_response(task_id), "project": project_response(project_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/generation-tasks/{task_id}/retry")
async def retry_task(task_id: str) -> dict[str, Any]:
    try:
        project_id, _ = retry_generation_task(task_id)
        task_engine.wake()
        return {"task": task_response(task_id), "project": project_response(project_id)}
    except KeyError as error:
        raise not_found(str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/shots/{shot_id}/versions")
async def get_versions(shot_id: str) -> dict[str, Any]:
    return {"items": list_versions(shot_id)}


@app.post("/api/versions/{version_id}/activate")
async def post_activate_version(version_id: str) -> dict[str, Any]:
    try:
        shot_id = activate_version(version_id)
        return {"ok": True, "shotId": shot_id, "versions": list_versions(shot_id)}
    except KeyError as error:
        raise not_found(str(error)) from error


@app.get("/api/projects/{project_id}/costs")
async def get_project_costs(project_id: str) -> dict[str, Any]:
    project_response(project_id)
    return list_costs(project_id)


@app.get("/api/projects/{project_id}/qc")
async def get_project_qc(project_id: str) -> dict[str, Any]:
    project_response(project_id)
    return {"items": list_qc(project_id=project_id)}


@app.post("/api/shots/{shot_id}/review")
async def review_shot(shot_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    payload = payload or {}
    return await patch_shot_resource(shot_id, {"reviewed": payload.get("reviewed", True)})


@app.get("/api/models")
async def get_models() -> dict[str, Any]:
    return {"items": list_models(), "provider": registry.summary()}


@app.post("/api/episodes/{episode_id}/matrix")
async def post_episode_matrix(episode_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(generate_episode_matrix_ai, episode_id, payload or {})
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/scenes/{scene_id}/script")
async def post_scene_script(scene_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(generate_scene_script_ai, scene_id, payload or {})
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/scenes/{scene_id}/breakdown")
async def post_scene_breakdown(scene_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        return {"items": await asyncio.to_thread(generate_shot_breakdown_ai, scene_id, payload or {})}
    except KeyError as error:
        raise not_found(str(error)) from error


# Compatibility endpoints for the existing frontend and older desktop builds.
@app.get("/api/project")
async def get_project_legacy() -> dict[str, Any]:
    return project_response(PROJECT_ID)


@app.put("/api/project")
async def put_project_legacy(project: dict[str, Any] = Body(...)) -> dict[str, Any]:
    if not project.get("id"):
        raise HTTPException(status_code=422, detail="项目数据格式无效")
    seed_legacy_project(project)
    return project_response(project["id"])


@app.post("/api/generations")
async def create_generation_legacy(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return await generate_shot(payload.get("shot_id") or payload.get("shotId"), {"prompt": payload.get("prompt", "")})


@app.get("/{path:path}")
async def serve_client(path: str = ""):
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    if not DIST_DIR.exists():
        raise HTTPException(status_code=404, detail="前端尚未构建，请先运行 npm.cmd run build")
    candidate = (DIST_DIR / path).resolve()
    if candidate.is_file() and DIST_DIR.resolve() in candidate.parents:
        from fastapi.responses import FileResponse

        return FileResponse(candidate)
    from fastapi.responses import FileResponse

    return FileResponse(DIST_DIR / "index.html")


if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), reload=False)
