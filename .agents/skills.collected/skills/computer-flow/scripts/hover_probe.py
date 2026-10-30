"""Find controls that only appear (or change icon) on hover.

Static screenshots show the resting state. Many desktop/web UIs swap an icon on
hover — e.g. a calendar glyph becomes a "clear" button, a row reveals delete
actions, a toolbar shows labels. A plan built only from the resting state will
either miss those controls or click the wrong thing (clicking a calendar icon
that happened to be a clear button in disguise).

This module probes by moving the pointer and diffing captures. It never clicks.

Hover probing is heuristic by nature: caret blink and cursor sprites also change
pixels. Callers should treat "no stable difference" as inconclusive rather than
proof that nothing is hidden.
"""

import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _capture_patch(frame, box):
    return frame.image.crop(box)


def _diff_ratio(a, b, threshold=40):
    """Fraction of pixels that changed by more than `threshold`."""
    import numpy as np

    left = np.asarray(a.convert("L"), dtype=np.int16)
    right = np.asarray(b.convert("L"), dtype=np.int16)
    if left.shape != right.shape:
        return 1.0
    changed = np.abs(left - right) > threshold
    return float(changed.sum()) / max(changed.size, 1)


def probe_hover(
    handle,
    points,
    settle=0.6,
    rest=(50, 50),
    diff_threshold=0.02,
    patch=48,
    baseline_repeats=2,
    abort=None,
):
    """Hover each point and report where the UI changed.

    `points` are screen coordinates. For each one the pointer moves there, the
    window is re-captured, and the local patch is compared against a baseline
    taken with the pointer parked at `rest` (a corner, away from the target).

    `baseline_repeats` guards against blink/noise: the resting patch is sampled
    twice and any point whose own resting noise already exceeds the threshold is
    reported as unstable instead of "reacts to hover".

    `abort` is an execution_safety.AbortFlag; each point costs seconds of
    capture and cursor movement, so it is checked per point.

    Returns a list of {point, changed, ratio, unstable} dicts.
    """
    from windows_capture import capture_window

    import ctypes

    user32 = ctypes.windll.user32
    # Use the frame's own origin: capture_window may fall back to a screen crop,
    # whose origin can differ from GetWindowRect when the window hangs off-screen.
    reference = capture_window(handle)
    origin_x, origin_y = reference.origin

    def local_box(px, py):
        half = patch // 2
        x0 = max(0, int(px - origin_x - half))
        y0 = max(0, int(py - origin_y - half))
        x1 = max(x0 + 1, int(px - origin_x + half))
        y1 = max(y0 + 1, int(py - origin_y + half))
        return (x0, y0, x1, y1)

    def sample(px, py):
        frame = capture_window(handle)
        return _capture_patch(frame, local_box(px, py))

    user32.SetCursorPos(int(rest[0]), int(rest[1]))
    time.sleep(settle)
    first = {point: sample(*point) for point in points}
    unstable = set()
    if baseline_repeats > 1:
        time.sleep(settle)
        for point in points:
            again = sample(*point)
            if _diff_ratio(first[point], again) >= diff_threshold:
                unstable.add(point)
                first[point] = again

    results = []
    for point in points:
        if abort is not None:
            abort.check()
        user32.SetCursorPos(int(point[0]), int(point[1]))
        time.sleep(settle)
        current = sample(*point)
        ratio = _diff_ratio(first[point], current)
        results.append({
            "point": [round(point[0], 1), round(point[1], 1)],
            "changed": ratio >= diff_threshold and point not in unstable,
            "ratio": round(ratio, 4),
            "unstable": point in unstable,
        })
    user32.SetCursorPos(int(rest[0]), int(rest[1]))
    return results


def scan_row(handle, y, x_start, x_end, step=8, **kwargs):
    """Convenience: probe every `step` pixels along a horizontal band."""
    points = [(x, y) for x in range(int(x_start), int(x_end), int(step))]
    return probe_hover(handle, points, **kwargs)


def classify(results, min_lift=1.5):
    """Separate real hotspots from baseline noise using a step, not an absolute cut.

    In practice a whole row of points shows some non-zero diff (anti-aliasing,
    caret blink, sub-pixel text rendering). Those sit at a consistent floor.
    A control that actually reacts to hover stands clearly above that floor.
    This returns (hotspots, floor) where `floor` is the median ratio and a
    hotspot is any point at least `min_lift` times the floor.
    """
    ratios = sorted(item["ratio"] for item in results if not item.get("unstable"))
    if not ratios:
        return [], 0.0
    mid = len(ratios) // 2
    floor = ratios[mid] if len(ratios) % 2 else (ratios[mid - 1] + ratios[mid]) / 2
    if floor <= 0:
        hot = [item for item in results if item["ratio"] > 0 and not item.get("unstable")]
        return hot, 0.0
    hot = [
        item for item in results
        if not item.get("unstable") and item["ratio"] >= floor * min_lift
    ]
    return hot, round(floor, 4)


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Probe which screen points react to hover (icon swaps, revealed actions)."
    )
    parser.add_argument("--handle", type=int, required=True)
    parser.add_argument("--y", type=float, required=True, help="band centre, screen Y")
    parser.add_argument("--x-start", type=float, required=True)
    parser.add_argument("--x-end", type=float, required=True)
    parser.add_argument("--step", type=int, default=8)
    parser.add_argument("--settle", type=float, default=0.6)
    parser.add_argument("--threshold", type=float, default=0.02)
    parser.add_argument("--min-lift", type=float, default=1.5)
    args = parser.parse_args()

    from execution_safety import AbortFlag, DesktopLock, ExecutionBusy, listen_for_escape
    from windows_capture import set_dpi_awareness

    set_dpi_awareness()
    abort = AbortFlag(scope=str(args.handle))
    abort.clear()
    try:
        # Hover probing moves the real cursor; it must not run next to another
        # automation session, and it must be interruptible.
        with DesktopLock(owner=f"hover_probe:{args.handle}"):
            listen_for_escape(abort)
            results = scan_row(
                args.handle, args.y, args.x_start, args.x_end,
                step=args.step, settle=args.settle, diff_threshold=args.threshold,
                abort=abort,
            )
            hotspots, floor = classify(results, min_lift=args.min_lift)
            print(json.dumps({
                "probed": len(results),
                "noise_floor": floor,
                "hotspots": hotspots,
                "hint": "放大每个 hotspot 对比静息/悬停截图，确认它变成了什么再写进 plan",
            }, ensure_ascii=False, indent=2))
    except ExecutionBusy as exc:
        print(json.dumps({"busy": True, "reason": str(exc)}, ensure_ascii=False))
        raise SystemExit(5)


if __name__ == "__main__":
    main()
