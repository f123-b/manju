from __future__ import annotations

import json
from typing import Any

from ..domain.repository import (
    create_shot,
    episode_dict,
    list_scenes,
    list_shots_for_scene,
    patch_episode,
    patch_scene,
    project_to_dict,
)
from ..providers.llm import LLMProvider
from .runtime_settings import _raw_settings


def generate_episode_matrix(episode_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    episode = episode_dict(episode_id)
    payload = payload or {}
    defaults = {
        "hook": "一个新的决定改变了故事走向。",
        "coreEvent": "主角在关键关系中做出不可逆的选择。",
        "payoff": "选择带来短期代价，也打开新的行动空间。",
        "twist": "看似偶然的线索指向更大的秘密。",
        "endingHook": "一个新问题把观众带入下一集。",
    }
    patch = {key: payload.get(key) or episode.get(key) or value for key, value in defaults.items()}
    patch_episode(episode_id, patch)
    return episode_dict(episode_id)


def _project_context_for_episode(episode_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    from ..core.database import session

    with session() as connection:
        row = connection.execute("SELECT project_id FROM episodes WHERE id = ?", (episode_id,)).fetchone()
    if not row:
        raise KeyError(f"episode {episode_id} not found")
    project = project_to_dict(row["project_id"])
    return project, episode_dict(episode_id)


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


def generate_episode_matrix_ai(episode_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    project, episode = _project_context_for_episode(episode_id)
    data = _llm_json(
        "你是短剧编剧。根据故事圣经和本集上下文，生成剧集矩阵。只返回 JSON，字段必须是 hook、coreEvent、payoff、twist、endingHook，每个字段都是具体可拍的中文句子。",
        {
            "storyBible": project["storyBible"],
            "episode": episode,
            "currentDraft": {key: payload.get(key, "") for key in ("hook", "coreEvent", "payoff", "twist", "endingHook")},
        },
    )
    return generate_episode_matrix(episode_id, data or payload)


def generate_scene_script(scene_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    episode_ids = _episode_ids_for_scene(scene_id)
    scenes = [scene for episode_id in episode_ids for scene in list_scenes(episode_id)]
    scene = next((item for item in scenes if item["id"] == scene_id), None)
    if not scene:
        raise KeyError(f"scene {scene_id} not found")
    script = payload.get("script") or scene.get("script") or {
        "beats": [
            {"type": "action", "text": scene.get("purpose") or "人物进入场景并建立关系张力。"},
            {"type": "dialogue", "text": "林泽：这一次，我会按自己的选择走。"},
            {"type": "turn", "text": "一个新的线索打破了原有平衡。"},
        ],
        "dialogue": ["林泽：到此为止吧。"],
        "sound": "城市夜风与远处车流，情绪保持克制。",
    }
    patch_scene(scene_id, {"script": script, "summary": payload.get("summary") or scene.get("summary") or scene.get("purpose", "")})
    return next(item for episode_id in _episode_ids_for_scene(scene_id) for item in list_scenes(episode_id) if item["id"] == scene_id)


def generate_scene_script_ai(scene_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    episode_ids = _episode_ids_for_scene(scene_id)
    if not episode_ids:
        raise KeyError(f"scene {scene_id} not found")
    project, episode = _project_context_for_episode(episode_ids[0])
    scene = next((item for item in list_scenes(episode_ids[0]) if item["id"] == scene_id), None)
    if not scene:
        raise KeyError(f"scene {scene_id} not found")
    data = _llm_json(
        "你是短剧场景编剧。把场景写成可拍的动作、对白和声音节拍。只返回 JSON：{beats:[{type:'action'|'dialogue'|'turn',text:string}],dialogue:[string],sound:string,summary:string}。内容必须遵守故事规则。",
        {"storyBible": project["storyBible"], "episode": episode, "scene": scene, "draft": payload},
    )
    if data and data.get("beats"):
        return generate_scene_script(scene_id, {"script": data, "summary": data.get("summary") or payload.get("summary")})
    return generate_scene_script(scene_id, payload)


def generate_shot_breakdown(scene_id: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    existing = list_shots_for_scene(scene_id)
    if existing:
        return existing
    payload = payload or {}
    defaults = payload.get("shots") or [
        {"description": "人物进入场景，建立空间关系", "size": "全景", "duration": 4, "movement": "固定镜头"},
        {"description": "主角看向对方，情绪收紧", "size": "近景", "duration": 4, "movement": "微推（Slow Push In）"},
        {"description": "两人保持沉默，留下悬念", "size": "中景", "duration": 4, "movement": "缓慢拉远"},
    ]
    for shot in defaults:
        create_shot(scene_id, shot)
    return list_shots_for_scene(scene_id)


def generate_shot_breakdown_ai(scene_id: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = payload or {}
    episode_ids = _episode_ids_for_scene(scene_id)
    if not episode_ids:
        raise KeyError(f"scene {scene_id} not found")
    project, episode = _project_context_for_episode(episode_ids[0])
    scene = next((item for item in list_scenes(episode_ids[0]) if item["id"] == scene_id), None)
    if not scene:
        raise KeyError(f"scene {scene_id} not found")
    data = _llm_json(
        "你是短剧分镜师。把场景拆成 3 到 8 个可生成镜头。只返回 JSON：{shots:[{description,size,duration,movement,dialogue}]}。镜头要连续、可拍，并遵守故事规则。",
        {"storyBible": project["storyBible"], "episode": episode, "scene": scene},
    )
    if data and isinstance(data.get("shots"), list) and data["shots"]:
        return generate_shot_breakdown(scene_id, {"shots": data["shots"]})
    return generate_shot_breakdown(scene_id, payload)


def _episode_ids_for_scene(scene_id: str) -> list[str]:
    from ..core.database import session

    with session() as connection:
        row = connection.execute("SELECT episode_id FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        return [row["episode_id"]] if row else []
