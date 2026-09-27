from __future__ import annotations

import os
import json
from typing import Any

from ..core.database import session
from ..domain.repository import dumps, new_id


def workspace_context() -> dict[str, str]:
    return {
        "workspaceId": os.environ.get("SHORT_DRAMA_WORKSPACE_ID", "local"),
        "actorId": os.environ.get("SHORT_DRAMA_ACTOR_ID", "local-user"),
    }


def session_descriptor() -> dict[str, Any]:
    context = workspace_context()
    with session() as connection:
        workspace = connection.execute("SELECT id, name FROM workspaces WHERE id = ?", (context["workspaceId"],)).fetchone()
        member = connection.execute("SELECT user_id, display_name, role FROM workspace_members WHERE workspace_id = ? AND user_id = ?", (context["workspaceId"], context["actorId"])).fetchone()
    return {
        "workspace": {"id": workspace["id"], "name": workspace["name"]} if workspace else {"id": context["workspaceId"], "name": "未注册工作区"},
        "user": {"id": member["user_id"], "name": member["display_name"], "role": member["role"]} if member else {"id": context["actorId"], "name": "待登录用户", "role": "member"},
        "auth": {"mode": "local-preview", "readyForExternalIdentity": True},
    }


def record_audit(action: str, resource_type: str, resource_id: str = "", metadata: dict[str, Any] | None = None) -> None:
    context = workspace_context()
    with session() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO workspaces(id, name) VALUES (?, ?)",
            (context["workspaceId"], context["workspaceId"]),
        )
        connection.execute(
            "INSERT OR IGNORE INTO workspace_members(workspace_id, user_id, display_name, role) VALUES (?, ?, ?, ?)",
            (context["workspaceId"], context["actorId"], context["actorId"], "owner"),
        )
        connection.execute(
            "INSERT INTO audit_events(id, workspace_id, actor_id, action, resource_type, resource_id, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_id("AUD-"), context["workspaceId"], context["actorId"], action, resource_type, resource_id, dumps(metadata or {})),
        )


def list_audit_events(limit: int = 50) -> list[dict[str, Any]]:
    context = workspace_context()
    with session() as connection:
        rows = connection.execute(
            "SELECT id, workspace_id, actor_id, action, resource_type, resource_id, metadata_json, created_at FROM audit_events WHERE workspace_id = ? ORDER BY created_at DESC LIMIT ?",
            (context["workspaceId"], max(1, min(int(limit), 200))),
        ).fetchall()
        return [{**dict(row), "metadata": json.loads(row["metadata_json"] or "{}")} for row in rows]
