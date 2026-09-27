from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException

from .services.story_engine import develop_project_story, story_snapshot, validate_story_project

router = APIRouter(prefix="/api", tags=["story-engine"])


@router.get("/projects/{project_id}/story-engine")
async def get_story_engine(project_id: str) -> dict[str, Any]:
    try:
        return story_snapshot(project_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/projects/{project_id}/story/develop")
async def post_story_develop(project_id: str, payload: Optional[dict[str, Any]] = Body(default=None)) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(develop_project_story, project_id, payload or {})
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/projects/{project_id}/story/validate")
async def post_story_validate(project_id: str) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(validate_story_project, project_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
