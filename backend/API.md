# 外部视频生成 API 契约

## 内部资源 API

服务端使用 SQLite 关系表保存项目、剧集、场景、镜头、资产、生成任务、版本、成本和质检记录。桌面预览版默认使用 `P001`，主要资源接口如下：

```text
GET/PATCH /api/projects/{project_id}
GET       /api/projects/{project_id}/tasks
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
GET/PATCH  /api/settings/providers
POST       /api/settings/providers/test
GET        /api/session
GET        /api/audit-events

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
PATCH/DELETE /api/audio-clips/{clip_id}
GET/POST   /api/projects/{project_id}/video-clips
PATCH/DELETE /api/video-clips/{clip_id}
POST        /api/projects/{project_id}/qc
POST        /api/projects/{project_id}/continuity-check
POST        /api/shots/{shot_id}/qc
POST        /api/agent/runs
GET         /api/projects/{project_id}/agent/runs
GET         /api/agent/runs/{run_id}
POST        /api/agent/runs/{run_id}/resume
POST        /api/agent/runs/{run_id}/cancel
POST/GET    /api/episodes/{episode_id}/render(s)
```

生成任务会先写入 `generation_tasks` 的 `Queued` 状态，由独立后台 worker 领取；服务重启会把未完成的 `Running` 任务恢复为 `Queued`，不会依赖请求协程存活。`GET /api/projects/{project_id}/tasks` 会把图片、视频、音频、Agent 和 MP4 渲染任务统一成同一字段结构；渲染任务的 `targetType` 为 `render`，Provider 为 `local`，模型为 `FFmpeg`。

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

视觉 QC 约定：默认执行本地图片解码、尺寸、画幅、曝光和角色绑定检查；当 `llmProviderUrl` 已配置时，`POST /api/shots/{shot_id}/qc` 和 `POST /api/projects/{project_id}/qc` 会向 OpenAI 兼容的 `/chat/completions` 发送结构化多模态请求。镜头图片会以本地 data URL 或远程 URL 放入 `image_url`，模型返回的 `vision_semantic` 结论会写入 `qc_records`，不会覆盖本地检查。

视频时间线片段的 `timelineStartMs`、`sourceStartMs` 和 `durationMs` 会在 `POST /api/episodes/{episode_id}/render` 时生效：图片作为帧序列，`.mp4/.mov/.mkv/.webm` 等本地视频按源起点裁切；片段之间的空隙输出黑场，重叠片段按时间线顺序叠加。渲染需要本机可用 FFmpeg，结果保存在 `data/generated-video` 并通过 `/generated-media/{filename}` 提供访问。

LLM / Agent 配置字段：

```env
SHORT_DRAMA_LLM_PROVIDER_URL=http://127.0.0.1:11434/v1
SHORT_DRAMA_LLM_PROVIDER_NAME=OpenAI Compatible
SHORT_DRAMA_LLM_MODEL=gpt-4o-mini
SHORT_DRAMA_LLM_API_KEY=
```

本地 MiniMax 可使用 vLLM 的 OpenAI-compatible 服务接入 Agent。建议把 vLLM 监听在 `8001`，避免和本应用 FastAPI 的 `8000` 冲突：

```bash
vllm serve MiniMaxAI/MiniMax-M2.1 --trust-remote-code --port 8001
```

然后在设置页选择“MiniMax M2.1 · 本地 vLLM”，或填写：

```env
SHORT_DRAMA_LLM_PROVIDER_URL=http://127.0.0.1:8001/v1
SHORT_DRAMA_LLM_PROVIDER_NAME=MiniMax Local · vLLM
SHORT_DRAMA_LLM_MODEL=MiniMaxAI/MiniMax-M2.1
SHORT_DRAMA_LLM_API_KEY=
```

适配器会自动请求 `/v1/chat/completions`，并在测试时读取 `/v1/models`。部分本地运行时不支持 `response_format`，系统会自动重试一次纯 JSON 请求；MiniMax 推理模型返回的 `<think>` 或 Markdown JSON 包裹也会自动清理。M2 系列主要用于 Agent 文本任务；视觉 QC 要使用本地支持图像输入的 MiniMax-VL 模型，否则系统仍会保留本地像素和连续性检查。

Provider 和 LLM API Key 不会通过 API 返回明文。Windows 桌面预览使用当前用户 DPAPI 加密；非 Windows 开发环境使用 `data/.secret-key` 的本地密钥文件回退，文件已加入忽略列表。`/api/session` 和 `audit_events` 为后续多用户身份、权限和审计接入预留边界，当前预览版仍是本机单用户模式。

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
