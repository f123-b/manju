from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


ROOT = Path(__file__).resolve().parents[1]


def load_env_file() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("SHORT_DRAMA_DB", DATA_DIR / "short-drama.sqlite3"))
DIST_DIR = ROOT / "dist" / "client"
DB_LOCK = threading.Lock()


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_state (
                project_id TEXT PRIMARY KEY,
                data_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS generation_events (
                task_id TEXT PRIMARY KEY,
                shot_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                error TEXT
            )
            """
        )


def read_project() -> dict[str, Any] | None:
    init_db()
    with DB_LOCK, sqlite3.connect(DB_PATH) as connection:
        row = connection.execute(
            "SELECT data_json FROM project_state ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
    return json.loads(row[0]) if row else None


def write_project(project: dict[str, Any]) -> dict[str, Any]:
    init_db()
    project_id = str(project.get("id") or "P001")
    project["id"] = project_id
    project["schemaVersion"] = int(project.get("schemaVersion") or 1)
    with DB_LOCK, sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO project_state(project_id, data_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
            """,
            (project_id, json.dumps(project, ensure_ascii=False), now_text()),
        )
    return project


def record_event(task_id: str, shot_id: str, provider: str, status: str, error: str | None = None) -> None:
    init_db()
    with DB_LOCK, sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO generation_events(task_id, shot_id, provider, status, created_at, completed_at, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                status = excluded.status,
                completed_at = excluded.completed_at,
                error = excluded.error
            """,
            (task_id, shot_id, provider, status, now_text(), now_text() if status != "Running" else None, error),
        )


class GenerateRequest(BaseModel):
    shot_id: str
    prompt: str = ""


class GenerationProvider:
    name = "Auto"
    estimated_cost = 0.73

    async def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class LocalDemoProvider(GenerationProvider):
    name = "Local Demo"

    async def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(float(os.environ.get("SHORT_DRAMA_DEMO_DELAY", "2.2")))
        return {"status": "Success", "cost": self.estimated_cost}


class HttpGenerationProvider(GenerationProvider):
    """Generic provider adapter for a video platform with a JSON POST endpoint.

    Configure SHORT_DRAMA_PROVIDER_URL and SHORT_DRAMA_PROVIDER_API_KEY. The
    endpoint should return JSON with status=Success, or a status_url that can
    be polled until the task finishes.
    """

    name = os.environ.get("SHORT_DRAMA_PROVIDER_NAME", "External Video API")
    estimated_cost = float(os.environ.get("SHORT_DRAMA_ESTIMATED_COST", "0.73"))

    def __init__(self, url: str, api_key: str | None) -> None:
        self.url = url
        self.api_key = api_key
        self.model = os.environ.get("SHORT_DRAMA_PROVIDER_MODEL", "video-default")
        self.auth_header = os.environ.get("SHORT_DRAMA_PROVIDER_AUTH_HEADER", "Authorization")
        self.auth_prefix = os.environ.get("SHORT_DRAMA_PROVIDER_AUTH_PREFIX", "Bearer")

    def _request(self, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers[self.auth_header] = f"{self.auth_prefix} {self.api_key}".strip()
        request = urllib.request.Request(
            url,
            data=json.dumps(payload or {}).encode("utf-8") if payload is not None else None,
            headers=headers,
            method="POST" if payload is not None else "GET",
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))

    async def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await asyncio.to_thread(self._request, self.url, payload)
        status_url = response.get("status_url") or response.get("statusUrl")
        if status_url and response.get("status") in {None, "Running", "Queued", "Processing"}:
            for _ in range(90):
                await asyncio.sleep(2)
                response = await asyncio.to_thread(self._request, status_url)
                if response.get("status") in {"Success", "Failed", "Cancelled"}:
                    break
        if response.get("status") == "Failed":
            raise RuntimeError(response.get("error") or "外部生成平台返回失败")
        return {
            "status": "Success",
            "cost": float(response.get("cost") or self.estimated_cost),
            "output_url": response.get("output_url") or response.get("video_url"),
        }


def provider_for_request() -> GenerationProvider:
    url = os.environ.get("SHORT_DRAMA_PROVIDER_URL")
    if url:
        return HttpGenerationProvider(url, os.environ.get("SHORT_DRAMA_PROVIDER_API_KEY"))
    return LocalDemoProvider()


def finish_project_generation(project: dict[str, Any], task_id: str, result: dict[str, Any]) -> dict[str, Any]:
    task = next((item for item in project.get("tasks", []) if item.get("id") == task_id), None)
    if not task:
        return project
    shot = next((item for item in project.get("shots", []) if item.get("id") == task.get("shotId")), None)
    if not shot:
        task["status"] = "Failed"
        task["error"] = "镜头不存在"
        return project

    was_generated = shot.get("status") == "已生成"
    versions = [{**version, "active": False} for version in shot.get("versions", [])]
    versions.append({
        "id": f"V{len(versions) + 1}",
        "createdAt": now_text(),
        "active": True,
        **({"outputUrl": result["output_url"]} if result.get("output_url") else {}),
    })
    cost = round(float(result.get("cost") or task.get("cost") or 0.73), 2)
    shot.update({
        "status": "已生成",
        "qcScore": shot.get("qcScore") or 91,
        "cost": round(float(shot.get("cost") or 0) + cost, 2),
        "versions": versions,
    })
    task.update({"status": "Success", "cost": cost, "completedAt": now_text()})
    project["spent"] = round(float(project.get("spent") or 0) + cost, 2)
    production = project.setdefault("production", {})
    production["generatedShots"] = int(production.get("generatedShots") or 0) + (0 if was_generated else 1)
    return project


async def run_generation(task_id: str, shot_id: str, prompt: str, provider: GenerationProvider) -> None:
    try:
        result = await provider.generate({
            "project_id": (read_project() or {}).get("id", "P001"),
            "shot_id": shot_id,
            "prompt": prompt,
            "model": getattr(provider, "model", provider.name),
        })
        project = read_project()
        if project:
            write_project(finish_project_generation(project, task_id, result))
        record_event(task_id, shot_id, provider.name, "Success")
    except Exception as error:  # noqa: BLE001 - task state must be visible to the UI
        project = read_project()
        if project:
            task = next((item for item in project.get("tasks", []) if item.get("id") == task_id), None)
            shot = next((item for item in project.get("shots", []) if item.get("id") == shot_id), None)
            if task:
                task.update({"status": "Failed", "error": str(error)})
            if shot:
                shot["status"] = "待生成"
            write_project(project)
        record_event(task_id, shot_id, provider.name, "Failed", str(error))


app = FastAPI(title="Short Drama OS API", version="0.2.0")


@app.on_event("startup")
async def startup() -> None:
    init_db()


@app.get("/api/health")
async def health() -> dict[str, Any]:
    provider = provider_for_request()
    return {"ok": True, "database": str(DB_PATH), "provider": provider.name, "mode": "remote" if isinstance(provider, HttpGenerationProvider) else "demo"}


@app.get("/api/project")
async def get_project() -> dict[str, Any]:
    project = read_project()
    if not project:
        raise HTTPException(status_code=404, detail="尚未初始化项目")
    return project


@app.put("/api/project")
async def put_project(project: dict[str, Any] = Body(...)) -> dict[str, Any]:
    if project.get("schemaVersion") != 1 or not project.get("id"):
        raise HTTPException(status_code=422, detail="项目数据格式无效")
    return write_project(project)


@app.post("/api/generations")
async def create_generation(request: GenerateRequest) -> dict[str, Any]:
    project = read_project()
    if not project:
        raise HTTPException(status_code=404, detail="尚未初始化项目")
    shot = next((item for item in project.get("shots", []) if item.get("id") == request.shot_id), None)
    if not shot:
        raise HTTPException(status_code=404, detail="镜头不存在")

    provider = provider_for_request()
    task_id = f"T{int(time.time() * 1000)}"
    while any(item.get("id") == task_id for item in project.get("tasks", [])):
        await asyncio.sleep(0.001)
        task_id = f"T{int(time.time() * 1000)}"
    task = {
        "id": task_id,
        "shotId": request.shot_id,
        "type": "视频",
        "model": provider.name,
        "status": "Running",
        "cost": provider.estimated_cost,
        "createdAt": now_text(),
    }
    project.setdefault("tasks", []).insert(0, task)
    shot["prompt"] = request.prompt or shot.get("prompt", "")
    shot["status"] = "生成中"
    write_project(project)
    record_event(task_id, request.shot_id, provider.name, "Running")
    asyncio.create_task(run_generation(task_id, request.shot_id, shot["prompt"], provider))
    return {"task": task, "project": project, "provider": provider.name}


@app.get("/{path:path}")
async def serve_client(path: str = ""):
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    if not DIST_DIR.exists():
        raise HTTPException(status_code=404, detail="前端尚未构建，请先运行 npm.cmd run build")
    candidate = (DIST_DIR / path).resolve()
    if candidate.is_file() and DIST_DIR.resolve() in candidate.parents:
        return FileResponse(candidate)
    return FileResponse(DIST_DIR / "index.html")


if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), reload=False)
