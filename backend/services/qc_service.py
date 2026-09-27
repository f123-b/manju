from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

from ..core.config import DATA_DIR, ROOT
from ..core.database import session
from ..domain.repository import dumps, new_id, now_text
from ..providers.llm import LLMProvider
from .runtime_settings import _raw_settings


def _local_image(url: str | None) -> Path | None:
    if not url:
        return None
    if url.startswith("/assets/"):
        candidate = (ROOT / "public" / url.lstrip("/")).resolve()
    elif url.startswith("/generated-media/"):
        name = Path(url).name
        candidates = [DATA_DIR / "generated-video" / name, DATA_DIR / "generated-audio" / name]
        candidate = next((item.resolve() for item in candidates if item.is_file()), candidates[0].resolve())
    else:
        candidate = Path(url).resolve()
    return candidate if candidate.is_file() and (ROOT.resolve() in candidate.parents or DATA_DIR.resolve() in candidate.parents) else None


def _image_checks(shot) -> list[dict[str, Any]]:
    path = _local_image(shot["image"])
    if not path:
        return [{"type": "visual_decode", "score": 60, "severity": "warning", "message": "镜头图像来自外部地址，当前未缓存，跳过像素级检测", "metadata": {"image": shot["image"]}}]
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            brightness = round(float(ImageStat.Stat(image.convert("L")).mean[0]), 1)
            ratio = width / max(height, 1)
            expected_ratio = 16 / 9 if "16:9" in (shot["frame"] or "") else None
            ratio_ok = expected_ratio is None or abs(ratio - expected_ratio) <= 0.08
            return [
                {"type": "visual_decode", "score": 100, "severity": "info", "message": "图像可解码", "metadata": {"width": width, "height": height, "mode": image.mode}},
                {"type": "visual_dimensions", "score": 100 if width >= 512 and height >= 288 else 65, "severity": "info" if width >= 512 and height >= 288 else "warning", "message": f"图像尺寸 {width}×{height}", "metadata": {"width": width, "height": height}},
                {"type": "visual_aspect", "score": 100 if ratio_ok else 65, "severity": "info" if ratio_ok else "warning", "message": "画幅比例符合镜头设置" if ratio_ok else "画幅比例与镜头设置不一致", "metadata": {"ratio": round(ratio, 4), "expected": expected_ratio}},
                {"type": "visual_exposure", "score": 100 if 12 <= brightness <= 242 else 65, "severity": "info" if 12 <= brightness <= 242 else "warning", "message": f"平均亮度 {brightness}", "metadata": {"meanLuma": brightness}},
            ]
    except (OSError, ValueError) as error:
        return [{"type": "visual_decode", "score": 0, "severity": "error", "message": f"图像解码失败：{error}", "metadata": {"path": str(path)}}]


def _vision_source(connection, shot, active_version):
    source = shot["image"]
    if active_version and active_version["media_asset_id"]:
        asset = connection.execute("SELECT path_or_url FROM media_assets WHERE id = ?", (active_version["media_asset_id"],)).fetchone()
        if asset and asset["path_or_url"]:
            source = asset["path_or_url"]
    local = _local_image(source)
    if local:
        return local
    if source and str(source).startswith(("http://", "https://", "data:")):
        return source
    return None


def _number(value, fallback: float) -> float:
    try:
        return round(max(0, min(100, float(value))), 1)
    except (TypeError, ValueError):
        return fallback


def _confidence(value) -> float | None:
    try:
        return round(max(0, min(1, float(value))), 3)
    except (TypeError, ValueError):
        return None


def _semantic_vision_qc(shot, active_version, bindings, source) -> dict[str, Any]:
    """Run optional semantic image QC through the configured LLM provider.

    Local pixel checks remain the source of truth when no vision model is
    configured. A configured provider is additive: its structured findings are
    persisted as ordinary QC records, so the UI and exports see one audit trail.
    """
    settings = _raw_settings()
    provider = LLMProvider(settings)
    result: dict[str, Any] = {"status": "not_configured", "provider": None, "model": None, "findings": []}
    if not provider.configured:
        return result
    if not source:
        return {**result, "status": "unavailable", "provider": provider.provider, "model": provider.model, "message": "没有可发送给视觉模型的镜头图片"}
    context = {
        "shotId": shot["id"],
        "description": shot["description"],
        "prompt": shot["prompt"],
        "frame": shot["frame"],
        "shotSize": shot["shot_size"],
        "dialogue": shot["dialogue"],
        "characters": [{"characterId": item["character_id"], "emotion": item["emotion"], "action": item["action"]} for item in bindings],
    }
    system = "你是短剧视觉 QC 审核器。只返回合法 JSON，不要 Markdown。判断图片是否符合镜头意图、构图、人物数量和明显的视觉错误。输出 {status: pass|warning|fail, score: 0-100, findings: [{type, severity: info|warning|error, score: 0-100, message, confidence: 0-1}]}。不要臆测图片中无法确认的细节。"
    user = "请审核下面的镜头上下文，并结合附图给出可执行的结构化结论：" + dumps(context)
    try:
        payload = provider.complete_vision_json_sync(system, user, source)
        payload = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        raw_findings = payload.get("findings") or payload.get("issues") or []
        if not isinstance(raw_findings, list):
            raw_findings = []
        overall = _number(payload.get("score"), 100 if str(payload.get("status", "pass")).lower() == "pass" else 70)
        findings: list[dict[str, Any]] = []
        for raw in raw_findings:
            if not isinstance(raw, dict):
                continue
            severity = str(raw.get("severity") or "warning").lower()
            if severity not in {"info", "warning", "error"}:
                severity = "warning"
            findings.append({
                "type": "vision_semantic",
                "score": _number(raw.get("score"), overall),
                "severity": severity,
                "message": str(raw.get("message") or raw.get("reason") or "视觉模型发现需要复核的内容")[:500],
                "metadata": {"provider": provider.provider, "model": provider.model, "category": str(raw.get("type") or "general"), "confidence": _confidence(raw.get("confidence"))},
            })
        if not findings:
            findings.append({"type": "vision_semantic", "score": overall, "severity": "info" if overall >= 90 else "warning", "message": "视觉模型未发现明显语义问题" if overall >= 90 else "视觉模型建议人工复核镜头语义", "metadata": {"provider": provider.provider, "model": provider.model}})
        return {"status": "success", "provider": provider.provider, "model": provider.model, "score": overall, "findings": findings}
    except Exception as error:  # noqa: BLE001 - QC must return a reviewable result
        return {"status": "error", "provider": provider.provider, "model": provider.model, "findings": [], "message": f"视觉模型调用失败：{str(error)[:300]}"}


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
    connection.execute("DELETE FROM qc_records WHERE shot_id = ? AND (type LIKE 'visual_%' OR type LIKE 'vision_%')", (shot_id,))
    for check in checks:
        connection.execute(
            "INSERT INTO qc_records(id, shot_id, type, score, severity, message, metadata_json, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (new_id("QC-"), shot_id, check["type"], check.get("score"), check["severity"], check["message"], dumps(check.get("metadata", {})), "passed" if check["severity"] == "info" else "needs_review"),
        )
    connection.execute("UPDATE shots SET qc_score = ?, updated_at = ? WHERE id = ?", (score, now_text(), shot_id))


def run_shot_visual_qc(shot_id: str) -> dict[str, Any]:
    with session() as connection:
        shot = dict(_shot_row(connection, shot_id))
        active_version_row = connection.execute("SELECT * FROM generation_versions WHERE shot_id = ? AND is_active = 1", (shot_id,)).fetchone()
        active_version = dict(active_version_row) if active_version_row else None
        bindings = connection.execute("SELECT sc.*, c.canonical_reference_id FROM shot_characters sc JOIN characters c ON c.id = sc.character_id WHERE sc.shot_id = ?", (shot_id,)).fetchall()
        bindings = [dict(item) for item in bindings]
        approved_refs = connection.execute(
            "SELECT COUNT(*) AS count FROM character_references r JOIN shot_characters sc ON sc.character_id = r.character_id WHERE sc.shot_id = ? AND r.lifecycle_status = 'approved'",
            (shot_id,),
        ).fetchone()["count"]
        vision_source = _vision_source(connection, shot, active_version)
    checks = [
        {"type": "visual_media", "score": 100 if active_version or shot["status"] == "已生成" else 0, "severity": "info" if active_version or shot["status"] == "已生成" else "error", "message": "已找到生成版本" if active_version or shot["status"] == "已生成" else "镜头还没有可检测的生成版本", "metadata": {"versionId": active_version["id"] if active_version else None}},
        {"type": "visual_prompt", "score": 100 if shot["prompt"] else 60, "severity": "info" if shot["prompt"] else "warning", "message": "生成提示词已记录" if shot["prompt"] else "缺少生成提示词，无法完整判断画面意图", "metadata": {}},
        {"type": "visual_identity", "score": 100 if bindings and approved_refs >= len(bindings) else 70 if bindings else 50, "severity": "info" if bindings and approved_refs >= len(bindings) else "warning", "message": "角色参考已绑定" if bindings and approved_refs >= len(bindings) else "角色参考尚未全部审核或绑定", "metadata": {"bindings": len(bindings), "approvedReferences": approved_refs}},
        {"type": "visual_duration", "score": 100 if int(shot["duration"] or 0) > 0 else 0, "severity": "info" if int(shot["duration"] or 0) > 0 else "error", "message": "镜头时长有效" if int(shot["duration"] or 0) > 0 else "镜头时长必须大于 0", "metadata": {"duration": shot["duration"]}},
    ]
    checks.extend(_image_checks(shot))
    vision = _semantic_vision_qc(shot, active_version, bindings, vision_source)
    if vision["status"] == "success":
        checks.extend(vision["findings"])
    elif vision["status"] in {"error", "unavailable"}:
        checks.append({"type": "vision_semantic", "score": 60, "severity": "warning", "message": vision.get("message") or "视觉模型未完成检查", "metadata": {"provider": vision.get("provider"), "model": vision.get("model"), "status": vision["status"]}})
    score = round(sum(item["score"] for item in checks) / len(checks), 1)
    with session() as connection:
        _save_checks(connection, shot_id, checks, score)
    return {"shotId": shot_id, "score": score, "status": "pass" if all(item["severity"] == "info" for item in checks) else "warning", "checks": checks, "vision": vision}


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
