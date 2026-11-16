#!/usr/bin/env python3
"""只读能力探测：把“技能已接线 / 本机资源已缓存 / 账号或宿主专属”分开。

    python scripts/capability_probe.py
    python scripts/capability_probe.py --out capabilities.json
    python scripts/capability_probe.py --out capabilities.json --force
    python scripts/capability_probe.py --list

输出一个 JSON 对象，schema 为 ``jianying-capabilities/v1``。它不启动剪映、
不调用 bridge、不读 token/cookie、不改任何文件（``--out`` 除外）。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jylib import env as env_mod

SCHEMA = "jianying-capabilities/v1"

# channel:
#   file      = 本技能直接写 draft_info.json / 跑外部 ffmpeg
#   bridge    = 需要剪映运行并连 native bridge
#   resource  = 需要本机已缓存资源包（转场/滤镜/特效/贴纸/模板/字体）
#   official  = 剪映安装目录里的官方技能，外部只能读协议，写入口在宿主
#   account   = 账号/云端/会员权益，技能不绕过
#   manual    = 只能在剪映 GUI 或人工交接完成
#
# status: implemented / planned / conditional / missing_resource / host_only /
#         account_gated / manual / unverified
CAPABILITIES = [
    # 草稿与导出
    {"id": "draft.build", "label": "新建多轨明文草稿", "category": "草稿",
     "channel": "file", "status": "implemented",
     "requires": ["install", "ffprobe"],
     "note": "build 写 draft_info.json；不启动剪映。"},
    {"id": "draft.inspect", "label": "读取草稿结构", "category": "草稿",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "只读；不解密。"},
    {"id": "draft.patch", "label": "修改明文草稿", "category": "草稿",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "默认写副本；--in-place 需授权并备份。"},
    {"id": "version.history", "label": "草稿版本链（快照/差异/恢复）", "category": "草稿",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "build/patch 自动写 v001 起的历史；restore 只写新目录；diff 比结构+材质指纹，不做像素 diff。"},
    {"id": "export.render", "label": "剪映原生导出视频/音频/动图", "category": "导出",
     "channel": "bridge", "status": "conditional", "requires": ["install", "bridge"],
     "note": "需要剪映运行且 bridge health 可用；端口每次启动会变；format 支持 mp4/mov/gif/mp3/wav/aac/flac/aiff/ogg；draftPath 入口不支持视频自定义码率，分辨率/帧率走画布。"},
    {"id": "export.transcode", "label": "本机 ffmpeg 转码到目标码率", "category": "导出",
     "channel": "file", "status": "implemented", "requires": ["ffmpeg"],
     "note": "后处理转码，不是剪映原生码率参数；用于补 native bridge 不支持的视频码率。"},
    {"id": "export.publish", "label": "复制进草稿根并登记首页", "category": "导出",
     "channel": "file", "status": "implemented",
     "requires": ["draft_root"],
     "note": "默认 dry-run；--apply 会改索引，必须先退出剪映并备份。"},
    {"id": "resource.catalog", "label": "本机资源目录（字体/贴纸/特效/模板）", "category": "草稿",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "只读 rp.db 与 Cache 资源包；cached 只代表本机有包，不代表账号权益或导出一定生效。"},
    {"id": "resource.download", "label": "下载免费素材/字体到本机", "category": "草稿",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "只下载免费非商业资源；会员/商业/过期 URL 明确失败；字体、字幕模板已真实导出验证，文字模板槽位仍需验收。"},
    {"id": "resource.verify", "label": "资源面板/权益/缓存预检", "category": "草稿",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "检查资源是否免费、已缓存、属于期望面板；不验像素，只防把 glow/bubble 等资源类型混用。"},
    {"id": "packaging.preset", "label": "本地包装 preset（标题/字幕/BGM 组合）", "category": "交付",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "组合主视频/标题/字幕/BGM/字体/字幕模板/标题动画；是本地 preset，不是剪映云端智能包装；2026-11-16 真实导出验证。"},

    # 已实现的草稿字段
    {"id": "visual.keyframes", "label": "缩放/位移/透明度/旋转/音量关键帧", "category": "画面",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "position_x / rotation 已有结构，但未单独抽帧确认。"},
    {"id": "speed.linear", "label": "线性变速", "category": "画面",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "图片固定 speed=1；视频按 duration*speed 取源区间。"},
    {"id": "audio.volume", "label": "音量与音量关键帧", "category": "音频",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "0..10；volume 关键帧已实测。"},
    {"id": "canvas.layout", "label": "画布/多轨层级/画中画", "category": "画面",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "画中画要 flag=2 且 render_index>=1。"},
    {"id": "text.basic", "label": "文字/字幕样式与位置", "category": "文字",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "文字素材必须是 type=text；subtitle 会触发 entitlement_denied。"},
    {"id": "text.highlight", "label": "本地关键词高亮", "category": "文字",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "按词匹配写 content.styles range；本地规则，不冒充剪映 AI 划重点；2026-11-16 真实导出验证。"},
    {"id": "text.decorate", "label": "文字背景/阴影/粗斜下划线", "category": "文字",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "已接线 background_* / has_shadow / bold_width / italic_degree / underline；真实导出抽帧已确认深色背景与阴影。"},
    {"id": "native.escape", "label": "native 原生结构逃生舱", "category": "草稿",
     "channel": "file", "status": "unverified", "requires": ["python"],
     "note": "允许写 segment/material/任意已存在 materials 桶；技能不校验字段语义，必须自带真实结构并回读验收。"},
    {"id": "subtitle.srt", "label": "SRT 生成/规范化/校验", "category": "字幕",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "只做已有文案的时间码分配，不做语音识别。"},
    {"id": "subtitle.asr.local", "label": "本地 Paraformer 识别字幕", "category": "字幕",
     "channel": "file", "status": "implemented",
     "requires": ["asr_model", "asr_deps"],
     "note": "用剪映「识别字幕」已下载的本地模型；不登录、不联网；输出逐字时间戳和 SRT。"},
    {"id": "subtitle.apply", "label": "SRT 写入可编辑字幕轨", "category": "字幕",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "patch 的 add_subtitles op；写 text 轨并自动成为下一版本，可继续 set_text/set_style。"},
    {"id": "subtitle.workflow", "label": "字幕自动流水线", "category": "字幕",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "本地 ASR/SRT → packaging plan → 可编辑草稿；不给 --srt 时需要 ASR 模型与依赖，可用 --srt 跳过。"},
    {"id": "subtitle.template", "label": "字幕模板（caption_template_info）", "category": "字幕",
     "channel": "resource", "status": "conditional", "requires": ["cache_artistEffect"],
     "note": "2026-11-16 免费“白字黑边”真实导出，cue 文本绑定成功；模板依赖字体/花字仍需缓存。"},
    {"id": "subtitle.postprocess", "label": "本地去水词/标点（启发式）", "category": "字幕",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "规则匹配删除口头禅、按停顿加标点；不冒充剪映 AI 去水词/标点。"},
    {"id": "subtitle.burn", "label": "硬字幕烧录", "category": "字幕",
     "channel": "file", "status": "implemented", "requires": ["ffmpeg_libass"],
     "note": "需要带 libass 的外部 ffmpeg；剪映自带 ffmpeg 不支持 subtitles 滤镜。"},

    # 协议有、技能还没接线：A 类
    {"id": "adjust.basic", "label": "基础调色（亮度/对比度/饱和度/色温/锐化/暗角/褪色/颗粒）", "category": "调色",
     "channel": "file", "status": "planned", "requires": ["python"],
     "note": "官方 XML 语义已核对，但 native picture_adjust 写入口未确认；plan 里的 adjust 会被显式拒绝，不能静默忽略。"},
    {"id": "adjust.hsl", "label": "HSL 分颜色调节", "category": "调色",
     "channel": "file", "status": "unverified", "requires": ["python"],
     "note": "已按官方 11.8 hsl 白名单写入 materials.hsl；真实导出首测未观察到像素变化，禁止当已支持。"},
    {"id": "color.wheels", "label": "色轮/色彩匹配", "category": "调色",
     "channel": "resource", "status": "unverified", "requires": ["cache_effect"],
     "note": "已接线 primary_color_wheels + 可选 hsl；2026-11-15 真机 gamma red=0.5 导出抽帧与无调色帧一致，11.8 未观察到像素变化。"},
    {"id": "audio.fade", "label": "音频淡入淡出", "category": "音频",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "已接线 materials.audio_fades（微秒）；独立音频轨真实导出已测 1s 淡入/淡出，波形有变化。视频原声淡入淡出未验证。"},
    {"id": "audio.effect", "label": "音效/音色（场景音/变声）", "category": "音频",
     "channel": "resource", "status": "conditional", "requires": ["cache_effect"],
     "note": "已接线 materials.audio_effects；2026-11-16 免费“萝莉”VC 资源真机 440Hz→740Hz；其他资源需逐个听感验收。"},
    {"id": "audio.channel", "label": "左/右声道选择", "category": "音频",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "写 materials.sound_channel_mappings[].audio_channel_mapping + is_config_open；2026-11-16 左only 源：0 左 -11.0dB/右静音，1 左右均 -11.0dB，2 双声道静音。"},
    {"id": "speed.curve", "label": "曲线变速", "category": "画面",
     "channel": "file", "status": "unverified", "requires": ["python"],
     "note": "已接线 materials.speeds[].curve_speed；只写材质，不改 target/source 时长；像素未抽帧。"},
    {"id": "crop.flip", "label": "裁剪与翻转", "category": "画面",
     "channel": "file", "status": "implemented", "requires": ["python"],
     "note": "已接线 crop 四角多边形 + clip.flip；2026-11-15 真实导出抽帧确认裁剪、水平翻转与垂直翻转均生效。"},
    {"id": "visual.reverse", "label": "视频倒放", "category": "画面",
     "channel": "file", "status": "unverified", "requires": ["python"],
     "note": "已接线 segment.reverse；2026-11-15 真实导出抽帧被 11.8 忽略，倒放未生效。"},
    {"id": "visual.freeze", "label": "定格", "category": "画面",
     "channel": "file", "status": "planned", "requires": ["python"],
     "note": "只做工作流：抽帧图片 + 前后视频段，不冒充原生 freeze；plan 里的 freeze 会被显式拒绝。"},

    # 资源依赖：B 类
    {"id": "effects.transition", "label": "转场", "category": "转场/特效",
     "channel": "resource", "status": "conditional", "requires": ["cache_effect"],
     "note": "必须已缓存对应资源；未缓存会静默忽略或 dependency_missing。"},
    {"id": "effects.filter", "label": "滤镜", "category": "转场/特效",
     "channel": "resource", "status": "conditional", "requires": ["cache_effect"],
     "note": "结构写入不等于效果生效；先做资源预检。"},
    # 这六项本地参考结构存在，但本技能还没有任何写入口：
    # draft.py 只写 filters/transitions，不能因为“本机有缓存”就标成有入口。
    {"id": "effects.video", "label": "画面特效", "category": "转场/特效",
     "channel": "resource", "status": "conditional", "requires": ["cache_effect"],
     "note": "已接线独立 effect 轨 + video_effects；效果包需缓存，像素未验收。"},
    {"id": "visual.mask", "label": "形状蒙版", "category": "画面",
     "channel": "resource", "status": "conditional", "requires": ["cache_effect"],
     "note": "已接线 common_mask 单材质引用；2026-11-15 真机 circle 82432977 + width/height 抽帧已确认；config 为空会全黑。"},
    {"id": "visual.matting", "label": "智能抠像", "category": "智能",
     "channel": "resource", "status": "conditional", "requires": ["python"],
     "note": "已接线视频材质 matting.path；构建时校验目录必须已存在，且必须由剪映生成逐帧蒙版。"},
    {"id": "visual.chroma", "label": "绿幕抠像（chroma）", "category": "智能",
     "channel": "file", "status": "unverified", "requires": ["python"],
     "note": "已接线 materials.chromas + refs；真实导出首测未抠绿，可能需额外触发字段；不要承诺已生效。"},
    {"id": "text.animation", "label": "文字动画", "category": "文字",
     "channel": "resource", "status": "conditional", "requires": ["cache_effect"],
     "note": "2026-11-16 免费“变色输入”经 material_animations 真实导出；动画资源需缓存。"},
    {"id": "visual.animation", "label": "视频/图片入场出场动画", "category": "画面",
     "channel": "resource", "status": "conditional", "requires": ["cache_effect"],
     "note": "2026-11-16 免费“翻入”经 material_animations[type=video_animation] 真实导出；资源需缓存。"},
    {"id": "text.effect", "label": "花字/文字特效", "category": "文字",
     "channel": "resource", "status": "unverified", "requires": ["cache_artistEffect"],
     "note": "已接线 filters[type=text_effect] + effectStyle；官方要求 ref 为 flower，DeepGlow 是 tool_text_glow，资源类型不匹配；需真实 flower 资源再做像素验收。"},
    {"id": "text.bubble", "label": "文字气泡", "category": "文字",
     "channel": "resource", "status": "unverified", "requires": ["cache_artistEffect"],
     "note": "已接线 filters[type=text_shape]；需要真实气泡资源，尚未渲染验收。"},
    {"id": "text.template", "label": "文字模板", "category": "文字",
     "channel": "resource", "status": "conditional", "requires": ["cache_artistEffect"],
     "note": "已接线 text_templates；模板包与槽位资源需缓存，像素未验收。"},
    {"id": "sticker", "label": "贴纸", "category": "画面",
     "channel": "resource", "status": "conditional", "requires": ["cache_effect"],
     "note": "已接线独立 sticker 轨；2026-11-15 两个包：7675620818189077810 render 409 entitlement，7202575978646737469 render ok 但抽帧无贴纸。"},

    # 官方/账号/人工：C 类
    {"id": "official.xml.draft", "label": "官方 XMLDraft 编排协议", "category": "官方",
     "channel": "official", "status": "host_only", "requires": ["official_skills"],
     "note": "DraftEditing 是宿主写入口；外部只读协议，不能提交 Selection。"},
    {"id": "ai.subtitle", "label": "智能字幕识别", "category": "AI",
     "channel": "account", "status": "account_gated", "requires": [],
     "note": "剪映客户端的云端识别/翻译/划重点仍受账号限制；本地识别已由 subtitle.asr.local 覆盖。"},
    {"id": "ai.lyric", "label": "歌词识别/歌词动效", "category": "AI",
     "channel": "account", "status": "account_gated", "requires": [],
     "note": "宿主/云端能力；外部不调用。"},
    {"id": "ai.tts", "label": "TTS/音色克隆", "category": "AI",
     "channel": "account", "status": "account_gated", "requires": [],
     "note": "音色克隆官方也列为暂不支持；用用户自备音频。"},
    {"id": "ai.digital_human", "label": "数字人/AI 成片", "category": "AI",
     "channel": "account", "status": "account_gated", "requires": [],
     "note": "云端/账号能力；本技能不下载、不解锁。"},
    {"id": "template.package", "label": "模板/剪同款/素材包", "category": "模板",
     "channel": "account", "status": "account_gated", "requires": [],
     "note": "需要客户端模板与云端素材；只做人工交接。"},
]

REQUIREMENT_LABELS = {
    "install": "剪映安装目录",
    "ffprobe": "ffprobe",
    "ffmpeg": "ffmpeg",
    "ffmpeg_libass": "带 libass 的 ffmpeg",
    "python": "Python",
    "bridge": "native bridge health",
    "draft_root": "剪映草稿根",
    "official_skills": "官方 canvas_agent/skills",
    "cache_effect": "Cache/effect 资源",
    "cache_artistEffect": "Cache/artistEffect 资源",
    "asr_model": "剪映本地 ASR 模型",
    "asr_deps": "numpy / onnxruntime / kaldi-native-fbank",
}


MODEL_FILES = ("asr-model-encoder.onnx", "asr-model-decoder.onnx",
               "asr-model-token.txt")


def _asr_root():
    explicit = os.environ.get("JY_LOCAL_ASR_DIR", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    return Path(local) / "JianyingPro" / "User Data" / "SupplysStore" / "local-asr-supplies"


def _asr_info():
    root = _asr_root()
    info = {"root": str(root) if root else None, "available": False,
            "model_dir": None}
    if not root or not root.is_dir():
        return info
    try:
        children = [child for child in root.iterdir() if child.is_dir()]
        children.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        for directory in [root, *children]:
            if all((directory / name).is_file() for name in MODEL_FILES):
                info["available"] = True
                info["model_dir"] = str(directory)
                break
    except OSError:
        pass
    return info


def _asr_deps():
    return {name: importlib.util.find_spec(name) is not None
            for name in ("numpy", "onnxruntime", "kaldi_native_fbank")}


def _dir_count(path):
    try:
        return sum(1 for child in path.iterdir() if child.is_dir())
    except OSError:
        return None


def _official_skills(install):
    if not install or not install.get("dir"):
        return {"root": None, "exists": False, "registered": [], "directories": []}
    root = Path(install["dir"]) / "Resources" / "canvas_agent" / "skills"
    registry_path = root.parent / "packaged-skills.json"
    registered = []
    if registry_path.is_file():
        try:
            data = json.loads(registry_path.read_text("utf-8"))
            for item in data.get("skills") or []:
                if isinstance(item, dict) and item.get("skillId"):
                    registered.append({
                        "skill_id": item["skillId"],
                        "name": item.get("name"),
                        "version": item.get("version"),
                        "status": item.get("status"),
                    })
        except (OSError, json.JSONDecodeError):
            pass
    directories = []
    if root.is_dir():
        try:
            directories = sorted(child.name for child in root.iterdir() if child.is_dir())
        except OSError:
            directories = []
    return {
        "root": str(root),
        "registry": str(registry_path) if registry_path.is_file() else None,
        "exists": root.is_dir(),
        "registered": registered,
        "directories": directories,
        "xml_builder": str(root / "jianying.hub.studio_lyra_xml_timeline_builder_v2")
        if (root / "jianying.hub.studio_lyra_xml_timeline_builder_v2").is_dir() else None,
    }


def _cache_info(cache):
    """Accept either env.probe()'s cache dict or a plain path string.

    env.probe() returns ``{root, exists, packages}``; older callers may pass a
    path. Keep this tolerant so the probe can run before the environment probe
    grows a field.
    """
    if isinstance(cache, dict):
        root_value = cache.get("root")
        packages = cache.get("packages")
        if isinstance(packages, dict):
            return {
                "root": root_value,
                "exists": bool(cache.get("exists")),
                "counts": {key: packages.get(key)
                           for key in ("effect", "artistEffect", "music", "template")},
            }
        cache_root = root_value
    else:
        cache_root = cache
    if not cache_root:
        return {"root": None, "exists": False, "counts": {}}
    root = Path(cache_root)
    counts = {key: _dir_count(root / key)
              for key in ("effect", "artistEffect", "music", "template")}
    return {"root": str(root), "exists": root.is_dir(), "counts": counts}


def _requirements_available(requires, facts):
    asr_deps = facts.get("asr_deps") or {}
    checks = {
        "install": bool(facts["install"]),
        "ffprobe": bool(facts["ffprobe"]),
        "ffmpeg": bool(facts["ffmpeg"]),
        "ffmpeg_libass": bool(facts["ffmpeg_libass"]),
        "python": True,
        "bridge": bool(facts["bridge"]),
        "draft_root": bool(facts["draft_root"]),
        "official_skills": bool(facts["official_skills"]["exists"]),
        "cache_effect": bool((facts["cache"]["counts"].get("effect") or 0) > 0),
        "cache_artistEffect": bool(
            (facts["cache"]["counts"].get("artistEffect") or 0) > 0),
        "asr_model": bool((facts.get("asr_model") or {}).get("available")),
        "asr_deps": bool(asr_deps) and all(asr_deps.values()),
    }
    return {name: checks.get(name, False) for name in requires}


def _resolve_status(item, facts):
    """Return the status the user should read, not just the code status.

    A capability can be implemented in code yet unavailable here because a
    prerequisite is missing (e.g. burn needs a libass ffmpeg). In that case the
    honest status is ``conditional``, not ``implemented``.
    """
    code_status = item["status"]
    missing = [name for name, ok in _requirements_available(
        item["requires"], facts).items() if not ok]
    if code_status == "implemented":
        return "conditional" if missing else "implemented"
    if code_status in {"planned", "host_only", "account_gated", "manual"}:
        return code_status
    if code_status == "conditional":
        if missing and any(name.startswith("cache_") for name in missing):
            return "missing_resource"
        return "conditional"
    return "unverified"


def _bridge_health(timeout=3.0):
    """探活 native bridge：描述文件存在不等于 health 可用。只读、不泄凭据。"""
    try:
        from jylib.bridge import Bridge
        bridge = Bridge.discover()
        info = bridge.safe_health()
        return {
            "reachable": True,
            "version": info.get("version"),
            "build": info.get("build"),
            "pid": info.get("pid"),
            "note": "",
        }
    except Exception as exc:  # noqa: BLE001 - 探测失败不能拖垮整份报告
        return {
            "reachable": False,
            "version": None,
            "build": None,
            "pid": None,
            "note": f"{type(exc).__name__}: {exc}",
        }


def _burn_ffmpeg():
    """Actual libass probe used by the burn path; never raises."""
    try:
        from subtitles.jy_common import resolve_ffmpeg
        info = resolve_ffmpeg()
        chosen = info.get("chosen") or {}
        return {
            "available": bool(info.get("burn_in_available")),
            "path": chosen.get("path"),
            "source": chosen.get("source"),
            "version": chosen.get("version"),
            "note": info.get("note"),
        }
    except Exception as exc:  # noqa: BLE001 - probe must not fail the report
        return {"available": False, "path": None, "source": None,
                "version": None, "note": f"探测失败：{type(exc).__name__}: {exc}"}


def probe():
    env = env_mod.probe()
    install = env.get("install") if isinstance(env.get("install"), dict) else None
    if install and install.get("error"):
        install = None
    ffmpeg = (env.get("ffmpeg") or {}).get("ffmpeg")
    burn = _burn_ffmpeg()
    bridge_health = _bridge_health()
    asr_model = _asr_info()
    asr_deps = _asr_deps()
    facts = {
        "install": bool(install and install.get("dir")),
        "ffprobe": bool((env.get("ffmpeg") or {}).get("ffprobe")),
        "ffmpeg": bool(ffmpeg),
        "ffmpeg_libass": bool(burn.get("available")),
        "bridge": bool(bridge_health.get("reachable")),
        "draft_root": bool((env.get("draft_root") or {}).get("exists")),
        "official_skills": _official_skills(install),
        "cache": _cache_info(env.get("cache") or {}),
        "asr_model": asr_model,
        "asr_deps": asr_deps,
    }
    capabilities = []
    for item in CAPABILITIES:
        entry = dict(item)
        entry["code_status"] = item["status"]
        entry["requirement_state"] = _requirements_available(item["requires"], facts)
        entry["status"] = _resolve_status(item, facts)
        capabilities.append(entry)

    summary = {}
    for entry in capabilities:
        summary[entry["status"]] = summary.get(entry["status"], 0) + 1

    return {
        "schema": SCHEMA,
        "generated_at": None,  # 由调用方决定是否写时间；这里不引入时区/时间依赖
        "environment": {
            "platform": env.get("platform"),
            "install": env.get("install"),
            "bridge": {
                "found": bool((env.get("bridge") or {}).get("found") is not False),
                "reachable": bool(bridge_health.get("reachable")),
                "descriptor": (env.get("bridge") or {}).get("descriptor"),
                "version": bridge_health.get("version") or
                           (env.get("bridge") or {}).get("version"),
                "build": bridge_health.get("build"),
                "health": bridge_health,
                "note": "不读桥接凭据；只通过 health 探活并读描述文件元信息。",
            },
            "draft_root": env.get("draft_root"),
            "ffmpeg": env.get("ffmpeg"),
            "burn_ffmpeg": burn,
            "cache": facts["cache"],
            "local_asr": {"model": asr_model, "deps": asr_deps},
        },
        "official": {
            "skills": facts["official_skills"],
            "package_registry": env.get("official_cli"),
        },
        "capabilities": capabilities,
        "summary": {
            "total": len(capabilities),
            "by_status": summary,
            "legend": {
                "implemented": "本技能已实现并有离线/实测证据",
                "planned": "协议/参考结构存在，技能尚未接线",
                "conditional": "有入口，但需要资源、bridge 或账号条件",
                "missing_resource": "本机资源未缓存，当前不可用",
                "host_only": "只能由剪映宿主/官方工具写，外部只读协议",
                "account_gated": "账号/云端/会员权益，技能不绕过",
                "manual": "只能人工在 GUI 完成",
                "unverified": "结构或字段存在，但未验证",
            },
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", help="写到指定 JSON 文件（默认只打印 stdout）")
    parser.add_argument("--force", action="store_true",
                        help="允许 --out 覆盖已存在的文件（默认拒绝）")
    parser.add_argument("--list", action="store_true", help="只列出能力 id/label/status")
    args = parser.parse_args(argv)
    data = probe()
    if args.list:
        for entry in data["capabilities"]:
            print(f"{entry['id']:<24} {entry['status']:<16} {entry['label']}")
        return 0
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        path = Path(args.out).expanduser()
        if path.exists() and not args.force:
            print(json.dumps({
                "ok": False,
                "error": {"code": "out-exists",
                          "message": f"输出文件已存在：{path}；换路径或加 --force"},
            }, ensure_ascii=False, indent=2))
            return 1
        try:
            path.write_text(text + "\n", "utf-8")
        except OSError as exc:
            print(json.dumps({
                "ok": False,
                "error": {"code": "io-error", "message": str(exc), "out": str(path)},
            }, ensure_ascii=False, indent=2))
            return 1
        print(json.dumps({"ok": True, "out": str(path), "summary": data["summary"]},
                         ensure_ascii=False, indent=2))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
