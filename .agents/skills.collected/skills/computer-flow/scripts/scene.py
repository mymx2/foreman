"""Describe the desktop the way a person looking at the screen would.

Reading OCR text is not "looking at the screen". A person also perceives, at a
glance: how many monitors there are, which window has focus, how big each window
is, which ones overlap, and whether a dialog has appeared on top. Every one of
those facts changes what the next action should be, and none of them shows up in
an element list.

This module answers those questions in one call so a caller can print a scene
summary before acting, instead of inferring the situation from element counts.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MIN_USEFUL = (120, 80)


def displays():
    """Monitors with their rects and DPI scale."""
    import ctypes
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    found = []

    def callback(hmonitor, hdc, rect, data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        ctypes.windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(info))
        dpi_x = ctypes.c_uint()
        dpi_y = ctypes.c_uint()
        try:
            ctypes.windll.shcore.GetDpiForMonitor(hmonitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
        except Exception:
            dpi_x.value = 96
        found.append({
            "primary": bool(info.dwFlags & 1),
            "rect": [info.rcMonitor.left, info.rcMonitor.top, info.rcMonitor.right, info.rcMonitor.bottom],
            "work_area": [info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom],
            "dpi": dpi_x.value,
            "scale": round(dpi_x.value / 96.0, 2),
            # What an application actually gets to lay itself out in.
            "logical_size": [
                int((info.rcMonitor.right - info.rcMonitor.left) / max(dpi_x.value / 96.0, 0.01)),
                int((info.rcMonitor.bottom - info.rcMonitor.top) / max(dpi_x.value / 96.0, 0.01)),
            ],
            "logical_work": [
                int((info.rcWork.right - info.rcWork.left) / max(dpi_x.value / 96.0, 0.01)),
                int((info.rcWork.bottom - info.rcWork.top) / max(dpi_x.value / 96.0, 0.01)),
            ],
        })
        return True

    callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.RECT), ctypes.c_void_p
    )
    ctypes.windll.user32.EnumDisplayMonitors(None, None, callback_type(callback), 0)
    return found


def scene(handle=None):
    """Build a description of what is on screen right now.

    `handle` marks the window the caller cares about; its relations to the rest
    of the scene (front-most, covered, off-screen, size) drive the verdict.
    """
    import ctypes
    import win32api
    import win32gui
    from windows_list import list_windows, overlay_chain

    foreground = win32gui.GetForegroundWindow()
    screens = displays()

    def dpi_of(hwnd):
        try:
            return ctypes.windll.user32.GetDpiForWindow(hwnd)
        except Exception:
            return None

    visible = []
    for w in list_windows():
        if not w.visible or w.minimized:
            continue
        if w.width < MIN_USEFUL[0] or w.height < MIN_USEFUL[1]:
            continue
        if not (w.title or "").strip() and w.class_name != "#32770":
            continue
        visible.append(w)

    # Z order from EnumWindows is front-to-back, so index 0 is topmost.
    order = {w.handle: index for index, w in enumerate(visible)}
    target = next((w for w in visible if w.handle == handle), None)
    dialogs = [w for w in visible if w.class_name == "#32770"]

    result = {
        "screens": screens,
        "virtual": {
            "left": win32api.GetSystemMetrics(76),
            "top": win32api.GetSystemMetrics(77),
            "width": win32api.GetSystemMetrics(78),
            "height": win32api.GetSystemMetrics(79),
        },
        "foreground": {
            "handle": foreground,
            "title": win32gui.GetWindowText(foreground)[:60],
            "class_name": win32gui.GetClassName(foreground),
        },
        "windows": [
            {
                "handle": w.handle,
                "title": w.title[:60],
                "class_name": w.class_name,
                "process_id": w.process_id,
                "rect": list(w.rect),
                "size": [w.width, w.height],
                "z_rank": order[w.handle],
                "dpi": dpi_of(w.handle),
            }
            for w in visible
        ],
        "dialogs": [{"handle": d.handle, "title": d.title[:60]} for d in dialogs],
    }

    if target is not None:
        scale = (dpi_of(target.handle) or 96) / 96.0
        result["target"] = {
            "handle": target.handle,
            "title": target.title[:60],
            "rect": list(target.rect),
            "size": [target.width, target.height],
            "screen_size": [target.width / scale, target.height / scale],
            "dpi": dpi_of(target.handle),
            "is_foreground": target.handle == foreground,
            "z_rank": order[target.handle],
            "covered_by": [
                {"handle": other.handle, "title": other.title[:40]}
                for other in visible
                if other.handle != target.handle
                and order.get(other.handle, 10 ** 6) < order.get(target.handle, 0)
                and _overlaps(other.rect, target.rect)
                and other.width * other.height > target.width * target.height * 0.5
            ],
        }
        try:
            overlays = overlay_chain(target.handle)
            result["target"]["overlays"] = [
                {"handle": o.handle, "size": [o.width, o.height], "title": o.title[:40]}
                for o in overlays
            ]
        except Exception:
            result["target"]["overlays"] = []

    return result


def _overlaps(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def verdict(report):
    """Turn the scene into the handful of facts that decide the next action."""
    notes = []

    # Layer 1: displays. Everything else is read through this lens, because an
    # app lays itself out for the *logical* size it is given, not physical pixels.
    screens = report.get("screens") or []
    if len(screens) > 1:
        scales = {s["scale"] for s in screens}
        if len(scales) > 1:
            detail = ", ".join(str(s["scale"]) + "x" for s in screens)
            notes.append(
                "多显示器且缩放不一致（" + detail + "）"
                " — 同一窗口拖到另一块屏会换一套布局，坐标和缓存都要重算"
            )
        primary = next((s for s in screens if s["primary"]), None)
        if primary and primary["scale"] != 1.0:
            notes.append(
                f"主屏缩放 {primary['scale']}x —— 不要假设主屏是 100%；"
                f"应用在主屏拿到的逻辑画布只有 {int((primary['rect'][2]-primary['rect'][0])/primary['scale'])}"
                f"×{int((primary['rect'][3]-primary['rect'][1])/primary['scale'])}"
            )

    target = report.get("target")
    if target is None:
        notes.append("目标窗口不在可见窗口列表里：可能被关闭、最小化，或标题不匹配")
        return notes

    # Layer 2: the window's own footprint, expressed in logical units.
    if target.get("screen_size"):
        logical_w, logical_h = target["screen_size"]
        notes.append(
            f"目标逻辑尺寸 {int(logical_w)}×{int(logical_h)}（物理 {target['size'][0]}×{target['size'][1]}，"
            f"{target.get('dpi')} DPI）"
        )
        if logical_w < 1000 or logical_h < 700:
            notes.append(
                "  ↑ 紧凑布局：侧栏可能折叠、导航项被压缩或收进「更多」、部分入口需要滚动才出现。"
                "不要假设所有入口都在当前可见区域，也不要为此把窗口挪到主屏（会占用用户主视角）"
            )

    # Layer 3: focus, occlusion, dialogs, overlays.
    if report["dialogs"]:
        notes.append(
            "有模态对话框挡在上面：" + ", ".join(d["title"] for d in report["dialogs"]) +
            " — 先处理它，否则后续点击会落到对话框上"
        )
    if not target["is_foreground"]:
        notes.append(
            f"目标不是前台（前台是 {report['foreground']['title']!r}）"
            " — 合成点击会被前台窗口接收，必须先强制激活"
        )
    if target["covered_by"]:
        notes.append("目标被更大的窗口压住：" + ", ".join(c["title"] for c in target["covered_by"]))
    if target["overlays"]:
        notes.append(f"目标有 {len(target['overlays'])} 个附属浮层窗口（抽屉/气泡/下拉）")

    if len(notes) == 1 and notes[0].startswith("目标逻辑尺寸"):
        notes.append("场景正常：窗口尺寸合理、在前台、无遮挡、无对话框")
    return notes


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Describe the current desktop scene.")
    parser.add_argument("--handle", type=int, help="window to describe in detail")
    parser.add_argument("--title", help="find the window by title substring instead")
    args = parser.parse_args()

    from windows_capture import set_dpi_awareness
    set_dpi_awareness()

    handle = args.handle
    if handle is None and args.title:
        import win32gui
        from windows_list import list_windows
        match = [w for w in list_windows() if w.visible and args.title in (w.title or "")]
        if match:
            handle = match[0].handle

    report = scene(handle)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print()
    print("判定：")
    for note in verdict(report):
        print("  -", note)


if __name__ == "__main__":
    main()
