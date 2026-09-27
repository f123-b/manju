from __future__ import annotations

from typing import Any

from ..core.database import session
from .repository import dumps, loads, new_id, now_text


def ensure_video_clips() -> None:
    """Create one editable timeline clip for every shot that lacks one."""
    with session() as connection:
        rows = connection.execute(
            """SELECT s.id, s.scene_id, sc.episode_id, e.project_id, s.duration
               FROM shots s JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id
               WHERE s.archived = 0 ORDER BY e.order_index, sc.order_index, s.order_index"""
        ).fetchall()
        offsets: dict[str, int] = {}
        for row in rows:
            existing = connection.execute("SELECT id FROM video_clips WHERE episode_id = ? AND shot_id = ? LIMIT 1", (row["episode_id"], row["id"])).fetchone()
            if existing:
                continue
            start = offsets.get(row["episode_id"], 0)
            duration = max(1, int(row["duration"] or 1)) * 1000
            connection.execute(
                """INSERT INTO video_clips(
                  id, project_id, episode_id, scene_id, shot_id, timeline_start_ms, source_start_ms, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
                (f"VCL-{row['id']}", row["project_id"], row["episode_id"], row["scene_id"], row["id"], start, duration),
            )
            offsets[row["episode_id"]] = start + duration


def _clip_dict(connection, row) -> dict[str, Any]:
    return {
        "id": row["id"], "projectId": row["project_id"], "episodeId": row["episode_id"], "sceneId": row["scene_id"],
        "shotId": row["shot_id"], "trackType": row["track_type"], "timelineStartMs": row["timeline_start_ms"],
        "sourceStartMs": row["source_start_ms"], "durationMs": row["duration_ms"],
        "transition": loads(row["transition_json"], {}), "metadata": loads(row["metadata_json"], {}),
        "image": row["source_url"] or row["shot_image"], "description": row["shot_description"], "status": row["shot_status"],
        "stale": bool(row["shot_stale"]), "createdAt": row["created_at"], "updatedAt": row["updated_at"],
    }


def _clip_query(connection, project_id: str, episode_id: str | None = None):
    values: list[Any] = [project_id]
    where = "vc.project_id = ? AND vc.archived = 0 AND s.archived = 0"
    if episode_id:
        where += " AND vc.episode_id = ?"
        values.append(episode_id)
    return connection.execute(
        f"""SELECT vc.*, s.image AS shot_image, s.description AS shot_description, s.status AS shot_status, s.stale AS shot_stale,
                   COALESCE(ma.path_or_url, s.image) AS source_url
            FROM video_clips vc JOIN shots s ON s.id = vc.shot_id
            LEFT JOIN generation_versions gv ON gv.shot_id = s.id AND gv.is_active = 1
            LEFT JOIN media_assets ma ON ma.id = gv.media_asset_id
            WHERE {where} ORDER BY vc.episode_id, vc.timeline_start_ms, vc.created_at""",
        values,
    ).fetchall()


def list_video_clips(project_id: str, episode_id: str | None = None) -> list[dict[str, Any]]:
    ensure_video_clips()
    with session() as connection:
        return [_clip_dict(connection, row) for row in _clip_query(connection, project_id, episode_id)]


def create_video_clip(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    shot_id = payload.get("shotId") or payload.get("shot_id")
    if not shot_id:
        raise ValueError("视频轨道需要 shotId")
    ensure_video_clips()
    with session() as connection:
        shot = connection.execute(
            """SELECT s.*, sc.episode_id, e.project_id FROM shots s JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id
               WHERE s.id = ? AND s.archived = 0""",
            (shot_id,),
        ).fetchone()
        if not shot or shot["project_id"] != project_id:
            raise KeyError(f"shot {shot_id} not found")
        existing = connection.execute("SELECT id FROM video_clips WHERE episode_id = ? AND shot_id = ? LIMIT 1", (shot["episode_id"], shot_id)).fetchone()
        if existing:
            connection.execute("UPDATE video_clips SET archived = 0, updated_at = ? WHERE id = ?", (now_text(), existing["id"]))
            clip_id = existing["id"]
        else:
            last = connection.execute("SELECT COALESCE(MAX(timeline_start_ms + duration_ms), 0) AS end_ms FROM video_clips WHERE episode_id = ? AND archived = 0", (shot["episode_id"],)).fetchone()["end_ms"]
            clip_id = payload.get("id") or new_id("VCL-")
            connection.execute(
                """INSERT INTO video_clips(id, project_id, episode_id, scene_id, shot_id, track_type, timeline_start_ms, source_start_ms, duration_ms, transition_json, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (clip_id, project_id, shot["episode_id"], shot["scene_id"], shot_id, payload.get("trackType", "video"), int(payload.get("timelineStartMs", last)), int(payload.get("sourceStartMs", 0)), int(payload.get("durationMs", max(1, int(shot["duration"] or 1)) * 1000)), dumps(payload.get("transition", {})), dumps(payload.get("metadata", {}))),
            )
        row = _clip_query(connection, project_id, shot["episode_id"])
        return next(item for item in (_clip_dict(connection, item) for item in row) if item["id"] == clip_id)


def patch_video_clip(clip_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"trackType": "track_type", "timelineStartMs": "timeline_start_ms", "sourceStartMs": "source_start_ms", "durationMs": "duration_ms"}
    with session() as connection:
        existing = connection.execute("SELECT id, project_id FROM video_clips WHERE id = ? AND archived = 0", (clip_id,)).fetchone()
        if not existing:
            raise KeyError(f"video clip {clip_id} not found")
        values: list[tuple[str, Any]] = []
        for key, column in allowed.items():
            if key not in payload:
                continue
            value = payload[key]
            if column in {"timeline_start_ms", "source_start_ms", "duration_ms"}:
                value = int(value or 0)
                if value < 0:
                    raise ValueError(f"{key} 不能小于 0")
            values.append((column, value))
        if "transition" in payload:
            values.append(("transition_json", dumps(payload["transition"])) )
        if "metadata" in payload:
            values.append(("metadata_json", dumps(payload["metadata"])))
        if values:
            values.append(("updated_at", now_text()))
            connection.execute(f"UPDATE video_clips SET {', '.join(f'{column} = ?' for column, _ in values)} WHERE id = ?", [value for _, value in values] + [clip_id])
        row = _clip_query(connection, existing["project_id"])
        return next(item for item in (_clip_dict(connection, item) for item in row) if item["id"] == clip_id)


def delete_video_clip(clip_id: str) -> dict[str, Any]:
    with session() as connection:
        row = connection.execute("SELECT project_id, episode_id FROM video_clips WHERE id = ? AND archived = 0", (clip_id,)).fetchone()
        if not row:
            raise KeyError(f"video clip {clip_id} not found")
        connection.execute("UPDATE video_clips SET archived = 1, updated_at = ? WHERE id = ?", (now_text(), clip_id))
        return {"id": clip_id, "projectId": row["project_id"], "episodeId": row["episode_id"]}
