from __future__ import annotations

import asyncio
import os
import threading
import time
from typing import Any

from ..domain.repository import (
    claim_next_task,
    complete_generation_task,
    fail_generation_task,
    generation_task,
    task_row,
    update_task_runtime,
    loads,
)
from ..providers.registry import ProviderRegistry


KIND_BY_TASK_TYPE = {"视频": "video", "图片": "image", "文本": "text", "语音": "audio", "音频": "audio", "工作流": "workflow"}
PENDING_STATUSES = {"Queued", "Retrying", "Running", "Processing", "Pending"}


class TaskEngine:
    """A small persistent worker queue backed by generation_tasks.

    The worker is deliberately independent from FastAPI request coroutines.
    A process restart leaves queued tasks in the database and converts stale
    Running tasks back to Queued before the worker starts.
    """

    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        self.registry = registry or ProviderRegistry()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        from ..core.database import session

        with session() as connection:
            connection.execute(
                "UPDATE generation_tasks SET status = 'Queued', updated_at = CURRENT_TIMESTAMP "
                "WHERE status IN ('Running', 'Processing')"
            )
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="short-drama-task-engine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None

    def wake(self) -> None:
        self._wake.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            task = claim_next_task()
            if task:
                try:
                    asyncio.run(self._process(task))
                except Exception as error:  # noqa: BLE001 - task failure must be persisted
                    try:
                        fail_generation_task(task["id"], str(error))
                    except Exception:
                        pass
                continue
            self._wake.wait(timeout=0.5)
            self._wake.clear()

    async def _process(self, task: dict[str, Any]) -> None:
        task_id = task["id"]
        # FastAPI settings and the durable worker are separate objects. Reload
        # before every task so a newly saved API key/model is used immediately
        # instead of leaving the worker on the startup-time mock provider.
        self.registry.reload()
        if task.get("target_type") == "agent_run":
            from .agent_service import run_agent_task

            await run_agent_task(task)
            return
        if task.get("target_type") == "asset":
            from .asset_generation_service import run_asset_task

            await run_asset_task(task, self.registry)
            return
        if task.get("target_type") == "runninghub_workflow":
            parameters = loads(task.get("parameters_json"), {})
            provider = self.registry.resolve("workflow", task.get("provider"), task.get("model"))
            payload = {
                "task_id": task["id"],
                "project_id": task["project_id"],
                "workflow_id": parameters.get("workflowId") or parameters.get("workflow_id"),
                "nodeInfoList": parameters.get("nodeInfoList") or [],
                "accessPassword": parameters.get("accessPassword"),
                "retainSeconds": parameters.get("retainSeconds"),
                "webhookUrl": parameters.get("webhookUrl"),
                "estimatedCost": task.get("estimated_cost"),
            }
            update_task_runtime(task_id, {"status": "Running", "progress": 10})
            response = await provider.submit(payload)
            response = response or {}
            provider_task_id = response.get("provider_task_id") or response.get("task_id") or response.get("id")
            update_task_runtime(task_id, {"provider_task_id": provider_task_id, "progress": 25})
            status = str(response.get("status") or "Queued")
            deadline = time.monotonic() + float(os.environ.get("SHORT_DRAMA_TASK_TIMEOUT", "900"))
            result = response
            while status.lower() in {item.lower() for item in PENDING_STATUSES}:
                if time.monotonic() > deadline:
                    raise TimeoutError("RunningHub 任务等待平台结果超时")
                await asyncio.sleep(float(os.environ.get("SHORT_DRAMA_POLL_INTERVAL", "2")))
                current = task_row(task_id)
                if current and current["status"] == "Cancelled":
                    if provider_task_id:
                        await provider.cancel(provider_task_id)
                    return
                result = await provider.status(provider_task_id or "")
                status = str(result.get("status") or "Running")
                update_task_runtime(task_id, {"progress": 90 if status.lower() == "success" else 45})
            if status.lower() in {"failed", "error"}:
                raise RuntimeError(result.get("error") or "RunningHub 返回失败")
            if status.lower() in {"cancelled", "canceled"}:
                from ..domain.repository import cancel_generation_task

                cancel_generation_task(task_id)
                return
            complete_generation_task(task_id, result)
            return
        kind = KIND_BY_TASK_TYPE.get(task.get("type", "视频"), "video")
        provider = self.registry.resolve(kind, task.get("provider"), task.get("model"))
        payload = {
            "task_id": task_id,
            "project_id": task["project_id"],
            "shot_id": task["shot_id"],
            "target_type": task.get("target_type", "shot"),
            "target_id": task.get("target_id") or task.get("shot_id"),
            "prompt": task.get("prompt", ""),
            "parameters": loads(task.get("parameters_json"), {}),
            "model": task.get("model"),
            "type": kind,
        }
        payload["references"] = payload["parameters"].get("references", [])
        update_task_runtime(task_id, {"status": "Running", "progress": 10})
        response = await provider.submit(payload)
        response = response or {}
        provider_task_id = response.get("provider_task_id") or response.get("task_id") or response.get("id")
        status_url = response.get("status_url") or response.get("statusUrl")
        if provider_task_id or status_url:
            update_task_runtime(task_id, {"provider_task_id": provider_task_id, "status_url": status_url, "progress": 25})

        current = task_row(task_id)
        if current and current["status"] == "Cancelled":
            if provider_task_id:
                await provider.cancel(provider_task_id, status_url)
            return

        result = response
        status = str(result.get("status") or "Success")
        deadline = time.monotonic() + float(os.environ.get("SHORT_DRAMA_TASK_TIMEOUT", "900"))
        while status.lower() in {item.lower() for item in PENDING_STATUSES}:
            if time.monotonic() > deadline:
                raise TimeoutError("生成任务等待平台结果超时")
            await asyncio.sleep(float(os.environ.get("SHORT_DRAMA_POLL_INTERVAL", "2")))
            current = task_row(task_id)
            if current and current["status"] == "Cancelled":
                if provider_task_id:
                    await provider.cancel(provider_task_id, status_url)
                return
            result = await provider.status(provider_task_id or status_url or "", status_url)
            status = str(result.get("status") or "Success")
            progress = result.get("progress")
            if progress is not None:
                update_task_runtime(task_id, {"progress": max(25, min(99, int(progress)))})

        if status.lower() in {"failed", "error"}:
            raise RuntimeError(result.get("error") or result.get("message") or "生成平台返回失败")
        if status.lower() in {"cancelled", "canceled"}:
            from ..domain.repository import cancel_generation_task

            cancel_generation_task(task_id)
            return
        complete_generation_task(task_id, {
            "output_url": result.get("output_url") or result.get("outputUrl") or result.get("video_url") or result.get("url"),
            "cost": result.get("cost"),
            "qc_score": result.get("qc_score") or result.get("qcScore") or 91,
            "duration_ms": result.get("duration_ms") or result.get("durationMs"),
        })


task_engine = TaskEngine()
