# 来源、候选与取舍

核对日期：2026-11-14。skills.sh 与其索引页会变动，安装第三方技能前重新核对仓库状态、版本和安全审计。

## skills.sh 候选

| 技能 | 来源 | 能力 | 结论 |
|---|---|---|---|
| `jianying-editor` | `luoluoluo22/jianying-editor-skill`，[skills.sh 页面](https://www.skills.sh/luoluoluo22/jianying-editor-skill/jianying-editor) | Python 封装、草稿生成、素材导入、字幕、录屏、自动导出 | 不采用为主链路。自动导出走 Windows UI Automation（页面口径），与剪映版本的绑定关系未核验；页面功能超出本机 11.8 已验证范围；2026-11-14 读取时 GitHub 主页/API 返回 404，2026-11-16 复核页面已可解析，源码仍未逐行核验。 |
| `capcut-edit` | `renezander030/capcut-cli`，[skills.sh 页面](https://www.skills.sh/renezander030/capcut-cli/capcut-edit) | 直接读写 CapCut/JianYing 本地草稿：字幕、时间、速度、音量、模板、切片 | 可选外部工具，不作为本技能运行时依赖。MIT，GitHub 仓库 2026-11-14 可读，默认分支 `master`，README 标注 v0.33.0。吸收其“关闭工程再写、`.bak` 加滚动历史快照、写后视觉验收、输出不静默覆盖”的约束。 |
| `jianying-video-compose` | 社区技能（ClawHub，作者发布），[ClawHub 页面](https://clawhub.ai/2719040953/jianying-video-compose) | 通过剪映代理 API 创建草稿、上传素材、云渲染 | 不采用。依赖第三方 HTTP 服务 `np-newsmgr-uat.eastmoney.com` 与 OSS 上传，素材离开本机，且服务可用性、授权和数据处理边界无法由本技能保证。 |

`capcut-edit` 只有在用户明确同意安装后才使用：

```bash
npx skills add renezander030/capcut-cli --skill capcut-edit
```

安装前必须核对版本：其 README 记录 **≤ 0.17.0** 存在本地命令/滤镜注入与凭据输出类问题，
**0.18.0 / 0.17.1** 已修复。低于修复版本不要使用，也不要把旧版本接进本技能链路。

本技能的 `scripts/` 不调用它。两者同时改一份草稿会产生冲突；同一工程同一时间只用一个写入口。

## 本地参考仓库

| 目录 | 实际定位 | 采用方式 |
|---|---|---|
| `__repros/jianying-1` | Windows 11.8 的明文草稿 + native bridge 导出链路，含 build/inspect/patch/publish 与 ffprobe 验收 | **主实现来源**，复制后补充安全覆盖保护、字幕工具、自测与来源说明 |
| `__repros/jianying-2` | 只读草稿盘点、媒体探测、SRT 生成/规范化/校验、硬字幕烧录 | **字幕与清单辅助来源**，收进 `scripts/subtitles/`；不做语音识别，不替代剪映原生时间线 |
| `jianying-headless-windows` | Apple Silicon macOS 的 11.5 无界面管线，核心项目与 Skill 分离安装；导出依赖固定版本/哈希白名单 | 不调用。Windows 11.8 会在安装发现阶段被版本白名单拒绝，不能改白名单绕过 |
| `jianying-agent-cli` | 官方风格 `jy` CLI，macOS 上走剪映引擎；Windows 适配不完整 | 不调用其 render/preflight。参考其草稿字段形状；Windows 的 `jianying_commands` 依赖 `/bin/ps`，进程存活判断也与非 Windows 语义不同 |

## 本机复核

2026-11-14 只读执行 `python scripts/jy.py probe`：

- 安装：`%LOCALAPPDATA%\JianyingPro\Apps\11.8.0.14778`
- 草稿根：`%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft`
- `root_meta_info.json` 存在；ffmpeg/ffprobe 位于剪映安装目录
- 首次探测时 native bridge 描述文件存在但 health 连接被拒；随后启动剪映，bridge 恢复为 11.8.0
- `probe` 未输出 token、cookie 或账号标识

2026-11-14 14:57 现场验收（临时多轨草稿，未触碰用户草稿）：

- `build`：640×360、2.5s，视频+图片画中画+音频+文字轨
- `render`：968,020B、2.507s、H.264+AAC；`draft_mutated:false`，导出前备份已生成
- `verify`：三帧 `0.2/1.2/2.2s`；目视确认字幕与图片叠加出现

因此本次交付能证明：安装版本、草稿根、ffmpeg、离线测试和一次真实原生导出；不能证明：其他剪映版本、会员素材、云端模板和未实现的 GUI 能力。

## 为什么不用纯 JSON 编辑覆盖一切

`draft_info.json` 只能说明结构存在，不能证明剪映渲染出预期画面。转场、滤镜、文字动画、会员素材和加密草稿都有独立的失败模式。任何写操作都要以 `inspect`、ffprobe 和抽帧为证据，不能拿“JSON 合法”代替“画面正确”。

## 商标与授权

`剪映`、`JianyingPro`、`CapCut` 是字节跳动相关主体的商标。本项目为独立的本地自动化技能，与字节跳动无隶属、赞助或背书关系。素材、字体、模板和会员能力分别受其授权约束；本技能不下载、破解或绕过任何会员资源。
