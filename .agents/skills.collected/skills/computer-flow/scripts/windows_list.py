"""Top-level window and overlay enumeration. Windows only."""

import sys
from dataclasses import asdict, dataclass

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MAX_OWNER_DEPTH = 4


@dataclass(frozen=True)
class WindowInfo:
    handle: int
    owner: int
    process_id: int
    class_name: str
    title: str
    visible: bool
    minimized: bool
    rect: tuple

    @property
    def width(self):
        return self.rect[2] - self.rect[0]

    @property
    def height(self):
        return self.rect[3] - self.rect[1]


def _info(hwnd):
    import win32con
    import win32gui
    import win32process

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return WindowInfo(
        handle=hwnd,
        owner=win32gui.GetWindow(hwnd, win32con.GW_OWNER),
        process_id=pid,
        class_name=win32gui.GetClassName(hwnd),
        title=win32gui.GetWindowText(hwnd),
        visible=bool(win32gui.IsWindowVisible(hwnd)),
        minimized=bool(win32gui.IsIconic(hwnd)),
        rect=(left, top, right, bottom),
    )


def list_windows(process_id=None):
    """Every top-level window, flattened once (EnumWindows already covers all of them)."""
    import win32gui

    handles = []
    win32gui.EnumWindows(lambda hwnd, _: (handles.append(hwnd), True)[1], None)
    windows = []
    for hwnd in handles:
        try:
            info = _info(hwnd)
        except Exception:
            continue
        if process_id is not None and info.process_id != process_id:
            continue
        windows.append(info)
    return windows


def window_rect_or_none(handle):
    """Screen rect of a usable window, or None when minimized/hidden/invalid."""
    import win32gui

    try:
        if not win32gui.IsWindow(handle) or win32gui.IsIconic(handle):
            return None
        left, top, right, bottom = win32gui.GetWindowRect(handle)
    except Exception:
        return None
    if left <= -32000 or top <= -32000 or right - left <= 0 or bottom - top <= 0:
        return None
    if not win32gui.IsWindowVisible(handle):
        return None
    return (left, top, right - left, bottom - top)


def overlay_chain(handle, process_id=None, max_depth=MAX_OWNER_DEPTH):
    """Visible windows owned by `handle`, following owner chains up to max_depth.

    Qt/CEF drawers, slide-out panels, popups and file dialogs are separate
    top-level windows whose GW_OWNER points at the app window. They therefore
    never appear in the host window's screenshot or accessibility tree.

    Owner chains are followed across processes on purpose: shell dialogs such as
    "Save As" are often hosted by a helper/downloader process, so filtering by
    the host window's PID would silently miss them.
    """
    everything = list_windows()
    if process_id is None:
        process_id = next((w.process_id for w in everything if w.handle == handle), None)
    if process_id is None:
        return []
    owned = {handle}
    for _ in range(max_depth):
        added = {w.handle for w in everything if w.owner in owned and w.handle not in owned}
        if not added:
            break
        owned |= added
    return [
        window
        for window in everything
        if window.handle in owned
        and window.handle != handle
        and window.visible
        and not window.minimized
    ]


def find_overlay(handle, process_id=None, min_width=40, min_height=40):
    """Largest usable overlay owned by `handle`, or None."""
    candidates = [
        window
        for window in overlay_chain(handle, process_id)
        if window.width >= min_width and window.height >= min_height
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda w: w.width * w.height)


def wait_for_overlay(handle, before_handles, timeout=8.0, poll=0.3, min_size=(120, 80)):
    """Wait for a *new* overlay window to appear after an action.

    Clicking a button often opens a dialog (Save As, confirm, file picker) that
    lives in a different process or in a Qt popup window. Callers that only
    re-observe the main window will act on stale state and may trigger the same
    dialog twice. Pass the overlay handles seen *before* the action; this returns
    the first handle that is not in that set.
    """
    import time

    deadline = time.monotonic() + timeout
    while True:
        for window in overlay_chain(handle):
            if window.handle in before_handles:
                continue
            if window.width < min_size[0] or window.height < min_size[1]:
                continue
            return window
        if time.monotonic() >= deadline:
            return None
        time.sleep(poll)


def find_windows_by_title(title, process_id=None):
    return [w for w in list_windows(process_id) if w.title == title and w.visible]


def main():
    process_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    import json

    print(json.dumps([asdict(window) for window in list_windows(process_id)], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
