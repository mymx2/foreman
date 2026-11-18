# 音频 Playbook

读此文件时，目标是让声音**可听、可验证**：原声/BGM 分层、音量、淡入淡出、声道、音效。
音频最容易“结构对了但听感不对”，每个任务都要用 `volumedetect` 或实际听音频验收。

## 1. 基本分层

| 层 | 放什么 | 字段 |
|---|---|---|
| BGM | 独立 audio 轨 | `type:"audio"`，`volume` 0..1 |
| 原声 | 视频自带音频 | 视频片段 `has_audio` 为真时自动带入 |
| 旁白/音效 | 独立 audio 轨 | `type:"audio"`，`volume` 按需 |
| 淡入淡出 | audio 片段 | `audio_fade: {"in":0.5,"out":0.5}` |

视频原声默认保留；要压低原声时对**视频片段**写 `volume`；要替换原声就单独加 BGM 轨并降低视频音量。
`volume` 0..10，0 静音。

## 2. 音量与音量关键帧

```json
{"type": "audio", "segments": [{
  "path": "media/bgm.m4a", "start": 0, "duration": 8,
  "volume": 0.35,
  "keyframes": {"volume": [[0, 0.05], [2, 0.5], [6, 0.5], [8, 0.1]]}
}]}
```

- `volume` 是基础音量；关键帧在片段内插值；
- 音频关键帧写 `KFTypeVolume`，真实导出已用 `volumedetect` 验证过渐变；
- 关键帧时间不能超过片段时长。

## 3. 淡入淡出

```json
{"type": "audio", "segments": [{
  "path": "media/bgm.m4a", "start": 0, "duration": 3,
  "audio_fade": {"in": 1.0, "out": 1.0}
}]}
```

- 写 `materials.audio_fades`，`fade_in_duration` / `fade_out_duration` 单位**微秒**；
- `in + out` 不得超过片段时长，否则 `VALIDATION`；
- **独立音频轨已真实验证**：1s 淡入/淡出，`volumedetect` 首段 -39.0dB、中段 -24.1dB、尾段 -34.0dB；
- **视频原声淡入淡出未生效**：不要把 `audio_fade` 写在视频片段上冒充原声淡出；要淡出就拆出独立
  audio 轨，或让用户在剪映客户端处理。

## 4. 声道

```json
{"type": "audio", "segments": [{
  "path": "media/bgm.m4a", "start": 0, "duration": 3, "channel": 2
}]}
```

- 0 保持原声道 / 1 左声道复制到双声道 / 2 右声道复制到双声道（左-only 源实测双声道静音，因为源右声道本身是静音）；
- 写 `materials.sound_channel_mappings` 的 `{audio_channel_mapping, is_config_open:true, type:""}`；
- **2026-11-16 真机已验收**：左only 源 `channel:0` 左 -11.0dB/右静音、`1` 左右均 -11.0dB、`2` 双声道静音；
  证据已移出仓库，能力已升为 `implemented`。

## 5.1 EBU R128 响度测量与增益

```bash
python scripts/jy.py loudness <draft> --target -14 --apply --out <副本目录>
```

- 用 ffmpeg `loudnorm=I=-14:TP=-1.0:LRA=11` 按片段 `source_timerange` 截取测量，输出 `lufs`、`true_peak_dbtp`、`lra`、当前 `volume` 与 `gain_ops`；
- `--max-gain-db` 默认 12、`--max-attenuation-db` 默认 24、`--max-true-peak` 可选；目标不可达时按上限截断并如实回执；
- `--apply` 必须同时给 `--target` 和 `--out`，通过 `patch` 写副本，不改原草稿；
- 2026-11-18 真机：4 秒 440Hz/-12dB 测试音测得 `-33.75 LUFS`；`--max-gain-db 6 --apply` 后剪映原生导出实测 `-27.86 LUFS`，与计划 `-27.75` 差 0.11 dB，确认音量增益进入成片。

## 5. 音效/音色

```json
{"type": "audio", "segments": [{
  "path": "media/sfx.m4a", "start": 1, "duration": 0.5,
  "audio_effect": {"resource_id": "tone-1", "name": "低音",
                   "category_id": "tone", "params": {"pitch": 0.8}}
}]}
```

- 写 `materials.audio_effects`，`type:"audio_effect"`；
- `category_id` 限 `sound_effect` / `tone` / `speech_to_song`；
- 资源 id、权益、听感未验收；没有真实资源时不要伪造。

## 6. 音频验收

先做确定性分析，再导出验收：

```bash
python scripts/jy.py detect silence in.mp4 --threshold -30 --min-silence 0.5 --pad 0.1
python scripts/jy.py detect scenes in.mp4 --threshold 0.3 --min-gap 0.5
python scripts/jy.py detect retakes --cues cues.json --window 60 --similarity 0.8
```

- `detect silence` 输出 `silences` 与 `keeps`，同时给秒和微秒；`--limit` 只保留最长 N 段；
- `detect scenes` 输出切点与场景区间；`detect retakes` 是本地文本 LCS，不冒充语义模型；
- 这三个命令只分析、不改草稿，结果可再喂给 `patch` 的 `trim`/`shift`。

```bash
ffmpeg -hide_banner -ss 0 -t 0.2 -i out.mp4 -af volumedetect -f null -
```

对开头/中段/尾段分别测 `mean_volume`：

- 淡入：开头应明显低于中段；
- 淡出：尾段应明显低于中段；
- 声道：左右声道分别 `-af "pan=mono|c0=c0"` / `c1` 听或测；
- 音效：对比原片与处理后同一时间窗。

只看 `ok:true` 不算音频验收。

## 7. 常见坑

| 现象 | 原因 | 修法 |
|---|---|---|
| 导出没声音 | 音频路径不存在/格式不支持 | `ffprobe` 确认，换 m4a/mp3/wav |
| 淡入淡出没效果 | 写在了视频原声上 | 拆独立 audio 轨 |
| 左右声道没差别 | 源本身是单声道/映射未生效 | 用双声道源；标记 unverified |
| 音量关键帧不生效 | 时间超过片段/通道写错 | 按片段时长重算 |
| BGM 盖住人声 | 原声没压低 | 视频 `volume` 降到 0.2–0.4，BGM 0.2–0.35 |

## 8. 案例

- `examples/07-vertical-title-bgm.py`：BGM + 音量；
- `examples/17-audio-mix.py`：BGM + 原声 + 淡入淡出 + 声道 + 音效；
- `examples/18-spoken-piece.py`：口播 + BGM + 字幕。
