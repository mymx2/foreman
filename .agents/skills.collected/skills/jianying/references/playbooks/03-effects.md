# 特效 Playbook

读此文件时，目标是给时间线加**视觉风格与动态**：转场、滤镜、画面特效、色轮、曲线变速。
本域最容易被“结构写入成功”误导成“效果生效”，所以每条都写清验收方式。

## 1. 转场

`segments[].transition`：

```json
{"resource_id": "123456789", "name": "叠化", "duration": 0.5, "path": ""}
```

- 写在**相邻片段**的其中一个上；
- 资源必须已缓存到 `Cache/effect`；
- 未缓存时剪映可能静默忽略，或导出报 `film_export_dependency_missing`；
- 抽帧看转场中段，不能只看首尾。

## 2. 滤镜

`filters` 是顶层数组，作用于整条时间线：

```json
"filters": [
  {"resource_id": "123456789", "name": "冷蓝", "value": 0.8, "start": 0, "duration": 5}
]
```

- 写 `materials.effects[type=filter]`；
- `value` 0..1；
- 资源需缓存；结构写入≠画面生效，导出抽帧对比原片。

## 3. 画面特效轨

```json
{"type": "effect", "segments": [{
  "resource_id": "555", "name": "星火", "path": "C:/cache/effect/555",
  "start": 0, "duration": 3, "value": 0.8,
  "adjust_params": {"intensity": 0.5}
}]}
```

- 独立 effect 轨，`render_index=11000`；
- 材质写 `materials.video_effects`；
- **不要**把特效绑到视频片段 `extra_material_refs`，会叠成黑层；
- 效果包必须已缓存；像素未验收时按 `conditional` 说明。

## 4. 色轮

```json
"color_wheel": {"segment": "gamma", "red": 0.1, "green": -0.2,
                "blue": 0.3, "hsl": true}
```

- `segment` 只能是 `gamma` / `lift` / `gain` / `offset`；
- 值 -1..1；写 `materials.primary_color_wheels`；
- `hsl:true` 时同时写 `materials.hsl` 伴随材质（HSL 本身未生效，见下）；
- 2026-11-15 真机 `gamma red=0.5` 导出抽帧与无调色帧一致，11.8 未观察到像素变化；不要承诺色轮效果；
  证据在 [`evidence/2026-11-15-real-probes/wheel/`](../evidence/2026-11-15-real-probes/wheel/)。

## 5. 曲线变速

```json
"curve_speed": {
  "name": "先慢后快",
  "points": [{"x":0,"y":1},{"x":0.5,"y":0.5},{"x":1,"y":2}]
}
```

- `points` 至少 2 点；`x` 0..1 单调不减；`y` 为正；
- 写 `materials.speeds` 的 `{type:"speed", mode:1, speed:avg, curve_speed:{...}}`；
- 片段 `speed` 会被曲线平均速度覆盖；
- 曲线像素未抽帧，导出后看速度变化。

## 6. 调色：当前边界

| 能力 | 状态 | 做法 |
|---|---|---|
| 基础调色 `adjust` | `planned` | plan 里出现直接 `VALIDATION`；用剪映客户端 |
| HSL `hsl` | `unverified` | 结构已写，真实导出首测未见像素变化；不要承诺 |
| 色轮 `color_wheel` | `unverified` | 结构已写；2026-11-15 真机 gamma red=0.5 抽帧与无调色帧一致，不要承诺 |
| 色彩匹配 `color_match` | 未接线 | 官方 XML 有；native 未映射；不要写 |

调色正确路径：11.8 native 色轮/HSL 均未观察到像素变化；需要精确亮度/对比度/HSL 时，让用户在剪映客户端调，
或把真实草稿字段通过 `native` 逃生舱带入并自行回读验收。

## 7. 资源预检

```bash
python scripts/capability_probe.py --list
```

看 `Cache/effect` / `Cache/artistEffect` 计数。计数 > 0 只证明有缓存，不证明资源 id 匹配、账号有权益、
导出会应用。资源缺失时案例 `SKIP`，不要伪造 id。

## 8. 验收

1. 结构：`inspect` 看 `materials.effects` / `video_effects` / `primary_color_wheels` 计数；
2. `render` 成功；
3. 抽帧：转场中段、滤镜前后对比、特效出现处、色轮前后对比；
4. 曲线变速看时长与动作节奏；
5. 任何静默忽略的效果，按 [limits](../limits.md) 降级，不重复轰炸导出。

## 9. 案例

- `examples/12-advanced-fields.py`：色轮/曲线/特效结构；
- `examples/16-transition-filter-effect.py`：转场 + 滤镜 + 画面特效 + 色轮；
- `examples/13-multitrack-pip.py`：曲线变速 + 蒙版。
