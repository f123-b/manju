# 外部视频生成 API 契约

## 内部资源 API

服务端使用 SQLite 关系表保存项目、剧集、场景、镜头、资产、生成任务、版本、成本和质检记录。桌面预览版默认使用 `P001`，主要资源接口如下：

```text
GET/PATCH /api/projects/{project_id}
GET/PATCH /api/projects/{project_id}/story-bible
GET/POST   /api/projects/{project_id}/episodes
GET/PATCH /api/episodes/{episode_id}
GET/POST   /api/episodes/{episode_id}/scenes
GET/PATCH /api/scenes/{scene_id}
GET/POST   /api/scenes/{scene_id}/shots
GET/PATCH/DELETE /api/shots/{shot_id}
GET/POST   /api/shots/{shot_id}/generate
GET       /api/generation-tasks/{task_id}
POST      /api/generation-tasks/{task_id}/retry|cancel
GET       /api/shots/{shot_id}/versions
POST      /api/versions/{version_id}/activate
GET       /api/projects/{project_id}/costs|qc
POST      /api/projects/{project_id}/export

# Audio Engine V1
GET/POST   /api/characters/{character_id}/voice-profiles
PATCH      /api/voice-profiles/{profile_id}
POST       /api/voice-profiles/{profile_id}/lock|unlock|test
GET/POST   /api/scenes/{scene_id}/dialogue-lines
POST       /api/scenes/{scene_id}/dialogue-lines/extract
GET        /api/episodes/{episode_id}/dialogue-lines|audio-status
POST       /api/episodes/{episode_id}/generate-dialogue|mixdown
PATCH      /api/dialogue-lines/{line_id}
POST       /api/dialogue-lines/{line_id}/direct-performance|generate
GET        /api/dialogue-lines/{line_id}/takes
POST       /api/voice-takes/{take_id}/activate|run-qc
GET        /api/voice-providers
GET/POST   /api/projects/{project_id}/audio-clips
```

生成任务会先写入 `generation_tasks` 的 `Queued` 状态，由独立后台 worker 领取；服务重启会把未完成的 `Running` 任务恢复为 `Queued`，不会依赖请求协程存活。

Short Drama OS 在服务端通过 `SHORT_DRAMA_PROVIDER_URL` 发起一个 JSON `POST` 请求。

请求体示例：

```json
{
  "project_id": "P001",
  "shot_id": "SH045",
  "prompt": "夜晚，城市天台……",
  "model": "video-default"
}
```

接口可以直接返回完成结果：

```json
{
  "status": "Success",
  "video_url": "https://example.com/video.mp4",
  "cost": 0.73
}
```

也可以返回异步任务：

```json
{
  "status": "Running",
  "status_url": "https://example.com/api/tasks/task_123"
}
```

服务端会每 2 秒轮询 `status_url`，直到返回 `Success`、`Failed` 或 `Cancelled`。完成后，视频地址会保存到镜头版本的 `outputUrl` 字段，任务状态会同步到“生成”页面。

环境变量：

```env
SHORT_DRAMA_PROVIDER_URL=https://your-provider.example.com/v1/videos
SHORT_DRAMA_PROVIDER_API_KEY=your-api-key
SHORT_DRAMA_PROVIDER_NAME=Your Provider
SHORT_DRAMA_PROVIDER_MODEL=video-default
SHORT_DRAMA_ESTIMATED_COST=0.73
SHORT_DRAMA_PROVIDER_AUTH_HEADER=Authorization
SHORT_DRAMA_PROVIDER_AUTH_PREFIX=Bearer

# Optional external voice runtimes. If unset, the deterministic local WAV
# provider is used for development and tests; no TTS model is bundled.
SHORT_DRAMA_COSYVOICE_URL=http://127.0.0.1:50000/inference_sft
SHORT_DRAMA_CHATTERBOX_URL=
SHORT_DRAMA_GPTSOVITS_URL=
SHORT_DRAMA_VOICE_PROVIDER=cosyvoice
SHORT_DRAMA_VOICE_PROVIDER_MODEL=voice-default
SHORT_DRAMA_VOICE_ESTIMATED_COST=0.08
```
