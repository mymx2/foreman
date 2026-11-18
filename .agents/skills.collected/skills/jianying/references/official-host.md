# 官方宿主能力面（剪映 11.8.0.14778）

这里记录剪映安装目录里**已经存在、但本技能没有调用**的官方能力。全部只读探测，
不启动剪映、不读取登录态。技能自己的实现走草稿文件 + native bridge；这些是另一条
「宿主内 agent」的路线，需要剪映自己注入运行时，外部无法直接调用。

## 1. 位置与运行时清单

`%LOCALAPPDATA%\JianyingPro\Apps\11.8.0.14778\Resources\agent_runtime_env\`：

| 路径 | 内容 |
|---|---|
| `env-manifest.json` | 构建信息（build `20261113-013126`、git `d901ced0…`），`provides: native-tools/v1, python-runtime/v1` |
| `bin/` | `canvas-draft.exe`(108 MB)、`creator-cli`、`hubcli`、`lyra-cli.cmd`、`ffprobe.exe`、`fd.exe`、`rg.exe`、`jq.exe` |
| `cli/hubcli/` | `cli.mjs` + `sdk.mjs` + **55 份 `contracts/*.json`** |
| `cli/creator-cli/`、`cli/lyra-resources/`、`cli/native-tools/`、`cli/npm-tools/`、`cli/python/`(3.12.10) | 未逐个探测 |
| `skills/_lib/host-capability-client.mjs` | 宿主能力客户端（11 KB） |
| `motiongraph/` | MotionGraph SDK + `host-tools.json`（CEF renderer） |

## 2. hubcli 契约（协议 `custom-agent.hub-cli.v1`）

`hubcli` 是宿主注入的 bun 可执行文件 + IPC 的包装：

```
bin/hubcli.cmd → %CUSTOM_AGENT_BUN_EXECUTABLE% cli/hubcli/cli.mjs
```

没有 `CUSTOM_AGENT_BUN_EXECUTABLE`（只有剪映 agent 运行时才会注入）时它直接拒绝启动，
**所以技能不调用、也不能伪造调用**。契约文件本身是静态 JSON，可以当官方 schema 读。

命令面（55 条，按域归并）：

| 域 | 命令 | 用途（来自契约 description） |
|---|---|---|
| asset | `asset.list` / `asset.get` / `asset.export` / `asset.import` | 素材库读写 |
| media | `media.transcribe` / `media.reviewVideo` | **宿主 ASR**（按毫秒返回段落/词，支持 `ranges`）、审片 |
| agent | `agent.models` | 列出当前继承模型、可用模型、上下文窗口 |
| document | `canvas.document.getNode` / `getNodes` / `getEdge` / `getEdges` / `getUsages` / `getMediaHistory` / `getDocumentProperties` | 读画布结构 |
| 选区 | `canvas.context.getSelection` | 当前选中节点 |
| 节点 | `canvas.nodes.move` / `canvas.nodes.rename` / `canvas.node.replaceMaterial` / `canvas.node.setGenerationInput` | 移动/重命名/换材质/写生成输入 |
| 批量 | `canvas.batch`（108 KB 契约）/ `canvas.check` | 批量执行、参数与前置条件校验 |
| 文本 | `canvas.text.add` / `canvas.text.setContent` | 新建/改文字节点 |
| 图像/视频/音频 | `canvas.image.add` / `canvas.image.setAssetType` / `canvas.video.add` / `canvas.audio.add` / `canvas.audio.setSpeechRate` / `canvas.audio.setSubType` / `canvas.audio.setTtsVoice` | 节点创建；音频语速/子类型/**TTS 音色** |
| 结构 | `canvas.group.*` / `canvas.characterGroup.add` / `canvas.characterSet.create|dissolve` / `canvas.assetOrganizer.*` / `canvas.storyboard.*` / `canvas.link.add` | 分组、角色集、素材整理、分镜 |
| 生成 | `canvas.generation.get` / `canvas.generation.resubmit` / `canvas.node.setGenerationInput` | AI 生成任务状态与重提 |
| 动态图形 | `canvas.motionGraphic.import` / `update` / `checkout` / `generation.begin` | MotionGraph 资产导入/更新/签出/生成 |
| 其它 | `canvas.help` / `web.read` | 命令发现、网页读取 |

`media.transcribe` 的契约要点：

- 输入 `path`（当前任务可读的媒体路径）、可选 `ranges`（毫秒，如 `0-30000,45000-60000`）、`out`；
- 输出「源时间段落 + 可用词级时间戳（毫秒）」，大结果落 `data.result_path`；
- 效果是 `write`（写任务输出目录），不是素材库写入；
- 这是**宿主侧 ASR**，与技能自己的 `subtitle.asr.local`（离线 ONNX）是两条独立路线。

## 3. MotionGraph

- `motiongraph/host-tools.json` 声明 `schema: lyra.mg-cef-deployment.v1`、`renderer: cef`，
  并列出 SDK 每个文件的 sha256；
- `sdk/resources/Resources/motiongraph/` 里有 `component-composition.js`、`component-core.js`、
  `components-2d.js`、`components-spatial.js`、`frame-runtime.js`、`motion-schema.js`、`path-trim.js`；
- 它是 CEF 内运行的动态图形运行时，**没有独立 CLI 入口**，离开宿主无法渲染。

## 4. 对技能的意义

1. **不能拿契约当草稿 schema**：`canvas.text.add` 等描述的是宿主 RPC 入参（含
   `sourceRef`/`stateToken`/`generationInput`），不是 `draft_info.json` 的字段结构，
   直接套用写草稿会写错。
2. **`media.transcribe` 不去抢**：本地 ASR 的优势是离线、无账号、可逐 token 调；宿主 ASR
   的优势是模型更新、可能更强，但需要 agent 运行时。两条线并存，技能只做前者。
3. **TTS / AI 生成 / 动态图形仍属宿主/账号能力**：`canvas.audio.setTtsVoice`、
   `canvas.generation.*`、`canvas.motionGraphic.*` 都需要宿主，技能保持 `host_only`。

## 5. 其余 CLI 的结论（2026-11-18 收尾盘点）

| 目录 | 内容 | 结论 |
|---|---|---|
| `cli/creator-cli/` | `creator-cli.js`(418 KB) + `index.js`(407 KB)；`bin/creator-cli` 是 shim，同样要求 `CUSTOM_AGENT_BUN_EXECUTABLE` | **host_only**，外部不可调用 |
| `cli/lyra-resources/` | `models/audiomodel/` | 宿主侧资源模型，无外部入口 |
| `cli/native-tools/` | `manifest.json` + `fd`/`ffprobe`/`jq`/`rg` 的 license 目录 | 只是随包分发的原生工具，技能已优先用系统/剪映 ffmpeg |
| `cli/npm-tools/` | `node_modules`（`@clack`、`@larksuite`、`ansi` 等）+ `package.json` | CLI 的终端 UI 依赖，不是能力入口 |
| `motiongraph/sdk/script/` | 大量 `motion_graph` 脚本 | 需要 CEF 宿主，无独立渲染入口 |
| `skills/_lib/host-capability-client.mjs` | 11 KB 宿主能力客户端 | 依赖宿主 IPC，外部进程不可复用 |

**总结**：安装侧这些额外目录都挂在同一个宿主运行时上（bun + IPC + CEF），
离开剪映 agent 会话无法调用。技能继续走「明文草稿 + native bridge」，不碰这条路。
