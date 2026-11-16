"""Minimal client for 剪映's local native bridge (Windows 11.8 and macOS).

The bridge is the app's own local HTTP service. The descriptor file carries a
per-launch token; this module keeps it in memory and never logs it. Only the
export route is used, plus health/context for preflight.
"""

from __future__ import annotations

import hashlib
import json
import re
import socket
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .errors import SkillError

HEALTH_PATH = "/.infinite-canvas-native-bridge/health"
CONTEXT_PATH = "/custom-agent/context"
EXPORT_PATH = "/custom-agent/film-export"
SENSITIVE_CAPABILITY = re.compile(r"token|cookie|secret|authorization|session", re.I)


def _public_capabilities(value):
    """Only expose flat, non-sensitive capability facts.

    The health response also contains internal objects with credentials. Those
    are never useful to a caller and must not reach stdout or a transcript.
    """
    if not isinstance(value, dict):
        return {}
    public = {}
    for key, item in value.items():
        if not isinstance(key, str) or SENSITIVE_CAPABILITY.search(key):
            continue
        if isinstance(item, (bool, int, float, str)) and len(str(item)) <= 300:
            public[key] = item
    return public

EXPORT_ERRORS = {
    "film_export_entitlement_denied": (
        "剪映拒绝导出：草稿里有需要会员/授权的素材。",
        "最常见原因是文字素材 type=\"subtitle\"（被当作 AI 字幕）。把文字素材改成 "
        "type=\"text\"；其次检查是否引用了会员字体、会员特效/转场。",
    ),
    "film_export_entitlement_bypass_forbidden": (
        "剪映拒绝绕过会员校验。",
        "移除会员素材，或在剪映客户端里由账号正常导出。",
    ),
    "film_export_dependency_missing": (
        "草稿引用的素材包没有下载到本机缓存。",
        "先在剪映里点开对应转场/滤镜/特效让它下载，或从计划里去掉该素材。",
    ),
    "film_export_draft_unreadable": (
        "剪映读不了这份草稿：draft_info.json 被加密、损坏或路径不对。",
        "只对本技能生成的明文草稿做原生导出；被剪映重存加密的草稿请在剪映里打开后导出。",
    ),
    "film_export_no_audio": (
        "导出要求音频但草稿没有可用的音频流。",
        "检查音频素材路径，或改为只导出画面。",
    ),
    "film_export_format_unavailable": (
        "当前版本不支持该导出格式。",
        "改用 mp4。",
    ),
    "film_export_options_unavailable": (
        "导出参数不可用。",
        "不要传自定义导出参数，使用默认 mp4。",
    ),
    "film_export_invalid_request": (
        "导出请求格式不合法。",
        "用本技能的 render 命令生成请求，不要手拼字段。",
    ),
    "film_export_invalid_state": (
        "剪映当前状态不允许导出（可能正在播放、导出或切换草稿）。",
        "等剪映空闲后重试。",
    ),
    "film_export_draft_manager_unavailable": (
        "剪映草稿管理器不可用。",
        "重启剪映后再试。",
    ),
    "film_export_frame_canvas_unavailable": (
        "导出画布不可用。",
        "重启剪映，或换一个草稿画布尺寸。",
    ),
    "film_export_runtime_unavailable": (
        "剪映导出运行时未就绪。",
        "打开剪映并等它完全启动后重试。",
    ),
    "film_export_request_canceled": (
        "剪映取消了这次导出请求。",
        "停止重复调用；确认剪映界面没有弹窗或未完成的导出，再重新发起。",
    ),
    "film_export_timeout": (
        "剪映导出超过请求的超时时间。",
        "保留当前草稿和输出目录，确认剪映是否仍在导出；不要并发重试同一草稿。",
    ),
    "film_export_token_invalid": (
        "本地 bridge 的临时 token 已失效。",
        "不要复用旧 token；重新运行 probe 读取剪映新启动后写的描述文件。",
    ),
    "film_export_unsupported_timeline": (
        "剪映原生导出不接受当前时间线布局。",
        "把草稿保存为单时间线，或直接在剪映客户端导出；不要改写 Timelines 结构绕过。",
    ),
    "film_export_cancelled_or_timeout": (
        "剪映取消或等待导出超时。",
        "保留现场，确认剪映是否仍在导出；同一草稿不要并发重试。",
    ),
    "film_export_panel_unavailable": (
        "导出面板或注入执行不可用。",
        "退出剪映后重开；若仍失败，改用剪映客户端导出，不要改官方文件。",
    ),
}


def _request(method, url, headers, body=None, timeout=30.0):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers = {**headers, "content-type": "application/json"}
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            try:
                body = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                body = {"raw": raw[:500]}
            return response.status, body
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = {"raw": raw[:500]}
        return exc.code, payload
    except socket.timeout as exc:
        raise SkillError(
            "等待剪映响应超时",
            code="BRIDGE_TIMEOUT",
            details={"url": url.split("?")[0], "timeout_s": timeout},
            fix="确认剪映没有卡住；导出大草稿可加大 --timeout。",
            retriable=True,
        ) from exc
    except urllib.error.URLError as exc:
        raise SkillError(
            "连不上剪映本地桥接",
            code="BRIDGE_UNREACHABLE",
            details={"reason": str(exc.reason)},
            fix="确认剪映正在运行；桥接端口每次启动都会变，重新运行 probe 读取描述文件。",
            retriable=True,
        ) from exc
    except OSError as exc:
        # ConnectionResetError 等发生在 response.read() 阶段：剪映中途退出/重启
        # 会重置连接。归为可重试的桥接不可达，而不是落到 INTERNAL 兜底。
        raise SkillError(
            "剪映本地桥接连接中断",
            code="BRIDGE_UNREACHABLE",
            details={"reason": f"{type(exc).__name__}: {exc}"},
            fix="确认剪映仍在运行；端口每次启动都会变，重新运行 probe 读取描述文件。",
            retriable=True,
        ) from exc


class Bridge:
    def __init__(self, descriptor, timeout=5.0):
        self.descriptor = descriptor
        self.origin = descriptor["origin"]
        self.headers = {"x-infinite-canvas-native-token": descriptor["token"]}
        self.timeout = timeout
        self._scope = None

    @classmethod
    def discover(cls):
        from .env import find_bridge_descriptor

        descriptor = find_bridge_descriptor()
        if not descriptor:
            raise SkillError(
                "剪映没有运行：找不到 native bridge 描述文件",
                code="BRIDGE_NOT_FOUND",
                fix="打开剪映专业版并保持运行（不需要点任何界面），然后重试。",
                retriable=True,
                details={"descriptor_name": "infinite-canvas-native-bridge.json"},
            )
        return cls(descriptor)

    def health(self, timeout=5.0):
        status, body = _request("GET", self.origin + HEALTH_PATH, self.headers, timeout=timeout)
        if status != 200 or not isinstance(body, dict):
            raise SkillError(
                "剪映桥接 health 检查失败",
                code="BRIDGE_HEALTH_FAILED",
                details={"status": status},
                fix="重启剪映后重试；若仍失败，说明该版本没有开放本地桥接。",
            )
        return body

    def safe_health(self):
        body = self.health()
        app = body.get("compatibility", {}).get("application", {})
        capabilities = body.get("compatibility", {}).get("capabilities", {})
        return {
            "application_path": body.get("application_path"),
            "version": app.get("version"),
            "build": app.get("build"),
            "pid": body.get("pid"),
            "capabilities": _public_capabilities(capabilities),
        }

    def account_scope(self):
        if self._scope:
            return self._scope
        status, body = _request("GET", self.origin + CONTEXT_PATH, self.headers, timeout=60.0)
        if status != 200 or not isinstance(body, dict):
            raise SkillError(
                "读取剪映登录上下文失败",
                code="CONTEXT_FAILED",
                details={"status": status},
                fix="在剪映里登录后重试。",
            )
        principal = (body.get("authContext") or {}).get("principal") or {}
        uid = str(principal.get("userId") or "").strip()
        if not uid:
            raise SkillError(
                "剪映未登录，无法确定导出账号",
                code="NOT_LOGGED_IN",
                fix="在剪映客户端登录账号后重试。",
                details={"authenticated": False},
            )
        self._scope = f"uid:{uid}"
        return self._scope

    def _export_error(self, status, payload):
        code = ""
        if isinstance(payload, dict):
            code = str(payload.get("error") or "")
        message, fix = EXPORT_ERRORS.get(
            code, ("剪映拒绝了导出请求。", "检查草稿结构；必要时重启剪映。")
        )
        return SkillError(
            message,
            code=code or "FILM_EXPORT_FAILED",
            details={"status": status, "native_error": code},
            fix=fix,
            retriable=status >= 500,
        )

    def export(self, draft_dir, output_path, *, fmt="mp4", timeout_ms=300000):
        root = Path(draft_dir).expanduser().resolve()
        info = root / "draft_info.json"
        if not info.is_file():
            raise SkillError(
                "草稿目录缺少 draft_info.json",
                code="DRAFT_NOT_FOUND",
                details={"draft": str(root)},
                fix="先用 build 生成明文草稿，或指向正确的草稿目录。",
            )
        try:
            document = json.loads(info.read_text("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SkillError(
                "draft_info.json 不是明文 JSON（剪映重存后可能被加密）",
                code="DRAFT_ENCRYPTED",
                details={"draft": str(root), "error": str(exc)},
                fix="加密草稿只能由剪映客户端导出；本技能的原生导出只支持明文草稿。",
            ) from exc
        if not isinstance(document, dict):
            raise SkillError("draft_info.json 不是 JSON 对象", code="DRAFT_INVALID",
                             details={"draft": str(root)})

        digest = hashlib.sha256(info.read_bytes()).hexdigest()
        request_id = str(uuid.uuid4())
        out = Path(output_path).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "accountScope": self.account_scope(),
            "requestId": request_id,
            "snapshotId": f"film-export-{request_id}",
            "revision": f"sha256:{digest}",
            "draftPath": str(root),
            "draftSha256": digest,
            "outputPath": str(out),
            "format": fmt,
            "timeoutMs": int(timeout_ms),
        }
        started = time.monotonic()
        status, payload = _request(
            "POST", self.origin + EXPORT_PATH, self.headers, body,
            timeout=timeout_ms / 1000.0 + 30.0,
        )
        if status != 200 or not isinstance(payload, dict) or payload.get("ok") is not True:
            raise self._export_error(status, payload)
        if payload.get("path") and Path(payload["path"]).resolve() != out:
            raise SkillError(
                "剪映回执的输出路径与请求不一致",
                code="EXPORT_RECEIPT_MISMATCH",
                details={"receipt_path": payload.get("path"), "requested": str(out)},
            )
        if not out.is_file() or out.stat().st_size <= 0:
            raise SkillError(
                "剪映报告成功，但输出文件不存在或为空",
                code="EXPORT_EMPTY_OUTPUT",
                details={"path": str(out)},
            )
        return {
            "path": str(out),
            "bytes": out.stat().st_size,
            "format": payload.get("format", fmt),
            "request_id": payload.get("requestId"),
            "revision": payload.get("revision"),
            # duration_ms 是本次导出的墙钟耗时（毫秒），不是成片媒体时长；保留旧字段名
            "duration_ms": int(round((time.monotonic() - started) * 1000)),
            "export_elapsed_ms": int(round((time.monotonic() - started) * 1000)),
            "draft_sha256": digest,
        }
