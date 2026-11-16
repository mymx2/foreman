# 剪映明文草稿结构（11.8 实测）

本技能只写**明文** `draft_info.json`。剪映重存后可能把时间线迁到 `Timelines/<uuid>/` 或加密；
遇到这两种情况，`inspect` 能读结构，`patch` 和 `version` 支持主时间线，`render` 会明确报错
（桥接只接受单时间线根布局），不猜。

## 目录布局

单时间线（本技能生成）：

```
<draft>/
├── draft_info.json        # 时间线 + 素材清单（核心）
├── draft_meta_info.json   # 首页元信息
├── draft_cover.jpg        # 封面，可无
└── .jianying-skill.json   # 本技能标记，--force 只覆盖带标记的目录
```

剪映自己保存后可能变成：

```
<draft>/
├── draft_meta_info.json
├── Timelines/
│   ├── project.json
│   └── <timeline-id>/draft_info.json
```

多时间线布局下 `resolve_draft_info` 会优先读 `project.json` 的 `main_timeline_id`，
找不到再取最近修改的 timeline。`render` 的桥接接口只接受根目录 `draft_info.json`，
因此原生导出目前只支持单时间线布局。

## draft_info.json 顶层

```json
{
  "canvas_config": {"width": 1920, "height": 1080, "ratio": "original", "background": null},
  "fps": 30.0,
  "duration": 4000000,
  "id": "UUID",
  "name": "草稿名",
  "path": "D:\\...\\draft",
  "create_time": 1794582629,
  "update_time": 1794582629,
  "new_version": "75.0.0",
  "materials": {...},
  "tracks": [...]
}
```

`duration` 与所有 `timerange` 都是**微秒**。`create_time` / `update_time` 是**秒**（11.x 实测）。

## tracks

```json
{
  "id": "UUID",
  "type": "video" | "audio" | "text" | "filter" | "sticker" | "effect",
  "flag": 0 | 2,
  "attribute": 0,
  "name": "",
  "is_default_name": true,
  "segments": [segment...]
}
```

- 第一条视频/图片轨 `flag: 0`，后续 `flag: 2`。
- 文字轨 `type: "text"`，字幕素材 `type: "text"`，两者都不要写 `subtitle`。
- 音频轨 `type: "audio"`。

## segment

```json
{
  "id": "UUID",
  "material_id": "素材 id",
  "target_timerange": {"start": 0, "duration": 4000000},
  "source_timerange": {"start": 0, "duration": 4000000},
  "speed": 1.0,
  "volume": 1.0,
  "render_index": 0,
  "track_render_index": 0,
  "extra_material_refs": [],
  "clip": {
    "alpha": 1.0,
    "rotation": 0.0,
    "scale": {"x": 1.0, "y": 1.0},
    "transform": {"x": 0.0, "y": 0.0},
    "flip": {"horizontal": false, "vertical": false}
  },
  "common_keyframes": [...]
}
```

主轨 `render_index: 0`；画中画从 1 递增。文字用 15000 段位，滤镜用 10000。
`clip.transform` 的 y 轴**向上为正**。

## 输入校验

`build` 与 `patch` 走同款区间/取值校验，非法值直接返回 `code="VALIDATION"`，`details` 带 `field`
与原值，不会写出半截草稿：

- 画布宽、高与 `fps` 必须 > 0；
- `opacity` ∈ [0, 1]，`scale` > 0，`rotation` 为有限值；
- `trim` / `set_speed` 不得让源区间越过素材时长；
- 会把所有片段删空的 ops 草稿会被拒（`reason=empty_draft`）。

## 视频 / 图片素材

```json
{
  "id": "UUID",
  "type": "video" | "photo",
  "path": "绝对路径",
  "duration": 4000000,
  "width": 1920,
  "height": 1080,
  "material_name": "文件名",
  "has_audio": true
}
```

图片用 `type: "photo"`，`duration` 是展示时长。图片作为画中画时，所在轨道必须 `flag: 2`，
segment 的 `render_index` 必须 ≥ 1，否则画面不出现。

## 文字素材

```json
{
  "id": "UUID",
  "type": "text",
  "content": "{\"text\":\"...\",\"styles\":[{\"range\":[0,4],\"size\":14,\"fill\":{...},\"strokes\":[...]}]}",
  "base_content": "同上",
  "text_color": "#FFFFFF",
  "font_size": 14.0,
  "border_color": "#000000",
  "border_width": 0.08,
  "alignment": 1,
  "line_spacing": 0.02,
  "letter_spacing": 0.0,
  "font_path": "",
  "font_name": "",
  "font_id": ""
}
```

`content` 是**字符串化 JSON**，不是对象。`range` 按 UTF-16 码元计数。改字时必须同步
`content` 与 `base_content`，并把 `range` 重算到新文本长度。

## 音频素材

```json
{
  "id": "UUID",
  "type": "extract_music",
  "name": "bgm",
  "duration": 4000000,
  "path": "绝对路径",
  "category_name": "local",
  "music_id": "",
  "resource_id": "",
  "local_material_id": "",
  "similiar_music_info": {},
  "tts_benefit_info": {"benefit_type": "none"}
}
```

`extra_material_refs: []` 即可。音频轨不需要 beat 信息也能导出。

## 关键帧

在 `segment.common_keyframes[]`：

```json
{
  "id": "UUID",
  "material_id": "",
  "property_type": "KFTypeScaleX",
  "keyframe_list": [
    {"id": "UUID", "time_offset": 0, "left_control": {"x":0,"y":0},
     "right_control": {"x":0,"y":0}, "values": [1.0]}
  ]
}
```

常用 `property_type`：`KFTypeScaleX`、`KFTypeScaleY`、`KFTypePositionX`、`KFTypePositionY`、
`KFTypeAlpha`、`KFTypeRotation`、`KFTypeVolume`。时间相对片段起点。

## 首页登记（root_meta_info.json）

草稿根：

```
C:\Users\<user>\AppData\Local\JianyingPro\User Data\Projects\com.lveditor.draft
```

索引结构：

```json
{"all_draft_store": [entry...], "draft_ids": 1, "root_path": "..."}
```

条目共 38 个键，模板在 `scripts/jylib/index.py` 的 `ENTRY_TEMPLATE`。关键字段：

| 字段 | 值 |
|---|---|
| `draft_fold_path` | 草稿目录绝对路径 |
| `draft_json_file` | `draft_info.json` 绝对路径 |
| `draft_root_path` | 草稿根 |
| `draft_id` | 与 `draft_info.id` 一致 |
| `draft_name` | 首页显示名 |
| `draft_cover` | 封面绝对路径；无封面空串（首页索引口径，见下） |
| `tm_draft_create` / `tm_draft_modified` | 微秒 |
| `tm_duration` | 微秒 |
| `draft_timeline_materials_size` | 素材字节数估算 |
| `draft_ids`（顶层） | 整数，写入后取 `max(旧值, 条目数) + 1` |

封面的两种口径不要混：草稿目录里 `draft_meta_info.json` 的 `draft_cover` 是**草稿目录内的文件名**
（如 `draft_cover.jpg`，无封面为空串）；首页索引 `root_meta_info.json` 条目的 `draft_cover` 是**绝对路径**。
`build` 生成的封面文件落在草稿目录内，写索引时由 `index.py` 转成绝对路径。

写索引前会备份到 `<草稿根>/.jianying-backups/root_meta_info.<时间戳>.json`，
写临时文件后 `os.replace`，再回读确认条目存在。

`build --force` 覆盖前，把旧草稿目录**整体移动**到 `<out>` 同级的
`.jianying-backups-<name>-<时间戳>/`（不先删除，非本技能生成的目录一律拒绝）；
`patch --in-place` 改稿前，把 `draft_info.json` 与 `draft_meta_info.json` 备份到草稿目录的
`.jianying-backups\`（唯一后缀）。

## 渲染时剪映会补什么

原生导出成功后，草稿目录会多出 `draft_content.json`、`common_attachment/`、
`attachment_editing.json`、`draft.extra`。这些是剪映运行时产物，不需要预置，也不要当成源文件改。
