from __future__ import annotations

import json
from typing import Any

from ..core.database import session
from .repository import dumps, new_id, now_text


EPISODE_TITLES = [
    "重生归来", "当众拒绝", "撕下伪装", "新的开始", "暗流涌动", "真相浮现",
    "旧情反噬", "旧情难断", "各自为战", "风向逆转", "终局对峙", "新的我",
]


def seed_demo_project() -> None:
    shots = [
        {"id": "SH041", "time": "00:00 – 00:04", "description": "林泽看着苏晴，眼神复杂", "size": "近景", "duration": 4, "image": "/assets/shot-hero.png", "status": "已生成", "qcScore": 92, "reviewed": False, "lens": "85mm（中长焦，人物特写）", "angle": "平视", "movement": "微推（Slow Push In）", "dialogue": "你真的以为，我还会像以前一样吗？", "characters": ["C001", "C002"], "outfit": "O001", "cost": 0.73, "version": "2026-09-26 09:20"},
        {"id": "SH042", "time": "00:04 – 00:08", "description": "苏晴情绪收敛，质问林泽", "size": "中景", "duration": 4, "image": "/assets/shot-woman.png", "status": "已生成", "qcScore": 89, "reviewed": False, "lens": "50mm（标准镜头）", "angle": "平视", "movement": "固定镜头", "dialogue": "所以你一直都在骗我？", "characters": ["C002"], "outfit": "O002", "cost": 0.68, "version": "2026-09-26 09:24"},
        {"id": "SH043", "time": "00:08 – 00:12", "description": "两人对峙，城市夜景", "size": "全景", "duration": 4, "image": "/assets/shot-wide.png", "status": "已生成", "qcScore": 95, "reviewed": True, "lens": "35mm（环境人像）", "angle": "平视", "movement": "缓慢拉远", "dialogue": "真相从来都不是你想的那样。", "characters": ["C001", "C002"], "outfit": "O001", "cost": 0.81, "version": "2026-09-26 09:30"},
        {"id": "SH044", "time": "00:12 – 00:16", "description": "林泽冷静回应", "size": "近景", "duration": 4, "image": "/assets/shot-hero.png", "status": "已生成", "qcScore": 93, "reviewed": False, "lens": "85mm（中长焦，人物特写）", "angle": "平视", "movement": "固定镜头", "dialogue": "到此为止吧。", "characters": ["C001"], "outfit": "O001", "cost": 0.72, "version": "2026-09-26 09:35"},
        {"id": "SH045", "time": "00:16 – 00:20", "description": "苏晴渐渐心软，转身离开", "size": "特写", "duration": 4, "image": "/assets/shot-woman.png", "status": "待生成", "qcScore": None, "reviewed": False, "lens": "85mm（中长焦，人物特写）", "angle": "平视", "movement": "微推（Slow Push In）", "dialogue": "苏晴没有回答。", "characters": ["C002"], "outfit": "O002", "cost": 0, "version": None},
        {"id": "SH046", "time": "00:20 – 00:24", "description": "林泽独自站在天台", "size": "远景", "duration": 4, "image": "/assets/shot-wide.png", "status": "待生成", "qcScore": None, "reviewed": False, "lens": "35mm（环境人像）", "angle": "低机位", "movement": "缓慢拉远", "dialogue": "夜风吹过，他终于松开了手。", "characters": ["C001"], "outfit": "O001", "cost": 0, "version": None},
    ]
    project = {
        "schemaVersion": 1,
        "id": "P001",
        "title": "重生之后我不当舔狗了",
        "status": "制作中",
        "format": "16:9",
        "targetEpisodes": 24,
        "currentEpisodeId": "EP08",
        "dueDate": "2026-10-30",
        "budget": 120,
        "spent": 52.36,
        "production": {"totalShots": 328, "generatedShots": 143, "qcScore": 91},
        "storyBible": {
            "logline": "重生后的林泽拒绝继续讨好所有人，并用看见财富潜力的能力重新掌控人生。",
            "coreConflict": "林泽必须在复仇、成长与重新相信他人之间做出选择。",
            "mainLine": "林泽从被背叛的程序员成长为掌控局面的创业者，并揭开苏晴隐瞒的真实身份。",
            "theme": "边界、自尊与真正的重生。",
            "ending": "林泽放下过去，与真正尊重他的伙伴建立新事业。",
            "world": "现代都市，商业竞争与情感关系交织，整体低饱和、冷暖对比。",
            "style": "电影感、现代都市、低饱和、冷暖对比、轻胶片颗粒；避免赛博朋克与过度霓虹。",
            "rules": ["林泽在 EP08 前不知道苏晴的真实身份。", "周凯在 EP15 前不能死亡。", "能力只能看到财富潜力，不能直接看到余额。"],
        },
        "episodes": [
            {
                "id": f"EP{index:02d}",
                "title": EPISODE_TITLES[index - 1] if index <= len(EPISODE_TITLES) else f"第 {index:02d} 集",
                "status": "已完成" if index <= 7 else "分镜中" if index == 8 else "已策划" if index <= 12 else "待策划",
                "hook": "旧爱在天台拦住林泽，逼他面对过去。" if index == 8 else "一个新的决定改变了故事走向。",
                "scenes": 6 if index == 8 else 0,
                "shots": 24 if index == 8 else 0,
                "duration": "01:32" if index <= 8 else "--:--",
            }
            for index in range(1, 25)
        ],
        "currentScene": {"id": "SC03", "number": 3, "title": "天台上的真相", "purpose": "林泽拒绝苏晴的挽回，完成与过去的切割。"},
        "assets": {
            "characters": [
                {"id": "C001", "name": "林泽", "meta": "男主｜28岁", "description": "黑发，克制冷静，创业者。", "image": "/assets/shot-hero.png", "status": "已锁定"},
                {"id": "C002", "name": "苏晴", "meta": "女主｜26岁", "description": "长发，外冷内热，身份成谜。", "image": "/assets/shot-woman.png", "status": "已锁定"},
            ],
            "locations": [{"id": "L001", "name": "城市天台", "meta": "夜景｜主场景", "description": "可俯瞰江面与城市天际线。", "image": "/assets/shot-wide.png", "status": "已锁定"}],
            "props": [{"id": "P001", "name": "旧照片", "meta": "剧情道具", "description": "承载林泽与苏晴的过去。", "image": "/assets/shot-woman.png", "status": "待确认"}],
        },
        "tasks": [
            {"id": "T9382", "shotId": "SH044", "type": "视频", "model": "Seedance", "status": "Success", "cost": 0.72, "createdAt": "2026-09-26 09:35"},
            {"id": "T9381", "shotId": "SH043", "type": "视频", "model": "Kling", "status": "Success", "cost": 0.81, "createdAt": "2026-09-26 09:30"},
            {"id": "T9380", "shotId": "SH042", "type": "视频", "model": "Vidu", "status": "Failed", "cost": 0.42, "createdAt": "2026-09-26 09:25"},
        ],
        "shots": shots,
    }
    seed_legacy_project(project)


def seed_legacy_project(data: dict[str, Any]) -> None:
    from .repository import project_to_dict

    project_id = data.get("id", "P001")
    episodes = data.get("episodes") or []
    shots = data.get("shots") or []
    current_scene = data.get("currentScene") or {"id": "SC03", "number": 3, "title": "天台上的真相", "purpose": ""}
    with session() as connection:
        connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        connection.execute(
            """INSERT INTO projects(id, title, status, format, target_episodes, current_episode_id, due_date, budget, spent, generated_shots, total_shots, qc_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, data.get("title", "Short Drama OS"), data.get("status", "策划中"), data.get("format", "16:9"), data.get("targetEpisodes", 24), data.get("currentEpisodeId", "EP01"), data.get("dueDate"), data.get("budget", 0), data.get("spent", 0), data.get("production", {}).get("generatedShots", 0), data.get("production", {}).get("totalShots", len(shots)), data.get("production", {}).get("qcScore", 0)),
        )
        bible = data.get("storyBible", {})
        connection.execute(
            """INSERT INTO story_bibles(id, project_id, logline, core_conflict, main_line, theme, ending, world, style, rules_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f"SB-{project_id}", project_id, bible.get("logline", ""), bible.get("coreConflict", ""), bible.get("mainLine", ""), bible.get("theme", ""), bible.get("ending", ""), bible.get("world", ""), bible.get("style", ""), dumps(bible.get("rules", []))),
        )
        for index, episode in enumerate(episodes, 1):
            episode_id = episode.get("id", f"EP{index:02d}")
            connection.execute(
                """INSERT INTO episodes(id, project_id, order_index, title, summary, opening_hook, core_event, payoff, twist, ending_hook, status, duration)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (episode_id, project_id, index, episode.get("title", f"第 {index:02d} 集"), episode.get("summary", ""), episode.get("hook", episode.get("openingHook", "")), episode.get("coreEvent", ""), episode.get("payoff", ""), episode.get("twist", ""), episode.get("endingHook", ""), episode.get("status", "待策划"), episode.get("duration", "--:--")),
            )
        if not episodes:
            for index in range(1, int(data.get("targetEpisodes", 24)) + 1):
                episode_id = f"EP{index:02d}"
                connection.execute("INSERT INTO episodes(id, project_id, order_index, title, status) VALUES (?, ?, ?, ?, ?)", (episode_id, project_id, index, f"第 {index:02d} 集", "待策划"))
        episode_id = data.get("currentEpisodeId", "EP01")
        scene_id = current_scene.get("id", "SC03")
        connection.execute(
            """INSERT INTO scenes(id, episode_id, order_index, title, purpose, summary, estimated_duration)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (scene_id, episode_id, current_scene.get("number", 1), current_scene.get("title", "未命名场景"), current_scene.get("purpose", ""), current_scene.get("summary", current_scene.get("purpose", "")), 24),
        )
        assets = data.get("assets", {})
        for item in assets.get("characters", []):
            connection.execute("INSERT INTO characters(id, project_id, name, age, gender, role, appearance, personality, meta, image, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (item["id"], project_id, item.get("name", ""), item.get("meta", ""), "", "", item.get("description", ""), "", item.get("meta", ""), item.get("image"), item.get("status", "待确认")))
        for item in assets.get("locations", []):
            connection.execute("INSERT INTO locations(id, project_id, name, meta, description, image, status) VALUES (?, ?, ?, ?, ?, ?, ?)", (item["id"], project_id, item.get("name", ""), item.get("meta", ""), item.get("description", ""), item.get("image"), item.get("status", "待确认")))
        for item in assets.get("props", []):
            connection.execute("INSERT INTO props(id, project_id, name, meta, description, image, status) VALUES (?, ?, ?, ?, ?, ?, ?)", (item["id"], project_id, item.get("name", ""), item.get("meta", ""), item.get("description", ""), item.get("image"), item.get("status", "待确认")))
        for outfit_id, character_id, name in (("O001", "C001", "黑色高领毛衣+风衣"), ("O002", "C002", "白色针织衫")):
            if connection.execute("SELECT 1 FROM characters WHERE id = ?", (character_id,)).fetchone():
                connection.execute("INSERT INTO character_outfits(id, character_id, name, description, status) VALUES (?, ?, ?, ?, ?)", (outfit_id, character_id, name, "演示服装造型", "已锁定"))
        for order, shot in enumerate(shots, 1):
            shot_scene_id = shot.get("sceneId", scene_id)
            if not connection.execute("SELECT 1 FROM scenes WHERE id = ?", (shot_scene_id,)).fetchone():
                shot_scene_id = scene_id
            connection.execute(
                """INSERT INTO shots(id, scene_id, order_index, timecode, description, shot_size, frame, camera_angle, lens, movement, duration, dialogue, prompt, image, status, reviewed, qc_score, cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (shot["id"], shot_scene_id, order, shot.get("time", ""), shot.get("description", ""), shot.get("size", ""), shot.get("frame", "16:9（横屏）"), shot.get("angle", "平视"), shot.get("lens", ""), shot.get("movement", ""), shot.get("duration", 4), shot.get("dialogue", ""), shot.get("prompt", ""), shot.get("image"), shot.get("status", "待生成"), int(bool(shot.get("reviewed"))), shot.get("qcScore"), shot.get("cost", 0)),
            )
            for character_id in shot.get("characterIds", shot.get("characters", [])):
                outfit_id = shot.get("outfitId", shot.get("outfit"))
                if connection.execute("SELECT 1 FROM characters WHERE id = ?", (character_id,)).fetchone():
                    connection.execute("INSERT OR IGNORE INTO shot_characters(shot_id, character_id, outfit_id) VALUES (?, ?, ?)", (shot["id"], character_id, outfit_id))
            for version in shot.get("versions", []):
                version_id = version.get("id", "V1")
                connection.execute("INSERT OR IGNORE INTO generation_versions(id, shot_id, version_number, provider, model, prompt_snapshot, actual_cost, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (f"{shot['id']}-{version_id}", shot["id"], int(version_id.lstrip("V") or 1), "seed", "seed", shot.get("prompt", ""), shot.get("cost", 0), int(bool(version.get("active"))), version.get("createdAt", now_text())))
            if shot.get("qcScore") is not None and not shot.get("versions"):
                connection.execute("INSERT OR IGNORE INTO generation_versions(id, shot_id, version_number, provider, model, prompt_snapshot, actual_cost, is_active, created_at) VALUES (?, ?, 1, ?, ?, ?, ?, 1, ?)", (f"{shot['id']}-V1", shot["id"], "seed", "seed", shot.get("prompt", ""), shot.get("cost", 0), now_text()))
            if shot.get("qcScore") is not None:
                connection.execute("INSERT INTO qc_records(id, shot_id, version_id, type, score, severity, message, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (new_id("QC-"), shot["id"], f"{shot['id']}-V1", "character_consistency", shot.get("qcScore"), "warning" if shot.get("qcScore", 0) < 90 else "info", "Seed QC record", "passed" if shot.get("qcScore", 0) >= 90 else "warning"))
        for task in data.get("tasks", []):
            shot_id = task.get("shotId")
            if not shot_id or not connection.execute("SELECT 1 FROM shots WHERE id = ?", (shot_id,)).fetchone():
                continue
            status = task.get("status", "Queued")
            connection.execute("INSERT OR IGNORE INTO generation_tasks(id, project_id, shot_id, type, provider, model, status, estimated_cost, actual_cost, completed_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (task["id"], project_id, shot_id, task.get("type", "视频"), task.get("model", "Auto"), task.get("model", "Auto"), status, task.get("cost", 0), task.get("cost", 0) if status == "Success" else None, task.get("completedAt"), task.get("createdAt", now_text())))
            if status == "Success":
                context = connection.execute("SELECT * FROM shots WHERE id = ?", (shot_id,)).fetchone()
                connection.execute("INSERT OR IGNORE INTO cost_records(id, project_id, shot_id, task_id, provider, model, category, estimated_cost, actual_cost, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (new_id("COST-"), project_id, shot_id, task["id"], task.get("model", "Auto"), task.get("model", "Auto"), "video", task.get("cost", 0), task.get("cost", 0), "actual"))
        _seed_models(connection)


def _seed_models(connection) -> None:
    models = [
        ("mock", "mock-text", "Mock Text", "text", '{"unit": "request"}', '{"json": true}'),
        ("mock", "mock-image", "Mock Image", "image", '{"unit": "image"}', '{"reference": true}'),
        ("mock", "mock-video", "Mock Video", "video", '{"unit": "second"}', '{"reference": true, "max_duration": 10}'),
        ("mock", "mock-voice", "Mock Voice", "voice", '{"unit": "minute"}', '{"audio": true}'),
    ]
    for provider, model_id, display, kind, pricing, capabilities in models:
        connection.execute("INSERT OR IGNORE INTO model_definitions(provider, model_id, display_name, type, pricing_json, capabilities_json) VALUES (?, ?, ?, ?, ?, ?)", (provider, model_id, display, kind, pricing, capabilities))
