from __future__ import annotations

import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..core.config import DATA_DIR, ROOT
from ..core.database import session
from ..domain.repository import dumps, new_id, now_text
from ..domain.video_engine import ensure_video_clips


VIDEO_SUFFIXES = {".avi", ".mkv", ".mov", ".mp4", ".m4v", ".webm"}


def _ffmpeg_path() -> str | None:
    configured = os.environ.get("SHORT_DRAMA_FFMPEG", "").strip()
    if configured and Path(configured).is_file():
        return configured
    return shutil.which("ffmpeg")


def _local_media(url: str | None) -> Path | None:
    if not url:
        return None
    if url.startswith("/assets/"):
        candidate = (ROOT / "public" / url.lstrip("/")).resolve()
    elif url.startswith("/generated-media/"):
        name = Path(url).name
        candidates = [DATA_DIR / "generated-video" / name, DATA_DIR / "generated-audio" / name]
        candidate = next((item.resolve() for item in candidates if item.is_file()), candidates[0].resolve())
    else:
        candidate = Path(url).resolve()
    return candidate if candidate.is_file() and (ROOT.resolve() in candidate.parents or DATA_DIR.resolve() in candidate.parents) else None


def _render_dict(connection, job_id: str) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM render_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise KeyError(f"render job {job_id} not found")
    return {
        "id": row["id"], "projectId": row["project_id"], "episodeId": row["episode_id"],
        "status": row["status"], "outputUrl": row["output_url"], "error": row["error_message"],
        "metadata": json.loads(row["metadata_json"] or "{}"),
        "createdAt": row["created_at"], "startedAt": row["started_at"], "completedAt": row["completed_at"],
    }


def list_render_jobs(episode_id: str) -> list[dict[str, Any]]:
    with session() as connection:
        return [_render_dict(connection, row["id"]) for row in connection.execute("SELECT id FROM render_jobs WHERE episode_id = ? ORDER BY created_at DESC", (episode_id,)).fetchall()]


def render_episode_mp4(episode_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    ensure_video_clips()
    with session() as connection:
        episode = connection.execute("SELECT * FROM episodes WHERE id = ? AND archived = 0", (episode_id,)).fetchone()
        if not episode:
            raise KeyError(f"episode {episode_id} not found")
        clips = connection.execute(
            """SELECT vc.id, vc.timeline_start_ms, vc.source_start_ms, vc.duration_ms, COALESCE(ma.path_or_url, s.image) AS source_url
               FROM video_clips vc JOIN shots s ON s.id = vc.shot_id
               LEFT JOIN generation_versions gv ON gv.shot_id = s.id AND gv.is_active = 1
               LEFT JOIN media_assets ma ON ma.id = gv.media_asset_id
               WHERE vc.episode_id = ? AND vc.archived = 0 AND s.archived = 0
               ORDER BY vc.timeline_start_ms, vc.created_at""",
            (episode_id,),
        ).fetchall()
        mixdown = connection.execute("SELECT m.*, a.path_or_url AS audio_url FROM audio_mixdowns m JOIN media_assets a ON a.id = m.media_asset_id WHERE m.episode_id = ? ORDER BY m.created_at DESC LIMIT 1", (episode_id,)).fetchone()
        job_id = new_id("RND-")
        connection.execute("INSERT INTO render_jobs(id, project_id, episode_id, status, metadata_json) VALUES (?, ?, ?, 'queued', ?)", (job_id, episode["project_id"], episode_id, dumps({"clipCount": len(clips), "audioMixdownId": mixdown["id"] if mixdown else None})))

    ffmpeg = _ffmpeg_path()
    media_paths = [_local_media(row["source_url"]) for row in clips]
    if not ffmpeg:
        message = "未找到 FFmpeg。请安装 FFmpeg，或设置 SHORT_DRAMA_FFMPEG 指向 ffmpeg 可执行文件后重试。"
        with session() as connection:
            connection.execute("UPDATE render_jobs SET status = 'blocked', error_message = ?, completed_at = ? WHERE id = ?", (message, now_text(), job_id))
            return _render_dict(connection, job_id)
    if not clips or any(path is None for path in media_paths):
        message = "本集缺少可读取的镜头图像，无法执行 MP4 渲染。"
        with session() as connection:
            connection.execute("UPDATE render_jobs SET status = 'blocked', error_message = ?, completed_at = ? WHERE id = ?", (message, now_text(), job_id))
            return _render_dict(connection, job_id)

    output_dir = DATA_DIR / "generated-video"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{job_id}.mp4"
    command = [ffmpeg, "-y"]
    timeline_duration = max((int(row["timeline_start_ms"] or 0) + int(row["duration_ms"] or 1000)) for row in clips) / 1000
    timeline_duration = max(0.1, timeline_duration)
    for row, path in zip(clips, media_paths):
        duration = max(0.1, float(row["duration_ms"] or 1000) / 1000)
        if path.suffix.lower() in VIDEO_SUFFIXES:
            source_start = max(0, int(row["source_start_ms"] or 0)) / 1000
            command.extend(["-ss", str(source_start), "-t", str(duration), "-i", str(path)])
        else:
            command.extend(["-loop", "1", "-framerate", "30", "-t", str(duration), "-i", str(path)])
    audio_index = len(clips)
    audio_path = _local_media(mixdown["audio_url"]) if mixdown and mixdown["audio_url"] else None
    if audio_path:
        command.extend(["-i", str(audio_path)])
    filters = [f"color=c=black:s=1280x720:r=30:d={timeline_duration:.3f}[base]"]
    last = "base"
    for index, row in enumerate(clips):
        start = max(0, int(row["timeline_start_ms"] or 0)) / 1000
        duration = max(0.1, float(row["duration_ms"] or 1000) / 1000)
        end = start + duration
        filters.append(f"[{index}:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,trim=duration={duration:.3f},setpts=PTS-STARTPTS[v{index}]")
        mix = f"mix{index}"
        filters.append(f"[{last}][v{index}]overlay=x=0:y=0:eof_action=pass:repeatlast=0:enable='between(t,{start:.3f},{end:.3f})'[{mix}]")
        last = mix
    filters.append(f"[{last}]format=yuv420p[vout]")
    command.extend(["-filter_complex", ";".join(filters), "-map", "[vout]"])
    if audio_path:
        command.extend(["-map", f"{audio_index}:a:0", "-af", "apad", "-c:a", "aac"])
    command.extend(["-t", f"{timeline_duration:.3f}", "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_file)])

    with session() as connection:
        connection.execute("UPDATE render_jobs SET status = 'running', started_at = ? WHERE id = ?", (now_text(), job_id))
    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=int(payload.get("timeoutSeconds", 900)), check=False)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr[-1200:] or "FFmpeg 渲染失败")
        output_url = f"/generated-media/{output_file.name}"
        with session() as connection:
            connection.execute("UPDATE render_jobs SET status = 'ready', output_url = ?, completed_at = ? WHERE id = ?", (output_url, now_text(), job_id))
            return _render_dict(connection, job_id)
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as error:
        with session() as connection:
            connection.execute("UPDATE render_jobs SET status = 'failed', error_message = ?, completed_at = ? WHERE id = ?", (str(error), now_text(), job_id))
            return _render_dict(connection, job_id)
