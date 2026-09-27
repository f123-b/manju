from __future__ import annotations

import json
from typing import Any

from ..core.database import session
from ..domain.repository import (
    create_scene,
    dumps,
    list_scenes,
    new_id,
    now_text,
    project_to_dict,
    task_row,
    update_task_runtime,
)
from ..providers.llm import LLMNotConfigured, LLMProvider
from ..services.runtime_settings import _raw_settings
from .script_service import generate_episode_matrix, generate_scene_script, generate_shot_breakdown


STEP_DEFINITIONS = [
    ("context", "读取故事上下文"),
    ("matrix", "推进剧集矩阵"),
    ("scene", "准备可拍场景"),
    ("script", "生成场景剧本"),
    ("breakdown", "拆解生产镜头"),
]


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _goal_spec(goal: str, episode_id: str, rules: list[str]) -> dict[str, Any]:
    normalized = goal.strip()
    deliverables: list[str] = []
    keyword_map = [("剧本", "scene_script"), ("分镜", "shot_breakdown"), ("镜头", "shot_breakdown"), ("对白", "dialogue"), ("连续", "continuity_check"), ("角色", "character_consistency")]
    for keyword, deliverable in keyword_map:
        if keyword in normalized and deliverable not in deliverables:
            deliverables.append(deliverable)
    if not deliverables:
        deliverables = ["scene_script", "shot_breakdown"]
    return {"intent": normalized, "episodeId": episode_id, "deliverables": deliverables, "constraints": rules, "requiresHumanReview": True}


def _run_dict(connection, run_id: str) -> dict[str, Any]:
    run = connection.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        raise KeyError(f"agent run {run_id} not found")
    task = connection.execute("SELECT id, status, progress, error_message FROM generation_tasks WHERE target_type = 'agent_run' AND target_id = ? ORDER BY created_at DESC LIMIT 1", (run_id,)).fetchone()
    steps = connection.execute("SELECT * FROM agent_steps WHERE run_id = ? ORDER BY step_order", (run_id,)).fetchall()
    return {
        "id": run["id"], "projectId": run["project_id"], "episodeId": run["episode_id"], "goal": run["goal"],
        "status": run["status"], "currentStep": run["current_step"], "result": json.loads(run["result_json"] or "{}"),
        "error": run["error_message"], "createdAt": run["created_at"], "updatedAt": run["updated_at"],
        "completedAt": run["completed_at"], "taskId": task["id"] if task else None,
        "taskStatus": task["status"] if task else None, "progress": task["progress"] if task else 0,
        "steps": [{"key": item["step_key"], "title": dict(STEP_DEFINITIONS).get(item["step_key"], item["step_key"]), "status": item["status"], "input": json.loads(item["input_json"] or "{}"), "output": json.loads(item["output_json"] or "{}"), "error": item["error_message"], "startedAt": item["started_at"], "completedAt": item["completed_at"]} for item in steps],
    }


def get_agent_run(run_id: str) -> dict[str, Any]:
    with session() as connection:
        return _run_dict(connection, run_id)


def list_agent_runs(project_id: str, episode_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    with session() as connection:
        values: list[Any] = [project_id]
        where = "project_id = ?"
        if episode_id:
            where += " AND episode_id = ?"
            values.append(episode_id)
        values.append(max(1, min(int(limit), 100)))
        rows = connection.execute(f"SELECT id FROM agent_runs WHERE {where} ORDER BY created_at DESC LIMIT ?", values).fetchall()
        return [_run_dict(connection, row["id"]) for row in rows]


def create_agent_run(project_id: str, episode_id: str, goal: str) -> dict[str, Any]:
    if not goal.strip():
        raise ValueError("制作目标不能为空")
    with session() as connection:
        if not connection.execute("SELECT 1 FROM projects WHERE id = ? AND archived = 0", (project_id,)).fetchone():
            raise KeyError(f"project {project_id} not found")
        if not connection.execute("SELECT 1 FROM episodes WHERE id = ? AND project_id = ? AND archived = 0", (episode_id, project_id)).fetchone():
            raise KeyError(f"episode {episode_id} not found")
        run_id = new_id("AR-")
        task_id = new_id("T-")
        settings = _raw_settings()
        provider = settings.get("llmProviderName") or "Local Agent"
        model = settings.get("llmModel") or "local-agent"
        connection.execute("INSERT INTO agent_runs(id, project_id, episode_id, goal, status) VALUES (?, ?, ?, ?, 'queued')", (run_id, project_id, episode_id, goal.strip()))
        for index, (key, _title) in enumerate(STEP_DEFINITIONS):
            connection.execute("INSERT INTO agent_steps(id, run_id, step_key, step_order) VALUES (?, ?, ?, ?)", (new_id("ARS-"), run_id, key, index))
        connection.execute("INSERT INTO generation_tasks(id, project_id, shot_id, target_type, target_id, type, provider, model, status, prompt, parameters_json, estimated_cost) VALUES (?, ?, NULL, 'agent_run', ?, 'Agent', ?, ?, 'Queued', ?, ?, 0)", (task_id, project_id, run_id, provider, model, goal.strip(), dumps({"episodeId": episode_id})))
        return _run_dict(connection, run_id)


def cancel_agent_run(run_id: str) -> dict[str, Any]:
    with session() as connection:
        run = connection.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            raise KeyError(f"agent run {run_id} not found")
        connection.execute("UPDATE agent_runs SET status = 'cancelled', error_message = '用户取消', updated_at = ?, completed_at = ? WHERE id = ? AND status IN ('queued', 'running', 'failed')", (now_text(), now_text(), run_id))
        connection.execute("UPDATE generation_tasks SET status = 'Cancelled', completed_at = ?, updated_at = ? WHERE target_type = 'agent_run' AND target_id = ? AND status IN ('Queued', 'Running', 'Retrying')", (now_text(), now_text(), run_id))
        return _run_dict(connection, run_id)


def resume_agent_run(run_id: str) -> dict[str, Any]:
    with session() as connection:
        run = connection.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            raise KeyError(f"agent run {run_id} not found")
        if run["status"] == "success":
            return _run_dict(connection, run_id)
        connection.execute("UPDATE agent_steps SET status = 'pending', error_message = '', started_at = NULL, completed_at = NULL WHERE run_id = ? AND status = 'failed'", (run_id,))
        connection.execute("UPDATE agent_runs SET status = 'queued', error_message = '', updated_at = ? WHERE id = ?", (now_text(), run_id))
        connection.execute("UPDATE generation_tasks SET status = 'Retrying', retry_count = retry_count + 1, error_message = NULL, queued_at = ?, updated_at = ? WHERE target_type = 'agent_run' AND target_id = ? AND status IN ('Failed', 'Cancelled', 'Retrying')", (now_text(), now_text(), run_id))
        return _run_dict(connection, run_id)


def _context(project_id: str, episode_id: str, goal: str) -> dict[str, Any]:
    project = project_to_dict(project_id)
    episode = next((item for item in project["episodes"] if item["id"] == episode_id), {})
    scenes = list_scenes(episode_id)
    return {"goal": goal, "storyBible": project["storyBible"], "episode": episode, "scenes": scenes, "shots": [shot for shot in project["shots"] if shot["episodeId"] == episode_id], "characters": project["assets"]["characters"]}


async def _llm_step(step_key: str, context: dict[str, Any], settings: dict[str, str]) -> tuple[dict[str, Any], str]:
    provider = LLMProvider(settings)
    if not provider.configured:
        return {}, "local-fallback"
    schema = {
        "context": "{summary: string, goalSpec: {intent, episodeId, deliverables: [string], constraints: [string], requiresHumanReview: boolean}}",
        "matrix": "{data: {hook, coreEvent, payoff, twist, endingHook, beats:[{type,weight,setup,payoff}]}}",
        "scene": "{data: {sceneId?, title, purpose, summary, timeOfDay}}",
        "script": "{data: {summary, acceptanceCriteria:[string], flow:[{kind:'action',action}|{kind:'dialogue',speakerId,line,delivery}], sound:string}}",
        "breakdown": "{data: {segments:[{blocking,soundscape,music,cuts:[{beatRefs,seconds,size,camera,characters,frame,shot,lens,cameraPosition,composition,eyeline,focus,stability}]}]}}",
    }[step_key]
    system = "你是短剧制作 Agent。只返回合法 JSON，不要 Markdown。输出必须符合指定结构；内容必须继承故事圣经和不可违反规则。"
    user = json.dumps({"step": step_key, "expected": schema, "context": context}, ensure_ascii=False)
    return await provider.complete_json(system, user), provider.provider


def _fallback_step(step_key: str, context: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    episode_id = context["episode"]["id"]
    if step_key == "context":
        return {"summary": "已读取故事圣经、规则、剧集和角色资产", "goalSpec": _goal_spec(context["goal"], episode_id, context["storyBible"].get("rules", []))}
    if step_key == "matrix":
        return generate_episode_matrix(episode_id, data)
    if step_key == "scene":
        scenes = list_scenes(episode_id)
        scene_id = data.get("sceneId")
        if scene_id and any(item["id"] == scene_id for item in scenes):
            return next(item for item in scenes if item["id"] == scene_id)
        if scenes:
            return scenes[0]
        scene_id = create_scene(episode_id, {"title": data.get("title") or "Agent 场景", "purpose": data.get("purpose") or "推进本集核心冲突并留下下一集问题", "summary": data.get("summary") or context["goal"], "timeOfDay": data.get("timeOfDay") or "夜晚"})
        return next(item for item in list_scenes(episode_id) if item["id"] == scene_id)
    scene = context.get("agentScene") or _fallback_step("scene", context, {})
    scene_id = data.get("sceneId") or scene["id"]
    if step_key == "script":
        return generate_scene_script(scene_id, {"script": data} if data.get("flow") or data.get("beats") else data)
    return {"items": generate_shot_breakdown(scene_id, data)}


async def run_agent_task(task: dict[str, Any]) -> None:
    run_id = task["target_id"]
    run = get_agent_run(run_id)
    context = _context(run["projectId"], run["episodeId"], run["goal"])
    settings = _raw_settings()
    try:
        with session() as connection:
            connection.execute("UPDATE agent_runs SET status = 'running', updated_at = ? WHERE id = ?", (now_text(), run_id))
        for index, (step_key, _title) in enumerate(STEP_DEFINITIONS):
            current = get_agent_run(run_id)
            step = next(item for item in current["steps"] if item["key"] == step_key)
            if step["status"] == "success":
                if step["output"].get("sceneId"):
                    context["agentScene"] = next((item for item in list_scenes(run["episodeId"]) if item["id"] == step["output"]["sceneId"]), context.get("agentScene"))
                continue
            if task_row(task["id"])["status"] == "Cancelled":
                return
            with session() as connection:
                connection.execute("UPDATE agent_runs SET current_step = ?, status = 'running', updated_at = ? WHERE id = ?", (step_key, now_text(), run_id))
                connection.execute("UPDATE agent_steps SET status = 'running', input_json = ?, started_at = ? WHERE run_id = ? AND step_key = ?", (dumps(context), now_text(), run_id, step_key))
            response, provider_name = await _llm_step(step_key, context, settings)
            data = _json(response.get("data") if isinstance(response, dict) else response)
            output = _fallback_step(step_key, context, data)
            output = {"provider": provider_name, "source": "llm" if provider_name != "local-fallback" else "fallback", **output}
            if step_key == "scene":
                output["sceneId"] = output.get("id")
                context["agentScene"] = output
            if step_key == "context":
                context["goalSpec"] = output.get("goalSpec") or _goal_spec(run["goal"], run["episodeId"], context["storyBible"].get("rules", []))
            with session() as connection:
                connection.execute("UPDATE agent_steps SET status = 'success', output_json = ?, completed_at = ?, error_message = '' WHERE run_id = ? AND step_key = ?", (dumps(output), now_text(), run_id, step_key))
                connection.execute("UPDATE generation_tasks SET progress = ? WHERE id = ?", (min(99, (index + 1) * 20), task["id"]))
        result = {"episodeId": run["episodeId"], "sceneId": context.get("agentScene", {}).get("id"), "provider": settings.get("llmProviderName") if settings.get("llmProviderUrl") else "local-fallback"}
        with session() as connection:
            connection.execute("UPDATE agent_runs SET status = 'success', current_step = 'complete', result_json = ?, updated_at = ?, completed_at = ? WHERE id = ?", (dumps(result), now_text(), now_text(), run_id))
            connection.execute("UPDATE generation_tasks SET status = 'Success', progress = 100, actual_cost = 0, completed_at = ?, updated_at = ? WHERE id = ?", (now_text(), now_text(), task["id"]))
    except Exception as error:  # noqa: BLE001 - persist the checkpoint before returning
        with session() as connection:
            connection.execute("UPDATE agent_steps SET status = 'failed', error_message = ?, completed_at = ? WHERE run_id = ? AND status = 'running'", (str(error), now_text(), run_id))
            connection.execute("UPDATE agent_runs SET status = 'failed', error_message = ?, updated_at = ? WHERE id = ?", (str(error), now_text(), run_id))
            connection.execute("UPDATE generation_tasks SET status = 'Failed', error_message = ?, completed_at = ?, updated_at = ? WHERE id = ?", (str(error), now_text(), now_text(), task["id"]))
