from __future__ import annotations

import os
from urllib.parse import quote
from typing import Any, Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .core.config import DB_PATH, DIST_DIR, PROJECT_ID
from .core.database import init_database
from .domain.repository import (
    activate_version,
    affected_shots,
    cancel_generation_task,
    create_episode,
    create_asset,
    create_generation_task,
    create_project,
    create_scene,
    create_shot,
    delete_shot,
    episode_dict,
    generation_task,
    list_costs,
    list_models,
    list_projects,
    list_qc,
    list_scenes,
    list_shots_for_scene,
    list_versions,
    patch_asset,
    patch_episode,
    patch_project,
    patch_scene,
    patch_shot,
    patch_story_bible,
    project_to_dict,
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
from .providers.registry import ProviderRegistry
from .services.export_service import export_project_package
from .services.asset_generation_service import generate_asset_image
from .services.script_service import generate_episode_matrix, generate_scene_script, generate_shot_breakdown
from .services.task_engine import task_engine


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
    task_engine.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    task_engine.stop()


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "database": str(DB_PATH), "schemaVersion": 2, **registry.summary()}


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
        return await generate_asset_image(project_id, payload or {}, registry)
    except KeyError as error:
        raise not_found(str(error)) from error
    except (RuntimeError, TimeoutError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


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
    model = payload.get("model") or (registry.external_model if summary["mode"] == "remote" else "mock-video")
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
        return generate_episode_matrix(episode_id, payload or {})
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/scenes/{scene_id}/script")
async def post_scene_script(scene_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        return generate_scene_script(scene_id, payload or {})
    except KeyError as error:
        raise not_found(str(error)) from error


@app.post("/api/scenes/{scene_id}/breakdown")
async def post_scene_breakdown(scene_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        return {"items": generate_shot_breakdown(scene_id, payload or {})}
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
