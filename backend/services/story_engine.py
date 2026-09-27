from __future__ import annotations

import json
import math
from typing import Any

from ..core.database import session
from ..domain.repository import (
    dumps,
    episode_dict,
    list_scenes,
    list_shots_for_scene,
    loads,
    new_id,
    now_text,
    patch_episode,
    patch_scene,
    patch_story_bible,
    project_to_dict,
)
from ..providers.llm import LLMProvider
from .runtime_settings import _raw_settings


def _llm_json(system: str, context: dict[str, Any]) -> dict[str, Any] | None:
    provider = LLMProvider(_raw_settings())
    if not provider.configured:
        return None
    try:
        response = provider.complete_json_sync(system, json.dumps(context, ensure_ascii=False))
    except Exception:
        return None
    if not isinstance(response, dict):
        return None
    data = response.get("data")
    return data if isinstance(data, dict) else response


def _project_id_for_episode(episode_id: str) -> str:
    with session() as connection:
        row = connection.execute("SELECT project_id FROM episodes WHERE id = ? AND archived = 0", (episode_id,)).fetchone()
    if not row:
        raise KeyError(f"episode {episode_id} not found")
    return row["project_id"]


def _episode_for_scene(scene_id: str) -> tuple[str, str]:
    with session() as connection:
        row = connection.execute(
            "SELECT e.id AS episode_id, e.project_id FROM scenes s JOIN episodes e ON e.id = s.episode_id WHERE s.id = ? AND s.archived = 0",
            (scene_id,),
        ).fetchone()
    if not row:
        raise KeyError(f"scene {scene_id} not found")
    return row["project_id"], row["episode_id"]


def _character_maps(connection, project_id: str) -> tuple[dict[str, str], dict[str, str]]:
    rows = connection.execute("SELECT id, name FROM characters WHERE project_id = ? AND archived = 0", (project_id,)).fetchall()
    return ({row["id"]: row["name"] for row in rows}, {row["name"]: row["id"] for row in rows})


def _json_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def story_snapshot(project_id: str) -> dict[str, Any]:
    project = project_to_dict(project_id)
    with session() as connection:
        bible = connection.execute("SELECT * FROM story_bibles WHERE project_id = ?", (project_id,)).fetchone()
        characters = connection.execute("SELECT * FROM characters WHERE project_id = ? AND archived = 0 ORDER BY id", (project_id,)).fetchall()
        locations = connection.execute("SELECT * FROM locations WHERE project_id = ? AND archived = 0 ORDER BY id", (project_id,)).fetchall()
        props = connection.execute("SELECT * FROM props WHERE project_id = ? AND archived = 0 ORDER BY id", (project_id,)).fetchall()
        beats = connection.execute("SELECT * FROM story_beats WHERE project_id = ? ORDER BY episode_id, order_index", (project_id,)).fetchall()
        segments = connection.execute("SELECT * FROM generation_segments WHERE project_id = ? ORDER BY episode_id, scene_id, order_index", (project_id,)).fetchall()
        quality = connection.execute("SELECT * FROM story_quality_runs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (project_id,)).fetchone()
    return {
        "projectId": project_id,
        "storyBible": {
            **project["storyBible"],
            "thematicQuestion": bible["thematic_question"] if bible else "",
            "genre": bible["genre"] if bible else "",
            "tone": bible["tone"] if bible else "",
            "audience": bible["audience"] if bible else "",
            "platform": bible["platform"] if bible else "",
            "structureType": bible["structure_type"] if bible else "",
            "majorTurns": loads(bible["major_turns_json"], []) if bible else [],
            "characterMap": loads(bible["character_map_json"], {}) if bible else {},
        },
        "characters": [
            {
                "id": row["id"], "name": row["name"], "role": row["role"], "tier": row["story_tier"],
                "want": row["story_want"], "need": row["story_need"], "flaw": row["story_flaw"], "arc": row["story_arc"],
                "speechStyle": row["speech_style"], "secrets": loads(row["story_secrets_json"], []),
                "relationships": loads(row["story_relationships_json"], []), "appearance": row["appearance"], "personality": row["personality"],
            }
            for row in characters
        ],
        "locations": [
            {
                "id": row["id"], "name": row["name"], "description": row["description"],
                "narrativeFunction": row["narrative_function"], "geography": row["geography"],
                "visualAnchors": loads(row["visual_anchors_json"], []), "colorPalette": loads(row["color_palette_json"], []),
                "materials": loads(row["materials_json"], []), "lightingStates": loads(row["lighting_states_json"], []),
                "weatherStates": loads(row["weather_states_json"], []),
            }
            for row in locations
        ],
        "props": [
            {
                "id": row["id"], "name": row["name"], "description": row["description"],
                "narrativeFunction": row["narrative_function"], "continuityStates": loads(row["continuity_states_json"], []),
            }
            for row in props
        ],
        "beats": [
            {
                "id": row["id"], "episodeId": row["episode_id"], "order": row["order_index"], "type": row["beat_type"],
                "weight": row["weight"], "setup": row["setup"], "payoff": row["payoff"], "metadata": loads(row["metadata_json"], {}),
            }
            for row in beats
        ],
        "segments": [
            {
                "id": row["id"], "episodeId": row["episode_id"], "sceneId": row["scene_id"], "order": row["order_index"],
                "blocking": row["blocking"], "soundscape": row["soundscape"], "music": row["music"],
                "videoPrompt": row["video_prompt"], "duration": row["duration_seconds"], "metadata": loads(row["metadata_json"], {}),
            }
            for row in segments
        ],
        "quality": loads(quality["result_json"], {}) if quality else None,
    }


def _upsert_story_bible(project_id: str, data: dict[str, Any]) -> None:
    patch_story_bible(project_id, {
        "logline": data.get("logline", ""),
        "coreConflict": data.get("coreConflict", ""),
        "mainLine": data.get("mainLine", ""),
        "theme": data.get("theme", ""),
        "ending": data.get("ending", ""),
        "world": data.get("world", ""),
        "style": data.get("style", ""),
        "rules": _json_list(data.get("rules")),
    })
    with session() as connection:
        connection.execute(
            """UPDATE story_bibles SET thematic_question = ?, genre = ?, tone = ?, audience = ?, platform = ?,
               structure_type = ?, major_turns_json = ?, character_map_json = ?, updated_at = ? WHERE project_id = ?""",
            (
                data.get("thematicQuestion", ""), data.get("genre", ""), data.get("tone", ""), data.get("audience", ""),
                data.get("platform", ""), data.get("structureType", ""), dumps(_json_list(data.get("majorTurns"))),
                dumps(data.get("characterMap") if isinstance(data.get("characterMap"), dict) else {}), now_text(), project_id,
            ),
        )


def _upsert_character(connection, project_id: str, item: dict[str, Any]) -> str:
    name = str(item.get("name") or "").strip()
    if not name:
        raise ValueError("character name is required")
    row = connection.execute("SELECT id FROM characters WHERE project_id = ? AND name = ? AND archived = 0", (project_id, name)).fetchone()
    character_id = row["id"] if row else str(item.get("id") or new_id("C-"))
    if not row:
        connection.execute(
            """INSERT INTO characters(id, project_id, name, role, appearance, personality, status)
               VALUES (?, ?, ?, ?, ?, ?, '待确认')""",
            (character_id, project_id, name, item.get("role", ""), item.get("appearance", ""), item.get("personality", "")),
        )
    connection.execute(
        """UPDATE characters SET role = ?, appearance = ?, personality = ?, story_tier = ?, story_want = ?, story_need = ?,
           story_flaw = ?, story_arc = ?, speech_style = ?, story_secrets_json = ?, story_relationships_json = ?, updated_at = ?
           WHERE id = ?""",
        (
            item.get("role", ""), item.get("appearance", ""), item.get("personality", ""), item.get("tier", "support"),
            item.get("want", ""), item.get("need", ""), item.get("flaw", ""), item.get("arc", ""), item.get("speechStyle", ""),
            dumps(_json_list(item.get("secrets"))), dumps(_json_list(item.get("relationships"))), now_text(), character_id,
        ),
    )
    return character_id


def _upsert_location(connection, project_id: str, item: dict[str, Any]) -> str:
    name = str(item.get("name") or "").strip()
    if not name:
        raise ValueError("location name is required")
    row = connection.execute("SELECT id FROM locations WHERE project_id = ? AND name = ? AND archived = 0", (project_id, name)).fetchone()
    location_id = row["id"] if row else str(item.get("id") or new_id("L-"))
    if not row:
        connection.execute("INSERT INTO locations(id, project_id, name, description, status) VALUES (?, ?, ?, ?, '待确认')", (location_id, project_id, name, item.get("description", "")))
    connection.execute(
        """UPDATE locations SET description = ?, narrative_function = ?, geography = ?, visual_anchors_json = ?, color_palette_json = ?,
           materials_json = ?, lighting_states_json = ?, weather_states_json = ?, updated_at = ? WHERE id = ?""",
        (
            item.get("description", ""), item.get("narrativeFunction", ""), item.get("geography", ""),
            dumps(_json_list(item.get("visualAnchors"))), dumps(_json_list(item.get("colorPalette"))),
            dumps(_json_list(item.get("materials"))), dumps(_json_list(item.get("lightingStates"))),
            dumps(_json_list(item.get("weatherStates"))), now_text(), location_id,
        ),
    )
    return location_id


def _upsert_prop(connection, project_id: str, item: dict[str, Any]) -> str:
    name = str(item.get("name") or "").strip()
    if not name:
        raise ValueError("prop name is required")
    row = connection.execute("SELECT id FROM props WHERE project_id = ? AND name = ? AND archived = 0", (project_id, name)).fetchone()
    prop_id = row["id"] if row else str(item.get("id") or new_id("P-"))
    if not row:
        connection.execute("INSERT INTO props(id, project_id, name, description, status) VALUES (?, ?, ?, ?, '待确认')", (prop_id, project_id, name, item.get("description", "")))
    connection.execute(
        "UPDATE props SET description = ?, narrative_function = ?, continuity_states_json = ?, updated_at = ? WHERE id = ?",
        (item.get("description", ""), item.get("narrativeFunction", ""), dumps(_json_list(item.get("continuityStates"))), now_text(), prop_id),
    )
    return prop_id


def _persist_episode_plan(project_id: str, episodes: list[dict[str, Any]]) -> None:
    with session() as connection:
        existing = connection.execute("SELECT * FROM episodes WHERE project_id = ? AND archived = 0 ORDER BY order_index", (project_id,)).fetchall()
        by_order = {row["order_index"]: row for row in existing}
        for index, item in enumerate(episodes, 1):
            order_index = int(item.get("order") or item.get("ep") or index)
            row = by_order.get(order_index)
            episode_id = row["id"] if row else str(item.get("id") or new_id("EP-"))
            if not row:
                connection.execute(
                    """INSERT INTO episodes(id, project_id, order_index, title, status) VALUES (?, ?, ?, ?, '已策划')""",
                    (episode_id, project_id, order_index, item.get("title") or f"第 {order_index:02d} 集"),
                )
            connection.execute(
                """UPDATE episodes SET title = ?, summary = ?, opening_hook = ?, core_event = ?, payoff = ?, twist = ?, ending_hook = ?,
                   status = CASE WHEN status = '待策划' THEN '已策划' ELSE status END, updated_at = ? WHERE id = ?""",
                (
                    item.get("title") or f"第 {order_index:02d} 集", item.get("synopsis") or item.get("summary", ""),
                    item.get("hook") or item.get("openingHook", ""), item.get("coreEvent", ""), item.get("payoff", ""),
                    item.get("twist", ""), item.get("endingHook") or item.get("suspense", ""), now_text(), episode_id,
                ),
            )
            beats = _json_list(item.get("beats"))
            if beats:
                connection.execute("DELETE FROM story_beats WHERE episode_id = ?", (episode_id,))
                for beat_index, beat in enumerate(beats, 1):
                    connection.execute(
                        """INSERT INTO story_beats(id, project_id, episode_id, order_index, beat_type, weight, setup, payoff, metadata_json)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            new_id("B-"), project_id, episode_id, beat_index, beat.get("type", ""), beat.get("weight", "minor"),
                            beat.get("setup", ""), beat.get("payoff", ""), dumps({k: v for k, v in beat.items() if k not in {"type", "weight", "setup", "payoff"}}),
                        ),
                    )
        if episodes:
            connection.execute("UPDATE projects SET target_episodes = MAX(target_episodes, ?), updated_at = ? WHERE id = ?", (len(episodes), now_text(), project_id))


def develop_project_story(project_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    project = project_to_dict(project_id)
    source_text = str(payload.get("sourceText") or payload.get("idea") or payload.get("source") or "").strip()
    context = {
        "project": {"title": project["title"], "format": project["format"], "targetEpisodes": project["targetEpisodes"]},
        "currentStoryBible": project["storyBible"],
        "currentCharacters": project["assets"]["characters"],
        "currentLocations": project["assets"]["locations"],
        "currentProps": project["assets"]["props"],
        "sourceText": source_text,
        "preferences": payload.get("preferences") or [],
    }
    generated = _llm_json(
        """你是短剧总编剧兼制片。把用户素材开发成结构化短剧生产圣经。只返回 JSON。
字段：storyBible{logline,coreConflict,mainLine,theme,thematicQuestion,genre,tone,audience,platform,world,style,ending,structureType,majorTurns[],rules[],characterMap{}},
characters[{name,role,tier,want,need,flaw,arc,speechStyle,appearance,personality,secrets[],relationships[]}],
locations[{name,narrativeFunction,description,geography,visualAnchors[],colorPalette[],materials[],lightingStates[],weatherStates[]}],
props[{name,narrativeFunction,description,continuityStates[]}],
episodes[{order,title,synopsis,hook,coreEvent,payoff,twist,endingHook,beats:[{type,weight,setup,payoff}]}]。
短剧要求：每集有开场钩子、兑现/爽点和结尾问题；人物数量克制；场景优先可复用；不要把对白写进分集梗概。""",
        context,
    )
    data = generated
    if not data:
        data = {
            "storyBible": {**project["storyBible"], "genre": payload.get("genre", ""), "tone": payload.get("tone", ""), "thematicQuestion": payload.get("thematicQuestion", "")},
            "characters": [],
            "locations": [],
            "props": [],
            "episodes": [
                {
                    "order": item.get("order", index + 1), "title": item["title"], "synopsis": item.get("summary", ""),
                    "hook": item.get("hook", ""), "coreEvent": item.get("coreEvent", ""), "payoff": item.get("payoff", ""),
                    "twist": item.get("twist", ""), "endingHook": item.get("endingHook", ""), "beats": [],
                }
                for index, item in enumerate(project["episodes"])
            ],
        }
    bible = data.get("storyBible") if isinstance(data.get("storyBible"), dict) else {}
    _upsert_story_bible(project_id, bible)
    with session() as connection:
        for item in _json_list(data.get("characters")):
            if isinstance(item, dict):
                _upsert_character(connection, project_id, item)
        for item in _json_list(data.get("locations")):
            if isinstance(item, dict):
                _upsert_location(connection, project_id, item)
        for item in _json_list(data.get("props")):
            if isinstance(item, dict):
                _upsert_prop(connection, project_id, item)
    _persist_episode_plan(project_id, [item for item in _json_list(data.get("episodes")) if isinstance(item, dict)])
    result = story_snapshot(project_id)
    result["source"] = "llm" if generated else "local-fallback"
    result["quality"] = validate_story_project(project_id)
    return result


def generate_episode_matrix(episode_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    project_id = _project_id_for_episode(episode_id)
    project = project_to_dict(project_id)
    episode = episode_dict(episode_id)
    direct = any(payload.get(key) for key in ("hook", "coreEvent", "payoff", "twist", "endingHook"))
    data = payload if direct else _llm_json(
        """你是竖屏短剧分集编剧。只返回 JSON：{hook,coreEvent,payoff,twist,endingHook,beats:[{type,weight,setup,payoff}]}。
所有字段具体可拍；开头立即产生问题，中段必须升级冲突，结尾必须形成下一集驱动力。""",
        {"storyBible": project["storyBible"], "episode": episode, "characters": project["assets"]["characters"], "draft": payload},
    ) or payload
    patch = {
        "hook": data.get("hook") or episode.get("hook") or "一个具体事件立即改变人物目标。",
        "coreEvent": data.get("coreEvent") or episode.get("coreEvent") or "主角做出不可逆选择。",
        "payoff": data.get("payoff") or episode.get("payoff") or "本集承诺得到一次明确兑现。",
        "twist": data.get("twist") or episode.get("twist") or "新信息改变观众判断。",
        "endingHook": data.get("endingHook") or episode.get("endingHook") or "新的问题迫使观众进入下一集。",
    }
    patch_episode(episode_id, patch)
    beats = [beat for beat in _json_list(data.get("beats")) if isinstance(beat, dict)]
    if beats:
        with session() as connection:
            connection.execute("DELETE FROM story_beats WHERE episode_id = ?", (episode_id,))
            for index, beat in enumerate(beats, 1):
                connection.execute(
                    "INSERT INTO story_beats(id, project_id, episode_id, order_index, beat_type, weight, setup, payoff, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_id("B-"), project_id, episode_id, index, beat.get("type", ""), beat.get("weight", "minor"), beat.get("setup", ""), beat.get("payoff", ""), dumps({})),
                )
    return episode_dict(episode_id)


def _normalize_flow(project_id: str, script: dict[str, Any]) -> list[dict[str, Any]]:
    raw = script.get("flow") if isinstance(script.get("flow"), list) else script.get("beats")
    raw = raw if isinstance(raw, list) else []
    with session() as connection:
        ids, names = _character_maps(connection, project_id)
    result: list[dict[str, Any]] = []
    for index, beat in enumerate(raw, 1):
        if not isinstance(beat, dict):
            continue
        kind = beat.get("kind") or beat.get("type")
        if kind == "dialogue" or beat.get("line") is not None:
            line = str(beat.get("line") or beat.get("text") or "").strip()
            speaker_id = beat.get("speakerId") or beat.get("speaker")
            if speaker_id not in ids:
                for separator in ("：", ":"):
                    if separator in line:
                        maybe_name, remainder = line.split(separator, 1)
                        if maybe_name.strip() in names:
                            speaker_id = names[maybe_name.strip()]
                            line = remainder.strip()
                            break
            result.append({"id": beat.get("id") or f"BT{index:03d}", "kind": "dialogue", "speakerId": speaker_id, "line": line, "delivery": beat.get("delivery", "")})
        else:
            action = str(beat.get("action") or beat.get("text") or "").strip()
            if action:
                result.append({"id": beat.get("id") or f"BT{index:03d}", "kind": "action", "action": action})
    return result


def generate_scene_script(scene_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    project_id, episode_id = _episode_for_scene(scene_id)
    project = project_to_dict(project_id)
    scene = next(item for item in list_scenes(episode_id) if item["id"] == scene_id)
    supplied_script = payload.get("script") if isinstance(payload.get("script"), dict) else None
    data = supplied_script or _llm_json(
        """你是短剧场景编剧。只返回 JSON：
{summary,acceptanceCriteria:[string],flow:[{kind:'action',action:string}|{kind:'dialogue',speakerId:string,line:string,delivery:string}],sound:string}。
speakerId 必须来自提供的角色 ID。动作和台词必须分开；每个场景都要发生状态变化；台词口语化、短句、可配音。""",
        {
            "storyBible": project["storyBible"], "episode": episode_dict(episode_id), "scene": scene,
            "characters": [{"id": item["id"], "name": item["name"], "description": item.get("description", "")} for item in project["assets"]["characters"]],
            "draft": payload,
        },
    )
    if not data:
        characters = project["assets"]["characters"]
        first = characters[0]["id"] if characters else None
        data = {
            "summary": payload.get("summary") or scene.get("summary") or scene.get("purpose", ""),
            "acceptanceCriteria": ["场景结束时人物状态发生变化", "场景中的信息能被后续剧情引用"],
            "flow": [
                {"kind": "action", "action": scene.get("purpose") or "人物进入场景，空间关系被建立。"},
                *([{"kind": "dialogue", "speakerId": first, "line": "这件事不能再拖下去了。", "delivery": "克制但明确"}] if first else []),
                {"kind": "action", "action": "一个新的线索改变了原有判断。"},
            ],
            "sound": "保留环境底噪和关键动作声。",
        }
    flow = _normalize_flow(project_id, data)
    acceptance = _json_list(data.get("acceptanceCriteria") or payload.get("acceptanceCriteria"))
    script = {
        "version": 2,
        "flow": flow,
        "beats": [
            {"type": "dialogue", "speakerId": beat.get("speakerId"), "text": beat.get("line", ""), "delivery": beat.get("delivery", "")}
            if beat["kind"] == "dialogue" else {"type": "action", "text": beat.get("action", "")}
            for beat in flow
        ],
        "dialogue": [beat["line"] for beat in flow if beat["kind"] == "dialogue"],
        "sound": data.get("sound", ""),
        "acceptanceCriteria": acceptance,
        "source": "story-engine",
    }
    patch_scene(scene_id, {"script": script, "summary": data.get("summary") or payload.get("summary") or scene.get("summary", "")})
    with session() as connection:
        connection.execute("UPDATE scenes SET acceptance_criteria_json = ?, updated_at = ? WHERE id = ?", (dumps(acceptance), now_text(), scene_id))
        for speaker_id in {beat.get("speakerId") for beat in flow if beat.get("speakerId")}:
            if connection.execute("SELECT 1 FROM characters WHERE id = ? AND project_id = ?", (speaker_id, project_id)).fetchone():
                connection.execute("INSERT OR IGNORE INTO scene_characters(scene_id, character_id) VALUES (?, ?)", (scene_id, speaker_id))
    return next(item for item in list_scenes(episode_id) if item["id"] == scene_id)


def _fallback_segments(scene: dict[str, Any]) -> list[dict[str, Any]]:
    flow = (scene.get("script") or {}).get("flow") or []
    cuts: list[dict[str, Any]] = []
    for index, beat in enumerate(flow, 1):
        if beat.get("kind") == "dialogue":
            seconds = max(2, min(5, int(math.ceil(len(str(beat.get("line", ""))) / 4.5)) or 2))
            characters = [beat.get("speakerId")] if beat.get("speakerId") else []
            description = f"{beat.get('speakerId') or '人物'}说出：{beat.get('line', '')}"
        else:
            seconds = 3
            characters = []
            description = beat.get("action", "动作推进")
        cuts.append({
            "beatRefs": [beat.get("id") or f"BT{index:03d}"], "seconds": seconds, "size": "medium" if index % 3 else "close",
            "camera": "Static Shot" if index % 2 else "Push In", "characters": characters, "props": [],
            "frame": description, "shot": description, "lens": "50mm 标准，中浅景深", "cameraPosition": "平视",
            "composition": "三分法", "eyeline": "对方面部" if characters else "主体", "focus": "锁定主要动作主体", "stability": "stable",
        })
    segments: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    total = 0
    for cut in cuts:
        if current and total + cut["seconds"] > 15:
            segments.append({"blocking": "保持人物左右关系连续", "soundscape": scene.get("script", {}).get("sound", ""), "music": "", "cuts": current})
            current, total = [], 0
        current.append(cut)
        total += cut["seconds"]
    if current:
        segments.append({"blocking": "保持人物左右关系连续", "soundscape": scene.get("script", {}).get("sound", ""), "music": "", "cuts": current})
    return segments


def _legacy_shots_to_segments(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cuts = []
    for item in shots:
        cuts.append({
            "beatRefs": item.get("beatRefs", []), "seconds": max(2, min(5, int(item.get("duration", 4)))),
            "size": item.get("size", "medium"), "camera": item.get("movement", "Static Shot"), "characters": item.get("characters", []),
            "props": item.get("props", []), "frame": item.get("frame") or item.get("description", ""), "shot": item.get("description", ""),
            "lens": item.get("lens", "50mm 标准，中浅景深"), "cameraPosition": item.get("cameraPosition", "平视"),
            "composition": item.get("composition", "三分法"), "eyeline": item.get("eyeline", "主体"), "focus": item.get("focus", "主体"),
            "stability": item.get("stability", "stable"), "dialogue": item.get("dialogue", ""),
        })
    segments, current, total = [], [], 0
    for cut in cuts:
        if current and total + cut["seconds"] > 15:
            segments.append({"blocking": "保持轴线与人物位置连续", "soundscape": "", "music": "", "cuts": current})
            current, total = [], 0
        current.append(cut)
        total += cut["seconds"]
    if current:
        segments.append({"blocking": "保持轴线与人物位置连续", "soundscape": "", "music": "", "cuts": current})
    return segments


def generate_storyboard(scene_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    project_id, episode_id = _episode_for_scene(scene_id)
    scene = next(item for item in list_scenes(episode_id) if item["id"] == scene_id)
    existing = list_shots_for_scene(scene_id)
    if existing and not payload.get("replaceExisting") and not payload.get("segments") and not payload.get("shots"):
        return {"shots": existing, "segments": _segments_for_scene(scene_id)}
    direct_segments = payload.get("segments") if isinstance(payload.get("segments"), list) else None
    if direct_segments is None and isinstance(payload.get("shots"), list):
        direct_segments = _legacy_shots_to_segments(payload["shots"])
    data = {"segments": direct_segments} if direct_segments is not None else _llm_json(
        """你是短剧导演和摄影指导。把结构化场景节拍转为可生成分镜。只返回 JSON：
{segments:[{blocking,soundscape,music,videoPrompt,cuts:[{beatRefs:[string],seconds:2-5,size,camera,characters:[角色ID],props:[道具ID],frame,shot,lens,cameraPosition,composition,eyeline,focus,stability,sfx,lighting}]}]}。
每段总时长<=15秒且不跨场；每镜2-5秒；角色 ID 必须来自项目；每镜明确景别、运镜、镜头位置、构图、视线和焦点。""",
        {"storyBible": project_to_dict(project_id)["storyBible"], "episode": episode_dict(episode_id), "scene": scene, "payload": payload},
    )
    segments = [item for item in _json_list((data or {}).get("segments")) if isinstance(item, dict)]
    if not segments:
        segments = _fallback_segments(scene)
    with session() as connection:
        if payload.get("replaceExisting"):
            old_count = connection.execute("SELECT COUNT(*) AS n FROM shots WHERE scene_id = ? AND archived = 0", (scene_id,)).fetchone()["n"]
            connection.execute("UPDATE shots SET archived = 1, updated_at = ? WHERE scene_id = ? AND archived = 0", (now_text(), scene_id))
            connection.execute("UPDATE projects SET total_shots = MAX(total_shots - ?, 0), updated_at = ? WHERE id = ?", (old_count, now_text(), project_id))
        connection.execute("DELETE FROM generation_segments WHERE scene_id = ?", (scene_id,))
        shot_count = 0
        flow = (scene.get("script") or {}).get("flow") or []
        flow_by_id = {beat.get("id"): beat for beat in flow if isinstance(beat, dict)}
        for segment_index, segment in enumerate(segments, 1):
            segment_id = new_id("SEG-")
            cuts = [cut for cut in _json_list(segment.get("cuts")) if isinstance(cut, dict)]
            duration = sum(max(2, min(5, float(cut.get("seconds", 4)))) for cut in cuts)
            if duration > 15:
                raise ValueError(f"segment {segment_index} duration exceeds 15 seconds")
            connection.execute(
                """INSERT INTO generation_segments(id, project_id, episode_id, scene_id, order_index, blocking, soundscape, music, video_prompt, duration_seconds, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (segment_id, project_id, episode_id, scene_id, segment_index, segment.get("blocking", ""), segment.get("soundscape", ""), segment.get("music", ""), segment.get("videoPrompt", ""), duration, dumps({"source": "story-engine"})),
            )
            for cut_index, cut in enumerate(cuts, 1):
                shot_id = new_id("SH-")
                order_index = connection.execute("SELECT COALESCE(MAX(order_index), 0) + 1 AS n FROM shots WHERE scene_id = ?", (scene_id,)).fetchone()["n"]
                seconds = max(2, min(5, int(round(float(cut.get("seconds", 4))))))
                beat_refs = _json_list(cut.get("beatRefs"))
                dialogue = cut.get("dialogue", "")
                if not dialogue:
                    dialogue = " ".join(flow_by_id[ref].get("line", "") for ref in beat_refs if ref in flow_by_id and flow_by_id[ref].get("kind") == "dialogue").strip()
                connection.execute(
                    """INSERT INTO shots(id, scene_id, order_index, description, shot_size, camera_angle, lens, movement, duration, dialogue, prompt,
                       beat_refs_json, camera_position, composition, eyeline, focus, stability, keyframe_prompt, video_prompt, sfx, lighting, segment_id, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '待生成')""",
                    (
                        shot_id, scene_id, order_index, cut.get("shot") or cut.get("frame") or "新镜头", cut.get("size", "medium"),
                        cut.get("angle", "平视"), cut.get("lens", "50mm 标准，中浅景深"), cut.get("camera", "Static Shot"), seconds,
                        dialogue, cut.get("frame", ""), dumps(beat_refs), cut.get("cameraPosition", ""), cut.get("composition", ""),
                        cut.get("eyeline", ""), cut.get("focus", ""), cut.get("stability", "stable"), cut.get("frame", ""),
                        cut.get("videoPrompt") or cut.get("shot", ""), cut.get("sfx", ""), cut.get("lighting", ""), segment_id,
                    ),
                )
                for position, character_id in enumerate(_json_list(cut.get("characters"))):
                    if character_id and connection.execute("SELECT 1 FROM characters WHERE id = ? AND project_id = ?", (character_id, project_id)).fetchone():
                        connection.execute("INSERT OR IGNORE INTO shot_characters(shot_id, character_id, position) VALUES (?, ?, ?)", (shot_id, character_id, position))
                shot_count += 1
        if shot_count:
            connection.execute("UPDATE projects SET total_shots = total_shots + ?, updated_at = ? WHERE id = ?", (shot_count, now_text(), project_id))
    return {"shots": list_shots_for_scene(scene_id), "segments": _segments_for_scene(scene_id)}


def _segments_for_scene(scene_id: str) -> list[dict[str, Any]]:
    with session() as connection:
        rows = connection.execute("SELECT * FROM generation_segments WHERE scene_id = ? ORDER BY order_index", (scene_id,)).fetchall()
    return [
        {"id": row["id"], "sceneId": row["scene_id"], "order": row["order_index"], "blocking": row["blocking"], "soundscape": row["soundscape"], "music": row["music"], "videoPrompt": row["video_prompt"], "duration": row["duration_seconds"]}
        for row in rows
    ]


def validate_story_project(project_id: str) -> dict[str, Any]:
    snapshot = story_snapshot(project_id)
    project = project_to_dict(project_id)
    gates: list[dict[str, Any]] = []

    def gate(key: str, ok: bool, message: str, warning: bool = False) -> None:
        gates.append({"id": key, "status": "pass" if ok else ("warning" if warning else "fail"), "message": message})

    bible = snapshot["storyBible"]
    required = ["logline", "coreConflict", "theme", "world"]
    missing = [key for key in required if not str(bible.get(key) or "").strip()]
    gate("story-bible", not missing, "故事圣经完整" if not missing else f"缺少：{', '.join(missing)}")

    episodes = project["episodes"]
    gate("episode-count", len(episodes) == int(project["targetEpisodes"]), f"当前 {len(episodes)} / 目标 {project['targetEpisodes']} 集", warning=True)
    structured = [ep for ep in episodes if ep.get("hook") and ep.get("coreEvent") and ep.get("endingHook")]
    gate("episode-structure", len(structured) == len(episodes), f"{len(structured)}/{len(episodes)} 集具备钩子、核心事件与结尾钩子", warning=True)

    leads = [item for item in snapshot["characters"] if item.get("tier") == "lead"] or snapshot["characters"][:3]
    character_ok = all(item.get("want") and item.get("need") and item.get("flaw") and item.get("arc") for item in leads) if leads else False
    gate("character-bible", character_ok, "主角组 Want/Need/Flaw/Arc 已建立" if character_ok else "主角组 Character Bible 仍不完整", warning=True)

    location_ok = bool(snapshot["locations"]) and all(item.get("visualAnchors") and item.get("lightingStates") for item in snapshot["locations"][:5])
    gate("art-bible", location_ok, "主要场景已有视觉锚点与光照状态" if location_ok else "主要场景还缺视觉锚点/光照状态", warning=True)

    with session() as connection:
        character_ids = {row["id"] for row in connection.execute("SELECT id FROM characters WHERE project_id = ? AND archived = 0", (project_id,)).fetchall()}
        scene_rows = connection.execute(
            "SELECT s.* FROM scenes s JOIN episodes e ON e.id = s.episode_id WHERE e.project_id = ? AND s.archived = 0",
            (project_id,),
        ).fetchall()
        invalid_speakers = 0
        scripted_scenes = 0
        missing_criteria = 0
        for row in scene_rows:
            script = loads(row["script_json"], {})
            flow = script.get("flow") if isinstance(script.get("flow"), list) else []
            if flow:
                scripted_scenes += 1
                if not loads(row["acceptance_criteria_json"], []):
                    missing_criteria += 1
                for beat in flow:
                    if beat.get("kind") == "dialogue" and beat.get("speakerId") not in character_ids:
                        invalid_speakers += 1
        shot_rows = connection.execute(
            "SELECT s.* FROM shots s JOIN scenes sc ON sc.id = s.scene_id JOIN episodes e ON e.id = sc.episode_id WHERE e.project_id = ? AND s.archived = 0",
            (project_id,),
        ).fetchall()
        segment_rows = connection.execute("SELECT * FROM generation_segments WHERE project_id = ?", (project_id,)).fetchall()

    gate("speaker-integrity", invalid_speakers == 0, "结构化对白说话人引用有效" if invalid_speakers == 0 else f"{invalid_speakers} 条对白缺少有效 speakerId")
    gate("scene-criteria", scripted_scenes == 0 or missing_criteria == 0, "场景剧本都有验收标准" if missing_criteria == 0 else f"{missing_criteria} 个已写场景缺少验收标准", warning=True)

    bad_duration = [row["id"] for row in shot_rows if not 2 <= int(row["duration"] or 0) <= 5]
    gate("shot-duration", not bad_duration, "镜头时长均在 2-5 秒" if not bad_duration else f"{len(bad_duration)} 个镜头超出 2-5 秒建议范围", warning=True)

    rich_shots = [row for row in shot_rows if row["segment_id"]]
    rich_ok = all(row["camera_position"] and row["composition"] and row["focus"] for row in rich_shots) if rich_shots else False
    gate("cinematography", rich_ok, "Story Engine 镜头已有机位、构图和焦点" if rich_ok else "尚未形成完整 Story Engine 摄影字段", warning=True)

    segment_ok = all(float(row["duration_seconds"] or 0) <= 15 for row in segment_rows)
    gate("segment-duration", segment_ok, "所有生成段 <= 15 秒" if segment_ok else "存在超过 15 秒的生成段")

    points = {"pass": 100, "warning": 60, "fail": 0}
    score = round(sum(points[item["status"]] for item in gates) / max(1, len(gates)), 1)
    status = "pass" if all(item["status"] == "pass" for item in gates) else "warning" if not any(item["status"] == "fail" for item in gates) else "fail"
    result = {"projectId": project_id, "score": score, "status": status, "gates": gates}
    with session() as connection:
        connection.execute("INSERT INTO story_quality_runs(id, project_id, score, status, result_json) VALUES (?, ?, ?, ?, ?)", (new_id("SQR-"), project_id, score, status, dumps(result)))
    return result
