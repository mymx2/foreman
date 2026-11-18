# 剪辑 Playbook

读此文件时，目标是把素材组织成可继续编辑的**多轨时间线**：顺序、层级、时长、变速、倒放、关键帧、
画中画、裁剪与 patch。调色/特效/字幕不是本域重点。

## 1. 先定时间线骨架

| 问题 | 决定 |
|---|---|
| 主轨是什么 | 第一条 `video`/`image` 轨；决定画布默认尺寸 |
| 画布比例 | 横屏 1920×1080；竖屏 1080×1920；方图 1080×1080 |
| 总时长 | 取最长片段；先 `ffprobe`，不靠文件名猜 |
| 层级 | `tracks` 顺序即层级，后写的 visual 轨在上层 |
| 是否需要画中画 | 需要时副 visual 轨自动 `flag: 2` + `render_index ≥ 1` |

最小骨架：

```json
{
  "schema": "jianying-plan/v1",
  "name": "剪辑骨架",
  "canvas": {"width": 1920, "height": 1080, "fps": 30},
  "tracks": [
    {"type": "video", "name": "主轨", "segments": [
      {"path": "media/main.mp4", "start": 0, "duration": 8}
    ]},
    {"type": "video", "name": "画中画", "segments": [
      {"path": "media/pip.mp4", "start": 2, "duration": 3,
       "scale": 0.35, "x": 0.55, "y": 0.45}
    ]}
  ]
}
```

## 2. 剪辑动作怎么表达

| 用户说法 | 计划写法 |
|---|---|
| 剪掉开头 | 同一素材 `source_start` + `start=0`，缩短 `duration` |
| 拼接 | 同一轨多个 segment，`start` 首尾相接 |
| 分割后删中间 | 两个 segment，第二个 `source_start` 跳过被删区间 |
| 慢动作 | `speed: 0.5`；`duration` 是时间线长度，源取 `duration*speed` |
| 快放 | `speed: 2`；源区间同样按 `duration*speed` |
| 倒放 | `reverse: true`；像素需导出抽帧确认 |
| 裁剪画面 | `crop: {"x":0.1,"y":0.2,"w":0.7,"h":0.6}`，归一化 |
| 翻转 | `flip: true` 或 `{"horizontal":true,"vertical":false}` |
| 定格 | 抽帧成图片 + 前后视频段，参考 `examples/06-freeze-workflow.py` |
| 改已有片段 | `patch --ops`，不要手改 `draft_info.json` |

时长/源区间规则：

- `duration` 是**时间线占用长度**，不是源素材长度；
- 视频 `duration * speed` 不能超过素材剩余长度，否则 `VALIDATION`；
- 图片固定 `speed=1`，写其他值会报错；
- 文字 `duration` 默认 2s，图片默认 3s。

## 3. 关键帧

`segments[].keyframes` 是通道到点数组的映射，时间相对片段起点：

```json
"keyframes": {
  "scale": [[0, 1.0], [1.2, 1.08], [3.0, 1.0]],
  "position_y": [[0, 0], [2.0, 0.12]],
  "opacity": [[0, 0], [0.4, 1]],
  "rotation": [[0, 0], [3, 8]]
}
```

可用通道：`scale`、`scale_x`、`scale_y`、`position_x`、`position_y`、`opacity`/`alpha`、
`rotation`、`volume`（音频）。点也可写 `{"time":1.2,"value":1.05}`。

**边界**：关键帧时间不能超过片段的目标时长；负时间直接 `VALIDATION`。变速片段按
`duration`（时间线长度）而不是源长度取边界。

## 4. 画中画与层级

- 副 visual 轨必须 `flag: 2`；`build` 自动处理。
- `render_index` 越大越靠上；不要手动写重复值。
- `scale` 0.3–0.4 常见；`x`/`y` 是归一化位移，`y` 正值向上。
- 画中画要加圆角/阴影时，用 `native` 写 `video_radius` / `video_shadows`（未验收，需抽帧）。

## 5. patch 已有草稿

```bash
python scripts/jy.py patch <draft> --ops ops.json --out <副本>
```

常用 op：

| op | 用途 |
|---|---|
| `rename` | 改草稿名 |
| `set_text` / `set_style` | 改文字内容/样式 |
| `set_volume` / `set_speed` | 音量/变速 |
| `shift` / `trim` | 起点/时长 |
| `set_transform` | x/y/scale/rotation/opacity |
| `remove` | 删片段（素材无引用时清理） |
| `set_canvas` / `fps` | 画布/帧率 |

默认写副本；`--in-place` 才改原稿，且先备份。输出不能落在源草稿内部。

### 5.1 模板、时间线交换与素材维护

```bash
python scripts/jy.py template save <draft> <片段id或下标> "标题" --out title.json
python scripts/jy.py template apply <draft> title.json 2.2 --text "新文案" --out <副本>
python scripts/jy.py otio export <draft> --out timeline.otio
python scripts/jy.py otio import timeline.otio --out plan.json
python scripts/jy.py relink <draft> --dir <素材目录> --out <副本>
python scripts/jy.py replace-media <draft> <片段> <新文件> --retime --out <副本>
python scripts/jy.py prune <draft> --out <副本>
```

- `template` 保存片段、主素材和全部 extra 材质，应用时重映射所有 id；文字模板可用 `--text` 改文案；
- `otio` 导出只含视频/图片/音频轨，文字/贴纸/特效轨在 `skipped` 里列明；导入生成 build 计划；
- `relink` 默认只补缺失文件；`replace-media --retime` 按新素材时长重算 speed；`prune` 只删无引用材质；
- 这些命令默认写副本，`--in-place` 才回写并备份。

## 6. 验收

1. `inspect`：`missing_media=[]`、`duration` 与计划一致、visual 轨数量正确；
2. `render`（如要成片）；`verify --frames` 抽 3 帧；
3. 看开头/中段/结尾：主轨、画中画、变速后的时长、倒放方向、裁剪边界；
4. patch 任务必须重新导出，不能只看 `ok:true`。

## 7. 常见坑

| 现象 | 原因 | 修法 |
|---|---|---|
| 画中画不显示 | 副轨没 `flag:2` 或 `render_index=0` | 用 `build`，不要手写轨道 |
| 视频报时长越界 | `duration*speed` 超过源剩余 | 缩短 `duration` 或加 `source_start` |
| 图片报变速非法 | 图片写了 `speed` | 删掉，图片固定 1 |
| 关键帧不生效 | 时间超过目标时长/通道写错 | 按 `duration` 重算，查通道名 |
| 拼接处黑帧 | 相邻 segment 有 gap | `start` 首尾相接，或补图片/黑场 |

## 8. 案例

- `examples/04-media-build.py`：真实媒体构建 + 封面；
- `examples/07-vertical-title-bgm.py`：竖屏 + 标题 + BGM；
- `examples/08-patch-copy.py`：patch 副本；
- `examples/13-multitrack-pip.py`：多轨画中画 + 关键帧 + 蒙版 + 变速；
- `examples/18-spoken-piece.py`：口播成片骨架。
