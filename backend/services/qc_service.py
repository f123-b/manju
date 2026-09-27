from __future__ import annotations

from typing import Any

from ..core.database import session
from ..domain.repository import dumps, new_id, now_text


def _shot_row(connection, shot_id: str):
    row = connection.execute(
        """SELECT s.*, sc.episode_id, e.project_id FROM shots s
           JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id
           WHERE s.id = ? AND s.archived = 0""",
        (shot_id,),
    ).fetchone()
    if not row:
        raise KeyError(f"shot {shot_id} not found")
    return row


def _save_checks(connection, shot_id: str, checks: list[dict[str, Any]], score: float) -> None:
    connection.execute("DELETE FROM qc_records WHERE shot_id = ? AND type LIKE 'visual_%'", (shot_id,))
    for check in checks:
        connection.execute(
            "INSERT INTO qc_records(id, shot_id, type, score, severity, message, metadata_json, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (new_id("QC-"), shot_id, check["type"], check.get("score"), check["severity"], check["message"], dumps(check.get("metadata", {})), "passed" if check["severity"] == "info" else "needs_review"),
        )
    connection.execute("UPDATE shots SET qc_score = ?, updated_at = ? WHERE id = ?", (score, now_text(), shot_id))


def run_shot_visual_qc(shot_id: str) -> dict[str, Any]:
    with session() as connection:
        shot = _shot_row(connection, shot_id)
        active_version = connection.execute("SELECT * FROM generation_versions WHERE shot_id = ? AND is_active = 1", (shot_id,)).fetchone()
        bindings = connection.execute("SELECT sc.*, c.canonical_reference_id FROM shot_characters sc JOIN characters c ON c.id = sc.character_id WHERE sc.shot_id = ?", (shot_id,)).fetchall()
        approved_refs = connection.execute(
            "SELECT COUNT(*) AS count FROM character_references r JOIN shot_characters sc ON sc.character_id = r.character_id WHERE sc.shot_id = ? AND r.lifecycle_status = 'approved'",
            (shot_id,),
        ).fetchone()["count"]
        checks = [
            {"type": "visual_media", "score": 100 if active_version or shot["status"] == "已生成" else 0, "severity": "info" if active_version or shot["status"] == "已生成" else "error", "message": "已找到生成版本" if active_version or shot["status"] == "已生成" else "镜头还没有可检测的生成版本", "metadata": {"versionId": active_version["id"] if active_version else None}},
            {"type": "visual_prompt", "score": 100 if shot["prompt"] else 60, "severity": "info" if shot["prompt"] else "warning", "message": "生成提示词已记录" if shot["prompt"] else "缺少生成提示词，无法完整判断画面意图", "metadata": {}},
            {"type": "visual_identity", "score": 100 if bindings and approved_refs >= len(bindings) else 70 if bindings else 50, "severity": "info" if bindings and approved_refs >= len(bindings) else "warning", "message": "角色参考已绑定" if bindings and approved_refs >= len(bindings) else "角色参考尚未全部审核或绑定", "metadata": {"bindings": len(bindings), "approvedReferences": approved_refs}},
            {"type": "visual_duration", "score": 100 if int(shot["duration"] or 0) > 0 else 0, "severity": "info" if int(shot["duration"] or 0) > 0 else "error", "message": "镜头时长有效" if int(shot["duration"] or 0) > 0 else "镜头时长必须大于 0", "metadata": {"duration": shot["duration"]}},
        ]
        score = round(sum(item["score"] for item in checks) / len(checks), 1)
        _save_checks(connection, shot_id, checks, score)
        return {"shotId": shot_id, "score": score, "status": "pass" if all(item["severity"] == "info" for item in checks) else "warning", "checks": checks}


def run_project_continuity_check(project_id: str) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    with session() as connection:
        rows = connection.execute(
            """SELECT s.*, sc.episode_id, sc.order_index AS scene_order, e.order_index AS episode_order
               FROM shots s JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id
               WHERE e.project_id = ? AND s.archived = 0 ORDER BY e.order_index, sc.order_index, s.order_index""",
            (project_id,),
        ).fetchall()
        previous_refs: dict[str, str] = {}
        connection.execute("DELETE FROM qc_records WHERE shot_id IN (SELECT s.id FROM shots s JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id WHERE e.project_id = ?) AND type = 'continuity'", (project_id,))
        for shot in rows:
            checks: list[dict[str, Any]] = []
            bindings = connection.execute("SELECT sc.character_id, COALESCE(sc.primary_reference_id, c.canonical_reference_id, '') AS reference_id FROM shot_characters sc JOIN characters c ON c.id = sc.character_id WHERE sc.shot_id = ?", (shot["id"],)).fetchall()
            for binding in bindings:
                previous = previous_refs.get(binding["character_id"])
                current = binding["reference_id"]
                if previous and current and previous != current:
                    checks.append({"type": "continuity", "score": 35, "severity": "error", "message": "同一角色在相邻镜头间引用了不同主参考图", "metadata": {"characterId": binding["character_id"], "previousReference": previous, "currentReference": current}})
                if current:
                    previous_refs[binding["character_id"]] = current
            if shot["stale"]:
                checks.append({"type": "continuity", "score": 55, "severity": "warning", "message": shot["stale_reason"] or "镜头依赖的角色或场景已变化，需要重新生成", "metadata": {}})
            if shot["dialogue"] and not bindings:
                checks.append({"type": "continuity", "score": 65, "severity": "warning", "message": "镜头包含对白但没有绑定说话角色", "metadata": {}})
            if not checks:
                checks.append({"type": "continuity", "score": 100, "severity": "info", "message": "未发现明显的角色引用或镜头状态冲突", "metadata": {}})
            for check in checks:
                connection.execute("INSERT INTO qc_records(id, shot_id, type, score, severity, message, metadata_json, status) VALUES (?, ?, 'continuity', ?, ?, ?, ?, ?)", (new_id("QC-"), shot["id"], check["score"], check["severity"], check["message"], dumps(check.get("metadata", {})), "passed" if check["severity"] == "info" else "needs_review"))
            score = min(check["score"] for check in checks)
            connection.execute("UPDATE shots SET qc_score = ?, updated_at = ? WHERE id = ?", (score, now_text(), shot["id"]))
            findings.append({"shotId": shot["id"], "score": score, "status": "pass" if score >= 90 else "warning", "checks": checks})
    return {"projectId": project_id, "status": "pass" if all(item["status"] == "pass" for item in findings) else "warning", "findings": findings}


def run_project_qc(project_id: str) -> dict[str, Any]:
    with session() as connection:
        shot_ids = [row["id"] for row in connection.execute("SELECT s.id FROM shots s JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id WHERE e.project_id = ? AND s.archived = 0", (project_id,)).fetchall()]
    visual = [run_shot_visual_qc(shot_id) for shot_id in shot_ids]
    continuity = run_project_continuity_check(project_id)
    return {"projectId": project_id, "visual": visual, "continuity": continuity}
