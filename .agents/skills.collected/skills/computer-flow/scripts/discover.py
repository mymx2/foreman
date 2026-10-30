"""Discover displays and application windows before automating anything.

Discovery is read-only: it never activates a window or changes focus. Callers use
the result to pick a target by name/process, instead of hard-coding a handle that
changes between runs and between machines.
"""

import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def list_displays():
    """Physical monitors and their working areas, in screen pixels."""
    import ctypes
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    displays = []

    def _callback(hMonitor, hdc, rect, data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(info))
        displays.append(
            {
                "handle": int(hMonitor),
                "primary": bool(info.dwFlags & 1),
                "rect": [info.rcMonitor.left, info.rcMonitor.top, info.rcMonitor.right, info.rcMonitor.bottom],
                "work_area": [info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom],
            }
        )
        return True

    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.RECT), ctypes.c_void_p)
    ctypes.windll.user32.EnumDisplayMonitors(None, None, callback_type(_callback), 0)
    return displays


def virtual_screen():
    """Combined bounds of every display, which is what screen coordinates mean."""
    import win32api

    left = win32api.GetSystemMetrics(76)
    top = win32api.GetSystemMetrics(77)
    width = win32api.GetSystemMetrics(78)
    height = win32api.GetSystemMetrics(79)
    return {"left": left, "top": top, "width": width, "height": height}


def find_windows(title_contains=None, process_name=None, visible_only=True):
    """Find candidate top-level windows by title substring or executable name."""
    from windows_list import list_windows

    process_lookup = None
    if process_name:
        try:
            import psutil

            process_lookup = psutil
        except ImportError:
            process_lookup = None

    results = []
    for window in list_windows():
        if visible_only and not window.visible:
            continue
        if window.minimized:
            continue
        if title_contains and title_contains.lower() not in window.title.lower():
            continue
        if process_name:
            name = ""
            if process_lookup is not None:
                try:
                    name = process_lookup.Process(window.process_id).name()
                except Exception:
                    name = ""
            if process_name.lower() not in name.lower():
                continue
        results.append(window)
    return results


def describe_window(window, include_title=True):
    """Window facts for logs. Titles can carry document names, so callers may mask them."""
    return {
        "handle": window.handle,
        "title": window.title if include_title else mask_title(window.title),
        "class_name": window.class_name,
        "process_id": window.process_id,
        "owner": window.owner,
        "rect": list(window.rect),
        "size": [window.width, window.height],
        "visible": window.visible,
        "minimized": window.minimized,
    }


def mask_title(title, keep=6):
    """Keep just enough of a title to identify the app, not its contents."""
    if not title:
        return ""
    if len(title) <= keep:
        return title
    return title[:keep] + "…"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Discover displays and candidate application windows.")
    parser.add_argument("--title", help="substring to match in the window title")
    parser.add_argument("--process", help="executable name to match, e.g. app.exe")
    parser.add_argument("--all", action="store_true", help="include invisible/minimized windows")
    parser.add_argument("--full-titles", action="store_true",
                        help="print complete window titles (they may contain document names)")
    args = parser.parse_args()

    payload = {
        "displays": list_displays(),
        "virtual_screen": virtual_screen(),
        "windows": [
            describe_window(w, include_title=args.full_titles)
            for w in find_windows(args.title, args.process, visible_only=not args.all)
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
