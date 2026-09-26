from __future__ import annotations

import json
import math
import os
import struct
import uuid
import wave
from pathlib import Path
from typing import Any

from ..core.config import DATA_DIR
from ..core.database import session
from .repository import (
    _asset_url,
    _project_row,
    dumps,
    loads,
    new_id,
    now_text,
    task_row,
)


ALLOWED_CONSENT = {"user_owned", "licensed", "approved"}
DEFAULT_PROVIDER = "cosyvoice"


def _camel(value: Any, default: Any = None) -> Any:
    return default if value is None else value


def _profile_dict(connection, row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "characterId": row["character_id"],
        "name": row["name"],
        "providerType": row["provider_type"],
        "providerVoiceId": row["provider_voice_id"],
        "modelId": row["model_id"],
        "language": row["language"],
        "accent": row["accent"],
        "baseStyle": row["base_style"],
        "referenceAudioAssetId": row["reference_audio_asset_id"],
        "referenceAudioUrl": _asset_url(connection, row["reference_audio_asset_id"]),
        "referenceText": row["reference_text"],
        "embeddingRef": row["embedding_ref"],
        "metadata": loads(row["metadata_json"], {}),
        "consentStatus": row["consent_status"],
        "locked": bool(row["is_locked"]),
        "lockedAt": row["locked_at"],
        "default": bool(row["is_default"]),
        "source": row["source"],
        "ownerNote": row["owner_note"],
        "approvalAt": row["approval_at"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _performance_dict(row) -> dict[str, Any]:
    if not row:
        return {
            "emotion": "neutral", "emotionIntensity": 0.5, "speed": 1.0,
            "pitch": 0.0, "volumeDb": 0.0, "pauseBeforeMs": 0,
            "pauseAfterMs": 0, "breathCues": [], "deliveryInstruction": "",
            "targetDurationMs": None, "source": "manual",
        }
    return {
        "emotion": row["emotion"],
        "emotionIntensity": row["emotion_intensity"],
        "speed": row["speed"],
        "pitch": row["pitch"],
        "volumeDb": row["volume_db"],
        "pauseBeforeMs": row["pause_before_ms"],
        "pauseAfterMs": row["pause_after_ms"],
        "breathCues": loads(row["breath_cues_json"], []),
        "deliveryInstruction": row["delivery_instruction"],
        "targetDurationMs": row["target_duration_ms"],
        "source": row["source"],
    }


def _take_dict(connection, row) -> dict[str, Any]:
    qc = connection.execute(
        "SELECT check_type, score, severity, message, metadata_json, status FROM audio_qc_records WHERE voice_take_id = ? ORDER BY created_at",
        (row["id"],),
    ).fetchall()
    return {
        "id": row["id"],
        "dialogueLineId": row["dialogue_line_id"],
        "generationTaskId": row["generation_task_id"],
        "mediaAssetId": row["media_asset_id"],
        "outputUrl": _asset_url(connection, row["media_asset_id"]),
        "provider": row["provider"],
        "model": row["model"],
        "durationMs": row["duration_ms"],
        "estimatedCost": row["estimated_cost"],
        "actualCost": row["actual_cost"],
        "qcScore": row["qc_score"],
        "qcStatus": row["qc_status"],
        "status": row["status"],
        "active": bool(row["is_active"]),
        "stale": bool(row["stale"]),
        "staleReason": row["stale_reason"],
        "createdAt": row["created_at"],
        "qc": [
            {"type": item["check_type"], "score": item["score"], "severity": item["severity"], "message": item["message"], "metadata": loads(item["metadata_json"], {}), "status": item["status"]}
            for item in qc
        ],
    }


def _line_dict(connection, row) -> dict[str, Any]:
    profile = connection.execute("SELECT * FROM voice_profiles WHERE id = ?", (row["voice_profile_id"],)).fetchone() if row["voice_profile_id"] else None
    performance = connection.execute("SELECT * FROM voice_performances WHERE dialogue_line_id = ?", (row["id"],)).fetchone()
    takes = connection.execute("SELECT * FROM voice_takes WHERE dialogue_line_id = ? ORDER BY created_at DESC", (row["id"],)).fetchall()
    character = connection.execute("SELECT name FROM characters WHERE id = ?", (row["character_id"],)).fetchone() if row["character_id"] else None
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "episodeId": row["episode_id"],
        "sceneId": row["scene_id"],
        "shotId": row["shot_id"],
        "characterId": row["character_id"],
        "characterName": character["name"] if character else "未指定角色",
        "order": row["order_index"],
        "text": row["text"],
        "language": row["language"],
        "startOffsetMs": row["start_offset_ms"],
        "targetDurationMs": row["target_duration_ms"],
        "voiceProfileId": row["voice_profile_id"],
        "voiceProfile": _profile_dict(connection, profile) if profile else None,
        "pronunciationOverrides": loads(row["pronunciation_overrides_json"], {}),
        "performance": _performance_dict(performance),
        "status": row["status"],
        "stale": bool(row["stale"]),
        "staleReason": row["stale_reason"],
        "takes": [_take_dict(connection, item) for item in takes],
        "activeTake": next((_take_dict(connection, item) for item in takes if item["is_active"]), None),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _profile_for_character(connection, character_id: str | None):
    if not character_id:
        return None
    return connection.execute(
        "SELECT * FROM voice_profiles WHERE character_id = ? ORDER BY is_default DESC, created_at LIMIT 1",
        (character_id,),
    ).fetchone()


def migrate_legacy_audio() -> None:
    """Create safe, editable audio rows without erasing legacy fields."""
    with session() as connection:
        characters = connection.execute("SELECT * FROM characters WHERE archived = 0 ORDER BY id").fetchall()
        for character in characters:
            existing = connection.execute("SELECT id FROM voice_profiles WHERE character_id = ? LIMIT 1", (character["id"],)).fetchone()
            if existing:
                continue
            legacy = loads(character["voice_profile"], {}) if character["voice_profile"] else {}
            if not isinstance(legacy, dict):
                legacy = {}
            profile_id = f"VP-{character['id']}-DEFAULT"
            connection.execute(
                """INSERT OR IGNORE INTO voice_profiles(
                    id, project_id, character_id, name, provider_type, provider_voice_id, model_id,
                    language, accent, base_style, metadata_json, consent_status, is_default, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unknown', 1, ?)""",
                (
                    profile_id, character["project_id"], character["id"],
                    legacy.get("name") or f"{character['name']} · 默认声音",
                    legacy.get("providerType") or legacy.get("provider") or DEFAULT_PROVIDER,
                    legacy.get("providerVoiceId") or legacy.get("voiceId") or "",
                    legacy.get("modelId") or "",
                    legacy.get("language") or "zh-CN", legacy.get("accent") or "",
                    legacy.get("baseStyle") or legacy.get("style") or "",
                    dumps(legacy), "migrated",
                ),
            )
        shots = connection.execute(
            """SELECT s.*, sc.episode_id, e.project_id FROM shots s
               JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id
               WHERE s.archived = 0 AND TRIM(s.dialogue) <> '' ORDER BY e.order_index, sc.order_index, s.order_index"""
        ).fetchall()
        for shot in shots:
            bindings = connection.execute("SELECT character_id FROM shot_characters WHERE shot_id = ? ORDER BY character_id", (shot["id"],)).fetchall()
            for position, binding in enumerate(bindings):
                exists = connection.execute("SELECT id FROM dialogue_lines WHERE shot_id = ? AND character_id = ? LIMIT 1", (shot["id"], binding["character_id"])).fetchone()
                if exists:
                    continue
                line_id = f"DL-{shot['id']}-{binding['character_id']}"
                profile = _profile_for_character(connection, binding["character_id"])
                target = int(shot["duration"] or 0) * 1000 or None
                connection.execute(
                    """INSERT OR IGNORE INTO dialogue_lines(
                      id, project_id, episode_id, scene_id, shot_id, character_id, order_index,
                      text, target_duration_ms, voice_profile_id, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')""",
                    (line_id, shot["project_id"], shot["episode_id"], shot["scene_id"], shot["id"], binding["character_id"], position, shot["dialogue"], target, profile["id"] if profile else None),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO voice_performances(dialogue_line_id, target_duration_ms, source) VALUES (?, ?, 'migrated')",
                    (line_id, target),
                )


def list_voice_profiles(character_id: str) -> list[dict[str, Any]]:
    with session() as connection:
        rows = connection.execute("SELECT * FROM voice_profiles WHERE character_id = ? ORDER BY is_default DESC, created_at", (character_id,)).fetchall()
        if not rows and not connection.execute("SELECT 1 FROM characters WHERE id = ?", (character_id,)).fetchone():
            raise KeyError(f"character {character_id} not found")
        return [_profile_dict(connection, row) for row in rows]


def create_voice_profile(character_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with session() as connection:
        character = connection.execute("SELECT * FROM characters WHERE id = ? AND archived = 0", (character_id,)).fetchone()
        if not character:
            raise KeyError(f"character {character_id} not found")
        profile_id = payload.get("id") or new_id("VP-")
        is_default = bool(payload.get("default", payload.get("isDefault", False)))
        if is_default:
            connection.execute("UPDATE voice_profiles SET is_default = 0 WHERE character_id = ?", (character_id,))
        connection.execute(
            """INSERT INTO voice_profiles(
              id, project_id, character_id, name, provider_type, provider_voice_id, model_id,
              language, accent, base_style, reference_audio_asset_id, reference_text, embedding_ref,
              metadata_json, consent_status, is_default, source, owner_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile_id, character["project_id"], character_id,
                payload.get("name") or f"{character['name']} · 声音 {profile_id[-4:]}",
                payload.get("providerType") or payload.get("provider") or DEFAULT_PROVIDER,
                payload.get("providerVoiceId") or payload.get("voiceId") or "",
                payload.get("modelId") or "", payload.get("language") or "zh-CN",
                payload.get("accent") or "", payload.get("baseStyle") or payload.get("style") or "",
                payload.get("referenceAudioAssetId"), payload.get("referenceText") or "",
                payload.get("embeddingRef") or "", dumps(payload.get("metadata", {})),
                payload.get("consentStatus") or "unknown", int(is_default), payload.get("source") or "manual", payload.get("ownerNote") or "",
            ),
        )
        return _profile_dict(connection, connection.execute("SELECT * FROM voice_profiles WHERE id = ?", (profile_id,)).fetchone())


def _profile_row(connection, profile_id: str):
    row = connection.execute("SELECT * FROM voice_profiles WHERE id = ?", (profile_id,)).fetchone()
    if not row:
        raise KeyError(f"voice profile {profile_id} not found")
    return row


def _mark_profile_impact(connection, profile_id: str, reason: str) -> None:
    lines = connection.execute("SELECT id FROM dialogue_lines WHERE voice_profile_id = ?", (profile_id,)).fetchall()
    for line in lines:
        connection.execute("UPDATE dialogue_lines SET stale = 1, stale_reason = ?, updated_at = ? WHERE id = ?", (reason, now_text(), line["id"]))
        connection.execute("UPDATE voice_takes SET stale = 1, stale_reason = ?, updated_at = ? WHERE dialogue_line_id = ?", (reason, now_text(), line["id"]))
        connection.execute("UPDATE audio_clips SET stale = 1, stale_reason = ?, updated_at = ? WHERE linked_dialogue_line_id = ?", (reason, now_text(), line["id"]))


def patch_voice_profile(profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "name": "name", "providerType": "provider_type", "providerVoiceId": "provider_voice_id", "modelId": "model_id",
        "language": "language", "accent": "accent", "baseStyle": "base_style", "referenceAudioAssetId": "reference_audio_asset_id",
        "referenceText": "reference_text", "embeddingRef": "embedding_ref", "consentStatus": "consent_status", "ownerNote": "owner_note",
    }
    with session() as connection:
        row = _profile_row(connection, profile_id)
        if row["is_locked"]:
            raise ValueError("声音档案已锁定，请先解锁后修改")
        values = [(column, payload[key]) for key, column in allowed.items() if key in payload]
        if "metadata" in payload:
            values.append(("metadata_json", dumps(payload["metadata"])))
        if values:
            values.append(("updated_at", now_text()))
            connection.execute(f"UPDATE voice_profiles SET {', '.join(f'{column} = ?' for column, _ in values)} WHERE id = ?", [value for _, value in values] + [profile_id])
            _mark_profile_impact(connection, profile_id, "声音档案已更新，需要重新生成音频")
        return _profile_dict(connection, _profile_row(connection, profile_id))


def lock_voice_profile(profile_id: str) -> dict[str, Any]:
    with session() as connection:
        row = _profile_row(connection, profile_id)
        if row["consent_status"] not in ALLOWED_CONSENT:
            raise ValueError("锁定声音前请确认声音来源权利：自有、已授权或已审核")
        connection.execute("UPDATE voice_profiles SET is_locked = 1, locked_at = ?, updated_at = ? WHERE id = ?", (now_text(), now_text(), profile_id))
        return _profile_dict(connection, _profile_row(connection, profile_id))


def unlock_voice_profile(profile_id: str) -> dict[str, Any]:
    with session() as connection:
        _profile_row(connection, profile_id)
        connection.execute("UPDATE voice_profiles SET is_locked = 0, updated_at = ? WHERE id = ?", (now_text(), profile_id))
        return _profile_dict(connection, _profile_row(connection, profile_id))


def _line_row(connection, line_id: str):
    row = connection.execute("SELECT * FROM dialogue_lines WHERE id = ?", (line_id,)).fetchone()
    if not row:
        raise KeyError(f"dialogue line {line_id} not found")
    return row


def extract_dialogue_lines(scene_id: str) -> list[dict[str, Any]]:
    with session() as connection:
        scene = connection.execute("SELECT * FROM scenes WHERE id = ? AND archived = 0", (scene_id,)).fetchone()
        if not scene:
            raise KeyError(f"scene {scene_id} not found")
        episode = connection.execute("SELECT * FROM episodes WHERE id = ?", (scene["episode_id"],)).fetchone()
        shots = connection.execute("SELECT * FROM shots WHERE scene_id = ? AND archived = 0 AND TRIM(dialogue) <> '' ORDER BY order_index", (scene_id,)).fetchall()
        for shot in shots:
            bindings = connection.execute("SELECT character_id FROM shot_characters WHERE shot_id = ? ORDER BY character_id", (shot["id"],)).fetchall()
            for index, binding in enumerate(bindings):
                existing = connection.execute("SELECT id FROM dialogue_lines WHERE shot_id = ? AND character_id = ?", (shot["id"], binding["character_id"])).fetchone()
                if existing:
                    continue
                profile = _profile_for_character(connection, binding["character_id"])
                target = int(shot["duration"] or 0) * 1000 or None
                line_id = new_id("DL-")
                connection.execute(
                    "INSERT INTO dialogue_lines(id, project_id, episode_id, scene_id, shot_id, character_id, order_index, text, target_duration_ms, voice_profile_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (line_id, episode["project_id"], episode["id"], scene_id, shot["id"], binding["character_id"], shot["order_index"] * 100 + index, shot["dialogue"], target, profile["id"] if profile else None),
                )
                connection.execute("INSERT INTO voice_performances(dialogue_line_id, target_duration_ms, source) VALUES (?, ?, 'extracted')", (line_id, target))
        rows = connection.execute("SELECT * FROM dialogue_lines WHERE scene_id = ? ORDER BY order_index, created_at", (scene_id,)).fetchall()
        return [_line_dict(connection, row) for row in rows]


def list_dialogue_lines(*, project_id: str | None = None, episode_id: str | None = None, scene_id: str | None = None, shot_id: str | None = None) -> list[dict[str, Any]]:
    where = []
    values: list[Any] = []
    for column, value in (("project_id", project_id), ("episode_id", episode_id), ("scene_id", scene_id), ("shot_id", shot_id)):
        if value:
            where.append(f"{column} = ?")
            values.append(value)
    with session() as connection:
        rows = connection.execute(f"SELECT * FROM dialogue_lines {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY episode_id, scene_id, order_index, created_at", values).fetchall()
        return [_line_dict(connection, row) for row in rows]


def create_dialogue_line(scene_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with session() as connection:
        scene = connection.execute("SELECT s.*, e.project_id FROM scenes s JOIN episodes e ON e.id = s.episode_id WHERE s.id = ? AND s.archived = 0", (scene_id,)).fetchone()
        if not scene:
            raise KeyError(f"scene {scene_id} not found")
        line_id = payload.get("id") or new_id("DL-")
        text = (payload.get("text") or payload.get("dialogue") or "").strip()
        if not text:
            raise ValueError("台词内容不能为空")
        profile_id = payload.get("voiceProfileId") or payload.get("voice_profile_id")
        if profile_id:
            _profile_row(connection, profile_id)
        target = payload.get("targetDurationMs") or payload.get("target_duration_ms")
        connection.execute(
            "INSERT INTO dialogue_lines(id, project_id, episode_id, scene_id, shot_id, character_id, order_index, text, language, start_offset_ms, target_duration_ms, voice_profile_id, pronunciation_overrides_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (line_id, scene["project_id"], scene["episode_id"], scene_id, payload.get("shotId"), payload.get("characterId"), int(payload.get("order", 9999)), text, payload.get("language", "zh-CN"), int(payload.get("startOffsetMs", 0)), int(target) if target is not None else None, profile_id, dumps(payload.get("pronunciationOverrides", {}))),
        )
        connection.execute("INSERT INTO voice_performances(dialogue_line_id, target_duration_ms, source) VALUES (?, ?, 'manual')", (line_id, target))
        return _line_dict(connection, _line_row(connection, line_id))


def patch_dialogue_line(line_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"text": "text", "language": "language", "startOffsetMs": "start_offset_ms", "targetDurationMs": "target_duration_ms", "voiceProfileId": "voice_profile_id", "status": "status"}
    with session() as connection:
        _line_row(connection, line_id)
        values = [(column, payload[key]) for key, column in allowed.items() if key in payload]
        if "pronunciationOverrides" in payload:
            values.append(("pronunciation_overrides_json", dumps(payload["pronunciationOverrides"])))
        if values:
            values.append(("stale", 1))
            values.append(("stale_reason", "台词或目标时长已更新，需要重新生成"))
            values.append(("updated_at", now_text()))
            connection.execute(f"UPDATE dialogue_lines SET {', '.join(f'{column} = ?' for column, _ in values)} WHERE id = ?", [value for _, value in values] + [line_id])
        if any(key in payload for key in ("targetDurationMs",)):
            connection.execute("UPDATE voice_performances SET target_duration_ms = ?, updated_at = ? WHERE dialogue_line_id = ?", (payload.get("targetDurationMs"), now_text(), line_id))
        return _line_dict(connection, _line_row(connection, line_id))


def direct_performance(line_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with session() as connection:
        line = _line_row(connection, line_id)
        text = line["text"]
        emotion = payload.get("emotion") or ("惊讶" if "?" in text or "？" in text else "坚定" if "!" in text or "！" in text else "克制")
        intensity = float(payload.get("emotionIntensity", 0.72 if emotion in {"惊讶", "坚定"} else 0.48))
        speed = float(payload.get("speed", 1.0))
        values = (emotion, max(0, min(1, intensity)), max(0.5, min(1.5, speed)), float(payload.get("pitch", 0)), float(payload.get("volumeDb", 0)), int(payload.get("pauseBeforeMs", 0)), int(payload.get("pauseAfterMs", 0)), dumps(payload.get("breathCues", [])), payload.get("deliveryInstruction") or "先稳住情绪，再把关键词说清楚", line["target_duration_ms"], payload.get("source") or "direct", now_text())
        connection.execute("""INSERT INTO voice_performances(dialogue_line_id, emotion, emotion_intensity, speed, pitch, volume_db, pause_before_ms, pause_after_ms, breath_cues_json, delivery_instruction, target_duration_ms, source, updated_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(dialogue_line_id) DO UPDATE SET emotion=excluded.emotion, emotion_intensity=excluded.emotion_intensity, speed=excluded.speed, pitch=excluded.pitch, volume_db=excluded.volume_db, pause_before_ms=excluded.pause_before_ms, pause_after_ms=excluded.pause_after_ms, breath_cues_json=excluded.breath_cues_json, delivery_instruction=excluded.delivery_instruction, source=excluded.source, updated_at=excluded.updated_at""", (line_id, *values))
        connection.execute("UPDATE dialogue_lines SET stale = 1, stale_reason = '声音表现已更新，需要重新生成', updated_at = ? WHERE id = ?", (now_text(), line_id))
        return _performance_dict(connection.execute("SELECT * FROM voice_performances WHERE dialogue_line_id = ?", (line_id,)).fetchone())


def duration_fit(actual_ms: int | None, target_ms: int | None) -> dict[str, Any]:
    if not actual_ms or not target_ms:
        return {"actualMs": actual_ms, "targetMs": target_ms, "errorRatio": None, "decision": "not_applicable", "recommendation": "未设置目标时长"}
    error = abs(actual_ms - target_ms) / target_ms
    if error <= 0.05:
        decision, recommendation = "pass", "时长在目标范围内"
    elif error <= 0.12:
        decision, recommendation = "stretch", "允许小幅变速或受控 time-stretch"
    else:
        decision, recommendation = "regenerate", "建议重新生成或缩短台词，不要极端加速"
    return {"actualMs": actual_ms, "targetMs": target_ms, "errorRatio": round(error, 4), "decision": decision, "recommendation": recommendation}


def _profile_snapshot(connection, profile_id: str | None) -> dict[str, Any]:
    row = _profile_row(connection, profile_id) if profile_id else None
    return _profile_dict(connection, row) if row else {}


def generate_dialogue_line(line_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with session() as connection:
        line = _line_row(connection, line_id)
        profile = _profile_row(connection, line["voice_profile_id"]) if line["voice_profile_id"] else _profile_for_character(connection, line["character_id"])
        if not profile:
            raise ValueError("请先为台词绑定声音档案")
        if line["voice_profile_id"] != profile["id"]:
            connection.execute("UPDATE dialogue_lines SET voice_profile_id = ?, updated_at = ? WHERE id = ?", (profile["id"], now_text(), line_id))
        performance = connection.execute("SELECT * FROM voice_performances WHERE dialogue_line_id = ?", (line_id,)).fetchone()
        performance_data = _performance_dict(performance)
        target = payload.get("targetDurationMs") or line["target_duration_ms"] or performance_data.get("targetDurationMs")
        provider = payload.get("provider") or profile["provider_type"] or "mock"
        model = payload.get("model") or profile["model_id"] or f"{provider}-default"
        take_id = new_id("VT-")
        estimated = float(payload.get("estimatedCost", 0.08))
        connection.execute(
            """INSERT INTO voice_takes(id, project_id, dialogue_line_id, provider, model, voice_profile_snapshot_json, performance_snapshot_json, input_text_snapshot, reference_audio_snapshot_json, duration_ms, estimated_cost, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 'queued')""",
            (take_id, line["project_id"], line_id, provider, model, dumps(_profile_snapshot(connection, profile["id"])), dumps({**performance_data, "targetDurationMs": target}), line["text"], dumps({"referenceAudioAssetId": profile["reference_audio_asset_id"], "referenceText": profile["reference_text"]}), estimated),
        )
        task_id = new_id("T-")
        parameters = {
            "text": line["text"], "voice": _profile_snapshot(connection, profile["id"]),
            "performance": {**performance_data, "targetDurationMs": target},
            "target_duration_ms": target, "mock_duration_ratio": payload.get("mockDurationRatio"),
            "references": [profile["reference_audio_asset_id"]] if profile["reference_audio_asset_id"] else [],
        }
        connection.execute(
            """INSERT INTO generation_tasks(id, project_id, shot_id, target_type, target_id, type, provider, model, status, prompt, parameters_json, estimated_cost)
            VALUES (?, ?, NULL, 'voice_take', ?, '音频', ?, ?, 'Queued', ?, ?, ?)""",
            (task_id, line["project_id"], take_id, provider, model, line["text"], dumps(parameters), estimated),
        )
        connection.execute("UPDATE voice_takes SET generation_task_id = ?, updated_at = ? WHERE id = ?", (task_id, now_text(), take_id))
        connection.execute("UPDATE dialogue_lines SET status = 'queued', stale = 0, stale_reason = '', updated_at = ? WHERE id = ?", (now_text(), line_id))
    task = task_row(task_id)
    return {"takeId": take_id, "taskId": task_id, "lineId": line_id, "task": dict(task) if task else None}


def generate_episode_dialogue(episode_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    scene_id = payload.get("sceneId")
    if scene_id:
        extract_dialogue_lines(scene_id)
    lines = list_dialogue_lines(episode_id=episode_id)
    results = []
    failures = []
    for line in lines:
        try:
            results.append(generate_dialogue_line(line["id"], payload))
        except (KeyError, ValueError) as error:
            failures.append({"lineId": line["id"], "error": str(error)})
    return {"episodeId": episode_id, "created": results, "failures": failures, "count": len(results), "failedCount": len(failures)}


def list_takes(line_id: str) -> list[dict[str, Any]]:
    with session() as connection:
        _line_row(connection, line_id)
        return [_take_dict(connection, row) for row in connection.execute("SELECT * FROM voice_takes WHERE dialogue_line_id = ? ORDER BY created_at DESC", (line_id,)).fetchall()]


def activate_take(take_id: str) -> dict[str, Any]:
    with session() as connection:
        take = connection.execute("SELECT * FROM voice_takes WHERE id = ?", (take_id,)).fetchone()
        if not take:
            raise KeyError(f"voice take {take_id} not found")
        if take["status"] != "success" and take["status"] != "Success":
            raise ValueError("只有已完成的音频 Take 才能启用")
        connection.execute("UPDATE voice_takes SET is_active = 0 WHERE dialogue_line_id = ?", (take["dialogue_line_id"],))
        connection.execute("UPDATE voice_takes SET is_active = 1, updated_at = ? WHERE id = ?", (now_text(), take_id))
        connection.execute("UPDATE dialogue_lines SET status = 'active', stale = 0, stale_reason = '', updated_at = ? WHERE id = ?", (now_text(), take["dialogue_line_id"]))
        return _take_dict(connection, connection.execute("SELECT * FROM voice_takes WHERE id = ?", (take_id,)).fetchone())


def _audio_file(path_or_url: str | None) -> Path | None:
    if not path_or_url:
        return None
    if path_or_url.startswith("/generated-media/"):
        candidate = (DATA_DIR / "generated-audio" / Path(path_or_url).name).resolve()
        if DATA_DIR.resolve() in candidate.parents:
            return candidate
    if path_or_url.startswith("/"):
        candidate = Path(path_or_url)
        return candidate if candidate.is_file() else None
    return None


def run_qc(take_id: str) -> dict[str, Any]:
    with session() as connection:
        take = connection.execute("SELECT * FROM voice_takes WHERE id = ?", (take_id,)).fetchone()
        if not take:
            raise KeyError(f"voice take {take_id} not found")
        line = _line_row(connection, take["dialogue_line_id"])
        url = _asset_url(connection, take["media_asset_id"])
        path = _audio_file(url)
        connection.execute("DELETE FROM audio_qc_records WHERE voice_take_id = ?", (take_id,))
        checks: list[dict[str, Any]] = []
        actual_ms = None
        if not path or not path.exists():
            checks.append({"type": "file_exists", "score": 0, "severity": "error", "message": "音频文件不存在或当前远程地址未缓存", "metadata": {}})
        else:
            try:
                with wave.open(str(path), "rb") as audio:
                    frames = audio.readframes(audio.getnframes())
                    sample_width = audio.getsampwidth()
                    channels = audio.getnchannels()
                    rate = audio.getframerate()
                    actual_ms = round(audio.getnframes() * 1000 / max(rate, 1))
                    if sample_width == 2:
                        values = struct.unpack("<%dh" % (len(frames) // 2), frames)
                        values = values[::max(channels, 1)]
                        peak = max((abs(value) for value in values), default=0)
                        rms = math.sqrt(sum(value * value for value in values) / max(len(values), 1))
                        silence_ratio = sum(1 for value in values if abs(value) < 300) / max(len(values), 1)
                        clip_ratio = sum(1 for value in values if abs(value) >= 32760) / max(len(values), 1)
                        loudness = 20 * math.log10(max(rms, 1) / 32768)
                        checks.extend([
                            {"type": "file_exists", "score": 100, "severity": "info", "message": "WAV 可解码", "metadata": {"sampleRate": rate, "channels": channels}},
                            {"type": "silence", "score": round((1 - silence_ratio) * 100, 1), "severity": "warning" if silence_ratio > 0.8 else "info", "message": f"静音比例 {silence_ratio:.1%}", "metadata": {"silenceRatio": round(silence_ratio, 4)}},
                            {"type": "clipping", "score": round((1 - clip_ratio) * 100, 1), "severity": "error" if clip_ratio > 0.01 else "info", "message": f"峰值 {peak}/32767", "metadata": {"peak": peak, "clipRatio": round(clip_ratio, 4)}},
                            {"type": "loudness", "score": round(max(0, min(100, (loudness + 60) / 42 * 100)), 1), "severity": "info", "message": f"估算响度 {loudness:.1f} dBFS", "metadata": {"dbfs": round(loudness, 2)}},
                        ])
            except (wave.Error, EOFError, struct.error) as error:
                checks.append({"type": "decode", "score": 0, "severity": "error", "message": f"音频解码失败：{error}", "metadata": {}})
        fit = duration_fit(actual_ms, line["target_duration_ms"])
        checks.append({"type": "duration_fit", "score": 100 if fit["decision"] == "pass" else 75 if fit["decision"] == "stretch" else 40 if fit["decision"] == "regenerate" else None, "severity": "warning" if fit["decision"] in {"stretch", "regenerate"} else "info", "message": fit["recommendation"], "metadata": fit})
        for item in checks:
            connection.execute("INSERT INTO audio_qc_records(id, voice_take_id, check_type, score, severity, message, metadata_json, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (new_id("AQC-"), take_id, item["type"], item["score"], item["severity"], item["message"], dumps(item["metadata"]), "passed" if item["severity"] == "info" else "needs_review"))
        scores = [item["score"] for item in checks if item["score"] is not None]
        score = round(sum(scores) / len(scores), 1) if scores else 0
        status = "pass" if all(item["severity"] == "info" for item in checks) else "warning" if not any(item["severity"] == "error" for item in checks) else "fail"
        connection.execute("UPDATE voice_takes SET duration_ms = COALESCE(?, duration_ms), qc_score = ?, qc_status = ?, status = CASE WHEN status IN ('queued', 'running', 'Processing') THEN 'success' ELSE status END, updated_at = ? WHERE id = ?", (actual_ms, score, status, now_text(), take_id))
        return {"take": _take_dict(connection, connection.execute("SELECT * FROM voice_takes WHERE id = ?", (take_id,)).fetchone()), "status": status, "score": score, "checks": checks, "durationFit": fit}


def list_audio_clips(project_id: str, episode_id: str | None = None) -> list[dict[str, Any]]:
    with session() as connection:
        values: list[Any] = [project_id]
        where = "project_id = ?"
        if episode_id:
            where += " AND episode_id = ?"
            values.append(episode_id)
        rows = connection.execute(f"SELECT * FROM audio_clips WHERE {where} ORDER BY timeline_start_ms, track_type", values).fetchall()
        return [{"id": row["id"], "episodeId": row["episode_id"], "sceneId": row["scene_id"], "trackType": row["track_type"], "mediaAssetId": row["media_asset_id"], "outputUrl": _asset_url(connection, row["media_asset_id"]), "timelineStartMs": row["timeline_start_ms"], "durationMs": row["duration_ms"], "gainDb": row["gain_db"], "linkedDialogueLineId": row["linked_dialogue_line_id"], "stale": bool(row["stale"]), "staleReason": row["stale_reason"]} for row in rows]


def create_audio_clip(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with session() as connection:
        _project_row(connection, project_id)
        media_asset_id = payload.get("mediaAssetId")
        if payload.get("takeId"):
            take = connection.execute("SELECT media_asset_id, duration_ms, dialogue_line_id FROM voice_takes WHERE id = ?", (payload["takeId"],)).fetchone()
            if not take:
                raise KeyError(f"voice take {payload['takeId']} not found")
            media_asset_id = take["media_asset_id"]
            payload.setdefault("durationMs", take["duration_ms"] or 0)
            payload.setdefault("linkedDialogueLineId", take["dialogue_line_id"])
        if not media_asset_id:
            raise ValueError("音频轨道需要 mediaAssetId 或 takeId")
        clip_id = payload.get("id") or new_id("ACL-")
        connection.execute("INSERT INTO audio_clips(id, project_id, episode_id, scene_id, track_type, media_asset_id, timeline_start_ms, source_start_ms, duration_ms, gain_db, fade_in_ms, fade_out_ms, linked_dialogue_line_id, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (clip_id, project_id, payload.get("episodeId"), payload.get("sceneId"), payload.get("trackType", "dialogue"), media_asset_id, int(payload.get("timelineStartMs", 0)), int(payload.get("sourceStartMs", 0)), int(payload.get("durationMs", 0)), float(payload.get("gainDb", 0)), int(payload.get("fadeInMs", 0)), int(payload.get("fadeOutMs", 0)), payload.get("linkedDialogueLineId"), dumps(payload.get("metadata", {}))))
        row = connection.execute("SELECT * FROM audio_clips WHERE id = ?", (clip_id,)).fetchone()
        return {"id": row["id"], "trackType": row["track_type"], "timelineStartMs": row["timeline_start_ms"], "durationMs": row["duration_ms"], "outputUrl": _asset_url(connection, row["media_asset_id"]), "linkedDialogueLineId": row["linked_dialogue_line_id"]}


def _write_silence_or_mix(path: Path, clips: list[dict[str, Any]], connection) -> int:
    sample_rate = 16000
    end_ms = max([int(item["timeline_start_ms"] or 0) + int(item["duration_ms"] or 0) for item in clips] or [1000])
    samples = [0] * max(1, round(end_ms * sample_rate / 1000))
    for item in clips:
        source_url = _asset_url(connection, item["media_asset_id"])
        source = _audio_file(source_url)
        if not source or not source.exists():
            continue
        try:
            with wave.open(str(source), "rb") as audio:
                frames = audio.readframes(audio.getnframes())
                if audio.getsampwidth() != 2:
                    continue
                values = struct.unpack("<%dh" % (len(frames) // 2), frames)
                start = round(int(item["timeline_start_ms"] or 0) * sample_rate / 1000)
                for index, value in enumerate(values[: max(0, len(samples) - start)]):
                    samples[start + index] = max(-32768, min(32767, samples[start + index] + value))
        except (wave.Error, EOFError, struct.error):
            continue
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(struct.pack("<%dh" % len(samples), *samples))
    return round(len(samples) * 1000 / sample_rate)


def mixdown_episode(episode_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with session() as connection:
        episode = connection.execute("SELECT * FROM episodes WHERE id = ? AND archived = 0", (episode_id,)).fetchone()
        if not episode:
            raise KeyError(f"episode {episode_id} not found")
        clips = connection.execute("SELECT * FROM audio_clips WHERE episode_id = ? ORDER BY timeline_start_ms", (episode_id,)).fetchall()
        mix_id = new_id("MIX-")
        output_file = DATA_DIR / "generated-audio" / f"{mix_id}.wav"
        duration = _write_silence_or_mix(output_file, clips, connection)
        asset_id = new_id("AS-")
        output_url = f"/generated-media/{output_file.name}"
        connection.execute("INSERT INTO media_assets(id, project_id, type, path_or_url, source, provider, model, metadata_json) VALUES (?, ?, 'audio_mixdown', ?, 'generated', 'local-mix', 'wav', ?)", (asset_id, episode["project_id"], output_url, dumps({"episodeId": episode_id, "clipCount": len(clips)})))
        connection.execute("INSERT INTO audio_mixdowns(id, project_id, episode_id, media_asset_id, duration_ms, loudness_lufs, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?)", (mix_id, episode["project_id"], episode_id, asset_id, duration, -24.0, dumps({"clipCount": len(clips), "engine": "manju-v1"})))
        return {"id": mix_id, "episodeId": episode_id, "mediaAssetId": asset_id, "outputUrl": output_url, "durationMs": duration, "clipCount": len(clips), "status": "ready"}


def list_mixdowns(project_id: str, episode_id: str | None = None) -> list[dict[str, Any]]:
    with session() as connection:
        values: list[Any] = [project_id]
        where = "project_id = ?"
        if episode_id:
            where += " AND episode_id = ?"
            values.append(episode_id)
        rows = connection.execute(f"SELECT * FROM audio_mixdowns WHERE {where} ORDER BY created_at DESC", values).fetchall()
        return [{"id": row["id"], "episodeId": row["episode_id"], "outputUrl": _asset_url(connection, row["media_asset_id"]), "durationMs": row["duration_ms"], "loudnessLufs": row["loudness_lufs"], "status": row["status"], "createdAt": row["created_at"]} for row in rows]


def audio_status(episode_id: str) -> dict[str, Any]:
    lines = list_dialogue_lines(episode_id=episode_id)
    return {"episodeId": episode_id, "lines": lines, "counts": {"total": len(lines), "ready": sum(1 for line in lines if line["activeTake"]), "queued": sum(1 for line in lines if line["status"] == "queued"), "stale": sum(1 for line in lines if line["stale"])}, "mixdowns": list_mixdowns(next((line["projectId"] for line in lines), "P001"), episode_id) if lines else []}


def provider_definitions() -> list[dict[str, Any]]:
    with session() as connection:
        rows = connection.execute("SELECT * FROM voice_provider_definitions ORDER BY provider_type").fetchall()
        endpoints = {"cosyvoice": os.environ.get("SHORT_DRAMA_COSYVOICE_URL", ""), "chatterbox": os.environ.get("SHORT_DRAMA_CHATTERBOX_URL", ""), "gpt-sovits": os.environ.get("SHORT_DRAMA_GPTSOVITS_URL", "")}
        return [{"id": row["id"], "providerType": row["provider_type"], "displayName": row["display_name"], "endpoint": endpoints.get(row["provider_type"], row["endpoint"]), "enabled": bool(row["enabled"]), "capabilities": loads(row["capabilities_json"], {}), "languages": loads(row["supported_languages_json"], []), "health": "configured" if endpoints.get(row["provider_type"]) else ("ready" if row["provider_type"] == "mock" else "not_configured")} for row in rows]


def test_voice_profile(profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with session() as connection:
        profile = _profile_row(connection, profile_id)
        character = connection.execute("SELECT * FROM characters WHERE id = ?", (profile["character_id"],)).fetchone()
        text = payload.get("text") or f"这是{character['name']}的声音测试。"
        line_id = new_id("DL-TEST-")
        target = int(payload.get("targetDurationMs", 2000))
        connection.execute("INSERT INTO dialogue_lines(id, project_id, character_id, order_index, text, target_duration_ms, voice_profile_id, status) VALUES (?, ?, ?, 0, ?, ?, ?, 'draft')", (line_id, profile["project_id"], profile["character_id"], text, target, profile_id))
        connection.execute("INSERT INTO voice_performances(dialogue_line_id, target_duration_ms, source) VALUES (?, ?, 'test')", (line_id, target))
    return generate_dialogue_line(line_id, {"provider": payload.get("provider") or profile["provider_type"], "model": payload.get("model"), "mockDurationRatio": payload.get("mockDurationRatio")})
