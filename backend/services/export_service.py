from __future__ import annotations

import io
import json
import zipfile

from ..domain.repository import list_costs, list_models, list_qc, project_to_dict


def export_project_package(project_id: str) -> tuple[str, bytes]:
    project = project_to_dict(project_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        def write_json(path: str, value) -> None:
            archive.writestr(path, json.dumps(value, ensure_ascii=False, indent=2))

        write_json("project.json", project)
        write_json("story-bible.json", project["storyBible"])
        write_json("episodes.json", project["episodes"])
        write_json("shots.json", project["shots"])
        write_json("assets.json", project["assets"])
        write_json("generation-tasks.json", project["tasks"])
        write_json("costs.json", list_costs(project_id))
        write_json("qc.json", list_qc(project_id=project_id))
        write_json("models.json", list_models())
        archive.writestr("media/README.txt", "生成媒体文件由 Provider 返回的 URL 引用；此目录用于后续本地媒体归档。\n")
    return f"{project['title']}-project-package.zip", buffer.getvalue()
