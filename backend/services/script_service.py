from __future__ import annotations

from typing import Any

from ..domain.repository import episode_dict, list_shots_for_scene, patch_episode
from .story_engine import generate_episode_matrix as _story_matrix
from .story_engine import generate_scene_script as _story_script
from .story_engine import generate_storyboard as _storyboard


def generate_episode_matrix(episode_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _story_matrix(episode_id, payload or {})


def generate_episode_matrix_ai(episode_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _story_matrix(episode_id, payload or {})


def generate_scene_script(scene_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _story_script(scene_id, payload or {})


def generate_scene_script_ai(scene_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _story_script(scene_id, payload or {})


def generate_shot_breakdown(scene_id: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return _storyboard(scene_id, payload or {}).get("shots", list_shots_for_scene(scene_id))


def generate_shot_breakdown_ai(scene_id: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return _storyboard(scene_id, payload or {}).get("shots", list_shots_for_scene(scene_id))
