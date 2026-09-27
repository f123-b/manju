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

# RunningHub 工作流
GET/POST    /api/projects/{project_id}/runninghub/workflows
PATCH/DELETE /api/runninghub/workflows/{workflow_record_id}
POST        /api/runninghub/workflows/{workflow_record_id}/run
POST        /api/runninghub/upload

# Production Canvas
GET         /api/projects/{project_id}/canvas
POST        /api/projects/{project_id}/canvas/nodes
PATCH/DELETE /api/canvas-nodes/{node_id}
POST        /api/projects/{project_id}/canvas/edges
DELETE      /api/canvas-edges/{edge_id}
POST        /api/canvas-nodes/{node_id}/run
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

生产画布使用 `canvas_nodes` 和 `canvas_edges` 持久化节点工作流。画布首次打开时会为项目创建故事灵感、剧本 Agent、场景剧本、角色/场景参考、镜头画面、视频生成和时间线/音频七个起始节点。节点可保存标题、内容、提示词、资产或镜头绑定、位置和执行状态；Agent、图片和视频节点可从画布直接进入现有 Agent 或统一生成任务队列，文本和音频节点先作为可连接的工作流输入。

RunningHub 工作流页用于导入和运行 ComfyUI/RunningHub API JSON：

- `POST /api/projects/{project_id}/runninghub/workflows` 保存 `name`、`workflowId`、`description` 和 `apiJson`；编辑器从 API JSON 的 `inputs` 中提取可编辑字段，并在提交前转换为 RunningHub 的 `nodeInfoList`。
- `POST /api/runninghub/upload` 使用当前配置的 API Key 将图片或其他输入文件上传到 RunningHub，返回 provider 的 `fileName`，不把文件内容或密钥写入日志。
- `POST /api/runninghub/workflows/{workflow_record_id}/run` 创建统一生成任务；worker 调用 RunningHub 创建任务接口，再轮询任务状态，成功后把输出 URL 保存到任务结果和 `media_assets`。
- `GET /api/projects/{project_id}/tasks` 与“任务与结果”页继续统一展示 RunningHub、图片、视频、音频和渲染任务；没有 API Key 时运行请求会明确返回 422，而不会创建幽灵任务。

设置页字段：

```env
SHORT_DRAMA_RUNNINGHUB_BASE_URL=https://www.runninghub.cn
SHORT_DRAMA_RUNNINGHUB_API_KEY=
```

RunningHub 的公开 API 采用“提交任务返回 `taskId`、再查询状态和结果”的异步模式；完整工作流通常还需要把节点输入整理成 `nodeInfoList`，文件输入先通过上传接口转成 provider 文件名。实现依据官方公开文档：[API 概览](https://www.runninghub.cn/runninghub-api-doc-cn/)、[工作流完整接入示例](https://www.runninghub.cn/runninghub-api-doc-cn/doc-8287342)、[文件上传接口](https://rhtv.runninghub.cn/runninghub-api-doc-cn/api-425749007)、[V2 任务查询](https://www.runninghub.cn/runninghub-api-doc-cn/api-425767306)。

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
