# 未验证能力：现状、证据与解锁条件

`capabilities.md` 里仍标 `planned`/`unverified`，或带 `conditional` 条件（资源/账号/界面导出）的条目，不是「没写代码」，而是
**代码结构写进去了、但真实导出没有确认生效**。这里逐项记录证据和阻塞点，
避免下次重复猜。

## 0. 2026-11-18 真机环境

- 剪映 `11.8.0.14778` 在虚拟桌面启动，native bridge 存在（`infinite-canvas-native-bridge.json`，端口 63225）。
- 能读到登录 uid，`render` 真实导出成功；`11.8` 会在导出期间回写草稿，技能会保留导出前备份。
- 资源缓存：299 包 / 6472 条 / 已缓存 271；原 `flower2` 与 `bubble` 缓存为 0。
  本轮为验证 `text.effect` 单独把 `7127669365423508767` 花字包复制进 `artistEffect`，
  另有 718/735 两个测试包；它们不是用户原有资源，清理前需确认未被引用。

## 1. 本轮新增结论（2026-11-18）

一段 15 秒草稿里同时放倒放、曲线变速、绿幕、HSL，导出后按帧测量：

| 能力 | 实测 | 结论 |
|---|---|---|
| `speed.curve` | 曲线段白块 1s 0.203 / 2s 0.547，线性对照 0.172 / 0.328 | **生效**，已升为 `implemented` |
| `visual.reverse` | 倒放段 0.172 / 0.328，与正常完全一致；补 `reverse_path` 仍一致 | 仍被 11.8 忽略 |
| `visual.chroma` | 旧：bridge 导出角 `(0,254,0)`，补 `segment.enable_chroma=true` 仍是纯绿；2026-11-18 晚间重测：带 `materials.chromas` 的草稿在 UI 打开即蓝底红块，UI 导出 1s 角 `(0,0,254)`、中心 `(253,0,0)` | `conditional`（UI 出片，bridge 不应用） |
| `adjust.hsl` | 纯红帧 (252, 0, 0)；片段已有 `enable_hsl=true` | 仍无像素变化 |
| `text.effect` | DeepGlow 分别写 `text_glow` / `text_effect`，与无特效基线逐像素比较 `YAVG=0`、`YMAX=0` | 渲染侧未执行；官方要求 `flower`，DeepGlow 类型不符 |
| `text.template` | 免费字幕模板“粉黑”依赖 flower `7377285613952830730`；导出成功，抽帧却是白字黑边普通文字 | 缺花字依赖时模板视觉静默回落，不能只看 `render ok` |

证据与可复算脚本：仓库外证据归档（曲线/倒放/绿幕/HSL）
与 仓库外证据归档（文字特效、模板回落、依赖权益）。
本轮新增背景填充/混合/响度证据已移出仓库。

官方 11.8 选择协议（`editing-protocol/selection-skill/references/segment-text-sticker.md`）明确：

- `text_effect` 是普通 text/subtitle 的花字资源，ref 必填且必须绑定 `flower`，不能用 `text_template` 或普通视频特效替代。
- `text_glow_ref / text_glow_color / text_glow_range / text_glow_strength` 写在文字宿主属性上；
  官方 selection 文档写“仅 lyrics”，builder 文档又写 text/subtitle/lyrics，口径不一致；
  但都要求新增发光先取得真实 `text_glow` blueprint_ref。
- 协议里没有 `text_shape` 节点；11.8 的“气泡”在资源推荐表里是 `text_bubble` 文字模板（主候选 RID `7659366084470000920`），不是原生气泡材质。

## 2. 仍未验证

| 能力 | 状态 | 已有证据 | 阻塞点 | 解锁条件 |
|---|---|---|---|---|
| `adjust.basic` | planned | 2026-11-16 写 `materials.effects[type=adjust]` + `adjust_params`，抽帧无变化；2026-11-18 按 jianying-tool 写 `common_keyframes` `KFTypeBrightness` 仍无变化；plan 层直接拒绝 | 11.8 的真实字段名未知 | 手工在剪映调一次亮度/对比度并保存草稿，读 `draft_info.json` 对照 |
| `adjust.hsl` | unverified | 2026-11-18 真机导出无像素变化 | `materials.hsl` + `enable_hsl` 都在，渲染侧不执行 | 手工调 HSL 存草稿，或确认 11.8 是否移除了该能力 |
| `color.wheels` | unverified | 2026-11-15 `gamma red=0.5` 抽帧与无调色一致；2026-11-18 仍没有可用色轮缓存包 | 资源与字段可能都被忽略 | 缓存一个可用色轮资源 + 手工调一次存草稿 |
| `visual.reverse` | unverified | 两次真机导出（`reverse` 与 `reverse_path`）均无效 | 11.8 渲染侧忽略倒放字段 | 确认 11.8 是否移除倒放，或找新的原生字段 |
| `visual.freeze` | planned | 只做「抽帧图片 + 前后视频段」工作流 | 没写原生 freeze 结构 | 用同帧拆段 + `speed=0` 实现后真实导出抽帧 |
| `visual.chroma` | conditional | 2026-11-18 构建的草稿在 11.8 UI 打开即蓝底红块，`抠像` 面板读回“色度抠图”勾选、关键色绿色、强度 20；界面原生导出角点 `(0,0,254)`、中心 `(253,0,0)`。旧结论“取色器无法 UIA”是点错坐标，已推翻 | native bridge `draftPath` 仍与纯绿帧一致，`chromas` 不参与 headless 渲染 | 要绿幕成片走剪映界面导出；如需 bridge 出片，继续找 native 渲染入口 |
| `visual.beauty` | conditional | 2026-11-18 11.8 UI 读回 `磨皮=100` / `美白=100`；同草稿界面原生导出与 plain 对照：磨皮人脸 `avg_abs_rgb=1.215`、`changed_ratio=0.569`、边缘能量 `-6.2%`，美白皮肤 `RGB +7.1/+8.8/+9.2`；`makeup-root` 仅在美妆项存在时写入，修复后 `real-smooth2` 不再导致剪映退出 | native bridge `draftPath` 导出仍与 plain 帧 hash 相同；`shape`/`makeup` 单独导出均 409 `film_export_entitlement_denied`；`figure_algorithm` 目录为空 | 如需 bridge 出片，继续查 `figure` 是否缺 `blueprint_ref` / 导出开关；当前成片走剪映界面导出 |
| `visual.mix_mode` | conditional | 2026-11-18 11.8 UI 预览与 UI 原生导出为品红（界面导出样本已归档，仓库外，2026-11-18；0.3/1.0/1.7s 均 `(253,0,253)`）；同一结构 native bridge `draftPath` 导出仍纯红（`(253,0,0)`） | bridge 导出管线不应用 mix_mode，尚未找到 headless 入口 | 需要混合成片时用剪映界面导出；或找到 bridge 导出支持的 mix 字段 |
| `text.effect` | conditional | 2026-11-18 真实 flower 包 `7127669365423508767` 真机导出，与同文案无花字帧差 `YAVG=4.1713`/`YMAX=209`；带红字/绿描边/蓝阴影的 712 帧与默认 712 帧差 `0/0`，确认花字会重置文字颜色/描边/阴影（证据已移出仓库）；`7187739440347958589`、`7351316503771368713` 构建成功但 render 409 entitlement；优先级 `text_template` > `text_bubble` > `text_effect` | 部分花字包仍需账号权益；`712` 是否长期可用未确认 | 只对已缓存且账号可导出的真实 flower 包承诺；换资源前先看 `resource resolve` 与真机回执 |
| `text.bubble` | unverified | 材质桶已修正为 `materials.effects[type=text_shape]`；`capcut-mate` 实证 `effect_id=716434`、`resource_id=6821385652727190024` 必须分开给；官方 11.8 选择协议没有 `text_shape`，气泡走 `text_template`；`bubble` 缓存 0、面板免费数 0 | 本机没有真实气泡资源，11.8 原生路径也不是 text_shape | 用 `text_template` 的真实气泡模板验收，或用户手工加一次 |
| `text.template` | conditional | “粉黑”免费模板依赖 flower `7377285613952830730`，缺包导出成功但画面回落普通文字；`text_effects` 能读出模板 `effectStyle` 的 flower id | 缺真实 flower 包，模板视觉静默降级 | 缓存模板依赖的 flower 后复测抽帧 |
| `native.escape` | unverified | 结构原样写入（不校验语义，设计如此） | 「语义正确性」无法由技能保证 | 只能由真实导出验证；保持 unverified |

`text_glow` 不在独立能力行里，但结构已按 `capcut-mate` 的剪映实证修正：
`materials.effects[type="bloom"]`，`panel_id="text_glow"`，`value=0.0`，
`effect_id` 与 `resource_id` 分开，`bloom_params` 写颜色/方向/范围/强度，文字 `check_flag |= 64`，
不再写 `styles[0].effectStyle`，也不再和 `text_effect` 互斥。2026-11-18 用本机已缓存的
外发光 `7202576698775179837` / `9762443` 构建并导出，仍返回 409 entitlement；轮廓光同样
被权益拒绝，所以只有结构修正，没有像素证据，不能标为已支持。

另一个试过但不接线的能力：`capcut-mate` 的蒙版关键帧
（`KFTypeMaskPostionX/Y`、`KFTypeMaskSizeX/Y`、`KFTypeMaskRotation/Feather`）。
2026-11-18 用它给出的通道构建了一个 4 秒圆蒙版草稿，`common_keyframes` 已落盘，
但 11.8 导出 0.5s / 2.5s 两帧的蒙版位置和大小完全一致，说明渲染侧忽略这些通道；
不要把“结构写入”当成蒙版动画已支持。

## 3. 最快解锁方式

GitHub 上游项目的字段与做法见 [upstream](upstream.md) 的「GitHub 项目复核」；
可以借鉴模板模式、`common_keyframes` 和原生编解码思路，但它们的“已支持”不能直接当 11.8 验收结论。

**手工做一个 30 秒草稿**，把目标效果都加上（调色、HSL、色轮、倒放、定格、
绿幕、花字、气泡各来一段），保存后：

```bash
python scripts/jy.py inspect <草稿目录> --json
```

技能就能读到 11.8 的真实字段。这比继续猜字段名快得多，也不消耗账号权益以外的东西。

## 4. 本轮已顺手确认的

- `subtitle.asr.local` / `subtitle.postprocess` / `subtitle.itn`：已真机跑通
  （TTS 合成音频，非真人录音），证据在
  证据已移出仓库。
- 本地 ASR 的 `quality` 分数（剪映质量打分器）已经能读到，但**分数含义未标定**，
  只写进回执，不做阈值拦截。
- 曲线变速的真实导出样本已归档，可直接复算，不需要再起剪映。
