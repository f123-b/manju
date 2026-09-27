from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any

from ..core.database import session


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def loads(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


CANVAS_NODE_TYPES = {"text", "script", "image", "video", "audio", "agent", "asset"}

DEFAULT_CANVAS_NODES = [
    ("story", "text", "故事灵感", 120, 160, {"content": "从一句话灵感开始，逐步连接到脚本、分镜和生成任务。", "accent": "violet"}),
    ("agent", "agent", "剧本 Agent", 440, 160, {"content": "读取故事圣经，生成剧集矩阵和可拍分镜。", "accent": "blue"}),
    ("script", "script", "场景剧本", 760, 160, {"content": "把冲突拆成动作、对白和声音节拍。", "accent": "amber"}),
    ("shot", "image", "镜头画面", 1080, 160, {"content": "生成角色一致的镜头画面。", "shotId": "SH041", "accent": "pink"}),
    ("reference", "asset", "角色 / 场景参考", 120, 470, {"content": "拖入或选择已审核的角色、场景资产。", "accent": "green"}),
    ("video", "video", "视频生成", 760, 470, {"content": "用画面和提示词生成视频片段。", "shotId": "SH041", "model": "mock-video", "accent": "cyan"}),
    ("timeline", "audio", "时间线 / 音频", 1080, 470, {"content": "把视频、对白和声音送入时间线。", "accent": "slate"}),
]


def _ensure_canvas_seed(connection: sqlite3.Connection, project_id: str) -> None:
    if connection.execute("SELECT 1 FROM canvas_nodes WHERE project_id = ? LIMIT 1", (project_id,)).fetchone():
        return
    ids: dict[str, str] = {}
    for key, node_type, title, x, y, data in DEFAULT_CANVAS_NODES:
        node_id = f"CN-{project_id}-{key}"
        ids[key] = node_id
        connection.execute(
            "INSERT OR IGNORE INTO canvas_nodes(id, project_id, node_type, title, x, y, width, height, status, data_json) VALUES (?, ?, ?, ?, ?, ?, 280, 180, 'idle', ?)",
            (node_id, project_id, node_type, title, x, y, dumps(data)),
        )
    for source, target, label in (("story", "agent", "上下文"), ("agent", "script", "结构化输出"), ("script", "shot", "镜头描述"), ("reference", "shot", "参考素材"), ("shot", "video", "首帧 / 提示词"), ("video", "timeline", "成片片段")):
        connection.execute(
            "INSERT OR IGNORE INTO canvas_edges(id, project_id, source_node_id, target_node_id, label) VALUES (?, ?, ?, ?, ?)",
            (f"CE-{project_id}-{source}-{target}", project_id, ids[source], ids[target], label),
        )


def _canvas_node_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "type": row["node_type"],
        "title": row["title"],
        "x": row["x"],
        "y": row["y"],
        "width": row["width"],
        "height": row["height"],
        "status": row["status"],
        "data": loads(row["data_json"], {}),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _canvas_edge_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "source": row["source_node_id"],
        "target": row["target_node_id"],
        "label": row["label"],
        "createdAt": row["created_at"],
    }


def list_canvas(project_id: str) -> dict[str, Any]:
    with session() as connection:
        _project_row(connection, project_id)
        _ensure_canvas_seed(connection, project_id)
        nodes = connection.execute("SELECT * FROM canvas_nodes WHERE project_id = ? ORDER BY created_at, id", (project_id,)).fetchall()
        edges = connection.execute("SELECT * FROM canvas_edges WHERE project_id = ? ORDER BY created_at, id", (project_id,)).fetchall()
        return {"projectId": project_id, "nodes": [_canvas_node_dict(row) for row in nodes], "edges": [_canvas_edge_dict(row) for row in edges]}


def create_canvas_node(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    node_type = str(payload.get("type") or payload.get("nodeType") or "text").lower()
    if node_type not in CANVAS_NODE_TYPES:
        raise ValueError(f"不支持的画布节点类型：{node_type}")
    with session() as connection:
        _project_row(connection, project_id)
        node_id = new_id("CN-")
        connection.execute(
            """INSERT INTO canvas_nodes(id, project_id, node_type, title, x, y, width, height, status, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (node_id, project_id, node_type, str(payload.get("title") or "新节点"), float(payload.get("x", 120)), float(payload.get("y", 120)), float(payload.get("width", 280)), float(payload.get("height", 180)), str(payload.get("status") or "idle"), dumps(payload.get("data") or {})),
        )
        return _canvas_node_dict(connection.execute("SELECT * FROM canvas_nodes WHERE id = ?", (node_id,)).fetchone())


def patch_canvas_node(node_id: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    allowed = {"title", "x", "y", "width", "height", "status", "data_json"}
    values: list[tuple[str, Any]] = []
    for key, value in payload.items():
        database_key = "data_json" if key == "data" else key
        if database_key not in allowed:
            continue
        if database_key == "data_json":
            value = dumps(value)
        values.append((database_key, value))
    if not values:
        raise ValueError("没有可更新的画布节点字段")
    with session() as connection:
        row = connection.execute("SELECT project_id FROM canvas_nodes WHERE id = ?", (node_id,)).fetchone()
        if not row:
            raise KeyError(f"canvas node {node_id} not found")
        columns = ", ".join(f"{key} = ?" for key, _ in values)
        connection.execute(f"UPDATE canvas_nodes SET {columns}, updated_at = ? WHERE id = ?", [value for _, value in values] + [now_text(), node_id])
        return row["project_id"], _canvas_node_dict(connection.execute("SELECT * FROM canvas_nodes WHERE id = ?", (node_id,)).fetchone())


def delete_canvas_node(node_id: str) -> str:
    with session() as connection:
        row = connection.execute("SELECT project_id FROM canvas_nodes WHERE id = ?", (node_id,)).fetchone()
        if not row:
            raise KeyError(f"canvas node {node_id} not found")
        connection.execute("DELETE FROM canvas_nodes WHERE id = ?", (node_id,))
        return row["project_id"]


def create_canvas_edge(project_id: str, source_node_id: str, target_node_id: str, label: str = "") -> dict[str, Any]:
    if source_node_id == target_node_id:
        raise ValueError("画布节点不能连接到自身")
    with session() as connection:
        _project_row(connection, project_id)
        nodes = connection.execute("SELECT id, project_id FROM canvas_nodes WHERE id IN (?, ?)", (source_node_id, target_node_id)).fetchall()
        if len(nodes) != 2 or any(row["project_id"] != project_id for row in nodes):
            raise KeyError("画布连接节点不存在")
        edge_id = new_id("CE-")
        try:
            connection.execute("INSERT INTO canvas_edges(id, project_id, source_node_id, target_node_id, label) VALUES (?, ?, ?, ?, ?)", (edge_id, project_id, source_node_id, target_node_id, label))
        except sqlite3.IntegrityError as error:
            raise ValueError("这两个节点已经连接") from error
        return _canvas_edge_dict(connection.execute("SELECT * FROM canvas_edges WHERE id = ?", (edge_id,)).fetchone())


def delete_canvas_edge(edge_id: str) -> str:
    with session() as connection:
        row = connection.execute("SELECT project_id FROM canvas_edges WHERE id = ?", (edge_id,)).fetchone()
        if not row:
            raise KeyError(f"canvas edge {edge_id} not found")
        connection.execute("DELETE FROM canvas_edges WHERE id = ?", (edge_id,))
        return row["project_id"]


def _runninghub_workflow_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "workflowId": row["workflow_id"],
        "name": row["name"],
        "description": row["description"],
        "apiJson": loads(row["api_json"], {}),
        "status": row["status"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def list_runninghub_workflows(project_id: str) -> list[dict[str, Any]]:
    with session() as connection:
        _project_row(connection, project_id)
        rows = connection.execute("SELECT * FROM runninghub_workflows WHERE project_id = ? ORDER BY updated_at DESC, created_at DESC", (project_id,)).fetchall()
        return [_runninghub_workflow_dict(row) for row in rows]


def create_runninghub_workflow(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    api_json = payload.get("apiJson") or payload.get("api_json") or {}
    if not isinstance(api_json, dict):
        raise ValueError("工作流 JSON 必须是对象")
    name = str(payload.get("name") or "未命名工作流").strip() or "未命名工作流"
    with session() as connection:
        _project_row(connection, project_id)
        workflow_id = new_id("RHW-")
        connection.execute(
            "INSERT INTO runninghub_workflows(id, project_id, workflow_id, name, description, api_json, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (workflow_id, project_id, str(payload.get("workflowId") or ""), name, str(payload.get("description") or ""), dumps(api_json), str(payload.get("status") or "draft")),
        )
        return _runninghub_workflow_dict(connection.execute("SELECT * FROM runninghub_workflows WHERE id = ?", (workflow_id,)).fetchone())


def patch_runninghub_workflow(workflow_record_id: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    allowed = {"workflow_id", "name", "description", "api_json", "status"}
    values: list[tuple[str, Any]] = []
    for key, value in payload.items():
        database_key = {"workflowId": "workflow_id", "apiJson": "api_json"}.get(key, key)
        if database_key not in allowed:
            continue
        if database_key == "api_json":
            if not isinstance(value, dict):
                raise ValueError("工作流 JSON 必须是对象")
            value = dumps(value)
        values.append((database_key, value))
    if not values:
        raise ValueError("没有可更新的工作流字段")
    with session() as connection:
        row = connection.execute("SELECT project_id FROM runninghub_workflows WHERE id = ?", (workflow_record_id,)).fetchone()
        if not row:
            raise KeyError(f"runninghub workflow {workflow_record_id} not found")
        columns = ", ".join(f"{key} = ?" for key, _ in values)
        connection.execute(f"UPDATE runninghub_workflows SET {columns}, updated_at = ? WHERE id = ?", [value for _, value in values] + [now_text(), workflow_record_id])
        return row["project_id"], _runninghub_workflow_dict(connection.execute("SELECT * FROM runninghub_workflows WHERE id = ?", (workflow_record_id,)).fetchone())


def delete_runninghub_workflow(workflow_record_id: str) -> str:
    with session() as connection:
        row = connection.execute("SELECT project_id FROM runninghub_workflows WHERE id = ?", (workflow_record_id,)).fetchone()
        if not row:
            raise KeyError(f"runninghub workflow {workflow_record_id} not found")
        connection.execute("DELETE FROM runninghub_workflows WHERE id = ?", (workflow_record_id,))
        return row["project_id"]


def _project_row(connection: sqlite3.Connection, project_id: str):
    row = connection.execute("SELECT * FROM projects WHERE id = ? AND archived = 0", (project_id,)).fetchone()
    if not row:
        raise KeyError(f"project {project_id} not found")
    return row


def _episode_for_scene(connection: sqlite3.Connection, scene_id: str):
    return connection.execute(
        "SELECT e.* FROM episodes e JOIN scenes s ON s.episode_id = e.id WHERE s.id = ?",
        (scene_id,),
    ).fetchone()


def _shot_context(connection: sqlite3.Connection, shot_id: str):
    return connection.execute(
        """
        SELECT s.*, sc.episode_id, e.project_id
        FROM shots s
        JOIN scenes sc ON sc.id = s.scene_id
        JOIN episodes e ON e.id = sc.episode_id
        WHERE s.id = ? AND s.archived = 0
        """,
        (shot_id,),
    ).fetchone()


def _shot_dict(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    characters = connection.execute(
        "SELECT character_id, outfit_id, look_id, primary_reference_id, position, emotion, action, state_json, continuity_overrides_json FROM shot_characters WHERE shot_id = ? ORDER BY position, character_id",
        (row["id"],),
    ).fetchall()
    versions = connection.execute(
        "SELECT * FROM generation_versions WHERE shot_id = ? ORDER BY version_number",
        (row["id"],),
    ).fetchall()
    return {
        "id": row["id"],
        "episodeId": row["episode_id"],
        "sceneId": row["scene_id"],
        "order": row["order_index"],
        "time": row["timecode"],
        "description": row["description"],
        "size": row["shot_size"],
        "frame": row["frame"],
        "lens": row["lens"],
        "angle": row["camera_angle"],
        "movement": row["movement"],
        "duration": row["duration"],
        "action": row["action"],
        "emotion": row["emotion"],
        "dialogue": row["dialogue"],
        "prompt": row["prompt"],
        "negativePrompt": row["negative_prompt"],
        "image": row["image"],
        "status": row["status"],
        "reviewed": bool(row["reviewed"]),
        "qcScore": row["qc_score"],
        "cost": round(float(row["cost"] or 0), 2),
        "stale": bool(row["stale"]) if "stale" in row.keys() else False,
        "staleReason": row["stale_reason"] if "stale_reason" in row.keys() else "",
        "characterIds": [item["character_id"] for item in characters],
        "outfitId": next((item["outfit_id"] for item in characters if item["outfit_id"]), None),
        "characterBindings": [
            {
                "characterId": item["character_id"],
                "outfitId": item["outfit_id"],
                "lookId": item["look_id"] or item["outfit_id"],
                "primaryReferenceId": item["primary_reference_id"],
                "position": item["position"],
                "emotion": item["emotion"],
                "action": item["action"],
                "state": loads(item["state_json"], {}),
                "continuityOverrides": loads(item["continuity_overrides_json"], {}),
            }
            for item in characters
        ],
        "versions": [
            {
                "id": item["id"],
                "createdAt": item["created_at"],
                "active": bool(item["is_active"]),
                "outputUrl": _asset_url(connection, item["media_asset_id"]),
                "provider": item["provider"],
                "model": item["model"],
                "actualCost": item["actual_cost"],
            }
            for item in versions
        ],
    }


def _asset_url(connection: sqlite3.Connection, asset_id: str | None) -> str | None:
    if not asset_id:
        return None
    row = connection.execute("SELECT path_or_url FROM media_assets WHERE id = ?", (asset_id,)).fetchone()
    return row["path_or_url"] if row else None


def project_to_dict(project_id: str) -> dict[str, Any]:
    from .character_assets import character_dict
    from .audio_engine import list_audio_clips, list_dialogue_lines, list_mixdowns
    from .video_engine import list_video_clips

    with session() as connection:
        project = _project_row(connection, project_id)
        bible = connection.execute("SELECT * FROM story_bibles WHERE project_id = ?", (project_id,)).fetchone()
        episodes = connection.execute(
            "SELECT * FROM episodes WHERE project_id = ? AND archived = 0 ORDER BY order_index",
            (project_id,),
        ).fetchall()
        shots = connection.execute(
            """
            SELECT s.*, sc.episode_id, e.project_id
            FROM shots s JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id
            WHERE e.project_id = ? AND s.archived = 0 ORDER BY e.order_index, sc.order_index, s.order_index
            """,
            (project_id,),
        ).fetchall()
        characters = connection.execute("SELECT * FROM characters WHERE project_id = ? AND archived = 0 ORDER BY id", (project_id,)).fetchall()
        locations = connection.execute("SELECT * FROM locations WHERE project_id = ? AND archived = 0 ORDER BY id", (project_id,)).fetchall()
        props = connection.execute("SELECT * FROM props WHERE project_id = ? AND archived = 0 ORDER BY id", (project_id,)).fetchall()
        tasks = connection.execute("SELECT * FROM generation_tasks WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        render_jobs = connection.execute("SELECT * FROM render_jobs WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        audio_lines = list_dialogue_lines(project_id=project_id)
        audio_clips = list_audio_clips(project_id)
        audio_mixdowns = list_mixdowns(project_id)
        video_clips = list_video_clips(project_id)
        current_scene = connection.execute(
            """
            SELECT s.* FROM scenes s JOIN episodes e ON e.id = s.episode_id
            WHERE e.id = ? AND s.archived = 0 ORDER BY s.order_index LIMIT 1
            """,
            (project["current_episode_id"],),
        ).fetchone()
        result_episodes = []
        for episode in episodes:
            scene_count = connection.execute("SELECT COUNT(*) AS count FROM scenes WHERE episode_id = ? AND archived = 0", (episode["id"],)).fetchone()["count"]
            shot_count = connection.execute(
                "SELECT COUNT(*) AS count FROM shots s JOIN scenes sc ON sc.id = s.scene_id WHERE sc.episode_id = ? AND s.archived = 0",
                (episode["id"],),
            ).fetchone()["count"]
            result_episodes.append({
                "id": episode["id"], "title": episode["title"], "status": episode["status"],
                "hook": episode["opening_hook"], "summary": episode["summary"],
                "openingHook": episode["opening_hook"], "coreEvent": episode["core_event"],
                "payoff": episode["payoff"], "twist": episode["twist"], "endingHook": episode["ending_hook"],
                "order": episode["order_index"], "locked": bool(episode["locked"]),
                "scenes": scene_count, "shots": shot_count, "duration": episode["duration"],
            })
        return {
            "schemaVersion": 2,
            "id": project["id"], "title": project["title"], "status": project["status"],
            "format": project["format"], "targetEpisodes": project["target_episodes"],
            "currentEpisodeId": project["current_episode_id"], "dueDate": project["due_date"],
            "budget": project["budget"], "spent": round(float(project["spent"] or 0), 2),
            "production": {
                "totalShots": project["total_shots"],
                "generatedShots": project["generated_shots"],
                "qcScore": project["qc_score"],
            },
            "storyBible": {
                "logline": bible["logline"] if bible else "", "coreConflict": bible["core_conflict"] if bible else "",
                "mainLine": bible["main_line"] if bible else "", "theme": bible["theme"] if bible else "",
                "ending": bible["ending"] if bible else "", "world": bible["world"] if bible else "",
                "style": bible["style"] if bible else "", "rules": loads(bible["rules_json"], []) if bible else [],
            },
            "episodes": result_episodes,
            "currentScene": {
                "id": current_scene["id"], "number": current_scene["order_index"], "title": current_scene["title"],
                "purpose": current_scene["purpose"], "summary": current_scene["summary"],
            } if current_scene else None,
            "shots": [_shot_dict(connection, row) for row in shots],
            "assets": {
                "characters": [character_dict(connection, item) for item in characters],
                "locations": [{"id": item["id"], "name": item["name"], "meta": item["meta"], "description": item["description"], "image": item["image"], "status": item["status"]} for item in locations],
                "props": [{"id": item["id"], "name": item["name"], "meta": item["meta"], "description": item["description"], "image": item["image"], "status": item["status"]} for item in props],
            },
            "audio": {
                "dialogueLines": audio_lines,
                "clips": audio_clips,
                "mixdowns": audio_mixdowns,
                "counts": {
                    "lines": len(audio_lines),
                    "ready": sum(1 for line in audio_lines if line.get("activeTake")),
                    "stale": sum(1 for line in audio_lines if line.get("stale")),
                },
            },
            "timeline": {"videoClips": video_clips},
            "tasks": [
                {"id": item["id"], "shotId": item["shot_id"], "targetType": item["target_type"], "targetId": item["target_id"], "type": item["type"], "provider": item["provider"], "model": item["model"], "status": item["status"], "cost": round(float(item["actual_cost"] if item["actual_cost"] is not None else item["estimated_cost"]), 2), "createdAt": item["created_at"], "error": item["error_message"], "progress": item["progress"]}
                for item in tasks
            ] + [
                {"id": item["id"], "shotId": None, "targetType": "render", "targetId": item["episode_id"], "type": "渲染", "provider": "local", "model": "FFmpeg", "status": {"queued": "Queued", "running": "Running", "ready": "Success", "failed": "Failed", "blocked": "Blocked"}.get(item["status"], item["status"]), "cost": 0, "createdAt": item["created_at"], "error": item["error_message"], "progress": 100 if item["status"] == "ready" else 0}
                for item in render_jobs
            ],
        }


def project_ids() -> list[str]:
    with session() as connection:
        return [row["id"] for row in connection.execute("SELECT id FROM projects WHERE archived = 0 ORDER BY updated_at DESC").fetchall()]


def list_projects() -> list[dict[str, Any]]:
    with session() as connection:
        rows = connection.execute("SELECT * FROM projects WHERE archived = 0 ORDER BY updated_at DESC").fetchall()
        return [
            {
                "id": row["id"], "title": row["title"], "status": row["status"],
                "format": row["format"], "targetEpisodes": row["target_episodes"],
                "currentEpisodeId": row["current_episode_id"], "budget": row["budget"],
                "spent": round(float(row["spent"] or 0), 2),
                "generatedShots": row["generated_shots"], "totalShots": row["total_shots"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ]


def create_project(payload: dict[str, Any]) -> str:
    project_id = payload.get("id") or new_id("P-")
    data = {
        "schemaVersion": 2,
        "id": project_id,
        "title": payload.get("title", "未命名短剧"),
        "status": payload.get("status", "策划中"),
        "format": payload.get("format", "16:9"),
        "targetEpisodes": int(payload.get("targetEpisodes", 1)),
        "currentEpisodeId": payload.get("currentEpisodeId", "EP01"),
        "dueDate": payload.get("dueDate"),
        "budget": float(payload.get("budget", 0)),
        "spent": 0,
        "production": {"totalShots": 0, "generatedShots": 0, "qcScore": 0},
        "storyBible": payload.get("storyBible", {}),
        "episodes": payload.get("episodes") or [{"id": "EP01", "title": "第 01 集", "status": "待策划"}],
        "assets": payload.get("assets", {"characters": [], "locations": [], "props": []}),
        "shots": payload.get("shots", []),
        "tasks": [],
    }
    from .seed import seed_legacy_project

    seed_legacy_project(data)
    return project_id


def patch_project(project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    allowed = {"title": "title", "status": "status", "format": "format", "targetEpisodes": "target_episodes", "currentEpisodeId": "current_episode_id", "dueDate": "due_date", "budget": "budget"}
    values = [(allowed[key], value) for key, value in patch.items() if key in allowed]
    if not values:
        return project_to_dict(project_id)
    values.append(("updated_at", now_text()))
    with session() as connection:
        _project_row(connection, project_id)
        columns = ", ".join(f"{column} = ?" for column, _ in values)
        connection.execute(f"UPDATE projects SET {columns} WHERE id = ?", [value for _, value in values] + [project_id])
    return project_to_dict(project_id)


def patch_story_bible(project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    allowed = {"logline": "logline", "coreConflict": "core_conflict", "mainLine": "main_line", "theme": "theme", "ending": "ending", "world": "world", "style": "style", "rules": "rules_json"}
    values = []
    for key, value in patch.items():
        if key in allowed:
            values.append((allowed[key], dumps(value) if key == "rules" else value))
    if values:
        values.append(("updated_at", now_text()))
        with session() as connection:
            columns = ", ".join(f"{column} = ?" for column, _ in values)
            connection.execute(f"UPDATE story_bibles SET {columns} WHERE project_id = ?", [value for _, value in values] + [project_id])
    return project_to_dict(project_id)


def episode_row(episode_id: str):
    with session() as connection:
        return connection.execute("SELECT * FROM episodes WHERE id = ? AND archived = 0", (episode_id,)).fetchone()


def episode_dict(episode_id: str) -> dict[str, Any]:
    with session() as connection:
        row = connection.execute("SELECT * FROM episodes WHERE id = ? AND archived = 0", (episode_id,)).fetchone()
        if not row:
            raise KeyError(f"episode {episode_id} not found")
        return {
            "id": row["id"], "projectId": row["project_id"], "order": row["order_index"],
            "title": row["title"], "summary": row["summary"], "hook": row["opening_hook"],
            "openingHook": row["opening_hook"], "coreEvent": row["core_event"],
            "payoff": row["payoff"], "twist": row["twist"], "endingHook": row["ending_hook"],
            "status": row["status"], "duration": row["duration"], "locked": bool(row["locked"]),
        }


def list_episodes(project_id: str) -> list[dict[str, Any]]:
    project_to_dict(project_id)
    return project_to_dict(project_id)["episodes"]


def create_episode(project_id: str, payload: dict[str, Any]) -> str:
    with session() as connection:
        _project_row(connection, project_id)
        order_index = connection.execute("SELECT COALESCE(MAX(order_index), 0) + 1 AS next FROM episodes WHERE project_id = ?", (project_id,)).fetchone()["next"]
        episode_id = payload.get("id") or f"EP{int(order_index):02d}"
        connection.execute(
            "INSERT INTO episodes(id, project_id, order_index, title, summary, opening_hook, core_event, payoff, twist, ending_hook, status, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (episode_id, project_id, order_index, payload.get("title", f"第 {int(order_index):02d} 集"), payload.get("summary", ""), payload.get("hook", payload.get("openingHook", "")), payload.get("coreEvent", ""), payload.get("payoff", ""), payload.get("twist", ""), payload.get("endingHook", ""), payload.get("status", "待策划"), payload.get("duration", "--:--")),
        )
        connection.execute("UPDATE projects SET target_episodes = MAX(target_episodes, ?), updated_at = ? WHERE id = ?", (order_index, now_text(), project_id))
        return episode_id


def patch_episode(episode_id: str, patch: dict[str, Any]) -> str:
    allowed = {"title": "title", "summary": "summary", "hook": "opening_hook", "openingHook": "opening_hook", "coreEvent": "core_event", "payoff": "payoff", "twist": "twist", "endingHook": "ending_hook", "status": "status", "duration": "duration", "locked": "locked"}
    values = [(allowed[key], int(value) if key == "locked" else value) for key, value in patch.items() if key in allowed]
    with session() as connection:
        row = connection.execute("SELECT project_id FROM episodes WHERE id = ? AND archived = 0", (episode_id,)).fetchone()
        if not row:
            raise KeyError(f"episode {episode_id} not found")
        if values:
            columns = ", ".join(f"{column} = ?" for column, _ in values)
            connection.execute(f"UPDATE episodes SET {columns}, updated_at = ? WHERE id = ?", [value for _, value in values] + [now_text(), episode_id])
        return row["project_id"]


def patch_shot(shot_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    allowed = {"description": "description", "size": "shot_size", "frame": "frame", "lens": "lens", "angle": "camera_angle", "movement": "movement", "duration": "duration", "action": "action", "emotion": "emotion", "dialogue": "dialogue", "prompt": "prompt", "negativePrompt": "negative_prompt", "reviewed": "reviewed", "status": "status", "image": "image"}
    values = [(allowed[key], int(value) if key == "reviewed" else value) for key, value in patch.items() if key in allowed]
    context = None
    with session() as connection:
        context = _shot_context(connection, shot_id)
        if not context:
            raise KeyError(f"shot {shot_id} not found")
        if values:
            values.append(("updated_at", now_text()))
            columns = ", ".join(f"{column} = ?" for column, _ in values)
            connection.execute(f"UPDATE shots SET {columns} WHERE id = ?", [value for _, value in values] + [shot_id])
    return project_to_dict(context["project_id"])


def create_shot(scene_id: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    with session() as connection:
        scene = connection.execute("SELECT * FROM scenes WHERE id = ? AND archived = 0", (scene_id,)).fetchone()
        if not scene:
            raise KeyError(f"scene {scene_id} not found")
        episode = connection.execute("SELECT * FROM episodes WHERE id = ?", (scene["episode_id"],)).fetchone()
        project_id = episode["project_id"]
        count = connection.execute("SELECT COALESCE(MAX(order_index), 0) + 1 AS next FROM shots WHERE scene_id = ?", (scene_id,)).fetchone()["next"]
        number = connection.execute("SELECT COALESCE(MAX(CAST(SUBSTR(id, 3) AS INTEGER)), 40) + 1 AS next FROM shots WHERE id LIKE 'SH%'").fetchone()["next"]
        shot_id = payload.get("id") or f"SH{int(number):03d}"
        connection.execute(
            """INSERT INTO shots(id, scene_id, order_index, timecode, description, shot_size, frame, camera_angle, lens, movement, duration, dialogue, prompt, image, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (shot_id, scene_id, count, payload.get("time", "00:00 – 00:04"), payload.get("description", "新镜头"), payload.get("size", "远景"), payload.get("frame", "16:9（横屏）"), payload.get("angle", "平视"), payload.get("lens", "35mm（环境人像）"), payload.get("movement", "固定镜头"), int(payload.get("duration", 4)), payload.get("dialogue", ""), payload.get("prompt", ""), payload.get("image", "/assets/shot-wide.png"), "待生成"),
        )
        connection.execute("UPDATE projects SET total_shots = total_shots + 1, updated_at = ? WHERE id = ?", (now_text(), project_id))
    return project_id, project_to_dict(project_id)


def delete_shot(shot_id: str) -> str:
    with session() as connection:
        context = _shot_context(connection, shot_id)
        if not context:
            raise KeyError(f"shot {shot_id} not found")
        connection.execute("UPDATE shots SET archived = 1, updated_at = ? WHERE id = ?", (now_text(), shot_id))
        connection.execute("UPDATE projects SET total_shots = MAX(total_shots - 1, 0), updated_at = ? WHERE id = ?", (now_text(), context["project_id"]))
        return context["project_id"]


def patch_asset(asset_id: str, patch: dict[str, Any]) -> str:
    table = None
    for candidate in ("characters", "locations", "props"):
        with session() as connection:
            row = connection.execute(f"SELECT project_id FROM {candidate} WHERE id = ? AND archived = 0", (asset_id,)).fetchone()
        if row:
            table = candidate
            project_id = row["project_id"]
            break
    if not table:
        raise KeyError(f"asset {asset_id} not found")
    allowed = {"name": "name", "meta": "meta", "description": "description", "image": "image", "status": "status"}
    values = [(allowed[key], value) for key, value in patch.items() if key in allowed]
    if values:
        with session() as connection:
            columns = ", ".join(f"{column} = ?" for column, _ in values)
            if table == "characters":
                mapping = {"description": "appearance"}
                columns = ", ".join(f"{mapping.get(column, column)} = ?" for column, _ in values)
            connection.execute(f"UPDATE {table} SET {columns}, updated_at = ? WHERE id = ?", [value for _, value in values] + [now_text(), asset_id])
    return project_id


def create_asset(project_id: str, asset_type: str, payload: dict[str, Any]) -> str:
    table_map = {"characters": "characters", "locations": "locations", "props": "props"}
    table = table_map.get(asset_type)
    if not table:
        raise KeyError(f"asset type {asset_type} not found")
    with session() as connection:
        _project_row(connection, project_id)
        prefix = {"characters": "C", "locations": "L", "props": "P"}[table]
        next_number = connection.execute(f"SELECT COALESCE(MAX(CAST(SUBSTR(id, 2) AS INTEGER)), 0) + 1 AS next FROM {table} WHERE id LIKE ?", (f"{prefix}%",)).fetchone()["next"]
        asset_id = payload.get("id") or f"{prefix}{int(next_number):03d}"
        if table == "characters":
            connection.execute("INSERT INTO characters(id, project_id, name, age, gender, role, appearance, personality, prompt, meta, image, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (asset_id, project_id, payload.get("name", "新角色"), payload.get("age", ""), payload.get("gender", ""), payload.get("role", ""), payload.get("description", ""), payload.get("personality", ""), payload.get("prompt", ""), payload.get("meta", ""), payload.get("image"), payload.get("status", "待确认")))
        else:
            connection.execute(f"INSERT INTO {table}(id, project_id, name, meta, description, image, status) VALUES (?, ?, ?, ?, ?, ?, ?)", (asset_id, project_id, payload.get("name", "新资产"), payload.get("meta", ""), payload.get("description", ""), payload.get("image"), payload.get("status", "待确认")))
        connection.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now_text(), project_id))
        return asset_id


def list_scenes(episode_id: str) -> list[dict[str, Any]]:
    with session() as connection:
        rows = connection.execute("SELECT * FROM scenes WHERE episode_id = ? AND archived = 0 ORDER BY order_index", (episode_id,)).fetchall()
        return [{"id": row["id"], "episodeId": row["episode_id"], "order": row["order_index"], "title": row["title"], "locationId": row["location_id"], "timeOfDay": row["time_of_day"], "purpose": row["purpose"], "emotionStart": row["emotion_start"], "emotionEnd": row["emotion_end"], "summary": row["summary"], "estimatedDuration": row["estimated_duration"], "script": loads(row["script_json"], {})} for row in rows]


def create_scene(episode_id: str, payload: dict[str, Any]) -> str:
    with session() as connection:
        episode = connection.execute("SELECT project_id FROM episodes WHERE id = ? AND archived = 0", (episode_id,)).fetchone()
        if not episode:
            raise KeyError(f"episode {episode_id} not found")
        order_index = connection.execute("SELECT COALESCE(MAX(order_index), 0) + 1 AS next FROM scenes WHERE episode_id = ?", (episode_id,)).fetchone()["next"]
        scene_id = payload.get("id") or new_id("SC-")
        connection.execute("INSERT INTO scenes(id, episode_id, order_index, title, location_id, time_of_day, purpose, emotion_start, emotion_end, summary, estimated_duration, script_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (scene_id, episode_id, order_index, payload.get("title", f"场景 {order_index}"), payload.get("locationId"), payload.get("timeOfDay", ""), payload.get("purpose", ""), payload.get("emotionStart", ""), payload.get("emotionEnd", ""), payload.get("summary", ""), int(payload.get("estimatedDuration", 0)), dumps(payload.get("script", {}))))
        return episode["project_id"]


def patch_scene(scene_id: str, patch: dict[str, Any]) -> str:
    allowed = {"title": "title", "locationId": "location_id", "timeOfDay": "time_of_day", "purpose": "purpose", "emotionStart": "emotion_start", "emotionEnd": "emotion_end", "summary": "summary", "estimatedDuration": "estimated_duration", "script": "script_json"}
    values = []
    for key, value in patch.items():
        if key in allowed:
            values.append((allowed[key], dumps(value) if key == "script" else value))
    with session() as connection:
        row = connection.execute("SELECT e.project_id FROM scenes s JOIN episodes e ON e.id = s.episode_id WHERE s.id = ? AND s.archived = 0", (scene_id,)).fetchone()
        if not row:
            raise KeyError(f"scene {scene_id} not found")
        if values:
            columns = ", ".join(f"{column} = ?" for column, _ in values)
            connection.execute(f"UPDATE scenes SET {columns}, updated_at = ? WHERE id = ?", [value for _, value in values] + [now_text(), scene_id])
        return row["project_id"]


def list_shots_for_scene(scene_id: str) -> list[dict[str, Any]]:
    with session() as connection:
        rows = connection.execute("SELECT s.*, e.id AS episode_id, e.project_id FROM shots s JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id WHERE s.scene_id = ? AND s.archived = 0 ORDER BY s.order_index", (scene_id,)).fetchall()
        return [_shot_dict(connection, row) for row in rows]


def task_row(task_id: str):
    with session() as connection:
        return connection.execute("SELECT * FROM generation_tasks WHERE id = ?", (task_id,)).fetchone()


def generation_task(task_id: str) -> dict[str, Any]:
    row = task_row(task_id)
    if not row:
        raise KeyError(f"task {task_id} not found")
    return {"id": row["id"], "shotId": row["shot_id"], "targetType": row["target_type"], "targetId": row["target_id"], "status": row["status"], "provider": row["provider"], "model": row["model"], "progress": row["progress"], "estimatedCost": row["estimated_cost"], "actualCost": row["actual_cost"], "retryCount": row["retry_count"], "error": row["error_message"], "createdAt": row["created_at"], "startedAt": row["started_at"], "completedAt": row["completed_at"], "parameters": loads(row["parameters_json"], {})}


def create_generation_task(shot_id: str, prompt: str, provider: str, model: str, estimated_cost: float = 0.73, parameters: dict[str, Any] | None = None, task_type: str = "视频") -> tuple[str, str]:
    with session() as connection:
        context = _shot_context(connection, shot_id)
        if not context:
            raise KeyError(f"shot {shot_id} not found")
        task_id = new_id("T-")
        connection.execute(
            """INSERT INTO generation_tasks(id, project_id, shot_id, target_type, target_id, type, provider, model, status, prompt, parameters_json, estimated_cost)
            VALUES (?, ?, ?, 'shot', ?, ?, ?, ?, 'Queued', ?, ?, ?)""",
            (task_id, context["project_id"], shot_id, shot_id, task_type, provider, model, prompt, dumps(parameters or {}), estimated_cost),
        )
        connection.execute("UPDATE shots SET status = '生成中', prompt = ?, updated_at = ? WHERE id = ?", (prompt, now_text(), shot_id))
        return context["project_id"], task_id


def create_target_generation_task(project_id: str, target_type: str, target_id: str, prompt: str, provider: str, model: str, estimated_cost: float = 0.18, parameters: dict[str, Any] | None = None, task_type: str = "图片") -> str:
    with session() as connection:
        _project_row(connection, project_id)
        task_id = new_id("T-")
        connection.execute(
            """INSERT INTO generation_tasks(id, project_id, shot_id, target_type, target_id, type, provider, model, status, prompt, parameters_json, estimated_cost)
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?, 'Queued', ?, ?, ?)""",
            (task_id, project_id, target_type, target_id, task_type, provider, model, prompt, dumps(parameters or {}), estimated_cost),
        )
        return task_id


def claim_next_task() -> dict[str, Any] | None:
    with session() as connection:
        row = connection.execute("SELECT * FROM generation_tasks WHERE status IN ('Queued', 'Retrying') ORDER BY queued_at, created_at LIMIT 1").fetchone()
        if not row:
            return None
        connection.execute("UPDATE generation_tasks SET status = 'Running', progress = 5, started_at = COALESCE(started_at, ?), updated_at = ? WHERE id = ?", (now_text(), now_text(), row["id"]))
        return dict(connection.execute("SELECT * FROM generation_tasks WHERE id = ?", (row["id"],)).fetchone())


def update_task_runtime(task_id: str, patch: dict[str, Any]) -> None:
    allowed = {"status", "progress", "provider_task_id", "status_url", "parameters_json", "error_message", "started_at", "completed_at", "actual_cost", "updated_at"}
    values = [(key, value) for key, value in patch.items() if key in allowed]
    if not values:
        return
    with session() as connection:
        columns = ", ".join(f"{key} = ?" for key, _ in values)
        connection.execute(f"UPDATE generation_tasks SET {columns} WHERE id = ?", [value for _, value in values] + [task_id])


def complete_generation_task(task_id: str, result: dict[str, Any]) -> str:
    with session() as connection:
        task = connection.execute("SELECT * FROM generation_tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            raise KeyError(f"task {task_id} not found")
        if task["target_type"] == "asset":
            output_url = result.get("output_url") or result.get("image_url") or result.get("url") or "/assets/shot-wide.png"
            asset_type = loads(task["parameters_json"], {}).get("assetType")
            table = asset_type if asset_type in {"characters", "locations", "props"} else "locations"
            connection.execute(f"UPDATE {table} SET image = ?, status = '已生成', updated_at = ? WHERE id = ?", (output_url, now_text(), task["target_id"]))
            actual_cost = round(float(result.get("cost") or task["estimated_cost"] or 0), 2)
            connection.execute("UPDATE generation_tasks SET status = 'Success', progress = 100, actual_cost = ?, completed_at = ?, updated_at = ? WHERE id = ?", (actual_cost, now_text(), now_text(), task_id))
            connection.execute("UPDATE projects SET spent = spent + ?, updated_at = ? WHERE id = ?", (actual_cost, now_text(), task["project_id"]))
            connection.execute("INSERT INTO cost_records(id, project_id, task_id, provider, model, category, estimated_cost, actual_cost, status) VALUES (?, ?, ?, ?, ?, 'image', ?, ?, 'actual')", (new_id("COST-"), task["project_id"], task_id, task["provider"], task["model"], task["estimated_cost"], actual_cost))
            return task["project_id"]
        if task["target_type"] == "voice_take":
            output_url = result.get("output_url") or result.get("audio_url") or result.get("url")
            media_asset_id = None
            if output_url:
                media_asset_id = new_id("MEDIA-")
                connection.execute(
                    "INSERT INTO media_assets(id, project_id, type, path_or_url, source, provider, model, prompt, metadata_json) VALUES (?, ?, 'voice_take', ?, 'provider', ?, ?, ?, ?)",
                    (media_asset_id, task["project_id"], output_url, task["provider"], task["model"], task["prompt"], dumps({"targetType": task["target_type"], "targetId": task["target_id"], "durationMs": result.get("duration_ms")})),
                )
            actual_cost = round(float(result.get("cost") or task["estimated_cost"] or 0), 2)
            connection.execute(
                "UPDATE voice_takes SET media_asset_id = ?, duration_ms = COALESCE(?, duration_ms), actual_cost = ?, status = 'success', qc_status = 'pending', updated_at = ? WHERE id = ?",
                (media_asset_id, result.get("duration_ms"), actual_cost, now_text(), task["target_id"]),
            )
            connection.execute("UPDATE dialogue_lines SET status = 'generated', updated_at = ? WHERE id = (SELECT dialogue_line_id FROM voice_takes WHERE id = ?)", (now_text(), task["target_id"]))
            connection.execute("UPDATE generation_tasks SET status = 'Success', progress = 100, actual_cost = ?, completed_at = ?, updated_at = ? WHERE id = ?", (actual_cost, now_text(), now_text(), task_id))
            connection.execute("UPDATE projects SET spent = spent + ?, updated_at = ? WHERE id = ?", (actual_cost, now_text(), task["project_id"]))
            connection.execute("INSERT INTO cost_records(id, project_id, task_id, provider, model, category, estimated_cost, actual_cost, status) VALUES (?, ?, ?, ?, ?, 'voice', ?, ?, 'actual')", (new_id("COST-"), task["project_id"], task_id, task["provider"], task["model"], task["estimated_cost"], actual_cost))
            return task["project_id"]
        if task["target_type"] == "character_reference":
            output_url = result.get("output_url") or result.get("image_url") or result.get("url") or "/assets/shot-hero.png"
            media_asset_id = new_id("MEDIA-")
            connection.execute("INSERT INTO media_assets(id, project_id, type, path_or_url, source, provider, model, prompt, metadata_json) VALUES (?, ?, 'character_reference', ?, 'provider', ?, ?, ?, ?)", (media_asset_id, task["project_id"], output_url, task["provider"], task["model"], task["prompt"], dumps({"targetType": task["target_type"], "targetId": task["target_id"]})))
            connection.execute("UPDATE character_references SET media_asset_id = ?, lifecycle_status = 'generated', quality_score = ?, updated_at = ? WHERE id = ?", (media_asset_id, result.get("qc_score", 91), now_text(), task["target_id"]))
            actual_cost = round(float(result.get("cost") or task["estimated_cost"] or 0), 2)
            connection.execute("UPDATE generation_tasks SET status = 'Success', progress = 100, actual_cost = ?, completed_at = ?, updated_at = ? WHERE id = ?", (actual_cost, now_text(), now_text(), task_id))
            connection.execute("UPDATE projects SET spent = spent + ?, updated_at = ? WHERE id = ?", (actual_cost, now_text(), task["project_id"]))
            connection.execute("INSERT INTO cost_records(id, project_id, task_id, provider, model, category, estimated_cost, actual_cost, status) VALUES (?, ?, ?, ?, ?, 'character_reference', ?, ?, 'actual')", (new_id("COST-"), task["project_id"], task_id, task["provider"], task["model"], task["estimated_cost"], actual_cost))
            return task["project_id"]
        if task["target_type"] == "runninghub_workflow":
            parameters = loads(task["parameters_json"], {})
            results = result.get("results") if isinstance(result.get("results"), list) else []
            output_url = result.get("output_url") or result.get("url") or (results[0].get("url") if results and isinstance(results[0], dict) else None)
            media_asset_id = None
            if output_url:
                media_asset_id = new_id("MEDIA-")
                connection.execute(
                    "INSERT INTO media_assets(id, project_id, type, path_or_url, source, provider, model, prompt, metadata_json) VALUES (?, ?, 'runninghub_output', ?, 'provider', ?, ?, ?, ?)",
                    (media_asset_id, task["project_id"], output_url, task["provider"], task["model"], task["prompt"], dumps({"taskId": task["provider_task_id"], "results": results})),
                )
            parameters["results"] = results
            if media_asset_id:
                parameters["mediaAssetId"] = media_asset_id
            actual_cost = round(float(result.get("cost") or task["estimated_cost"] or 0), 2)
            connection.execute("UPDATE generation_tasks SET status = 'Success', progress = 100, actual_cost = ?, parameters_json = ?, completed_at = ?, updated_at = ? WHERE id = ?", (actual_cost, dumps(parameters), now_text(), now_text(), task_id))
            connection.execute("UPDATE projects SET spent = spent + ?, updated_at = ? WHERE id = ?", (actual_cost, now_text(), task["project_id"]))
            connection.execute("INSERT INTO cost_records(id, project_id, task_id, provider, model, category, estimated_cost, actual_cost, status) VALUES (?, ?, ?, ?, ?, 'workflow', ?, ?, 'actual')", (new_id("COST-"), task["project_id"], task_id, task["provider"], task["model"], task["estimated_cost"], actual_cost))
            return task["project_id"]
        shot = connection.execute("SELECT * FROM shots WHERE id = ?", (task["shot_id"],)).fetchone()
        if not shot:
            raise KeyError(f"shot {task['shot_id']} not found")
        was_generated = shot["status"] == "已生成"
        next_version = connection.execute("SELECT COALESCE(MAX(version_number), 0) + 1 AS next FROM generation_versions WHERE shot_id = ?", (shot["id"],)).fetchone()["next"]
        media_asset_id = None
        output_url = result.get("output_url") or result.get("video_url")
        if output_url:
            media_asset_id = new_id("MEDIA-")
            connection.execute("INSERT INTO media_assets(id, project_id, type, path_or_url, source, provider, model, prompt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (media_asset_id, task["project_id"], "generated_video", output_url, "provider", task["provider"], task["model"], task["prompt"]))
        connection.execute("UPDATE generation_versions SET is_active = 0 WHERE shot_id = ?", (shot["id"],))
        version_id = new_id("VER-")
        actual_cost = round(float(result.get("cost") or task["estimated_cost"] or 0), 2)
        connection.execute(
            """INSERT INTO generation_versions(id, shot_id, version_number, media_asset_id, provider, model, prompt_snapshot, negative_prompt_snapshot, parameters_json, estimated_cost, actual_cost, qc_score, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (version_id, shot["id"], next_version, media_asset_id, task["provider"], task["model"], task["prompt"], "", task["parameters_json"], task["estimated_cost"], actual_cost, result.get("qc_score", 91)),
        )
        connection.execute("UPDATE shots SET status = '已生成', qc_score = COALESCE(qc_score, ?), cost = cost + ?, updated_at = ? WHERE id = ?", (result.get("qc_score", 91), actual_cost, now_text(), shot["id"]))
        connection.execute("UPDATE generation_tasks SET status = 'Success', progress = 100, actual_cost = ?, completed_at = ?, updated_at = ? WHERE id = ?", (actual_cost, now_text(), now_text(), task_id))
        connection.execute("UPDATE projects SET spent = spent + ?, generated_shots = generated_shots + ?, updated_at = ? WHERE id = ?", (actual_cost, 0 if was_generated else 1, now_text(), task["project_id"]))
        connection.execute("INSERT INTO cost_records(id, project_id, episode_id, scene_id, shot_id, task_id, provider, model, category, estimated_cost, actual_cost, status) SELECT ?, e.project_id, e.id, sc.id, ?, ?, ?, ?, 'video', ?, ?, 'actual' FROM shots s JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id WHERE s.id = ?", (new_id("COST-"), shot["id"], task_id, task["provider"], task["model"], task["estimated_cost"], actual_cost, shot["id"]))
        connection.execute("INSERT INTO qc_records(id, shot_id, version_id, type, score, severity, message, status) VALUES (?, ?, ?, 'character_consistency', ?, ?, ?, ?)", (new_id("QC-"), shot["id"], version_id, result.get("qc_score", 91), "info" if result.get("qc_score", 91) >= 90 else "warning", "QC provider result", "passed" if result.get("qc_score", 91) >= 90 else "warning"))
        return task["project_id"]


def fail_generation_task(task_id: str, error_message: str) -> str:
    with session() as connection:
        task = connection.execute("SELECT * FROM generation_tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            raise KeyError(f"task {task_id} not found")
        connection.execute("UPDATE generation_tasks SET status = 'Failed', progress = 0, error_message = ?, completed_at = ?, updated_at = ? WHERE id = ?", (error_message, now_text(), now_text(), task_id))
        if task["target_type"] == "agent_run":
            connection.execute("UPDATE agent_runs SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?", (error_message, now_text(), task["target_id"]))
        if task["shot_id"]:
            connection.execute("UPDATE shots SET status = '待生成', updated_at = ? WHERE id = ? AND status = '生成中'", (now_text(), task["shot_id"]))
        if task["target_type"] == "asset":
            asset_type = loads(task["parameters_json"], {}).get("assetType")
            table = asset_type if asset_type in {"characters", "locations", "props"} else "locations"
            connection.execute(f"UPDATE {table} SET status = '生成失败', updated_at = ? WHERE id = ?", (now_text(), task["target_id"]))
        category = "video" if task["target_type"] == "shot" else "image" if task["target_type"] == "asset" else "workflow" if task["target_type"] == "runninghub_workflow" else "character_reference"
        connection.execute("INSERT INTO cost_records(id, project_id, shot_id, task_id, provider, model, category, estimated_cost, actual_cost, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'failed')", (new_id("COST-"), task["project_id"], task["shot_id"], task_id, task["provider"], task["model"], category, task["estimated_cost"]))
        return task["project_id"]


def cancel_generation_task(task_id: str) -> str:
    with session() as connection:
        task = connection.execute("SELECT * FROM generation_tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            raise KeyError(f"task {task_id} not found")
        connection.execute("UPDATE generation_tasks SET status = 'Cancelled', completed_at = ?, updated_at = ? WHERE id = ? AND status IN ('Queued', 'Running', 'Retrying')", (now_text(), now_text(), task_id))
        if task["shot_id"]:
            connection.execute("UPDATE shots SET status = '待生成', updated_at = ? WHERE id = ? AND status = '生成中'", (now_text(), task["shot_id"]))
        if task["target_type"] == "asset":
            asset_type = loads(task["parameters_json"], {}).get("assetType")
            table = asset_type if asset_type in {"characters", "locations", "props"} else "locations"
            connection.execute(f"UPDATE {table} SET status = '待确认', updated_at = ? WHERE id = ?", (now_text(), task["target_id"]))
        return task["project_id"]


def retry_generation_task(task_id: str) -> tuple[str, str]:
    with session() as connection:
        task = connection.execute("SELECT * FROM generation_tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            raise KeyError(f"task {task_id} not found")
        if int(task["retry_count"]) >= int(task["max_retries"]):
            raise ValueError("已达到最大重试次数")
        connection.execute("UPDATE generation_tasks SET status = 'Retrying', retry_count = retry_count + 1, error_message = NULL, queued_at = ?, updated_at = ? WHERE id = ?", (now_text(), now_text(), task_id))
        if task["shot_id"]:
            connection.execute("UPDATE shots SET status = '生成中', updated_at = ? WHERE id = ?", (now_text(), task["shot_id"]))
        if task["target_type"] == "asset":
            asset_type = loads(task["parameters_json"], {}).get("assetType")
            table = asset_type if asset_type in {"characters", "locations", "props"} else "locations"
            connection.execute(f"UPDATE {table} SET status = '生成中', updated_at = ? WHERE id = ?", (now_text(), task["target_id"]))
        if task["target_type"] == "agent_run":
            connection.execute("UPDATE agent_runs SET status = 'queued', error_message = '', updated_at = ? WHERE id = ?", (now_text(), task["target_id"]))
        return task["project_id"], task_id


def list_versions(shot_id: str) -> list[dict[str, Any]]:
    with session() as connection:
        rows = connection.execute("SELECT * FROM generation_versions WHERE shot_id = ? ORDER BY version_number", (shot_id,)).fetchall()
        return [{"id": row["id"], "shotId": row["shot_id"], "version": row["version_number"], "provider": row["provider"], "model": row["model"], "outputUrl": _asset_url(connection, row["media_asset_id"]), "estimatedCost": row["estimated_cost"], "actualCost": row["actual_cost"], "qcScore": row["qc_score"], "active": bool(row["is_active"]), "createdAt": row["created_at"]} for row in rows]


def activate_version(version_id: str) -> str:
    with session() as connection:
        row = connection.execute("SELECT shot_id FROM generation_versions WHERE id = ?", (version_id,)).fetchone()
        if not row:
            raise KeyError(f"version {version_id} not found")
        connection.execute("UPDATE generation_versions SET is_active = 0 WHERE shot_id = ?", (row["shot_id"],))
        connection.execute("UPDATE generation_versions SET is_active = 1 WHERE id = ?", (version_id,))
        return row["shot_id"]


def affected_shots(asset_id: str) -> list[str]:
    with session() as connection:
        rows = connection.execute("SELECT target_id FROM dependencies WHERE source_id = ?", (asset_id,)).fetchall()
        return [row["target_id"] for row in rows]


def list_models() -> list[dict[str, Any]]:
    with session() as connection:
        rows = connection.execute("SELECT * FROM model_definitions WHERE enabled = 1 ORDER BY type, provider, model_id").fetchall()
        return [{"provider": row["provider"], "modelId": row["model_id"], "displayName": row["display_name"], "type": row["type"], "pricing": loads(row["pricing_json"], {}), "capabilities": loads(row["capabilities_json"], {})} for row in rows]


def list_costs(project_id: str) -> dict[str, Any]:
    with session() as connection:
        rows = connection.execute("SELECT * FROM cost_records WHERE project_id = ? ORDER BY created_at DESC", (project_id,)).fetchall()
        items = [dict(row) for row in rows]
        return {"projectId": project_id, "totalEstimated": round(sum(float(row["estimated_cost"] or 0) for row in rows), 2), "totalActual": round(sum(float(row["actual_cost"] or 0) for row in rows), 2), "items": items}


def list_qc(project_id: str | None = None, shot_id: str | None = None) -> list[dict[str, Any]]:
    with session() as connection:
        query = "SELECT q.* FROM qc_records q JOIN shots s ON s.id = q.shot_id JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id WHERE 1 = 1"
        params: list[Any] = []
        if project_id:
            query += " AND e.project_id = ?"
            params.append(project_id)
        if shot_id:
            query += " AND q.shot_id = ?"
            params.append(shot_id)
        query += " ORDER BY q.created_at DESC"
        return [dict(row) for row in connection.execute(query, params).fetchall()]
