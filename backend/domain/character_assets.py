from __future__ import annotations

import re
from typing import Any

from ..core.database import session
from .repository import dumps, loads, new_id, now_text


REFERENCE_STATUSES = {"planned", "generated", "approved", "rejected"}


def _character_row(connection, character_id: str):
    row = connection.execute(
        "SELECT * FROM characters WHERE id = ? AND archived = 0", (character_id,)
    ).fetchone()
    if not row:
        raise KeyError(f"character {character_id} not found")
    return row


def _look_row(connection, look_id: str):
    row = connection.execute("SELECT * FROM character_looks WHERE id = ?", (look_id,)).fetchone()
    if not row:
        raise KeyError(f"look {look_id} not found")
    return row


def _reference_row(connection, reference_id: str):
    row = connection.execute("SELECT * FROM character_references WHERE id = ?", (reference_id,)).fetchone()
    if not row:
        raise KeyError(f"reference {reference_id} not found")
    return row


def _asset_url(connection, asset_id: str | None) -> str | None:
    if not asset_id:
        return None
    row = connection.execute("SELECT path_or_url FROM media_assets WHERE id = ?", (asset_id,)).fetchone()
    return row["path_or_url"] if row else None


def _json_field(row, key: str, default):
    return loads(row[key] if key in row.keys() else None, default)


def look_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "characterId": row["character_id"],
        "name": row["name"],
        "baseLookId": row["base_look_id"],
        "description": row["description"],
        "wardrobe": _json_field(row, "wardrobe_json", {}),
        "hairMakeup": _json_field(row, "hair_makeup_json", {}),
        "accessories": _json_field(row, "accessories_json", {}),
        "injuries": _json_field(row, "injuries_json", {}),
        "weathering": _json_field(row, "weathering_json", {}),
        "differences": _json_field(row, "differences_json", {}),
        "causeRef": row["cause_ref"],
        "validFromSceneId": row["valid_from_scene_id"],
        "validToSceneId": row["valid_to_scene_id"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def reference_dict(connection, row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "characterId": row["character_id"],
        "lookId": row["look_id"],
        "mediaAssetId": row["media_asset_id"],
        "image": _asset_url(connection, row["media_asset_id"]),
        "referenceType": row["reference_type"],
        "viewAngle": row["view_angle"],
        "qualityLevel": row["quality_level"],
        "lifecycleStatus": row["lifecycle_status"],
        "isPrimary": bool(row["is_primary"]),
        "source": row["source"],
        "generationVersionId": row["generation_version_id"],
        "generationTaskId": row["generation_task_id"],
        "candidateGroup": row["candidate_group"],
        "promptSnapshot": row["prompt_snapshot"],
        "qualityScore": row["quality_score"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _primary_reference(connection, character_id: str):
    return connection.execute(
        """
        SELECT cr.* FROM character_references cr
        WHERE cr.character_id = ? AND cr.lifecycle_status IN ('approved', 'generated')
          AND cr.media_asset_id IS NOT NULL
        ORDER BY CASE WHEN cr.lifecycle_status = 'approved' THEN 0 ELSE 1 END,
                 CASE WHEN cr.reference_type = 'master_sheet' THEN 0 ELSE 1 END,
                 cr.is_primary DESC, cr.created_at DESC
        LIMIT 1
        """,
        (character_id,),
    ).fetchone()


def character_dict(connection, row, include_details: bool = True) -> dict[str, Any]:
    primary = _primary_reference(connection, row["id"])
    looks = connection.execute(
        "SELECT * FROM character_looks WHERE character_id = ? ORDER BY created_at, id", (row["id"],)
    ).fetchall()
    references = connection.execute(
        "SELECT * FROM character_references WHERE character_id = ? ORDER BY created_at DESC", (row["id"],)
    ).fetchall()
    usage = connection.execute(
        "SELECT COUNT(*) AS count FROM shot_characters WHERE character_id = ?", (row["id"],)
    ).fetchone()["count"]
    image = _asset_url(connection, primary["media_asset_id"]) if primary else row["image"]
    data = {
        "id": row["id"],
        "projectId": row["project_id"],
        "name": row["name"],
        "age": row["age"],
        "ageRange": row["age_range"] if "age_range" in row.keys() else row["age"],
        "gender": row["gender"],
        "role": row["role"],
        "aliases": _json_field(row, "aliases_json", []),
        "description": row["appearance"],
        "appearance": row["appearance"],
        "personality": row["personality"],
        "voiceProfile": row["voice_profile"],
        "prompt": row["prompt"],
        "negativePrompt": row["negative_prompt"],
        "meta": row["meta"],
        "image": image,
        "legacyImage": row["image"],
        "status": "已锁定" if row["identity_locked"] else row["status"],
        "identityLocked": bool(row["identity_locked"]),
        "lockedAt": row["locked_at"],
        "identityAnchors": _json_field(row, "identity_anchors_json", {}),
        "persistentPerformanceFacts": _json_field(row, "persistent_performance_facts_json", {}),
        "canonicalReferenceId": row["canonical_reference_id"],
        "primaryReference": reference_dict(connection, primary) if primary else None,
        "lookCount": len(looks),
        "referenceCount": len([item for item in references if item["lifecycle_status"] != "rejected"]),
        "approvedReferenceCount": len([item for item in references if item["lifecycle_status"] == "approved"]),
        "usageCount": usage,
    }
    if include_details:
        data["looks"] = [look_dict(item) for item in looks]
        data["references"] = [reference_dict(connection, item) for item in references]
    return data


def list_characters(project_id: str) -> list[dict[str, Any]]:
    with session() as connection:
        rows = connection.execute(
            "SELECT * FROM characters WHERE project_id = ? AND archived = 0 ORDER BY id", (project_id,)
        ).fetchall()
        return [character_dict(connection, row) for row in rows]


def get_character(character_id: str) -> dict[str, Any]:
    with session() as connection:
        return character_dict(connection, _character_row(connection, character_id))


def create_character(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with session() as connection:
        project = connection.execute("SELECT 1 FROM projects WHERE id = ? AND archived = 0", (project_id,)).fetchone()
        if not project:
            raise KeyError(f"project {project_id} not found")
        number = connection.execute(
            "SELECT COALESCE(MAX(CAST(SUBSTR(id, 2) AS INTEGER)), 0) + 1 AS next FROM characters WHERE id GLOB 'C[0-9]*'"
        ).fetchone()["next"]
        character_id = payload.get("id") or f"C{int(number):03d}"
        connection.execute(
            """INSERT INTO characters(
              id, project_id, name, age, gender, role, appearance, personality,
              voice_profile, prompt, negative_prompt, meta, image, status,
              aliases_json, age_range, identity_anchors_json,
              persistent_performance_facts_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                character_id,
                project_id,
                payload.get("name", "新角色"),
                payload.get("age", ""),
                payload.get("gender", ""),
                payload.get("role", ""),
                payload.get("description", payload.get("appearance", "")),
                payload.get("personality", ""),
                payload.get("voiceProfile", ""),
                payload.get("prompt", ""),
                payload.get("negativePrompt", ""),
                payload.get("meta", ""),
                payload.get("image"),
                payload.get("status", "draft"),
                dumps(payload.get("aliases", [])),
                payload.get("ageRange", payload.get("age", "")),
                dumps(payload.get("identityAnchors", {})),
                dumps(payload.get("persistentPerformanceFacts", {})),
            ),
        )
        look_id = payload.get("lookId") or new_id("LOOK-")
        connection.execute(
            "INSERT INTO character_looks(id, character_id, name, description, status) VALUES (?, ?, ?, ?, ?)",
            (look_id, character_id, payload.get("lookName", "基础造型"), payload.get("lookDescription", ""), "draft"),
        )
        connection.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now_text(), project_id))
        return character_dict(connection, _character_row(connection, character_id))


def patch_character(character_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "name": "name", "age": "age", "ageRange": "age_range", "gender": "gender", "role": "role",
        "description": "appearance", "appearance": "appearance", "personality": "personality",
        "voiceProfile": "voice_profile", "prompt": "prompt", "negativePrompt": "negative_prompt",
        "meta": "meta", "aliases": "aliases_json", "identityAnchors": "identity_anchors_json",
        "persistentPerformanceFacts": "persistent_performance_facts_json", "status": "status",
    }
    with session() as connection:
        row = _character_row(connection, character_id)
        values = []
        for key, value in patch.items():
            if key in mapping:
                column = mapping[key]
                if key in {"aliases", "identityAnchors", "persistentPerformanceFacts"}:
                    value = dumps(value)
                values.append((column, value))
        if values:
            columns = ", ".join(f"{column} = ?" for column, _ in values)
            connection.execute(
                f"UPDATE characters SET {columns}, updated_at = ? WHERE id = ?",
                [value for _, value in values] + [now_text(), character_id],
            )
            _mark_character_impact(connection, row["project_id"], character_id, "角色身份信息发生变化")
        return character_dict(connection, _character_row(connection, character_id))


def extract_identity_anchors(character_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    with session() as connection:
        character = _character_row(connection, character_id)
        source = " ".join(
            str(item) for item in (
                payload.get("text"), character["appearance"], character["personality"],
                character["meta"], character["prompt"],
            ) if item
        )
        def first_match(pattern: str, default: str = "") -> str:
            match = re.search(pattern, source, re.IGNORECASE)
            return match.group(1) if match else default

        hair = first_match(r"(黑发|棕发|金发|银发|短发|长发|卷发)")
        age = character["age_range"] or character["age"]
        anchors = {
            "schemaVersion": 1,
            "faceShape": "未确认",
            "facialFeatures": ["保持角色五官比例稳定"],
            "hair": hair or "以用户确认的人物图为准",
            "bodySilhouette": "以用户确认的人物图为准",
            "skinOrSurface": "自然肤色，避免跨镜头漂移",
            "colorAnchors": {"hair": hair or "未确认", "signature": "低饱和都市色调"},
            "uniqueMarks": [],
            "sideViewAnchor": "保留耳廓、下颌线和发际线关系",
            "backViewAnchor": "保留后脑勺轮廓与发型块面",
            "scaleRelation": "以成年人物比例为基准",
            "notIdentity": ["表情", "服装", "伤痕", "妆容", "天气状态"],
            "ageRange": age or "未确认",
            "confidence": "draft",
            "creatorDecisionNeeded": ["脸型", "独特标记", "四视图细节"],
        }
        connection.execute(
            "UPDATE characters SET identity_anchors_json = ?, updated_at = ? WHERE id = ?",
            (dumps(anchors), now_text(), character_id),
        )
        return anchors


def list_looks(character_id: str) -> list[dict[str, Any]]:
    with session() as connection:
        _character_row(connection, character_id)
        return [look_dict(row) for row in connection.execute("SELECT * FROM character_looks WHERE character_id = ? ORDER BY created_at, id", (character_id,)).fetchall()]


def create_look(character_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with session() as connection:
        character = _character_row(connection, character_id)
        look_id = payload.get("id") or new_id("LOOK-")
        connection.execute(
            """INSERT INTO character_looks(
              id, character_id, name, base_look_id, description, wardrobe_json,
              hair_makeup_json, accessories_json, injuries_json, weathering_json,
              differences_json, cause_ref, valid_from_scene_id, valid_to_scene_id, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                look_id, character_id, payload.get("name", "新造型"), payload.get("baseLookId"),
                payload.get("description", ""), dumps(payload.get("wardrobe", {})),
                dumps(payload.get("hairMakeup", {})), dumps(payload.get("accessories", {})),
                dumps(payload.get("injuries", {})), dumps(payload.get("weathering", {})),
                dumps(payload.get("differences", {})), payload.get("causeRef"),
                payload.get("validFromSceneId"), payload.get("validToSceneId"), payload.get("status", "draft"),
            ),
        )
        _mark_character_impact(connection, character["project_id"], character_id, "角色造型发生变化")
        return look_dict(_look_row(connection, look_id))


def patch_look(look_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "name": "name", "baseLookId": "base_look_id", "description": "description",
        "wardrobe": "wardrobe_json", "hairMakeup": "hair_makeup_json", "accessories": "accessories_json",
        "injuries": "injuries_json", "weathering": "weathering_json", "differences": "differences_json",
        "causeRef": "cause_ref", "validFromSceneId": "valid_from_scene_id", "validToSceneId": "valid_to_scene_id", "status": "status",
    }
    with session() as connection:
        row = _look_row(connection, look_id)
        values = []
        for key, value in patch.items():
            if key in mapping:
                values.append((mapping[key], dumps(value) if key in {"wardrobe", "hairMakeup", "accessories", "injuries", "weathering", "differences"} else value))
        if values:
            columns = ", ".join(f"{column} = ?" for column, _ in values)
            connection.execute(f"UPDATE character_looks SET {columns}, updated_at = ? WHERE id = ?", [value for _, value in values] + [now_text(), look_id])
            _mark_character_impact(connection, connection.execute("SELECT project_id FROM characters WHERE id = ?", (row["character_id"],)).fetchone()["project_id"], row["character_id"], "角色造型发生变化")
        return look_dict(_look_row(connection, look_id))


def list_references(character_id: str) -> list[dict[str, Any]]:
    with session() as connection:
        _character_row(connection, character_id)
        return [reference_dict(connection, row) for row in connection.execute("SELECT * FROM character_references WHERE character_id = ? ORDER BY created_at DESC", (character_id,)).fetchall()]


def create_reference(character_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with session() as connection:
        character = _character_row(connection, character_id)
        reference_id = payload.get("id") or new_id("REF-")
        media_asset_id = payload.get("mediaAssetId")
        image = payload.get("image") or payload.get("url")
        if image and not media_asset_id:
            media_asset_id = new_id("MEDIA-")
            connection.execute("INSERT INTO media_assets(id, project_id, type, path_or_url, source, provider, model, prompt) VALUES (?, ?, 'character_reference', ?, ?, ?, ?, ?)", (media_asset_id, character["project_id"], image, payload.get("source", "manual"), payload.get("provider"), payload.get("model"), payload.get("prompt", "")))
        status = payload.get("lifecycleStatus", "generated")
        if status not in REFERENCE_STATUSES:
            raise ValueError("reference lifecycleStatus 不合法")
        connection.execute(
            """INSERT INTO character_references(
              id, character_id, look_id, media_asset_id, reference_type, view_angle,
              quality_level, lifecycle_status, is_primary, source, candidate_group,
              prompt_snapshot, quality_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (reference_id, character_id, payload.get("lookId"), media_asset_id, payload.get("referenceType", "candidate"), payload.get("viewAngle", "front"), payload.get("qualityLevel", "candidate"), status, int(bool(payload.get("isPrimary"))), payload.get("source", "manual"), payload.get("candidateGroup"), payload.get("prompt", ""), payload.get("qualityScore")),
        )
        return reference_dict(connection, _reference_row(connection, reference_id))


def generate_character_candidates(character_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from .repository import _project_row

    with session() as connection:
        character = _character_row(connection, character_id)
        count = max(1, min(int(payload.get("count", 4)), 8))
        provider = payload.get("provider", "mock")
        model = payload.get("model", "mock-image")
        cost = float(payload.get("estimatedCost", 0.18))
        group = new_id("CAND-")
        prompt = payload.get("prompt") or build_character_prompt(connection, character)
        look_id = payload.get("lookId")
        if look_id:
            look = _look_row(connection, look_id)
            if look["character_id"] != character_id:
                raise ValueError("造型不属于该角色")
        tasks = []
        refs = []
        for index in range(count):
            reference_id = new_id("REF-")
            task_id = new_id("T-")
            parameters = {
                "asset_type": "character_reference",
                "reference_type": "candidate",
                "candidate_group": group,
                "candidate_index": index + 1,
                "character_id": character_id,
                "look_id": look_id,
            }
            connection.execute(
                """INSERT INTO character_references(
                  id, character_id, look_id, reference_type, view_angle, quality_level,
                  lifecycle_status, source, generation_task_id, candidate_group, prompt_snapshot
                ) VALUES (?, ?, ?, 'candidate', ?, 'candidate', 'planned', 'generated', ?, ?, ?)""",
                (reference_id, character_id, look_id, payload.get("viewAngle", "front"), task_id, group, prompt),
            )
            connection.execute(
                """INSERT INTO generation_tasks(
                  id, project_id, target_type, target_id, type, provider, model, status,
                  prompt, parameters_json, estimated_cost
                ) VALUES (?, ?, 'character_reference', ?, '图片', ?, ?, 'Queued', ?, ?, ?)""",
                (task_id, character["project_id"], reference_id, provider, model, prompt, dumps(parameters), cost),
            )
            refs.append(reference_id)
            tasks.append(task_id)
        connection.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now_text(), character["project_id"]))
        return {
            "projectId": character["project_id"],
            "characterId": character_id,
            "candidateGroup": group,
            "referenceIds": refs,
            "taskIds": tasks,
            "prompt": prompt,
            "count": count,
        }


def generate_master_sheet(character_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with session() as connection:
        character = _character_row(connection, character_id)
        canonical_id = payload.get("canonicalReferenceId") or character["canonical_reference_id"]
        if not canonical_id:
            raise ValueError("请先选择 Canonical Reference")
        canonical = _reference_row(connection, canonical_id)
        if canonical["character_id"] != character_id:
            raise ValueError("Canonical Reference 不属于该角色")
        if canonical["lifecycle_status"] not in {"generated", "approved"}:
            raise ValueError("Canonical Reference 尚未生成完成")
        prompt = payload.get("prompt") or f"{character['name']} master reference sheet，front / 3-4 view / side / back，保持 identity anchors 稳定。"
        reference_id = new_id("REF-")
        task_id = new_id("T-")
        task_params = {"asset_type": "character_reference", "reference_type": "master_sheet", "character_id": character_id, "canonical_reference_id": canonical_id, "references": [reference_dict(connection, canonical)]}
        connection.execute("INSERT INTO character_references(id, character_id, reference_type, view_angle, quality_level, lifecycle_status, source, generation_task_id, prompt_snapshot) VALUES (?, ?, 'master_sheet', 'multi', 'master', 'planned', 'generated', ?, ?)", (reference_id, character_id, task_id, prompt))
        connection.execute("INSERT INTO generation_tasks(id, project_id, target_type, target_id, type, provider, model, status, prompt, parameters_json, estimated_cost) VALUES (?, ?, 'character_reference', ?, '图片', ?, ?, 'Queued', ?, ?, ?)", (task_id, character["project_id"], reference_id, payload.get("provider", "mock"), payload.get("model", "mock-image"), prompt, dumps(task_params), float(payload.get("estimatedCost", 0.42))))
        return {"projectId": character["project_id"], "characterId": character_id, "referenceId": reference_id, "taskId": task_id, "canonicalReferenceId": canonical_id, "prompt": prompt}


def set_canonical_reference(character_id: str, reference_id: str) -> dict[str, Any]:
    with session() as connection:
        character = _character_row(connection, character_id)
        reference = _reference_row(connection, reference_id)
        if reference["character_id"] != character_id:
            raise ValueError("参考图不属于该角色")
        if reference["lifecycle_status"] not in {"generated", "approved"}:
            raise ValueError("只有已生成或已审核的参考图可以设为 Canonical")
        connection.execute("UPDATE character_references SET is_primary = 0, updated_at = ? WHERE character_id = ?", (now_text(), character_id))
        connection.execute("UPDATE character_references SET is_primary = 1, reference_type = CASE WHEN reference_type = 'candidate' THEN 'canonical' ELSE reference_type END, updated_at = ? WHERE id = ?", (now_text(), reference_id))
        connection.execute("UPDATE characters SET canonical_reference_id = ?, updated_at = ? WHERE id = ?", (reference_id, now_text(), character_id))
        _mark_character_impact(connection, character["project_id"], character_id, "Canonical Reference 已更新")
        return character_dict(connection, _character_row(connection, character_id))


def review_reference(reference_id: str, status: str) -> dict[str, Any]:
    if status not in {"approved", "rejected"}:
        raise ValueError("审核状态不合法")
    with session() as connection:
        reference = _reference_row(connection, reference_id)
        if status == "approved" and not reference["media_asset_id"]:
            raise ValueError("参考图尚未生成，不能审核")
        character = _character_row(connection, reference["character_id"])
        connection.execute("UPDATE character_references SET lifecycle_status = ?, updated_at = ? WHERE id = ?", (status, now_text(), reference_id))
        if status == "rejected" and character["canonical_reference_id"] == reference_id:
            connection.execute("UPDATE characters SET canonical_reference_id = NULL, updated_at = ? WHERE id = ?", (now_text(), character["id"]))
        if status == "approved":
            _mark_reference_impact(connection, character["project_id"], reference_id, "已审核参考图可进入生产")
        return reference_dict(connection, _reference_row(connection, reference_id))


def lock_character(character_id: str) -> dict[str, Any]:
    with session() as connection:
        character = _character_row(connection, character_id)
        canonical_id = character["canonical_reference_id"]
        if not canonical_id:
            raise ValueError("请先选择 Canonical Reference")
        canonical = _reference_row(connection, canonical_id)
        if canonical["lifecycle_status"] != "approved":
            raise ValueError("Canonical Reference 必须先通过人工审核")
        locked_at = now_text()
        connection.execute("UPDATE characters SET identity_locked = 1, locked_at = ?, status = '已锁定', updated_at = ? WHERE id = ?", (locked_at, locked_at, character_id))
        connection.execute("DELETE FROM continuity_locks WHERE scope_type = 'character' AND scope_id = ? AND lock_key IN ('identity_anchors', 'canonical_reference')", (character_id,))
        for key, value in (("identity_anchors", _json_field(character, "identity_anchors_json", {})), ("canonical_reference", canonical_id)):
            connection.execute("INSERT INTO continuity_locks(id, project_id, scope_type, scope_id, lock_key, value_json, source_ref) VALUES (?, ?, 'character', ?, ?, ?, ?)", (new_id("LOCK-"), character["project_id"], character_id, key, dumps(value), canonical_id))
        return character_dict(connection, _character_row(connection, character_id))


def unlock_character(character_id: str) -> dict[str, Any]:
    with session() as connection:
        character = _character_row(connection, character_id)
        connection.execute("UPDATE characters SET identity_locked = 0, status = '待确认', updated_at = ? WHERE id = ?", (now_text(), character_id))
        connection.execute("UPDATE continuity_locks SET status = 'released', updated_at = ? WHERE scope_type = 'character' AND scope_id = ?", (now_text(), character_id))
        return character_dict(connection, _character_row(connection, character_id))


def get_shot_characters(shot_id: str) -> list[dict[str, Any]]:
    with session() as connection:
        shot = connection.execute("SELECT s.id, e.project_id FROM shots s JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id WHERE s.id = ?", (shot_id,)).fetchone()
        if not shot:
            raise KeyError(f"shot {shot_id} not found")
        return _shot_character_bindings_from_connection(connection, shot_id)


def _shot_character_bindings_from_connection(connection, shot_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT sc.*, c.name, c.identity_locked, cl.name AS look_name
           FROM shot_characters sc JOIN characters c ON c.id = sc.character_id
           LEFT JOIN character_looks cl ON cl.id = sc.look_id
           WHERE sc.shot_id = ? ORDER BY sc.position, sc.character_id""", (shot_id,)
    ).fetchall()
    result = []
    for row in rows:
        refs = connection.execute("SELECT * FROM character_references WHERE id = ? AND lifecycle_status = 'approved'", (row["primary_reference_id"],)).fetchall() if row["primary_reference_id"] else []
        result.append({"id": row["id"], "shotId": shot_id, "characterId": row["character_id"], "name": row["name"], "lookId": row["look_id"] or row["outfit_id"], "lookName": row["look_name"], "legacyOutfitId": row["outfit_id"], "primaryReferenceId": row["primary_reference_id"], "references": [reference_dict(connection, ref) for ref in refs], "position": row["position"], "emotion": row["emotion"], "action": row["action"], "state": _json_field(row, "state_json", {}), "continuityOverrides": _json_field(row, "continuity_overrides_json", {}), "identityLocked": bool(row["identity_locked"]), "approvedForProduction": bool(refs) or not row["primary_reference_id"]})
    return result


def bind_shot_characters(shot_id: str, bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with session() as connection:
        shot = connection.execute("SELECT s.id, e.project_id FROM shots s JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id WHERE s.id = ?", (shot_id,)).fetchone()
        if not shot:
            raise KeyError(f"shot {shot_id} not found")
        connection.execute("DELETE FROM shot_characters WHERE shot_id = ?", (shot_id,))
        for position, item in enumerate(bindings):
            character_id = item.get("characterId") or item.get("character_id")
            character = _character_row(connection, character_id)
            if character["project_id"] != shot["project_id"]:
                raise ValueError("角色不属于该项目")
            look_id = item.get("lookId") or item.get("look_id") or item.get("outfitId")
            if look_id:
                look = _look_row(connection, look_id)
                if look["character_id"] != character_id:
                    raise ValueError("造型不属于该角色")
            reference_id = item.get("primaryReferenceId") or item.get("primary_reference_id")
            if reference_id:
                reference = _reference_row(connection, reference_id)
                if reference["character_id"] != character_id or reference["lifecycle_status"] != "approved":
                    raise ValueError("镜头只能绑定该角色已审核的参考图")
            connection.execute(
                """INSERT INTO shot_characters(
                  id, shot_id, character_id, outfit_id, look_id, primary_reference_id,
                  position, emotion, action, state_json, continuity_overrides_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (new_id("SCB-"), shot_id, character_id, item.get("outfitId") or item.get("outfit_id"), look_id, reference_id, position, item.get("emotion", ""), item.get("action", ""), dumps(item.get("state", {})), dumps(item.get("continuityOverrides", {}))),
            )
            _mark_character_impact(connection, shot["project_id"], character_id, "分镜角色绑定发生变化", specific_shot_id=shot_id)
        return _shot_character_bindings_from_connection(connection, shot_id)


def affected_shots_for_character(character_id: str, look_id: str | None = None) -> dict[str, Any]:
    with session() as connection:
        character = _character_row(connection, character_id)
        if look_id:
            _look_row(connection, look_id)
            rows = connection.execute("SELECT DISTINCT s.id, s.description, s.stale, s.cost FROM shot_characters sc JOIN shots s ON s.id = sc.shot_id WHERE sc.character_id = ? AND sc.look_id = ?", (character_id, look_id)).fetchall()
        else:
            rows = connection.execute("SELECT DISTINCT s.id, s.description, s.stale, s.cost FROM shot_characters sc JOIN shots s ON s.id = sc.shot_id WHERE sc.character_id = ?", (character_id,)).fetchall()
        items = [{"shotId": row["id"], "description": row["description"], "stale": bool(row["stale"]), "estimatedRegenerationCost": round(float(row["cost"] or 0.73), 2)} for row in rows]
        return {"characterId": character_id, "lookId": look_id, "shotIds": [item["shotId"] for item in items], "estimatedCost": round(sum(item["estimatedRegenerationCost"] for item in items), 2), "items": items}


def shot_generation_context(shot_id: str) -> dict[str, Any]:
    with session() as connection:
        rows = connection.execute("SELECT sc.*, c.name FROM shot_characters sc JOIN characters c ON c.id = sc.character_id WHERE sc.shot_id = ? ORDER BY sc.position, sc.character_id", (shot_id,)).fetchall()
        references = []
        for row in rows:
            query = "SELECT * FROM character_references WHERE character_id = ? AND lifecycle_status = 'approved'"
            params: list[Any] = [row["character_id"]]
            if row["primary_reference_id"]:
                query += " AND id = ?"
                params.append(row["primary_reference_id"])
            query += " ORDER BY is_primary DESC, CASE WHEN reference_type = 'master_sheet' THEN 0 ELSE 1 END, created_at DESC"
            refs = connection.execute(query, params).fetchall()
            for ref in refs:
                data = reference_dict(connection, ref)
                data["characterName"] = row["name"]
                data["lookId"] = row["look_id"] or row["outfit_id"]
                references.append(data)
        return {"shotId": shot_id, "references": references}


def build_character_prompt(connection, character) -> str:
    anchors = _json_field(character, "identity_anchors_json", {})
    return f"{character['name']}，{character['appearance']}。Identity anchors: {dumps(anchors)}。生成可作为短剧连续性参考的人物图，正面半身，电影感写实。"


def _mark_character_impact(connection, project_id: str, character_id: str, reason: str, specific_shot_id: str | None = None) -> None:
    query = "SELECT DISTINCT sc.shot_id FROM shot_characters sc JOIN shots s ON s.id = sc.shot_id WHERE sc.character_id = ?"
    params: list[Any] = [character_id]
    if specific_shot_id:
        query += " AND sc.shot_id = ?"
        params.append(specific_shot_id)
    shot_ids = connection.execute(query, params).fetchall()
    for item in shot_ids:
        connection.execute("UPDATE shots SET stale = 1, stale_reason = ?, updated_at = ? WHERE id = ?", (reason, now_text(), item["shot_id"]))
        connection.execute("INSERT OR IGNORE INTO dependencies(id, project_id, source_type, source_id, target_type, target_id, relation, status, stale_reason) VALUES (?, ?, 'character', ?, 'shot', ?, 'affects', 'active', ?)", (new_id("DEP-"), project_id, character_id, item["shot_id"], reason))


def _mark_reference_impact(connection, project_id: str, reference_id: str, reason: str) -> None:
    shot_ids = connection.execute("SELECT DISTINCT shot_id FROM shot_characters WHERE primary_reference_id = ?", (reference_id,)).fetchall()
    for item in shot_ids:
        connection.execute("UPDATE shots SET stale = 1, stale_reason = ?, updated_at = ? WHERE id = ?", (reason, now_text(), item["shot_id"]))
        connection.execute("INSERT OR IGNORE INTO dependencies(id, project_id, source_type, source_id, target_type, target_id, relation, status, stale_reason) VALUES (?, ?, 'character_reference', ?, 'shot', ?, 'affects', 'active', ?)", (new_id("DEP-"), project_id, reference_id, item["shot_id"], reason))


def migrate_legacy_character_assets() -> None:
    """Make existing outfit/image data usable by the new engine idempotently."""
    with session() as connection:
        characters = connection.execute("SELECT * FROM characters WHERE archived = 0").fetchall()
        for character in characters:
            looks = connection.execute("SELECT id FROM character_looks WHERE character_id = ?", (character["id"],)).fetchall()
            if not looks:
                outfits = connection.execute("SELECT * FROM character_outfits WHERE character_id = ? ORDER BY id", (character["id"],)).fetchall()
                if outfits:
                    for outfit in outfits:
                        connection.execute("INSERT OR IGNORE INTO character_looks(id, character_id, name, description, wardrobe_json, status) VALUES (?, ?, ?, ?, ?, ?)", (outfit["id"], character["id"], outfit["name"], outfit["description"], dumps({"legacyPrompt": outfit["prompt"]}), "approved" if outfit["status"] == "已锁定" else "draft"))
                else:
                    connection.execute("INSERT OR IGNORE INTO character_looks(id, character_id, name, description, status) VALUES (?, ?, '基础造型', '', 'draft')", (f"LOOK-{character['id']}-BASE", character["id"]))
            if character["image"] and not connection.execute("SELECT 1 FROM character_references WHERE character_id = ?", (character["id"],)).fetchone():
                media_id = new_id("MEDIA-")
                ref_id = f"REF-{character['id']}-LEGACY"
                lifecycle = "approved" if character["status"] == "已锁定" else "generated"
                primary = int(lifecycle == "approved")
                connection.execute("INSERT INTO media_assets(id, project_id, type, path_or_url, source) VALUES (?, ?, 'character_reference', ?, 'migration')", (media_id, character["project_id"], character["image"]))
                connection.execute("INSERT INTO character_references(id, character_id, look_id, media_asset_id, reference_type, view_angle, quality_level, lifecycle_status, is_primary, source, prompt_snapshot) VALUES (?, ?, (SELECT id FROM character_looks WHERE character_id = ? ORDER BY id LIMIT 1), ?, 'portrait', 'front', 'master', ?, ?, 'migration', 'Legacy character image')", (ref_id, character["id"], character["id"], media_id, lifecycle, primary))
                if lifecycle == "approved":
                    connection.execute("UPDATE characters SET canonical_reference_id = ?, identity_locked = 1, locked_at = COALESCE(locked_at, ?) WHERE id = ?", (ref_id, now_text(), character["id"]))
            connection.execute(
                """UPDATE shot_characters SET
                   look_id = COALESCE(
                     look_id,
                     CASE WHEN EXISTS (SELECT 1 FROM character_looks WHERE id = shot_characters.outfit_id AND character_id = ?) THEN outfit_id END,
                     (SELECT id FROM character_looks WHERE character_id = ? ORDER BY id LIMIT 1)
                   ),
                   primary_reference_id = COALESCE(primary_reference_id, (SELECT id FROM character_references WHERE character_id = ? AND lifecycle_status = 'approved' ORDER BY is_primary DESC, created_at LIMIT 1))
                   WHERE character_id = ?""",
                (character["id"], character["id"], character["id"], character["id"]),
            )
        project_rows = connection.execute("SELECT id FROM projects WHERE archived = 0").fetchall()
        for project in project_rows:
            connection.execute("UPDATE shots SET stale = COALESCE(stale, 0) WHERE id IN (SELECT sc.shot_id FROM shot_characters sc JOIN scenes s ON s.id = (SELECT scene_id FROM shots WHERE id = sc.shot_id) JOIN episodes e ON e.id = s.episode_id WHERE e.project_id = ?)", (project["id"],))
