# 计划文件 schema（jianying-plan/v1）

`build` 读取的计划是一个 JSON 对象。所有时间单位都是**秒**（小数可），脚本内部转微秒。
相对路径以**计划文件所在目录**为基准，不按命令行当前目录。

## 最小可用计划

```json
{
  "schema": "jianying-plan/v1",
  "name": "我的第一条草稿",
  "canvas": {"width": 1920, "height": 1080, "fps": 30},
  "tracks": [
    {
      "type": "video",
      "name": "主轨",
      "segments": [{"path": "media/main.mp4", "start": 0, "duration": 5}]
    },
    {
      "type": "text",
      "name": "字幕",
      "segments": [
        {"text": "第一句", "start": 0.2, "duration": 2, "font_size": 8, "y": -0.72}
      ]
    }
  ]
}
```

`name`、`canvas` 可省略：`name` 默认 `jianying-draft`，画布默认取第一条视频的尺寸，帧率默认 30。

## 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema` | string | 固定 `jianying-plan/v1`；不校验，但建议写 |
| `name` | string | 草稿名，进入剪映首页的显示名 |
| `canvas.width` / `canvas.height` | int | 画布像素；竖屏用 1080×1920 |
| `canvas.fps` | number | 时间线帧率，默认 30 |
| `tracks` | array | 轨道数组，顺序即层级：先写的在下面（主轨优先） |
| `filters` | array | 实验性。滤镜规格，见下文 |

## 轨道

| `type` | 放入什么 | 行为 |
|---|---|---|
| `video` | 视频；也允许图片（按图片处理） | 第一条 `video` 轨是主轨，`flag: 0`；后续 `flag: 2` + 独立 `render_index`，否则不显示 |
| `image` | 只放图片 | 作为画中画/贴图层；`duration` 默认 3s（须为正数）；`scale`、`transform` 控制位置与大小；图片固定 `speed=1`，写其他值会报 `VALIDATION` |
| `audio` | 音频（m4a/mp3/wav…） | 独立音频轨；`volume` 0..10，默认 1 |
| `text` | 文字、字幕 | 每条字幕一个 segment；同轨可放多段，按时间切换 |
| `sticker` | 贴纸 | 独立 sticker 轨；`resource_id` + `path` 指向已缓存贴纸包，`scale`/`x`/`y` 控制大小与位置 |
| `effect` | 画面特效 | 独立 effect 轨；`resource_id`、`path`、`value`、`adjust_params`；效果包必须已缓存 |

`video` 与 `image` 轨的先后决定 `render_index`，数字越大越靠上层。图片放主轨（第一条 visual 轨）会被当成整屏背景。

## Segment 公共字段

| 字段 | 默认 | 说明 |
|---|---|---|
| `start` | 0 | 在时间线上的起点（秒） |
| `duration` | 视频=素材长度；图片=3；文字=2 | 在时间线上占用的长度 |
| `source_start` | 0 | 从素材第几秒开始取 |
| `speed` | 1 | **仅视频片段**（`video` 轨里的视频素材）；`2` 表示两倍速，源区间自动按 `duration*speed` 截取。图片片段（含 `video` 轨里的图片）固定 `speed=1`，写其他值报 `VALIDATION` |
| `volume` | 1 | 0..10；0 为静音 |
| `channel` | 0 | 仅音频片段；整数 `0` 保持原声道 / `1` 左声道复制到双声道 / `2` 右声道复制到双声道；写 `materials.sound_channel_mappings[].audio_channel_mapping` + `is_config_open`。2026-11-16 左only 源实测：`0` 左 -11.0dB/右静音，`1` 左右 -11.0dB，`2` 双声道静音（复制源右声道，源右本身静音） |
| `audio_fade` | — | 仅音频片段；`{"in":0.5,"out":1.0}` 秒，写 `materials.audio_fades`（微秒）；`in+out` 不得超过片段时长。独立音频轨真实导出已验证；视频原声未验证 |
| `audio_effect` | — | 仅音频片段；`{"resource_ref":"萝莉","category_id":"tone","params":{"音调":0.75,"音色":0.6}}`，写 `materials.audio_effects`（`path`、`sub_type`、带索引的 `audio_adjust_params`）；免费“萝莉”已真机 440→740Hz，其他资源仍需听感验收 |
| `scale` | 1 | 数字，或 `{"x":..,"y":..}`；0.5 = 半屏 |
| `x` / `y` | 0 | 归一化位移。**y 正值向上，负值向下**；字幕放底部用 `y: -0.7` 左右 |
| `transform` | — | `{"x":..,"y":..}`，与 `x`/`y` 等价 |
| `rotation` | 0 | 角度 |
| `opacity` | 1 | 0..1 |
| `font_path` | 空 | 文字专用；空 = 剪映默认字体。一般不要填 macOS 路径 |
| `resource_ref` | — | 任意资源 spec 的快捷引用：填资源 ID、md5 或完整标题；`build` 自动解析成 `resource_id`/`path`/`name`/`effect_id`，字体解析成 `font_path`。短标题不会模糊猜，先 `resource resolve` 拿 id/完整标题。未缓存时加 `--fetch-resources` 自动下载免费资源；会员/商业仍失败 |

视频段超出素材可用长度会直接报 `VALIDATION`，不会静默截断。
拼错的片段字段（如 `adjusts`、`freezes`）不会被读取，但会进 `warnings` 明确提示；不要把它当成已生效。

`resource_ref` 可以写在 `text_effect`、`text_template`、`sticker`、`effect`、`transition`、`filters[]`、`mask` 等资源 spec 里，例如
`{"text_effect":{"resource_ref":"<完整 flower 花字标题或 ID>"}}` 或文字片段直接写 `{"resource_ref":"毛笔行楷"}`。
不要拿 `DeepGlow` 当花字：它是 `tool_text_glow`，官方要求 `text_effect` 绑定 `flower`。
`build` 会先解析资源再校验；资源未缓存时默认 `RESOURCE_NOT_CACHED`，加 `--fetch-resources` 才会自动下载
免费非商业资源。字体自动映射到 `font_path`；模板槽位仍需显式 `resources`。

## 文字样式

| 字段 | 默认 | 说明 |
|---|---|---|
| `text` | 必填 | 文本内容，不能为空 |
| `font_size` | 14 | 剪映字号；1080p 字幕常用 7–9，标题 12–16 |
| `color` | `#FFFFFF` | 填充色，`#RRGGBB` |
| `stroke_color` | `#000000` | 描边色 |
| `stroke_width` | 0 | 0 = 无描边；常用 0.04–0.08 |
| `align` | `center` | `left` / `center` / `right` |
| `line_spacing` | 0.02 | 行距 |
| `letter_spacing` | 0 | 字距 |
| `bold` | false | 粗体；写 `bold_width=0.1` |
| `italic` | false | 斜体；写 `italic_degree=1` |
| `underline` | false | 下划线 |
| `background` | — | `{"color":"#112233","alpha":0.6,"round_radius":0.2,"width":0.5,"height":0.2,"horizontal_offset":0,"vertical_offset":0}`；写 `background_*` 并置 `check_flag |= 16` |
| `shadow` | — | `{"color":"#000000","alpha":0.5,"distance":4,"diffuse":12,"angle":-30}`；写 `content.styles[0].shadows` 与 `shadow_*`，置 `check_flag |= 32` |
| `highlight` | — | `{"words":["AI","工具"],"color":"#FFD400","bold":true}`；按词匹配追加 `content.styles` range；本地规则，不是剪映 AI 划重点 |

文字素材在草稿里必须是 `type: "text"`。写成 `subtitle` 会被剪映当成 AI 字幕，导出返回 409 `film_export_entitlement_denied`——这是本技能最贵的坑。

文字片段还支持：

- `animations`：文字/视频/图片都支持；`[{"type":"in","resource_ref":"翻入","duration":1.17}]`，`type` 只能是 `in` / `out` / `loop`；文字写 `material_animations`，视频/图片写 `material_animations[type=video_animation]`，动画资源必须已缓存。2026-11-16 免费“变色输入”/“翻入”已真实导出验证。
- `text_template`：`{"resource_id":"987654","name":"划重点","path":"…","resources":[{"panel":"text","resource_id":"111","path":"…"}]}`；片段的 `material_id` 会改成模板 id，文字材质进 `extra_material_refs`。
- `caption_template` / `subtitle_template`：`{"resource_ref":"白字黑边","resources":[]}`；写入文字材质的 `caption_template_info` 和 `recognize_text`（不是单独模板材质）。2026-11-16 用免费“白字黑边”真实导出确认 cue 文本能进模板。片段的 `caption_info` 单独写到 `segment.caption_info`；`text_template` 在模板目录有可读 `content.json` 时，会把 `caption_info` 派生成 `caption_duration_info` 注入模板槽位。
- `text_effect`：`{"resource_id":"…","effect_id":"…","name":"…","path":"…"}`；写入 `materials.effects[type=text_effect]`，并把文字 `content.styles[0].effectStyle` 指向它；同时把文字颜色/描边/阴影重置为白字、无描边、无阴影（`capcut-mate` 的剪映实证，2026-11-18 真机帧与默认 712 帧差 `YAVG=0`/`YMAX=0` 确认）。官方 11.8 要求 ref 绑定 `flower`，`DeepGlow` 属 `tool_text_glow` 不匹配。2026-11-18 用真实 flower 包 `7127669365423508767` 真机导出，与无花字对照帧差 `YAVG=4.1713`/`YMAX=209`；718/735 均 409，所以只对已缓存且账号可导出的 flower 资源承诺。`text_template` 生效时 `text_effect` 被忽略；`text_bubble` 生效时 `text_effect` 被忽略。
- `text_glow`：`{"resource_id":"7202576698775179837","effect_id":"9762443","bloom_params":{"color":"#FFFFFF","dir_x":0.5,"dir_y":0.5,"range":0.2,"strength":0.3}}`；写入 `materials.effects[type=bloom]`，`panel_id="text_glow"`，`value=0.0`，文字 `check_flag |= 64`。`effect_id` 与 `resource_id` 必须分开给，`bloom_params` 不写时用外发光默认值；不要再写 `styles[0].effectStyle`。它可以和 `text_effect` 叠加；本机外发光/轮廓光资源均被 409 entitlement 拒绝，尚无像素证据。
- `text_bubble`：`{"resource_id":"…","effect_id":"…","path":"…"}`；写入 `materials.effects[type=text_shape]`。`capcut-mate` 实证 `effect_id` 与 `resource_id` 不是同一个值（如 `716434` / `6821385652727190024`），两者都要给；气泡只加装饰底板，不改文字填充/描边/阴影。官方 11.8 选择协议没有 `text_shape`，气泡走 `text_template`；本字段只兼容旧草稿，必须使用真实缓存资源，未验收。模板存在时气泡被忽略；没有模板时气泡优先于花字。

字幕模板的 `caption_info` 结构：

```json
"caption_info": {
  "id": "caption-1", "speaker_type": "", "speaker_id": "",
  "caption_segment_id": "seg-1", "original_text": "字幕文本",
  "words": [{"id": "word-1", "text": "字幕文本", "tag": "", "origin_text": "字幕文本",
             "time_range": {"start": 0, "duration": 3000000}}]
}
```

`time_range` 是微秒相对片段起点；`words` 可以按逐字/逐词拆。模板依赖的字体/花字资源仍需在缓存里。
`caption_info` 落在 `segment.caption_info`；只有 `text_template` 的 `content.json` 可读时才会派生
`caption_duration_info`（毫秒 `start_time`/`end_time`），不要把它当成所有字幕模板的通用入口。

## 关键帧

`segments[].keyframes` 是对象，键为通道名，值为点数组：

```json
"keyframes": {
  "scale": [[0, 1.0], [1.5, 1.08], [4.0, 1.0]],
  "position_y": [[0, 0], [2, 0.12]],
  "opacity": [[0, 0], [0.5, 1]]
}
```

点也可以是 `{"time": 1.2, "value": 1.05}` 或 `{"time": 1.2, "values": [1.05]}`。
可用通道：`scale`、`scale_x`、`scale_y`、`position_x`、`position_y`、`opacity`/`alpha`、`rotation`、`volume`。
时间相对于片段起点，不是整条时间线。

## 逐片段高级字段（已接线，仍需导出抽帧验收）

> `chroma` / `beauty` / `mix_mode` 的成片只能取**剪映界面导出**的帧验收；native bridge 的
> `jy.py render` 帧不作为这三项生效的依据。

视频/图片片段还支持（`curve_speed` / `reverse` / `matting` 只适用于视频；图片写这三项会 `VALIDATION`）：

| 字段 | 形状 | 说明 |
|---|---|---|
| `crop` | `{"x":0..1,"y":0..1,"w":0..1,"h":0..1}` | 转为剪映四角多边形；`x+w` / `y+h` 不得超过 1 |
| `flip` | `true` 或 `{"horizontal":bool,"vertical":bool}` | 写入 `segment.clip.flip`；2026-11-15 真机确认水平与垂直翻转都生效 |
| `reverse` | `true` / `false` | 写入 `segment.reverse`；2026-11-15 真机抽帧被 11.8 忽略，倒放未生效 |
| `mask` | `{"resource_type":"line","resource_id":"123456","path":"…","config":{"center_x":0.5,"center_y":0.5,"width":0.5,"height":0.5,"feather":0.1,"invert":false}}` | 写入 `materials.common_mask`，单材质引用；`constant_material_id` 留空避免悬空引用；资源必须已缓存；**`config` 只接受 `center_x/center_y/width/height/feather/invert`；`center_x`/`center_y`/`feather` 限 [0,1]，`width`/`height` 限 (0,1]；非法键或未知键构建时从落盘 config 移除并给 warning**；`invert` 是布尔反转，原样落盘、代码不校验取值；`config` 为空或字段不全在 11.8 会全黑或只显示一角 |
| `curve_speed` | `{"points":[{"x":0,"y":1},{"x":1,"y":2}],"name":"…","preset_id":"…"}` | 写入 `materials.speeds[].curve_speed`；`x` 0..1 单调不减，`y` 为正；2026-11-18 真机抽帧确认曲线像素生效；**target/source 时长仍按线性计算** |
| `matting` | `{"path":"<逐帧蒙版目录>","reverse":false,"feather":0.1,"expansion":0.02}` | 写入视频材质 `matting.path/mask_video_path`；目录必须已存在且由剪映生成，否则 `VALIDATION` |
| `color_wheel` | `{"segment":"gamma","red":0.1,"green":-0.2,"blue":0.3,"hsl":true}` | 写入 `primary_color_wheels`，`hsl:true` 时同时写 `hsl` 伴随材质；**2026-11-15 真机未观察到像素变化，保持 unverified** |
| `hsl` | `[{"color":"red","hue":10,"saturation":-20,"lightness":0}]` | 写 `materials.hsl` + `enable_hsl`；颜色限 red/orange/yellow/green/cyan/blue/purple/magenta，值 -100..100；**2026-11-18 真机导出仍无像素变化，保持 unverified** |
| `chroma` | `{"color":"#00FF00FF","intensity":20,"shadow":2,"edge_smooth":1,"spill":0}` | 写 `materials.chromas` 并挂 refs；百分比转 0..1；2026-11-18 构建的草稿在 11.8 UI 打开即蓝底红块，界面导出角点 `(0,0,254)`、中心 `(253,0,0)`；native bridge 不应用，成片走界面导出；技能不内置 GUI 自动化 |
| `background_fill` | `{"type":"blur","blur":0.5}` 或 `{"type":"color","color":"#0000FFFF"}` | 写 `materials.canvases` 并挂 refs；只对第 0 条视觉轨（最底层）生效，非底层写 warning；2026-11-18 真机导出：纯色填充角落 `(0,0,254)`，渐变图模糊填充角落 `(242,0,9)`、边缘 `(101,0,152)`，确认不是黑底 |
| `mix_mode` | `"滤色"` 或 `{"name":"滤色","effect_id":"871339","resource_id":"6758325170760323597"}` | 写 `materials.effects[type=mix_mode]` 并挂 `extra_material_refs`；2026-11-18 11.8 界面预览/UI 原生导出为品红，但 native bridge `draftPath` 导出仍是纯红；需要混合模式成片请在剪映界面导出 |
| `beauty` | `{"skin":{"smooth":100,"whitening":50,"skin_tone":"冷白","intensity":60,"temperature":10},"shape":{"small_face":60},"makeup":{"look":"淡人妆","intensity":80,"face_id":-1},"body":{"slim_body":40}}` | 写 `materials.effects[type=figure]`，有美妆项时追加 `makeup-root`，挂到视频/图片片段；强度按剪映滑杆 0..100 归一（肤色冷暖按 99）；0 值不写；`width/chin_length/wide_shoulder` 必须为 0；2026-11-18 11.8 UI 读回 `磨皮=100` / `美白=100`，界面原生导出有像素变化（磨皮人脸 `avg_abs_rgb=1.215`，美白皮肤 `RGB +7~9`）；`jy.py render` 的 native bridge 不应用 `figure`，成片必须走剪映界面导出；`shape/makeup` 409 entitlement |

`adjust` 与 `freeze` 目前**没有可用的 native 写入口**：计划里出现这两个字段会直接报
`VALIDATION`，不会静默忽略。色轮/HSL 在 11.8 真机也未生效；需要调色请用剪映客户端；
定格请用 `examples/06-freeze-workflow.py` 的“抽帧图片 + 前后视频段”工作流。

### native 逃生舱

计划片段可带 `native` 对象，用于写技能尚未封装、但本机草稿里已确认存在的字段：

```json
"native": {
  "segment": {"some_native_flag": true},
  "material": {"some_material_flag": true},
  "materials": [{"bucket": "video_shadows", "value": {"type": "video_shadow", "shadow_alpha": 0.2}}]
}
```

- `segment` / `material` 是深合并补丁，不能改 `id` / `material_id` / `local_material_id` /
  `extra_material_refs` / `render_index` / `track_render_index`；
- `materials` 只能写入 `draft_base.json` 已存在的桶；`value.type` 必填；`value.id` 可显式给，
  但不能与已有素材 id 重复；`ref: true` 会把新材质 id 挂到片段 `extra_material_refs`，
  `ref: false` 只落桶不挂引用；
- 技能不校验字段语义，写错不会报错；必须 `inspect` + 真实导出验收。

常用逃生桶（`value.type` 必须与桶语义一致；字段要来自真实草稿/资源包，不要猜）：

| 桶 | 用途 | 常见字段线索 |
|---|---|---|
| `video_shadows` / `video_strokes` / `video_radius` | 画面阴影/描边/圆角 | `shadow_alpha`、`stroke_color`、`radius` |
| `color_curves` / `log_color_wheels` | 曲线调色/Log 色轮 | 曲线点数组、色轮通道 |
| `audio_pitch_shifts` / `vocal_beautifys` / `vocal_separations` | 变声/人声美化/人声分离 | `pitch`、`timbre`、分离模式 |
| `realtime_denoises` / `loudnesses` | 降噪/响度 | `level`、`mode` |
| `video_trackings` / `smart_relights` / `manual_beautys` | 跟踪/智能打光/美体 | 跟踪点、强度 |
| `green_screens` | 绿幕前后景 | `foreground` |
| `plugin_effects` | 插件特效 | `resource_id`、`plugin_id` |

这些字段不是“已支持清单”，只是告诉你 native 能写到哪些桶；写之前先找真实样例，写之后必须验收。



## 贴纸与画面特效轨

```json
{"type": "sticker", "segments": [
  {"resource_id": "8c1d-uuid", "path": "…/PluginSticker_x", "start": 1, "duration": 3,
   "scale": 0.3, "x": 0.1, "y": -0.2}]}
```

```json
{"type": "effect", "segments": [
  {"resource_id": "555", "name": "星火", "path": "…/Cache/effect/555/<md5>",
   "start": 0, "duration": 3, "value": 0.8, "adjust_params": {"intensity": 0.5}}]}
```

贴纸和画面特效都必须使用缓存包；特效不能绑在视频片段 `extra_material_refs`，否则会叠成黑层。

这些字段只证明结构写入；真实导出后必须抽帧确认裁剪、翻转、倒放、蒙版和曲线的像素效果。
2026-11-15 已目视确认：裁剪、水平/垂直翻转、圆形蒙版（垂直翻转有归档抽帧，裁剪/水平翻转未单独归档）；贴纸两个包分别 409 entitlement / render ok 但无像素；
色轮仍未见像素变化；声道已真机验收。待抽帧：关键帧 position_x/rotation、气泡；曲线变速 2026-11-18 已真机验收（白块 1s/2s `0.203`/`0.547`，线性对照 `0.172`/`0.328`）；花字 712 已有真机像素证据，文字/视频动画已有真机抽帧。

## 转场与滤镜（实验性）

`segments[].transition`：

```json
{"resource_id": "123456789", "name": "叠化", "duration": 0.5, "path": ""}
```

`filters`（顶层数组，作用于整条时间线）：

```json
{"resource_id": "123456789", "name": "冷蓝", "value": 0.8, "start": 0, "duration": 5}
```

两者都要求资源包已经下载到本机 `Cache/effect`。未缓存时剪映会静默忽略，或导出报
`film_export_dependency_missing`。没有实测过转场/滤镜的成片效果，先当成实验能力。

## 响度测量与增益（loudness 命令）

`loudness` 不是 plan 字段，而是对已构建草稿执行的音频工具链：

```bash
python scripts/jy.py loudness <draft> --target -14 --apply --out <副本目录>
```

- 用 ffmpeg `loudnorm=I=-14:TP=-1.0:LRA=11` 按每个音频/带音频视频片段的
  `source_timerange` 截取后测量，返回 `lufs`、`true_peak_dbtp`、`lra`、当前 `volume`
  和按目标计算的 `gain_ops`。
- `--target` 范围 -70..-5；不给只测量，不修改。
- `--max-gain-db` 默认 12，`--max-attenuation-db` 默认 24，`--max-true-peak` 可选；
  增益会被上限截断并在回执里说明。
- `--apply` 必须同时给 `--out`，通过 `patch` 写副本，不直接改原草稿。
- 2026-11-18 真机：4 秒 440Hz/-12dB 测试音测得 `-33.75 LUFS`；`--max-gain-db 6 --apply`
  后剪映原生导出音频实测 `-27.86 LUFS`，与计划 `-27.75` 相差 0.11 dB，确认音量增益进入成片。

## 补丁 ops（patch 命令）

`patch --ops` 接受数组，或 `{"ops": [...]}`。`segment` 可以是片段 `id`（或 id 前缀），也可以是扁平下标（从 0 开始，按 tracks 顺序）。

| op | 字段 | 作用 |
|---|---|---|
| `rename` | `name` | 改草稿名 |
| `set_canvas` | `width` / `height` | 改画布；不会自动重排已有元素 |
| `fps` | `value` | 改帧率 |
| `add_subtitles` | `srt` / `name` / `style` | 新建或替换同名文字轨，每个 cue 一个 text 片段；建议每次 patch 作为下一版 |
| `set_text` | `text` + 可选样式字段 | 改文字内容与样式 |
| `set_style` | `font_size` / `color` / `stroke_color` / `stroke_width` / `align` | 只改样式 |
| `set_volume` | `volume` | 改音量 |
| `set_speed` | `speed` | 仅视频片段；改倍速并同步源区间。图片片段会返回 `VALIDATION`，`details.field=speed`；文字片段返回 `VALIDATION` |
| `shift` | `start` | 改时间线起点 |
| `trim` | `duration` | 改占用时长，并同步源区间；文字片段只改占用时长，不写源区间 |
| `set_transform` | `x` / `y` / `scale` / `rotation` / `opacity` | 改画面位置与大小 |
| `remove` | — | 删除片段；素材无引用时一并清理 |

`add_subtitles.style` 支持 `font_size`、`color`、`stroke_color`、`stroke_width`、`align`、
`line_spacing`、`letter_spacing`、`bold`、`italic`、`underline`、`background`、`shadow`、
`highlight`、`line_max_width`、`font_path`、`y`、`x`、`transform`、`scale`、`rotation`、
`opacity`、`caption_template`、`subtitle_template`。`caption_template` 需显式 `resource_id`/`path`，
并会为每个 cue 生成 `segment.caption_info`。`text_template` / `template` / `text_effect` /
`effect` / `text_glow` / `text_bubble` / `bubble` / `animations` / `native` / `resource_ref`
会被显式拒绝，不会“绿着丢数据”；这些先走 build 的 text 轨。

`patch` 默认要求 `--out` 写副本；确需改原稿才加 `--in-place`，此时会先把 `draft_info.json`
与 `draft_meta_info.json`（存在时）都备份到草稿目录下的 `.jianying-backups/`
（`draft_info.<时间戳>.json` / `draft_meta_info.<时间戳>.json`，时间戳带毫秒与短后缀，同一秒两次操作不互相覆盖）；
备份失败会中止，不会留下改了一半的原稿。
