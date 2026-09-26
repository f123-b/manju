# 外部视频生成 API 契约

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
```
