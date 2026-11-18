# 合成 Playbook

读此文件时，目标是把多个画面/文字/贴纸**叠成一个镜头**：层级、蒙版、抠像、绿幕、文字模板、
气泡/花字、贴纸。每个效果都要区分“结构已写”和“真实导出已生效”。

## 1. 合成层级

| 层 | 放什么 | 关键字段 |
|---|---|---|
| 底层 | 主视频/背景图 | 第一条 visual 轨，`flag: 0` |
| 中层 | 画中画/蒙版素材 | 副 visual 轨，`flag: 2`，`render_index ≥ 1` |
| 文字层 | 标题/字幕/花字 | `type: "text"`，`render_index` 15000+ |
| 贴纸层 | 贴纸/装饰 | `type: "sticker"`，`render_index` 14000 |
| 特效层 | 画面特效 | `type: "effect"`，`render_index` 11000 |

贴纸/特效/文字轨由 `build` 自动分配 `render_index`，不要手写冲突值。

## 2. 形状蒙版

```json
"mask": {
  "resource_type": "circle",
  "name": "圆形",
  "resource_id": "82432977",
  "path": "C:/cache/effect/82432977/<package>",
  "config": {"center_x": 0.5, "center_y": 0.5,
             "width": 0.5, "height": 0.5, "feather": 0.1}
}
```

- 写入 `materials.common_mask`，单材质 `id` 进 `extra_material_refs`；`constant_material_id` 留空，避免悬空引用
- 片段的 `text_config.align_type=15`；
- **资源必须已缓存**；`resource_id` 不能是 `abc` 这类占位；
- 2026-11-15 真机 `82432977(circle)` + 上述 config 导出抽帧已确认中央椭圆可见；`config` 为空/字段不全会全黑或只显示一角，
  `build` 会给 warning（证据已移出仓库）。像素验收仍以导出抽帧为准。

## 3. 智能抠像（matting）

```json
"matting": {
  "path": "C:/cache/matting/<剪映生成的逐帧蒙版目录>",
  "reverse": false,
  "feather": 0.1,
  "expansion": 0.02
}
```

- 写视频材质 `matting.path/mask_video_path/reverse/flag/feather/expansion`；
- 目录必须由剪映生成，外部不能凭空生成逐帧蒙版；
- 没有真实目录时**不要写**，否则导出可能黑层或忽略。

## 4. 绿幕（chroma）

```json
"chroma": {"color": "#00FF00FF", "intensity": 20,
           "shadow": 2, "edge_smooth": 1, "spill": 0}
```

- 写 `materials.chromas`（`type:"chroma"`、`version:"v2"`）并挂 refs；
- 百分比转 0..1；
- 2026-11-18 真机：构建的草稿在 11.8 界面打开即预览蓝底红块，`抠像` 面板读回“色度抠图”勾选、
  关键色绿色、强度 20；界面原生导出 1s 角点 `(0,0,254)`、中心 `(253,0,0)`，确认抠绿生效。
- **限制**：native bridge `draftPath` 仍不应用 `chromas`，`jy.py render` 会得到绿幕；
  成片必须走剪映界面导出。
- 人工取色参考坐标：真正吸管按钮中心 `(1575,283)`（旧坐标 `(1606,265)` 落在按钮外），
  仅作验收/排查记录；**技能不内置 GUI 自动化**，也不把界面点击作为交付流程。
- 状态 `conditional`：结构可写、UI 可出片，但不要承诺 `render` 已支持。
  技能交付到“正确草稿”，绿幕成片由用户在剪映界面导出。

## 5. 文字模板

```json
"text_template": {
  "resource_id": "987654",
  "name": "划重点",
  "path": "C:/cache/template/987654",
  "resources": [{"panel": "text", "resource_id": "111", "path": "C:/cache/panel"}]
}
```

- 片段 `material_id` 改成模板 id，文字材质进 `extra_material_refs`，`render_index=14001`；
- `resources[].panel` 只能是 `default/sticker/fonts/text`；
- 模板包与槽位资源必须已缓存；像素未验收。

## 6. 花字/气泡/发光

```json
"text_effect": {"resource_id": "7127669365423508767", "effect_id": "7127669365423508767"},
"text_bubble": {"resource_id": "6821385652727190024", "effect_id": "716434"},
"text_glow": {"resource_id": "7202576698775179837", "effect_id": "9762443",
              "bloom_params": {"color": "#FFFFFF", "dir_x": 0.5, "dir_y": 0.5,
                               "range": 0.2, "strength": 0.3}}
```

- `text_effect` 写 `materials.effects[type=text_effect]`，并写文字 `content.styles[0].effectStyle={id,path}`；官方 11.8 要求 ref 绑定 `flower`，`DeepGlow`（`tool_text_glow`）不匹配。2026-11-18 真实 flower 包 `7127669365423508767` 真机导出，与无花字帧差 `YAVG=4.1713`/`YMAX=209`；718/735 均 409，必须用已缓存且账号可导出的真实花字。
- 花字接管外观时会把文字颜色/描边/阴影重置为白字、无描边、无阴影；2026-11-18 带红字/绿描边/蓝阴影的 712 导出帧与默认 712 帧差 `0/0`，确认这个行为，不要再叠加自定义字色/描边/阴影。背景和 `text_glow` 不重置。
- 优先级按剪映实证：`text_template` > `text_bubble` > `text_effect`。模板存在时气泡/花字被忽略；没有模板时气泡存在则花字被忽略；同时写不会叠加。
- `text_bubble` 写 `materials.effects[type=text_shape]`；`effect_id` 与 `resource_id` 不是同一个值（例 `716434` / `6821385652727190024`），两者都要给；它只加装饰底板，不改文字填充/描边/阴影。官方 11.8 选择协议没有 `text_shape`，气泡模板走 `text_template`，此字段只兼容旧草稿，未验收。
- `text_glow` 写 `materials.effects[type=bloom]`，`panel_id="text_glow"`、`value=0.0`，文字 `check_flag |= 64`；`effect_id`/`resource_id` 分开，`bloom_params` 写颜色/方向/范围/强度；不要再写 `effectStyle`，可以和 `text_effect` 叠加。本机外发光/轮廓光均 409 entitlement，尚无像素证据。
- 没有真实缓存 id 不要写占位；否则可能静默忽略或 409。2026-11-18 实测：免费字幕模板“粉黑”依赖 flower 但缺包，导出成功却回落成普通白字。

## 6.1 背景填充与混合模式

```json
"background_fill": {"type": "color", "color": "#0000FFFF"},
"mix_mode": "滤色"
```

- `background_fill` 写 `materials.canvases`（`canvas_color` / `canvas_blur`）并挂 refs；只对第 0 条视觉轨（最底层）生效，非底层会 warning。2026-11-18 真机：纯色填充角落 `(0,0,254)`；渐变图模糊填充角落 `(242,0,9)`、边缘 `(101,0,152)`，确认不是默认黑底。
- `mix_mode` 写 `materials.effects[type=mix_mode]` 并挂 refs；内置 10 种名称，也可给 `{name,effect_id,resource_id}`。11.8 界面预览/UI 原生导出为品红，但 native bridge `draftPath` 导出仍纯红；技能保持 `conditional`，`render` 会 warning。需要混合成片请在剪映界面导出。

## 6.2 美颜/美型/美妆/美体

```json
"beauty": {
  "skin": {"smooth": 100, "whitening": 50},
  "shape": {"small_face": 60},
  "makeup": {"look": "淡人妆", "intensity": 80},
  "body": {"slim_body": 40}
}
```

- 写 `materials.effects[type=figure]`，挂到视频/图片片段；不是独立 effect 轨；只有包含美妆项时才追加一个 `makeup-root`，单磨皮/单美白不要带；
- 强度按剪映滑杆 0..100 输入，写入时按 100 归一；0 值不写；`width/chin_length/wide_shoulder` 必须为 0；
- 2026-11-18 11.8 UI 实测：`real-smooth2` 打开后右侧 `美颜美体` 读回 `磨皮=100`，同草稿 plain 对照的界面原生导出人脸 `avg_abs_rgb=1.215`、边缘能量 `-6.2%`；`real-whiten` 读回 `美白=100`，导出皮肤 `RGB +7.09/+8.83/+9.15`；
- native bridge `draftPath` 仍不应用 `figure`，与 plain 帧 hash 相同；`shape/makeup` 单独导出 409 entitlement；`figure_algorithm` 目录为空；
- 结构可用、UI 可出片；`jy.py render` 不承诺美颜，成片必须在剪映界面导出。`jy.py beauty list` 只列可用项，不替代权益校验。

## 7. 贴纸

```json
{"type": "sticker", "segments": [{
  "resource_id": "8c1d-uuid",
  "path": "C:/cache/sticker/8c1d-uuid",
  "start": 1, "duration": 3, "scale": 0.3, "x": 0.1, "y": -0.2
}]}
```

- 独立 sticker 轨，材质写 `materials.stickers`；
- 贴纸包必须已缓存；2026-11-15 真机用 `7675620818189077810` 构建成功，但 render 409
  `film_export_entitlement_denied`；另一个 `7202575978646737469` render 成功但抽帧未见贴纸；
  换免费/已授权且能看见的贴纸再抽帧（证据已移出仓库）；
- `scale` 不要超过 1.0 除非故意放大。

## 8. 合成验收

1. `inspect`：`materials.common_mask` / `stickers` / `text_templates` 计数与计划一致；
2. `render` 后抽帧：底层、画中画、蒙版边界、文字/贴纸层是否都在正确位置；
3. 蒙版/抠像/绿幕任务，抽帧要看**边缘**，不只看中心；
4. `chroma`/`beauty`/`mix_mode` 的验收帧必须取自**剪映界面导出**；`jy.py render` 的 bridge 帧
   不作为这三项生效的依据（否则会把绿幕/plain/纯红误判成失败）；
5. 花字/气泡/贴纸无真实资源时，案例应 `SKIP`，不能当 PASS；
6. 任何“结构写进去但画面没变”的效果，按 [limits](../limits.md) 降级说明。

## 9. 案例

- `examples/12-advanced-fields.py`：蒙版/色轮/`native` 结构；
- `examples/14-mask-title.py`：蒙版 + 文字模板 + 背景/阴影；
- `examples/15-text-effects.py`：花字/气泡/文字动画 + 贴纸；
- `examples/13-multitrack-pip.py`：多轨画中画 + 蒙版。
