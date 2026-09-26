# Short Drama OS 桌面预览版

双击 `START_PREVIEW.bat` 或 `启动桌面预览版.bat`，会启动本地 FastAPI 服务并打开一个独立桌面窗口。

预览版默认使用 SQLite 和本地演示生成器。数据保存在：

`data/short-drama.sqlite3`

如需接入实际视频生成平台：

1. 复制根目录的 `.env.example` 为 `.env`。
2. 填写 `SHORT_DRAMA_PROVIDER_URL` 与 `SHORT_DRAMA_PROVIDER_API_KEY`。
3. 按平台接口约定，让 URL 接受 JSON POST，并返回 `status` 或 `status_url`。
4. 再次启动桌面预览版。

停止服务可双击 `停止桌面预览版.bat`。
