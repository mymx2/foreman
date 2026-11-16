#!/usr/bin/env python3
"""Command line for the 剪映 skill.

Every command prints one JSON object on stdout and exits non-zero on failure,
so an agent can branch on ``ok`` / ``error.code`` without parsing prose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import socket
import sys
import time
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jylib import draft as draft_mod
from jylib import env as env_mod
from jylib import index as index_mod
from jylib import media as media_mod
from jylib import packaging as packaging_mod
from jylib import resources as resources_mod
from jylib import transcode as transcode_mod
from jylib import versions as versions_mod
from jylib import workflow as workflow_mod
from jylib.bridge import Bridge
from jylib.errors import SkillError

# 中文 Windows 默认 GBK：JSON 含中文时必须强制 UTF-8，否则管道输出损坏。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def emit(command, data=None, warnings=None, error=None):
    payload = {
        "schema": "jianying-skill/v1",
        "command": command,
        "ok": error is None,
        "data": data,
        "warnings": warnings or [],
        "error": error,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if error is None else 1


def fail(command, exc):
    return emit(command, error=exc.to_dict())


def _timeout_seconds(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("timeout 必须是整数秒") from None
    if not 1 <= number <= 86400:
        raise argparse.ArgumentTypeError("timeout 必须在 1–86400 秒之间")
    return number


def _non_negative_seconds(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("必须是数字秒数") from None
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("必须是 ≥ 0 的有限秒数")
    return number


def _frame_times(value):
    items = [item.strip() for item in str(value).split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("--frames 至少给一个时间点")
    times = []
    for item in items:
        try:
            number = float(item)
        except (TypeError, ValueError):
            raise argparse.ArgumentTypeError(
                f"--frames 里的时间必须是数字：{item!r}") from None
        if not math.isfinite(number) or number < 0:
            raise argparse.ArgumentTypeError(
                f"--frames 里的时间必须是 ≥ 0 的有限秒数：{item!r}")
        times.append(number)
    return times


def cmd_probe(args):
    data = env_mod.probe()
    warnings = []
    bridge = None
    if data.get("bridge", {}).get("found") is False:
        warnings.append("剪映没有运行，或该版本没有开放 native bridge；render 需要它。")
    else:
        try:
            bridge = Bridge.discover()
            data["bridge"].update(bridge.safe_health())
        except SkillError as exc:
            data["bridge"]["health_error"] = exc.to_dict()
            warnings.append("桥接描述文件存在，但 health 检查失败。")
    if not data["ffmpeg"].get("ffprobe"):
        warnings.append("没有 ffprobe：无法读素材信息，也无法验证成片。")
    docs = data.get("docs") or {}
    if docs.get("status") == "unsupported":
        warnings.append(
            f"剪映 {docs.get('install_version')} 超出 supported "
            f"{docs.get('supported', {}).get('min')}–{docs.get('supported', {}).get('max')}；"
            "草稿仍可生成，但结论必须标为未验证。")
    elif docs.get("status") == "unverified":
        warnings.append(
            f"剪映 {docs.get('install_version')} 在 supported 窗口内，"
            "但未与 behavior/build 基线精确一致；结论标为未验证。")
    return emit("probe", data, warnings)


def cmd_build(args):
    if args.publish_apply and not args.publish:
        raise SkillError(
            "--publish-apply 只在 --publish 时有效；--publish 仅演练，"
            "--publish-apply 才真正复制进草稿根并改剪映首页列表",
            code="VALIDATION", details={"field": "publish_apply"})
    data = draft_mod.build(args.plan, args.out, force=args.force,
                           name=args.name, make_cover=not args.no_cover,
                           version_label=args.version_label,
                           fetch_resources=args.fetch_resources)
    warnings = data.pop("warnings", [])
    if args.publish:
        published = index_mod.publish(data["draft_dir"], apply=args.publish_apply,
                                      draft_root=args.draft_root, name=args.name)
        data["published"] = published
    return emit("build", data, warnings)


def cmd_inspect(args):
    return emit("inspect", draft_mod.inspect(args.draft))


def _draft_duration(info_path):
    try:
        document = json.loads(Path(info_path).read_text("utf-8-sig"))
        return float(document.get("duration") or 0) / 1_000_000
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


# 剪映导出时会回写的草稿文件；只比较存在的普通文件（链接一律跳过）。
_DRAFT_STATE_FILES = ("draft_info.json", "draft_meta_info.json",
                      "draft_content.json", "attachment_editing.json",
                      "draft.extra")


def _tree_sha(path):
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if draft_mod._is_link(item) or not item.is_file():
            continue
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
    return digest.hexdigest()


def _file_sha(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def _draft_file_hashes(draft_dir):
    folder = Path(draft_dir)
    hashes = {}
    for name in _DRAFT_STATE_FILES:
        path = folder / name
        try:
            if draft_mod._is_link(path):
                continue
            if path.is_dir():
                hashes[name] = _tree_sha(path)
            elif path.is_file():
                hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
    return hashes


def _connect_never_established(exc):
    """SkillError 是不是"TCP 连接根本没建立"，只有这种才允许重发导出。

    bridge._request 用 ``raise ... from exc`` 保留了底层异常，所以能按类型
    区分：连接被拒绝 / 连接超时会在异常链里留下 urllib.error.URLError，且
    reason 是 ConnectionRefusedError / TimeoutError。中途连接重置、读超时、
    业务 4xx/5xx 都不算——那时剪映可能已经收到导出请求，重发会重复导出。
    """
    if exc.code != "BRIDGE_UNREACHABLE":
        return False
    cause = exc.__cause__
    if not isinstance(cause, urllib.error.URLError):
        return False
    return isinstance(cause.reason, (ConnectionRefusedError, TimeoutError, socket.timeout))


def cmd_render(args):
    out = media_mod.ensure_output_path(args.out, force=args.force, label="成片文件")
    bridge = Bridge.discover()
    health = bridge.safe_health()
    resolved = draft_mod.resolve_draft_info(args.draft)
    if not resolved["info_path"]:
        raise SkillError("不是草稿目录", code="DRAFT_NOT_FOUND",
                         details={"draft": args.draft})
    if resolved["layout"] != "single":
        raise SkillError(
            "原生导出目前只支持单时间线布局",
            code="DRAFT_LAYOUT_UNSUPPORTED",
            details={"layout": resolved["layout"],
                     "info_path": str(resolved["info_path"])},
            fix="这份草稿已迁到 Timelines/ 多时间线布局；在剪映客户端里导出。",
        )
    before_sha = _file_sha(resolved["info_path"])
    before_files = _draft_file_hashes(resolved["draft_dir"])
    backups = draft_mod.backup_draft_files(resolved["draft_dir"], label="render")
    retried_connect = False
    try:
        data = bridge.export(resolved["draft_dir"], out, fmt=args.format,
                             timeout_ms=args.timeout * 1000)
    except SkillError as exc:
        if not _connect_never_established(exc):
            raise
        # 连接没建立过，剪映没收到请求；等 0.5s 再发一次，只此一次。
        time.sleep(0.5)
        retried_connect = True
        data = bridge.export(resolved["draft_dir"], out, fmt=args.format,
                             timeout_ms=args.timeout * 1000)
    after_sha = _file_sha(resolved["info_path"])
    after_files = _draft_file_hashes(resolved["draft_dir"])
    changed = sorted(name for name in set(before_files) | set(after_files)
                     if before_files.get(name) != after_files.get(name))
    data.update({
        "draft_sha256_before": before_sha,
        "draft_sha256_after": after_sha,
        "draft_mutated": bool(changed),
        "draft_files_changed": changed,
        "draft_backups": backups,
    })
    data["bridge"] = {"version": health.get("version"), "pid": health.get("pid")}
    # 回执记安装指纹，事后能对上是哪个 exe / DLL 导出的；找不到安装不阻断导出，
    # bridge 仍可能可用（例如安装在非默认路径、由别处注入）。
    try:
        install = env_mod.find_install()
    except SkillError as exc:
        install = None
        data["install"] = {"error": exc.message}
    else:
        if not install:
            data["install"] = {"error": "安装信息不可用"}
        else:
            data["install"] = {**env_mod.install_fingerprint(install),
                               "dir": str(install["dir"]), "version": install["version"]}
    warnings = []
    if retried_connect:
        warnings.append("首次导出时桥接连接未建立，已等待 0.5s 重试一次。")
    if changed:
        warnings.append(
            f"剪映在导出期间回写或移动了草稿文件：{', '.join(changed)}；"
            "已保留导出前备份，交付前复核草稿内容。")
    if after_sha is None:
        warnings.append(
            "导出后读不到 draft_info.json：剪映可能把它迁到 Timelines/ 或加密；"
            "按未验证处理，不要假设导出是只读操作。")
    tools = env_mod.find_ffmpeg(install)
    if tools.get("ffprobe"):
        probe = media_mod.probe_summary(tools["ffprobe"], data["path"])
        expected = _draft_duration(resolved["info_path"])
        data["probe"] = probe
        data["expected_duration"] = expected
        if expected and abs(probe["duration"] - expected) > 0.25:
            warnings.append(
                f"成片时长 {probe['duration']:.3f}s 与草稿 {expected:.3f}s 相差超过 0.25s；"
                "检查片段是否越界或渲染被截断。"
            )
        if probe["width"] == 0 or probe["height"] == 0:
            warnings.append("输出没有视频流（音频格式正常）；需要画面请换 mp4/mov/gif。")
    else:
        warnings.append("没有 ffprobe，未验证成片时长/分辨率。")
    data["warnings"] = warnings
    if not versions_mod.record_export(resolved["draft_dir"], data):
        warnings.append(
            "草稿没有 .jianying-versions 版本历史，本次导出未记入版本；"
            "可先运行 `jy.py version snapshot <draft> --label init`。")
    if changed and after_sha:
        try:
            rewritten = versions_mod.record_editor_rewrite(
                resolved["draft_dir"],
                note=f"剪映导出回写：{', '.join(changed)}")
        except (SkillError, OSError) as exc:
            rewritten = None
            code = getattr(exc, "code", type(exc).__name__)
            warnings.append(
                f"剪映回写后的草稿未能记入版本（{code}）；"
                "本次成片回执仍挂在导出前的版本上。")
        if rewritten:
            data["draft_version_after"] = rewritten["id"]
            warnings.append(
                f"剪映回写后的草稿已记为 {rewritten['id']}（editor-rewrite）；"
                "本次成片回执仍挂在导出前的版本上。")
    return emit("render", data, warnings)


def cmd_verify(args):
    tools = env_mod.find_ffmpeg(env_mod.find_install())
    if not tools.get("ffprobe"):
        raise SkillError("没有 ffprobe", code="FFPROBE_MISSING")
    probe = media_mod.probe_summary(tools["ffprobe"], args.video)
    warnings = []
    if args.expect_duration is not None:
        probe["expected_duration"] = args.expect_duration
        if abs(probe["duration"] - args.expect_duration) > 0.25:
            warnings.append(
                f"时长 {probe['duration']:.3f}s 与期望 {args.expect_duration:.3f}s 相差较大")
    frames = []
    if args.frames:
        if not tools.get("ffmpeg"):
            raise SkillError("没有 ffmpeg，无法抽帧", code="FFMPEG_MISSING")
        times = args.frames
        outdir = Path(args.outdir) if args.outdir else Path(args.video).resolve().parent / "frames"
        frames = media_mod.extract_frames(tools["ffmpeg"], args.video, times, outdir,
                                          force=args.force)
    if frames:
        probe["frames"] = frames
    return emit("verify", probe, warnings)


def cmd_frame(args):
    tools = env_mod.find_ffmpeg(env_mod.find_install())
    out = media_mod.extract_frame(tools.get("ffmpeg"), args.video, args.at, args.out,
                                  force=args.force)
    return emit("frame", {"path": out, "at": args.at})


def cmd_register(args):
    return emit("register", index_mod.register(
        args.draft, apply=args.apply, draft_root=args.draft_root, name=args.name))


def cmd_publish(args):
    return emit("publish", index_mod.publish(
        args.draft, apply=args.apply, draft_root=args.draft_root, name=args.name))


def cmd_patch(args):
    return emit("patch", draft_mod.patch(
        args.draft, args.ops, args.out, in_place=args.in_place,
        version_label=args.version_label))


def cmd_resource(args):
    command = f"resource.{args.resource_command}"
    try:
        if args.resource_command == "list":
            data = resources_mod.list_resources(
                panel=args.panel, keyword=args.keyword, cached_only=args.cached,
                include_vip=args.include_vip, limit=args.limit)
        elif args.resource_command == "stats":
            data = resources_mod.stats()
        elif args.resource_command == "resolve":
            data = resources_mod.resolve(args.ref)
        elif args.resource_command == "download":
            cache_root = (media_mod.local_path(args.cache_root, field="缓存根")
                          if args.cache_root else None)
            data = resources_mod.download_resource(
                args.ref, cache_root=cache_root,
                apply=args.apply, force=args.force)
        elif args.resource_command == "verify":
            data = resources_mod.verify(args.ref, expect_panel=args.expect_panel)
        else:
            raise SkillError("未知 resource 子命令", code="BAD_ARGS")
        return emit(command, data)
    except SkillError as exc:
        return fail(command, exc)


def cmd_packaging(args):
    try:
        style = json.loads(args.subtitle_style) if args.subtitle_style else None
        if style is not None and not isinstance(style, dict):
            raise SkillError("--subtitle-style 必须是 JSON 对象", code="VALIDATION")
        data = packaging_mod.build_plan(
            args.video, args.out, title=args.title,
            subtitle_srt=args.subtitle_srt, bgm=args.bgm,
            font_ref=args.font_ref,
            subtitle_template_ref=args.subtitle_template_ref,
            title_animation_ref=args.title_animation_ref,
            name=args.name, width=args.width, height=args.height,
            fps=args.fps, subtitle_style=style,
            highlight_words=args.highlight_words,
            highlight_color=args.highlight_color, force=args.force)
        return emit("packaging", data)
    except json.JSONDecodeError as exc:
        return fail("packaging", SkillError(
            "--subtitle-style 不是合法 JSON", code="VALIDATION",
            details={"reason": str(exc)}))
    except SkillError as exc:
        return fail("packaging", exc)


def cmd_transcode(args):
    try:
        data = transcode_mod.transcode(
            args.input, args.out, video_bitrate=args.video_bitrate,
            audio_bitrate=args.audio_bitrate, fps=args.fps,
            codec=args.codec, preset=args.preset, timeout=args.timeout,
            force=args.force)
        return emit("transcode", data)
    except SkillError as exc:
        return fail("transcode", exc)


def cmd_auto_subtitles(args):
    try:
        style = json.loads(args.subtitle_style) if args.subtitle_style else None
        if style is not None and not isinstance(style, dict):
            raise SkillError("--subtitle-style 必须是 JSON 对象", code="VALIDATION")
        data = workflow_mod.build_subtitle_draft(
            args.video, args.out, audio=args.audio, srt=args.srt,
            plan_out=args.plan_out, srt_out=args.srt_out,
            asr_json_out=args.asr_json_out, title=args.title, bgm=args.bgm,
            font_ref=args.font_ref,
            subtitle_template_ref=args.subtitle_template_ref,
            title_animation_ref=args.title_animation_ref, name=args.name,
            width=args.width, height=args.height, fps=args.fps,
            subtitle_style=style, highlight_words=args.highlight_words,
            highlight_color=args.highlight_color, model_dir=args.model_dir,
            remove_fillers=args.remove_fillers, fillers=args.fillers,
            punctuate=args.punctuate, max_chars=args.max_chars,
            max_dur=args.max_dur, gap=args.gap,
            fetch_resources=args.fetch_resources, force=args.force,
            make_cover=not args.no_cover)
        warnings = data.pop("warnings", [])
        return emit("auto-subtitles", data, warnings)
    except json.JSONDecodeError as exc:
        return fail("auto-subtitles", SkillError(
            "--subtitle-style 不是合法 JSON", code="VALIDATION",
            details={"reason": str(exc)}))
    except SkillError as exc:
        return fail("auto-subtitles", exc)


def cmd_version(args):
    action = args.version_command
    if action == "list":
        return emit("version.list", versions_mod.list_versions(args.draft))
    if action == "show":
        return emit("version.show", versions_mod.show_version(args.draft, args.version))
    if action == "diff":
        return emit("version.diff", versions_mod.diff_versions(
            args.draft, args.version, against=args.against))
    if action == "snapshot":
        return emit("version.snapshot", versions_mod.record_snapshot(
            args.draft, label=args.label, note=args.note))
    if action == "restore":
        return emit("version.restore", versions_mod.restore_version(
            args.draft, args.version, args.out, name=args.name))
    raise SkillError("未知 version 子命令", code="VALIDATION",
                     details={"command": action})


def build_parser():
    parser = argparse.ArgumentParser(prog="jianying", description="剪映草稿与原生导出")
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser("probe", help="探测剪映安装、桥接、草稿根、ffmpeg")
    probe.set_defaults(func=cmd_probe)

    build = sub.add_parser("build", help="从计划生成明文草稿")
    build.add_argument("--plan", required=True, help="jianying-plan/v1 JSON 文件")
    build.add_argument("--out", required=True, help="输出草稿目录")
    build.add_argument("--name", help="草稿名（默认取 plan.name）")
    build.add_argument("--force", action="store_true", help="覆盖本技能生成的旧草稿")
    build.add_argument("--no-cover", action="store_true", help="不生成封面")
    build.add_argument("--version-label", help="写入版本历史的标签（默认 build）")
    build.add_argument("--publish", action="store_true",
                       help="登记演练：只返回将要复制/登记的内容，不写盘；"
                            "配合 --publish-apply 才真正改剪映首页列表")
    build.add_argument("--publish-apply", action="store_true", dest="publish_apply",
                       help="真正复制进草稿根并写索引（仅在 --publish 时生效）")
    build.add_argument("--draft-root", help="剪映草稿根目录")
    build.add_argument("--fetch-resources", action="store_true", dest="fetch_resources",
                       help="遇到未缓存的免费资源时自动下载；会员/商业资源仍会失败")
    build.set_defaults(func=cmd_build)

    inspect = sub.add_parser("inspect", help="读取草稿摘要（不解密）")
    inspect.add_argument("draft")
    inspect.set_defaults(func=cmd_inspect)

    render = sub.add_parser("render", help="用剪映原生引擎导出视频/音频/动图")
    render.add_argument("draft")
    render.add_argument("-o", "--out", required=True, help="输出文件路径；扩展名要与 --format 一致")
    render.add_argument("--format", default="mp4",
                        choices=("mp4", "mov", "gif", "mp3", "wav", "aac",
                                 "flac", "aiff", "ogg"))
    render.add_argument("--timeout", type=_timeout_seconds, default=300, help="导出超时秒数（1–86400）")
    render.add_argument("--force", action="store_true", help="允许覆盖已存在的成片")
    render.set_defaults(func=cmd_render)

    verify = sub.add_parser("verify", help="ffprobe 校验成片，可抽帧")
    verify.add_argument("video")
    verify.add_argument("--expect-duration", type=_non_negative_seconds)
    verify.add_argument("--frames", type=_frame_times,
                        help="逗号分隔的抽帧时间，如 0.5,1.5")
    verify.add_argument("--outdir")
    verify.add_argument("--force", action="store_true", help="允许覆盖已存在的抽帧文件")
    verify.set_defaults(func=cmd_verify)

    frame = sub.add_parser("frame", help="抽一帧")
    frame.add_argument("video")
    frame.add_argument("--at", type=_non_negative_seconds, required=True)
    frame.add_argument("-o", "--out", required=True)
    frame.add_argument("--force", action="store_true", help="允许覆盖已存在的图片")
    frame.set_defaults(func=cmd_frame)

    register = sub.add_parser("register", help="把已在草稿根的草稿登记到首页（默认 dry-run）")
    register.add_argument("draft")
    register.add_argument("--apply", action="store_true")
    register.add_argument("--draft-root")
    register.add_argument("--name")
    register.set_defaults(func=cmd_register)

    publish = sub.add_parser("publish", help="复制进草稿根并登记（默认 dry-run）")
    publish.add_argument("draft")
    publish.add_argument("--apply", action="store_true")
    publish.add_argument("--draft-root")
    publish.add_argument("--name")
    publish.set_defaults(func=cmd_publish)

    patch = sub.add_parser("patch", help="改已有明文草稿（默认复制副本）")
    patch.add_argument("draft")
    patch.add_argument("--ops", required=True, help="补丁 JSON（数组或 {\"ops\": [...]}）")
    patch.add_argument("--out", help="副本输出目录（不加 --in-place 时必填）")
    patch.add_argument("--in-place", action="store_true", help="直接改原草稿")
    patch.add_argument("--version-label", help="写入版本历史的标签（默认 patch）")
    patch.set_defaults(func=cmd_patch)

    version = sub.add_parser("version", help="草稿版本链：列表/查看/差异/快照/恢复")
    vsub = version.add_subparsers(dest="version_command", required=True)
    vlist = vsub.add_parser("list", help="列出版本")
    vlist.add_argument("draft")
    vlist.set_defaults(func=cmd_version)
    vshow = vsub.add_parser("show", help="查看单个版本")
    vshow.add_argument("draft")
    vshow.add_argument("version")
    vshow.set_defaults(func=cmd_version)
    vdiff = vsub.add_parser("diff", help="结构差异（不是像素 diff）")
    vdiff.add_argument("draft")
    vdiff.add_argument("version")
    vdiff.add_argument("--against", help="基线版本；默认取父版本")
    vdiff.set_defaults(func=cmd_version)
    vsnap = vsub.add_parser("snapshot", help="把当前草稿存成新版本")
    vsnap.add_argument("draft")
    vsnap.add_argument("--label", default="snapshot")
    vsnap.add_argument("--note")
    vsnap.set_defaults(func=cmd_version)
    vrestore = vsub.add_parser("restore", help="恢复到新草稿目录（不覆盖）")
    vrestore.add_argument("draft")
    vrestore.add_argument("version")
    vrestore.add_argument("--out", required=True, help="新草稿目录，必须不存在")
    vrestore.add_argument("--name", help="恢复后的草稿名")
    vrestore.set_defaults(func=cmd_version)

    resource = sub.add_parser("resource", help="查询本机已收录/已缓存的素材资源")
    rsub = resource.add_subparsers(dest="resource_command", required=True)
    rlist = rsub.add_parser("list", help="列出资源（可只看已缓存）")
    rlist.add_argument("--panel", help="面板名，如 fonts/subtitle-templates/bubble/flower2/sticker")
    rlist.add_argument("--keyword", help="标题/名称关键词")
    rlist.add_argument("--cached", action="store_true", help="只列已下载到本机的资源包")
    rlist.add_argument("--include-vip", action="store_true", dest="include_vip",
                       help="包含会员资源（默认只看非会员）")
    rlist.add_argument("--limit", type=int, default=50)
    rlist.set_defaults(func=cmd_resource)
    rstats = rsub.add_parser("stats", help="按面板统计资源与缓存数量")
    rstats.set_defaults(func=cmd_resource)
    rresolve = rsub.add_parser("resolve", help="按 id/md5/标题解析资源与缓存路径")
    rresolve.add_argument("ref")
    rresolve.set_defaults(func=cmd_resource)
    rdownload = rsub.add_parser("download", help="下载免费资源包到本机缓存（默认 dry-run）")
    rdownload.add_argument("ref")
    rdownload.add_argument("--apply", action="store_true", help="真正下载并解包；不加只演练")
    rdownload.add_argument("--force", action="store_true", help="覆盖已存在的资源包")
    rdownload.add_argument("--cache-root", help="可选：下载到指定缓存根（默认剪映 Cache）")
    rdownload.set_defaults(func=cmd_resource)
    rverify = rsub.add_parser("verify", help="检查资源是否免费/已缓存且属于期望面板")
    rverify.add_argument("ref")
    rverify.add_argument("--expect-panel", dest="expect_panel",
                         help="期望面板，如 fonts/subtitle-templates/flower2/bubble/sticker")
    rverify.set_defaults(func=cmd_resource)

    pack = sub.add_parser("packaging", help="生成本地包装 preset 计划（非云端智能包装）")
    pack.add_argument("--video", required=True)
    pack.add_argument("--out", required=True, help="输出 jianying-plan/v1 JSON")
    pack.add_argument("--title")
    pack.add_argument("--subtitle-srt")
    pack.add_argument("--bgm")
    pack.add_argument("--font-ref", help="字体资源标题/ID；build 时解析为 font_path")
    pack.add_argument("--subtitle-template-ref", help="字幕模板资源标题/ID")
    pack.add_argument("--title-animation-ref", help="标题入场动画资源标题/ID")
    pack.add_argument("--name")
    pack.add_argument("--width", type=int)
    pack.add_argument("--height", type=int)
    pack.add_argument("--fps", type=float, default=30.0)
    pack.add_argument("--subtitle-style", help="JSON 对象，覆盖字幕样式")
    pack.add_argument("--highlight-words", help="逗号分隔的关键词，标题/字幕高亮（本地规则）")
    pack.add_argument("--highlight-color", default="#FFD400")
    pack.add_argument("--force", action="store_true")
    pack.set_defaults(func=cmd_packaging)

    auto = sub.add_parser("auto-subtitles", help="本地 ASR/SRT → 包装计划 → 可编辑草稿")
    auto.add_argument("--video", required=True, help="主视频；没有 --audio 时也作为 ASR 音源")
    auto.add_argument("--out", required=True, help="输出草稿目录")
    auto.add_argument("--audio", help="ASR 音源；默认用 --video")
    auto.add_argument("--srt", help="已有 SRT；给了就跳过 ASR")
    auto.add_argument("--srt-out", help="ASR SRT 输出路径；默认 <out>.srt")
    auto.add_argument("--asr-json-out", help="ASR token JSON；默认 <out>.asr.json")
    auto.add_argument("--plan-out", help="包装计划路径；默认 <out>-plan.json")
    auto.add_argument("--title")
    auto.add_argument("--bgm")
    auto.add_argument("--font-ref", help="字体资源标题/ID/完整标题")
    auto.add_argument("--subtitle-template-ref", help="字幕模板资源标题/ID")
    auto.add_argument("--title-animation-ref", help="标题动画资源标题/ID")
    auto.add_argument("--name")
    auto.add_argument("--width", type=int)
    auto.add_argument("--height", type=int)
    auto.add_argument("--fps", type=float, default=30.0)
    auto.add_argument("--subtitle-style", help="JSON 对象，覆盖字幕样式")
    auto.add_argument("--highlight-words", help="逗号分隔关键词，标题/字幕高亮")
    auto.add_argument("--highlight-color", default="#FFD400")
    auto.add_argument("--model-dir", help="本地 ASR 模型目录")
    auto.add_argument("--remove-fillers", action="store_true",
                     help="删除常见口头禅；本地规则")
    auto.add_argument("--fillers", help="逗号分隔的待删词")
    auto.add_argument("--punctuate", action="store_true",
                     help="按停顿启发式加标点；本地规则")
    auto.add_argument("--max-chars", type=int, default=16)
    auto.add_argument("--max-dur", type=float, default=5.0)
    auto.add_argument("--gap", type=float, default=0.35)
    auto.add_argument("--fetch-resources", action="store_true", dest="fetch_resources",
                     help="自动下载未缓存的免费资源")
    auto.add_argument("--force", action="store_true",
                     help="覆盖本技能生成的计划/草稿/SRT")
    auto.add_argument("--no-cover", action="store_true", help="不生成封面")
    auto.set_defaults(func=cmd_auto_subtitles)

    transcode = sub.add_parser("transcode", help="用本机 ffmpeg 转码到目标视频码率（非剪映原生）")
    transcode.add_argument("input")
    transcode.add_argument("-o", "--out", required=True)
    transcode.add_argument("--video-bitrate", required=True,
                           help="目标视频码率，如 2M、2500k")
    transcode.add_argument("--audio-bitrate", default="128k",
                           help="目标音频码率，默认 128k")
    transcode.add_argument("--fps", type=float, help="可选：输出帧率")
    transcode.add_argument("--codec", default="libx264")
    transcode.add_argument("--preset", default="medium")
    transcode.add_argument("--timeout", type=_timeout_seconds, default=600)
    transcode.add_argument("--force", action="store_true")
    transcode.set_defaults(func=cmd_transcode)
    return parser


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    command = argv[0] if argv and not argv[0].startswith("-") else "cli"
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code == 0:
            raise
        fail(command, SkillError(
            "命令行参数不合法",
            code="BAD_ARGS",
            details={"exit_code": exc.code},
            fix="运行 python scripts/jy.py --help 查看可用参数。",
        ))
        return 2
    try:
        return args.func(args)
    except SkillError as exc:
        return fail(args.command, exc)
    except KeyboardInterrupt:
        return fail(args.command, SkillError("被中断", code="INTERRUPTED"))
    except Exception as exc:
        return fail(args.command, SkillError(
            f"未预期的错误：{type(exc).__name__}: {exc}",
            code="INTERNAL",
            details={"type": type(exc).__name__},
            retriable=False))


if __name__ == "__main__":
    raise SystemExit(main())
