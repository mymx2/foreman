# 本地桥接与官方 CLI 边界

## 描述文件

剪映启动后写：

```
%TEMP%\infinite-canvas-native-bridge.json
```

内容（每次启动端口会变）：

```json
{
  "app": "infinite_canvas",
  "pid": 42876,
  "port": 56212,
  "token": "<每次启动随机>",
  "version": "11.8.0",
  "origin": "http://127.0.0.1:56212"
}
```

`token` 是敏感值，只放内存，不写日志、不进草稿、不出现在任何交付物里。
`probe` 只输出 `app / pid / port / version / build / capabilities`，不输出 token。

## 三个只读/写入路由

所有请求都带：

```
x-infinite-canvas-native-token: <token>
```

### `GET /.infinite-canvas-native-bridge/health`

返回 200，结构包含 `compatibility.application`（version/build）、
`compatibility.capabilities`、`pid`、`application_path`，以及
`local_agent_server` 等内部对象。**内部对象含 `localServerToken`，不要落盘、不要回显。**

能力位（11.8 实测）：

```
video.export, video.export.options, video.export.outputs,
editor.control:7, editor.preview:3, hub.session,
window.control, native.bridge, mcp.tracking, ...
```

### `GET /custom-agent/context`

返回当前登录上下文，`authContext.principal.userId` 用于拼 `accountScope = uid:<userId>`。
响应里带登录 cookie / 会话信息，属于敏感数据：只取 uid，其余不保留。

未登录时返回的 principal 没有 userId，`export` 会报 `NOT_LOGGED_IN`。

### `POST /custom-agent/film-export`

请求体：

```json
{
  "accountScope": "uid:123456",
  "requestId": "uuid4",
  "snapshotId": "film-export-uuid4",
  "revision": "sha256:<draft_info.json 的 SHA-256>",
  "draftPath": "D:\\...\\draft",
  "draftSha256": "<同一 digest>",
  "outputPath": "D:\\...\\out.mp4",
  "format": "mp4",
  "timeoutMs": 300000
}

```

- `draftPath` 必须指向含**明文** `draft_info.json` 的目录。
- `format` 实测支持 `mp4`、`mov`、`gif`、`mp3`、`wav`、`aac`、`flac`、`aiff`、`ogg`；
  音频格式要求草稿里实际有音轨，否则 409 `film_export_no_audio`。
- `revision` 与 `draftSha256` 必须是同一个 digest，剪映用它确认导出的是当前版本。
- 成功返回 200 `{"ok": true, "path": "...", "format": "mp4", "requestId": "...", "revision": "..."}`。
- 回执 `path` 与请求不一致、文件不存在或为 0 字节，技能都判失败。

## 导出错误码

| `error` | 含义 | 处理 |
|---|---|---|
| `film_export_entitlement_denied` | 草稿含会员/授权素材 | 最常见是文字素材写成 `subtitle`；改成 `text`，再去掉会员字体/特效 |
| `film_export_entitlement_bypass_forbidden` | 拒绝绕过会员校验 | 移除会员素材，或在剪映客户端正常导出 |
| `film_export_dependency_missing` | 素材包未缓存 | 先在剪映里打开对应转场/滤镜/特效让它下载，或从计划去掉 |
| `film_export_draft_unreadable` | 草稿加密/损坏/路径不对 | 只对明文草稿导出；加密草稿回剪映里导出 |
| `film_export_no_audio` | 要求音频但没有可用音频流 | 检查音频路径，或去掉音频 |
| `film_export_format_unavailable` | 格式不支持 | 用已实测的 `mp4/mov/gif/mp3/wav/aac/flac/aiff/ogg` |
| `film_export_options_unavailable` | 导出参数不可用 | 不传自定义参数 |
| `film_export_invalid_request` | 请求体不合法 | 用 `jy.py render` 生成，不手拼 |
| `film_export_invalid_state` | 剪映正忙（播放/导出/切换） | 等空闲后重试 |
| `film_export_draft_manager_unavailable` | 草稿管理器不可用 | 重启剪映 |
| `film_export_frame_canvas_unavailable` | 画布不可用 | 重启剪映，或换画布尺寸 |
| `film_export_runtime_unavailable` | 导出运行时未就绪 | 等剪映完全启动 |
| `film_export_request_canceled` | 剪映取消本次导出 | 停止并发重试，检查是否有弹窗或未完成导出 |
| `film_export_timeout` | 导出超过请求超时 | 保留现场，确认剪映是否仍在导出；不要并发重试同一草稿 |
| `film_export_token_invalid` | 本地 bridge token 失效 | 重新运行 `probe` 读取新描述文件，不复用旧 token |
| `film_export_unsupported_timeline` | 当前时间线布局不受支持 | 保存为单时间线，或在客户端导出 |
| `film_export_cancelled_or_timeout` | 导出取消或超时 | 保留现场，不要并发重试同一草稿 |
| `film_export_panel_unavailable` | 导出面板/注入执行不可用 | 退出重开剪映；仍失败就改客户端导出 |

HTTP 409 通常是 entitlement/dependency；HTTP 500 可重试；502 常用响应过长或解析失败，
不要把任意 502 都解释成业务拒绝，先保留 `status` 与 `native_error`，再按错误码处理。
`film_export_invalid_state` 等“剪映正忙”错误不要并发轰炸；同一草稿同一时间只跑一个导出。
技能按 `error` 字段给中文原因，不把原始 cookie 或 token 写进错误详情。

## 导出选项

2026-11-16 实测 `/custom-agent/film-export` 的 draftPath 请求体只接受固定字段：
基线导出 943,778 bps；追加 `options.bitrate`、`options.videoBitrate`、`exportOptions.bitrate`、
`videoExportOptions.bitrate` 或 `outputs` 全部返回 409 `film_export_invalid_request`。
本机官方 agent 工具 `custom-agent.film-export.v1` 的 schema 里，视频输出只有
`format`（mp4/mov）、`fps`、`resolution`；`bitrate` 只属于音频输出（192/256/320 kbps）。

所以视频自定义码率在这个 draftPath 桥接入口不可用，不能靠加字段绕过。分辨率/帧率可以改草稿
`canvas_config` 后导出；需要指定视频码率时，在剪映客户端导出，或先用本技能导出默认成片再用
外部 ffmpeg 转码。证据已移出仓库。

## 官方 CLI：能用与不能用

安装目录里有两套官方 CLI：

| 工具 | 实测边界 |
|---|---|
| `jianying-agent-cli.exe` | `draft query-content` / `plan-patch` / `validate-patch` 需要 `JIANYING_AGENT_RUNTIME_TOKEN` 或合法 `draft_patch artifact`；没有宿主注入时返回 `PERMISSION_DENIED` |
| `lyra-cli.exe` | `--help` 直接 `unauthorized host process`（-100015），只允许剪映宿主进程调用 |
| `canvas-draft.exe` | 只有 `inspect` / `downgrade`，不提供编辑/导出 |
| `Resources\canvas_agent\skills` | 官方 XML 草稿编排协议；`DraftEditing` 是唯一写入口，外部 agent 提交不了 Selection，只能当结构参考 |

`Resources\agent_runtime_env` 里的 `hubcli` 依赖宿主注入 `CUSTOM_AGENT_BUN_EXECUTABLE`，
外部 shell 也不能直接用。结论：**外部自动化走 native bridge，不走官方 CLI。**

## 参考仓库在 11.8 上为什么不能用

`jianying-headless-windows` 把 `videoeditor.dll` 的 SHA-256 白名单固定在某几个 11.5 版本，
本机 11.8 会在 `discover_installation` 阶段被拒绝。不要改白名单绕过。

`jianying-agent-cli`（jy）的 macOS 引擎在 Windows 上有两处硬伤：

- `jianying_commands._app_uptime_s()` 调 `/bin/ps`，Windows 抛 `FileNotFoundError`；
- `_pid_alive()` 用 `os.kill(pid, 0)`，Windows 上对存活进程也可能报错，导致
  `descriptor pid is not alive`（实测 pid 存活、health 200 仍误判）。

所以本技能不调用 jy 的 preflight/render，只借它的**草稿 JSON 形状**作参考，桥接调用自己实现。
