"""Windows capture primitives. All coordinates are physical screen pixels.

Nothing here knows about any specific application: callers pass a window handle
and receive images plus geometry, then decide what to do from the observation.
"""

import ctypes
import sys
import time
from dataclasses import dataclass

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MINIMIZED_SENTINEL = -32000


def is_windows():
    return sys.platform == "win32"


def require_windows():
    if not is_windows():
        raise RuntimeError("desktop capture here is implemented for Windows only")


def set_dpi_awareness():
    """Make every coordinate we read and send physical pixels.

    Without this a process can read 1600x952 for a window that really is
    3200x1904, and clicks computed from one and sent in the other land elsewhere.
    """
    require_windows()
    for attempt in (
        lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2),
        lambda: ctypes.windll.user32.SetProcessDPIAware(),
    ):
        try:
            attempt()
            return True
        except Exception:
            continue
    return False


@dataclass
class Frame:
    """One captured image bound to the screen rectangle it represents.

    `source` records which capture path produced it: "screen" is what the user
    sees; "printwindow" may be stale or partially composited.
    """

    image: object
    origin: tuple
    size: tuple
    source: str = "screen"

    @property
    def width(self):
        return self.size[0]

    @property
    def height(self):
        return self.size[1]

    def to_screen(self, x, y):
        return (self.origin[0] + x, self.origin[1] + y)

    def to_local(self, x, y):
        return (x - self.origin[0], y - self.origin[1])


def window_geometry(handle):
    """Current screen rectangle of a window, rejecting minimized/zero-size states."""
    import win32gui

    if win32gui.IsIconic(handle):
        raise RuntimeError(f"window {handle} is minimized; restore it before capture")
    left, top, right, bottom = win32gui.GetWindowRect(handle)
    width, height = right - left, bottom - top
    if left <= MINIMIZED_SENTINEL or top <= MINIMIZED_SENTINEL or width <= 0 or height <= 0:
        raise RuntimeError(f"window {handle} has no usable geometry: {(left, top, right, bottom)}")
    return (left, top, width, height)


def window_process(handle):
    import win32process

    return win32process.GetWindowThreadProcessId(handle)[1]


def bring_to_front(handle, timeout=2.0, require_exact=False):
    """Restore and raise a window, forcing focus when Windows refuses politely.

    SetForegroundWindow alone is unreliable: Windows blocks foreground stealing
    from a background process, and the click that follows is then delivered to
    whatever window *does* own the foreground. The point sits on the target,
    WindowFromPoint agrees, and still nothing happens — a silent failure that
    looks exactly like "the coordinates are wrong".

    AttachThreadInput borrows the foreground thread's input state so the call is
    treated as coming from the active thread. That is what makes synthetic
    clicks actually land.

    Returns a dict including `exact`. A restored, visible window is usable for
    capture and hit-testing even when focus was refused. Callers about to send
    keystrokes or paste must pass require_exact=True: if the foreground window
    is not exactly `handle`, input would land in somebody else's app, so the
    call raises instead of returning a tolerable-but-wrong state.
    """
    import win32con
    import win32gui

    require_windows()
    if win32gui.IsIconic(handle):
        win32gui.ShowWindow(handle, win32con.SW_RESTORE)

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    pid = window_process(handle)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        foreground = win32gui.GetForegroundWindow()
        if foreground and window_process(foreground) == pid and not win32gui.IsIconic(handle):
            if require_exact and foreground != handle:
                time.sleep(0.12)
                continue
            return {"handle": handle, "foreground": foreground, "exact": foreground == handle}

        current_tid = kernel32.GetCurrentThreadId()
        foreground_tid = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
        target_tid = user32.GetWindowThreadProcessId(handle, None)
        attached = []
        try:
            for tid in {foreground_tid, target_tid}:
                if tid and tid != current_tid and user32.AttachThreadInput(current_tid, tid, True):
                    attached.append(tid)
            user32.BringWindowToTop(handle)
            user32.SetForegroundWindow(handle)
        finally:
            for tid in attached:
                user32.AttachThreadInput(current_tid, tid, False)
        time.sleep(0.12)

    if not win32gui.IsIconic(handle) and win32gui.IsWindowVisible(handle):
        foreground = win32gui.GetForegroundWindow()
        if require_exact:
            raise RuntimeError(
                f"window {handle} did not become the foreground window within {timeout}s "
                f"(foreground is {foreground}); refusing to send input that would land elsewhere"
            )
        return {
            "handle": handle,
            "foreground": foreground,
            "exact": foreground == handle,
            "note": "focus not granted; window is restored and visible",
        }
    raise RuntimeError(f"window {handle} is not usable (minimized or hidden) after {timeout}s")


def _grab(handle, rect):
    import win32gui
    import win32ui
    from PIL import Image

    left, top, width, height = rect
    window_dc = win32gui.GetWindowDC(handle)
    source_dc = win32ui.CreateDCFromHandle(window_dc)
    memory_dc = source_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    try:
        bitmap.CreateCompatibleBitmap(source_dc, width, height)
        memory_dc.SelectObject(bitmap)
        if not ctypes.windll.user32.PrintWindow(handle, memory_dc.GetSafeHdc(), 2):
            raise RuntimeError(f"PrintWindow failed for window {handle}")
        image = Image.frombuffer(
            "RGB", (width, height), bitmap.GetBitmapBits(True), "raw", "BGRX", 0, 1
        )
    finally:
        # Cleanup must never mask the real failure: if the window vanished
        # mid-capture (app restarting, DPI change) DeleteDC raises, and that
        # exception would replace the useful "window is gone" error.
        for cleanup in (
            lambda: memory_dc.DeleteDC(),
            lambda: source_dc.DeleteDC(),
            lambda: win32gui.ReleaseDC(handle, window_dc),
            lambda: win32gui.DeleteObject(bitmap.GetHandle()),
        ):
            try:
                cleanup()
            except Exception:
                pass
    return Frame(image, (left, top), (width, height))


def _looks_blank(image, min_unique_ratio=0.02):
    """Detect a capture that is mostly one colour (black/white).

    PrintWindow returns success but produces a black or stale bitmap for some
    GPU-composited windows (Qt/CEF, windows spanning monitors with different
    DPI). Treating that as a valid observation would make OCR see nothing and
    every subsequent locator fail for the wrong reason.
    """
    small = image.convert("RGB").resize((64, 64))
    pixels = list(small.getdata())
    unique = len(set(pixels))
    return unique <= max(2, int(len(pixels) * min_unique_ratio))


def _has_black_band(image, threshold=0.25):
    """True when a contiguous run of fully-black rows covers the bottom of the image.

    PrintWindow on a Qt window that extends past the screen returns real pixels
    for the visible part and pure black for the rest. A genuine dark-themed UI
    still has anti-aliased glyphs, so "every pixel in the row is 0,0,0" is a
    reliable tell that the capture is truncated rather than dark.
    """
    from PIL import Image

    small = image.convert("RGB")
    width, height = small.size
    if height < 8:
        return False
    step_x = max(1, width // 64)
    black_rows = 0
    for y in range(height - 1, -1, -1):
        row = [small.getpixel((x, y)) for x in range(0, width, step_x)]
        if all(pixel == (0, 0, 0) for pixel in row):
            black_rows += 1
        else:
            break
    return black_rows >= max(4, int(height * threshold))


def _has_empty_stripe(image, min_ink=0.0015):
    """True when a wide vertical stripe of the capture contains no ink at all.

    PrintWindow does not always fail loudly. On some Qt/CEF surfaces it returns
    a bitmap of the right size where only part of the content was composited —
    typically the left portion is real and the rest is flat background. The
    result looks valid, OCR silently finds almost nothing, and locators fail
    with "element not found" for a page that is plainly on screen.

    A real UI never has a full-height stripe of pure background in the middle of
    a table or form, so an ink-free stripe wider than a nav rail is a reliable
    sign of a truncated capture.
    """
    import numpy as np

    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    height, width = gray.shape
    if width < 200 or height < 200:
        return False
    ink = gray < 200
    stripe = max(120, width // 6)
    # Ignore the outer margins; a legitimately empty gutter sits at the edges.
    for start in range(width // 12, width - stripe - width // 12, stripe):
        block = ink[:, start:start + stripe]
        if block.mean() < min_ink:
            return True
    return False


def capture_window(handle, prefer="auto"):
    """Capture a window's pixels, defaulting to what the user actually sees.

    Screen capture is the reference: BitBlt reads the composited desktop, so the
    bitmap always matches the screen. PrintWindow can produce a bitmap that is
    the right size but only partially composited — on Qt/CEF surfaces it often
    returns real pixels on the left and flat background on the right, with no
    error. OCR then finds almost nothing, and locators fail for a page that is
    plainly visible (measured here: 54 elements via PrintWindow vs 139 via
    screen crop, same window, same moment).

    Because that failure is silent, PrintWindow is not used as the default. It is
    still needed for one case: a window that is partly covered by another, where
    screen capture would return somebody else's pixels. Pass prefer="printwindow"
    for that, and check `Frame.source` to know which path ran.

    Screen capture requires the region to be visible; the result is clipped to
    the desktop and the returned origin reflects the clipped top-left so callers
    mapping to screen coordinates do not drift.
    """
    rect = window_geometry(handle)
    if prefer == "printwindow":
        try:
            frame = _grab(handle, rect)
        except RuntimeError:
            frame = None
        if frame is not None and not _looks_blank(frame.image) and not _has_black_band(frame.image):
            frame.source = "printwindow"
            return frame
        frame = _capture_window_from_screen(handle, rect)
        frame.source = "screen"
        return frame

    return _capture_window_from_screen(handle, rect)


def _capture_window_from_screen(handle, rect):
    """Crop the live screen to the window rect, clipped to the visible desktop."""
    screen = capture_screen()
    left, top, width, height = rect
    box = (
        left - screen.origin[0],
        top - screen.origin[1],
        left - screen.origin[0] + width,
        top - screen.origin[1] + height,
    )
    clipped = box[0] < 0 or box[1] < 0 or box[2] > screen.width or box[3] > screen.height
    safe = (
        max(box[0], 0),
        max(box[1], 0),
        min(box[2], screen.width),
        min(box[3], screen.height),
    )
    if safe[2] - safe[0] < 2 or safe[3] - safe[1] < 2:
        raise RuntimeError(
            f"window {handle} is off-screen and PrintWindow produced no usable image; "
            f"window rect {rect}, screen {screen.size}"
        )
    cropped = screen.image.crop(safe)
    if clipped:
        # Off-screen parts have no pixels; report the real origin so callers
        # mapping local coordinates to screen do not silently drift.
        return Frame(cropped, (left + (safe[0] - box[0]), top + (safe[1] - box[1])), cropped.size)
    return Frame(cropped, (left, top), cropped.size)


def capture_region(rect):
    """Screen pixels of an arbitrary rectangle, taken from the visible desktop."""
    import win32gui
    import win32ui
    from PIL import Image

    require_windows()
    left, top, width, height = rect
    if width <= 0 or height <= 0:
        raise RuntimeError(f"invalid region {(left, top, width, height)}")
    desktop_dc = win32gui.GetWindowDC(win32gui.GetDesktopWindow())
    source_dc = win32ui.CreateDCFromHandle(desktop_dc)
    memory_dc = source_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    try:
        bitmap.CreateCompatibleBitmap(source_dc, width, height)
        memory_dc.SelectObject(bitmap)
        memory_dc.BitBlt((0, 0), (width, height), source_dc, (left, top), 0x00CC0020)
        image = Image.frombuffer(
            "RGB", (width, height), bitmap.GetBitmapBits(True), "raw", "BGRX", 0, 1
        )
    finally:
        memory_dc.DeleteDC()
        source_dc.DeleteDC()
        win32gui.ReleaseDC(win32gui.GetDesktopWindow(), desktop_dc)
        win32gui.DeleteObject(bitmap.GetHandle())
    return Frame(image, (left, top), (width, height))


def capture_screen():
    import win32api

    return capture_region(
        (
            win32api.GetSystemMetrics(76),
            win32api.GetSystemMetrics(77),
            win32api.GetSystemMetrics(78),
            win32api.GetSystemMetrics(79),
        )
    )


def window_under_point(x, y):
    """Top-level window actually receiving a click at this physical point."""
    import win32con
    import win32gui

    hwnd = win32gui.WindowFromPoint((round(x), round(y)))
    if not hwnd:
        return None
    return win32gui.GetAncestor(hwnd, win32con.GA_ROOT) or hwnd


def visibility_of(window_frame, screen_frame, step=8):
    """How closely the window frame matches the same area of the live screen.

    High difference means the window is covered or offscreen, so injected clicks
    would not reach it. Returns measurements so callers can report evidence.
    """
    left, top, width, height = (
        window_frame.origin[0],
        window_frame.origin[1],
        window_frame.width,
        window_frame.height,
    )
    box = (
        left - screen_frame.origin[0],
        top - screen_frame.origin[1],
        left - screen_frame.origin[0] + width,
        top - screen_frame.origin[1] + height,
    )
    clipped = box[0] < 0 or box[1] < 0 or box[2] > screen_frame.width or box[3] > screen_frame.height
    safe = (
        max(box[0], 0),
        max(box[1], 0),
        min(box[2], screen_frame.width),
        min(box[3], screen_frame.height),
    )
    if safe[2] - safe[0] < 2 or safe[3] - safe[1] < 2:
        return {"comparable": False, "clipped": True, "mean_abs_diff": None, "samples": 0}

    window_pixels = window_frame.image.load()
    screen_pixels = screen_frame.image.load()
    dx = safe[0] - box[0]
    dy = safe[1] - box[1]
    total = 0
    samples = 0
    for y in range(dy, safe[3] - box[1], step):
        for x in range(dx, safe[2] - box[0], step):
            wr, wg, wb = window_pixels[x, y][:3]
            sr, sg, sb = screen_pixels[box[0] + x, box[1] + y][:3]
            total += abs(wr - sr) + abs(wg - sg) + abs(wb - sb)
            samples += 1
    if samples == 0:
        return {"comparable": False, "clipped": clipped, "mean_abs_diff": None, "samples": 0}
    mean = total / (samples * 3)
    return {
        "comparable": True,
        "clipped": clipped,
        "mean_abs_diff": round(mean, 2),
        "samples": samples,
        "looks_visible": mean <= 12.0,
    }


def blocker_at(x, y, expected_handle=None, allowed_handles=()):
    """Identify which top-level window currently covers a physical point.

    Returns the blocking window's info, or None when the point is on the
    expected window itself (or on a handle the caller explicitly expected,
    e.g. an overlay this step was told about). A same-process window that is
    not the target still blocks: a modal dialog owned by the app covers the
    main window's controls just as thoroughly as a foreign window does.
    """
    require_windows()
    hwnd = window_under_point(x, y)
    if hwnd is None:
        return None
    if expected_handle is not None and hwnd == expected_handle:
        return None
    if hwnd in set(allowed_handles):
        return None
    info = {
        "handle": hwnd,
        "title": None,
        "process_id": None,
        "class_name": None,
    }
    try:
        import win32gui

        info["title"] = win32gui.GetWindowText(hwnd)
        info["class_name"] = win32gui.GetClassName(hwnd)
        info["process_id"] = window_process(hwnd)
    except Exception:
        pass
    return info


def validate_point_in_window(x, y, handle):
    """Refuse to act on a point that is off the virtual screen, off the window's
    visible area, or computed from a stale/invalid window rectangle.

    Coordinates outside the screen would be clamped by SetCursorPos and click the
    wrong thing; coordinates in the part of a window rectangle that hangs off the
    visible desktop cannot receive real user input either.
    """
    require_windows()
    import win32gui

    if not win32gui.IsWindow(handle):
        raise RuntimeError(f"window {handle} no longer exists; re-discover before acting")
    screen = capture_screen()
    sx, sy = screen.origin
    sw, sh = screen.size
    if not (sx <= x < sx + sw and sy <= y < sy + sh):
        raise RuntimeError(
            f"point {(round(x), round(y))} is outside the virtual screen "
            f"({sx},{sy},{sw}x{sh}); recompute from a fresh observation"
        )
    left, top, width, height = window_geometry(handle)
    if not (left <= x < left + width and top <= y < top + height):
        raise RuntimeError(
            f"point {(round(x), round(y))} is outside window {handle} rect "
            f"{(left, top, left + width, top + height)}; the window moved or resized"
        )
    visible_left = max(left, sx)
    visible_top = max(top, sy)
    visible_right = min(left + width, sx + sw)
    visible_bottom = min(top + height, sy + sh)
    if not (visible_left <= x < visible_right and visible_top <= y < visible_bottom):
        raise RuntimeError(
            f"point {(round(x), round(y))} is in the off-screen part of window {handle}; "
            f"visible area is {(visible_left, visible_top, visible_right, visible_bottom)}"
        )
    return True


MOUSE_FLAGS = {
    "left": (0x0002, 0x0004),
    "right": (0x0008, 0x0010),
    "middle": (0x0020, 0x0040),
}


def click_screen(x, y, window_handle=None, strict=True, button="left", clicks=1, interval=0.04, allowed_handles=()):
    """Click at a physical point after proving the point belongs to the intended window.

    Strict mode requires the window under the cursor to be exactly
    `window_handle` (or one of `allowed_handles`, e.g. an overlay this step
    deliberately targets). A same-process top-level window sitting on top —
    an unexpected modal, tool window, or second document — still blocks the
    click; "same app" does not mean "same control".

    Double-click issues both press/release pairs inside one call and without an
    intervening position check: a second cursor move would exceed the system
    double-click interval, and the application would see two separate clicks
    instead of a WM_LBUTTONDBLCLK.
    """
    require_windows()
    if button not in MOUSE_FLAGS:
        raise ValueError(f"unsupported button: {button}")
    if clicks < 1:
        raise ValueError("clicks must be >= 1")
    if window_handle is not None and strict:
        blocker = blocker_at(x, y, expected_handle=window_handle, allowed_handles=allowed_handles)
        if blocker is not None:
            raise RuntimeError(
                f"point {(round(x), round(y))} is covered by window {blocker['handle']}: {blocker}"
            )
    user32 = ctypes.windll.user32
    from ctypes import wintypes

    user32.SetCursorPos(round(x), round(y))
    landed = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(landed))
    if abs(landed.x - round(x)) > 1 or abs(landed.y - round(y)) > 1:
        raise RuntimeError(f"cursor stopped at {(landed.x, landed.y)}, expected {(round(x), round(y))}")
    down, up = MOUSE_FLAGS[button]
    for index in range(clicks):
        user32.mouse_event(down, 0, 0, 0, 0)
        user32.mouse_event(up, 0, 0, 0, 0)
        if index < clicks - 1:
            time.sleep(interval)
    return (landed.x, landed.y)
