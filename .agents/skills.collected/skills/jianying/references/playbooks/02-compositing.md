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
  `build` 会给 warning（证据：[`evidence/2026-11-15-real-probes/mask/`](../evidence/2026-11-15-real-probes/mask/)）。像素验收仍以导出抽帧为准。

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
- **真实导出首测未抠绿**，状态 `unverified`。需要绿幕时优先在剪映客户端做，或把本字段当实验，
  导出后抽帧确认；不要对用户承诺“已支持绿幕抠像”。

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

## 6. 花字/气泡

```json
"text_effect": {"resource_id": "flower-1", "effect_id": "flower-e1", "path": "..."},
"text_bubble": {"resource_id": "bubble-1", "effect_id": "bubble-e1", "path": "..."}
```

- 写 `materials.filters[type=text_effect]` / `[type=text_shape]`，并挂 refs；
- 花字同时写文字 `content.styles[0].effectStyle={id,path}`；
- **必须使用真实缓存资源 id**，当前未渲染验收；没有真实 id 不要写，否则可能静默忽略。

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
  换免费/已授权且能看见的贴纸再抽帧（证据：[`evidence/2026-11-15-real-probes/sticker/`](../evidence/2026-11-15-real-probes/sticker/)）；
- `scale` 不要超过 1.0 除非故意放大。

## 8. 合成验收

1. `inspect`：`materials.common_mask` / `stickers` / `text_templates` 计数与计划一致；
2. `render` 后抽帧：底层、画中画、蒙版边界、文字/贴纸层是否都在正确位置；
3. 蒙版/抠像/绿幕任务，抽帧要看**边缘**，不只看中心；
4. 花字/气泡/贴纸无真实资源时，案例应 `SKIP`，不能当 PASS；
5. 任何“结构写进去但画面没变”的效果，按 [limits](../limits.md) 降级说明。

## 9. 案例

- `examples/12-advanced-fields.py`：蒙版/抠像/色轮/贴纸/特效结构；
- `examples/14-mask-title.py`：蒙版 + 文字模板 + 背景/阴影；
- `examples/15-text-effects.py`：花字/气泡/文字动画 + 贴纸；
- `examples/13-multitrack-pip.py`：多轨画中画 + 蒙版。
