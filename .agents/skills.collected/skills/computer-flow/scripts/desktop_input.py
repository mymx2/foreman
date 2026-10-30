"""Replace text in a focused edit control without losing the user's clipboard."""

import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TEXT_FORMATS = {1: "CF_TEXT", 13: "CF_UNICODETEXT", 7: "CF_OEMTEXT"}


def backup_clipboard():
    """Snapshot every format currently on the clipboard, not just text."""
    import win32clipboard

    backup = []
    win32clipboard.OpenClipboard()
    try:
        fmt = 0
        while True:
            try:
                fmt = win32clipboard.EnumClipboardFormats(fmt)
            except ValueError:
                break
            if not fmt:
                break
            try:
                if fmt in TEXT_FORMATS:
                    backup.append((fmt, win32clipboard.GetClipboardData(fmt)))
                else:
                    raw = win32clipboard.GetClipboardData(fmt)
                    backup.append((fmt, raw))
            except Exception:
                # Formats that must be rendered on demand are skipped, not dropped silently.
                continue
    finally:
        win32clipboard.CloseClipboard()
    return backup


def restore_clipboard(backup):
    """Put the previous clipboard back, never leaving our own text behind.

    Formats that cannot be restored are dropped, but the clipboard is always
    emptied first so a failed restore cannot leave the pasted secret sitting
    there for the user's next Ctrl+V.
    """
    import win32clipboard

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        restored = 0
        for fmt, data in backup:
            try:
                win32clipboard.SetClipboardData(fmt, data)
                restored += 1
            except Exception:
                continue
        return restored
    finally:
        win32clipboard.CloseClipboard()


def focused_edit_value():
    """Read the current value of the UIA-focused control, when it exposes one.

    Returns None when the focused control has no readable value (self-drawn
    editors typically don't); callers treat None as "cannot verify", not failure.
    """
    try:
        from pywinauto import Desktop

        focused = Desktop(backend="uia").get_focused()
        if focused is None:
            return None
        try:
            value = focused.get_value()
        except Exception:
            value = None
        if value is not None:
            return str(value)
        try:
            text = focused.window_text()
            return text if isinstance(text, str) else None
        except Exception:
            return None
    except Exception:
        return None


def focused_control_info():
    """Best-effort description of the currently focused control for evidence."""
    try:
        from pywinauto import Desktop

        focused = Desktop(backend="uia").get_focused()
        if focused is None:
            return None
        info = focused.element_info
        return {
            "name": getattr(info, "name", "") or "",
            "control_type": getattr(info, "control_type", "") or "",
            "automation_id": getattr(info, "automation_id", "") or "",
        }
    except Exception:
        return None


def read_selection_text(handle, activate=None, settle=0.4, restore=True):
    """Read what is currently inside a container by selecting and copying it.

    OCR guesses text from pixels and misreads small, low-contrast or icon-adjacent
    glyphs — and returns nothing at all on many self-drawn pages. The application
    itself knows the exact string, so Ctrl+A / Ctrl+C is both more accurate and
    often faster.

    Costs: it overwrites the clipboard (backed up and restored by default) and it
    changes the selection in the target container. Callers should clear the
    selection afterwards if the next step depends on it.

    Returns the copied text, or None when the container does not support it —
    that is a normal outcome, not an error; fall back to OCR.
    """
    from pywinauto import Desktop
    from pywinauto.keyboard import send_keys
    import time as _time

    window = Desktop(backend="uia").window(handle=handle)
    if not window.exists(timeout=1):
        return None
    window.set_focus()
    if activate is not None:
        activate(handle)

    backup = backup_clipboard() if restore else None
    try:
        import win32clipboard

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
        finally:
            win32clipboard.CloseClipboard()

        send_keys("^a")
        _time.sleep(0.15)
        send_keys("^c")
        _time.sleep(settle)

        win32clipboard.OpenClipboard()
        try:
            text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        except Exception:
            text = ""
        finally:
            win32clipboard.CloseClipboard()
        return text or None
    except Exception:
        return None
    finally:
        if restore and backup is not None:
            try:
                restore_clipboard(backup)
            except Exception:
                pass


def clear_selection(settle=0.15):
    """Drop a selection left behind by read_selection_text."""
    from pywinauto.keyboard import send_keys

    send_keys("{ESC}")
    time.sleep(settle)


def replace_text(handle, text, activate=None, verify=True):
    """Paste into the focused control, restoring the previous clipboard in all paths.

    After the paste, tries to read the value back through UIA. A control with no
    readable value (self-drawn editor) skips verification; a control whose value
    contradicts the paste raises, since ^a/^v then likely hit the wrong control.
    """
    from pywinauto import Desktop
    from pywinauto.keyboard import send_keys

    window = Desktop(backend="uia").window(handle=handle)
    if not window.exists(timeout=1):
        raise RuntimeError(f"window {handle} is not available")
    window.set_focus()
    if activate is not None:
        activate(handle)

    backup = backup_clipboard()
    try:
        import win32clipboard

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        send_keys("^a^v")
        time.sleep(0.2)
        if verify:
            current = focused_edit_value()
            # ^a + ^v replaces the edit's content, so the post-paste value should
            # equal what we sent. A containment check would silently pass when the
            # focus is on a label whose text happens to include our target.
            if current is not None and current.rstrip("\r\n") != text.rstrip("\r\n"):
                raise RuntimeError(
                    "focused control does not contain the pasted text; "
                    f"focus was likely not on the intended edit field (focused={focused_control_info()})"
                )
    finally:
        try:
            restore_clipboard(backup)
        except Exception:
            # Last resort: clear the clipboard, but only if it still holds the text
            # we pasted. If the user has pressed Ctrl+C in between, the clipboard
            # is theirs now — wiping it would silently destroy their fresh copy.
            try:
                import win32clipboard

                win32clipboard.OpenClipboard()
                try:
                    try:
                        current = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                    except Exception:
                        current = None
                    if current == text:
                        win32clipboard.EmptyClipboard()
                finally:
                    win32clipboard.CloseClipboard()
            except Exception:
                pass


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Replace text in a focused control via clipboard.")
    parser.add_argument("--handle", type=int, required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--observation-dir", type=Path, required=True)
    args = parser.parse_args()

    from execution_safety import AbortFlag, DesktopLock, ExecutionBusy, listen_for_escape
    from windows_capture import bring_to_front, capture_window, set_dpi_awareness

    set_dpi_awareness()
    abort = AbortFlag(scope=str(args.handle))
    abort.clear()
    try:
        # Typing shares the desktop with every other automation session; take
        # the same exclusive lock flow_run holds, or two runs interleave keys.
        with DesktopLock(owner=f"desktop_input:{args.handle}"):
            listen_for_escape(abort)
            abort.check()
            bring_to_front(args.handle, require_exact=True)
            abort.check()
            replace_text(args.handle, args.text)
            abort.check()
            time.sleep(0.3)
            args.observation_dir.mkdir(parents=True, exist_ok=True)
            capture_window(args.handle).image.save(args.observation_dir / "after.png")
            print(json.dumps({"action_sent": True, "after_image": str(args.observation_dir / "after.png")}))
    except ExecutionBusy as exc:
        print(json.dumps({"busy": True, "reason": str(exc)}, ensure_ascii=False))
        raise SystemExit(5)


if __name__ == "__main__":
    main()
