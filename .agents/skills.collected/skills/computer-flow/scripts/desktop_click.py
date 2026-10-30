"""Locate text inside a window's current observation and click it.

Every geometric input is relative to the window or region being observed right
now, so this works regardless of window size, position, DPI or app version.
"""

import argparse
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Click a text element in the current window observation.")
    parser.add_argument("--handle", type=int, required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--match", choices=["exact", "suffix", "contains"], default="exact")
    parser.add_argument("--region", type=float, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
                        help="fractions of the observed container, e.g. 0.5 0 1 1 for the right half")
    parser.add_argument("--source", action="append", choices=["ocr", "uia"],
                        help="restrict to these element sources (default: all)")
    parser.add_argument("--minimum-confidence", type=float, default=0.85)
    parser.add_argument("--expect-text")
    parser.add_argument("--expect-match", choices=["exact", "suffix", "contains"], default="exact")
    parser.add_argument("--expect-region", type=float, nargs=4)
    parser.add_argument("--wait", type=float, default=2.0)
    parser.add_argument("--observation-dir", type=Path, required=True)
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--stall-limit", type=int, default=2)
    parser.add_argument("--allow-occlusion", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    from desktop_action import (
        SelectionError,
        StallTracker,
        load_state,
        save_state,
        select,
        state_digest,
        write_json,
    )
    from desktop_observe import observe, save
    from execution_safety import AbortFlag, DesktopLock, Aborted, ExecutionBusy, listen_for_escape
    from windows_capture import (
        blocker_at,
        bring_to_front,
        capture_screen,
        click_screen,
        set_dpi_awareness,
        validate_point_in_window,
        window_process,
    )

    set_dpi_awareness()
    args.observation_dir.mkdir(parents=True, exist_ok=True)
    abort = AbortFlag(scope=str(args.handle))
    abort.clear()

    try:
        with DesktopLock(owner=f"desktop_click:{args.handle}"):
            listener = listen_for_escape(abort)

            activation = bring_to_front(args.handle)
            before = observe(args.handle)
            save(before, args.observation_dir / "before.json")
            capture_screen().image.save(args.observation_dir / "before-screen.png")

            result = {
                "handle": args.handle,
                "snapshot_id": before.snapshot_id,
                "activation": activation,
                "before_digest": state_digest(before.elements),
                "element_count": {"window": len(before.window), "overlay": len(before.overlays)},
            }

            try:
                target = select(
                    before.elements,
                    args.text,
                    container=before.rect,
                    match=args.match,
                    minimum_confidence=args.minimum_confidence,
                    region=args.region,
                    sources=args.source,
                )
            except SelectionError as exc:
                result["error"] = str(exc)
                result["retry"] = "safe_after_reobserve"
                write_json(args.observation_dir / "result.json", result)
                print(json.dumps(result, ensure_ascii=False))
                raise SystemExit(2)

            abort.check()
            point = target.center
            result["target"] = {
                "label": target.label,
                "source": target.source,
                "snapshot": target.snapshot,
                "screen": [round(point[0], 1), round(point[1], 1)],
            }

            try:
                validate_point_in_window(point[0], point[1], args.handle)
            except RuntimeError as exc:
                result["error"] = str(exc)
                result["retry"] = "safe_after_reobserve"
                write_json(args.observation_dir / "result.json", result)
                print(json.dumps(result, ensure_ascii=False))
                raise SystemExit(2)

            blocker = blocker_at(point[0], point[1], expected_handle=args.handle)
            result["occlusion"] = {"blocked": blocker is not None, "blocker": blocker}
            if blocker is not None and not args.allow_occlusion:
                result["retry"] = "never"
                write_json(args.observation_dir / "result.json", result)
                print(json.dumps(result, ensure_ascii=False))
                raise SystemExit(4)

            if args.dry_run:
                result["action_sent"] = False
                write_json(args.observation_dir / "result.json", result)
                print(json.dumps(result, ensure_ascii=False))
                return

            clicked = click_screen(point[0], point[1], window_handle=args.handle)
            result["sent"] = {"at": list(clicked), "observed": False}
            time.sleep(args.wait)

            abort.check()
            after = observe(args.handle)
            save(after, args.observation_dir / "after.json")
            capture_screen().image.save(args.observation_dir / "after-screen.png")
            result["after_digest"] = state_digest(after.elements)
            result["changed"] = result["before_digest"] != result["after_digest"]
            result["sent"]["observed"] = result["changed"]
            result["observed_state"] = {
                "snapshot_id": after.snapshot_id,
                "element_count": {"window": len(after.window), "overlay": len(after.overlays)},
            }

            assertion = {"skipped": True}
            if args.expect_text:
                try:
                    expected = select(
                        after.elements,
                        args.expect_text,
                        container=after.rect,
                        match=args.expect_match,
                        minimum_confidence=args.minimum_confidence,
                        region=args.expect_region,
                        sources=args.source,
                    )
                    assertion = {"passed": True, "label": expected.label, "source": expected.source}
                except SelectionError as exc:
                    assertion = {"passed": False, "error": str(exc), "retry": "never"}
            result["assertion"] = assertion

            state_path = args.state_file or (args.observation_dir / "state.json")
            state = load_state(state_path)
            key = f"{args.handle}:{args.text}:{args.region}"
            entry, stalled = StallTracker(limit=args.stall_limit).update(
                state.get(key), result["after_digest"], result["changed"]
            )
            state[key] = entry
            save_state(state_path, state)
            result["stall_count"] = entry["count"]
            result["stalled"] = stalled
            if stalled:
                result["retry"] = "diagnose_first"

            write_json(args.observation_dir / "result.json", result)
            print(json.dumps(result, ensure_ascii=False))

            if not assertion.get("passed", True):
                raise SystemExit(3)
            if stalled:
                raise SystemExit(f"stalled: state unchanged for {entry['count']} attempts on {args.text!r}")
    except Aborted as exc:
        print(json.dumps({"aborted": True, "reason": str(exc)}, ensure_ascii=False))
        raise SystemExit(130)
    except ExecutionBusy as exc:
        print(json.dumps({"busy": True, "reason": str(exc)}, ensure_ascii=False))
        raise SystemExit(5)


if __name__ == "__main__":
    main()
