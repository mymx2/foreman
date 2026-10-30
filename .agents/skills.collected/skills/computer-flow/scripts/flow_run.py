"""Run a declarative desktop plan. No coordinates are stored in the plan."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Execute a declarative desktop workflow plan. Dry-run unless --execute is given."
    )
    parser.add_argument("plan", type=Path, help="YAML or JSON plan file")
    parser.add_argument("--handle", type=int, help="target window handle; only for disambiguation")
    parser.add_argument("--app", help="substring of the target window title, e.g. 'Notepad'")
    parser.add_argument("--process", help="executable name to match, e.g. notepad.exe")
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                        help="plan variable, repeatable")
    parser.add_argument("--observation-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true",
                        help="actually click and type; without it the plan is only resolved")
    parser.add_argument("--evidence-screenshots", action="store_true",
                        help="also save per-step window screenshots (may contain personal data)")
    parser.add_argument("--allow-occlusion", action="store_true")
    parser.add_argument("--allow-launch", action="store_true",
                        help="permit 'launch' steps to start an application")
    parser.add_argument("--max-steps", type=int, default=50)
    return parser.parse_args()


def resolve_handle(args):
    """Pick the target window by explicit handle or by discovery, never by guesswork.

    A plan that starts with `launch` has no window yet; discovery is deferred to
    that step instead of failing (or worse, binding to a stale window from a
    previous instance of the app).
    """
    from discover import find_windows

    if getattr(args, "defer_window", False) and not args.handle:
        return None
    if args.handle:
        import win32gui

        if not win32gui.IsWindow(args.handle):
            raise SystemExit(f"--handle {args.handle} is not a live window; rediscover with --app/--process")
        return args.handle
    if not args.app and not args.process:
        raise SystemExit("provide --handle, or --app/--process to discover the target window")
    candidates = find_windows(title_contains=args.app, process_name=args.process)
    if not candidates:
        raise SystemExit(f"no visible window matched app={args.app!r} process={args.process!r}")
    if len(candidates) > 1:
        listing = [{"handle": w.handle, "title": w.title, "rect": list(w.rect)} for w in candidates]
        raise SystemExit(f"{len(candidates)} windows matched; pass --handle to disambiguate: {listing}")
    return candidates[0].handle


def parse_variables(pairs, plan):
    variables = dict(plan.get("vars") or {})
    for item in pairs:
        if "=" not in item:
            raise SystemExit(f"--set expects NAME=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        variables[key] = value
    return variables


def describe_target(target):
    """Human-readable target description for logs and error messages."""
    if target is None:
        return "<none>"
    if target.auto_id:
        return f"auto_id={target.auto_id!r}"
    return f"{target.text!r} (match={target.match})"


def describe_target_masked(target, variables):
    """describe_target with every plan-variable value masked.

    Assert/wait descriptions land in log.jsonl and on stdout; a record id or
    customer name passed via --set must not persist there in clear text.
    """
    shown = describe_target(target)
    for value in sorted((str(v) for v in variables.values()), key=len, reverse=True):
        if value:
            shown = shown.replace(value, mask(value))
    return shown


def resolve_target(target, observation, dry_run=False):
    from desktop_action import SelectionError, select

    if target is None or (not target.text and not target.auto_id):
        return None
    return select(
        observation.elements,
        target.text,
        container=observation.rect,
        match=target.match,
        minimum_confidence=target.min_confidence,
        region=target.region,
        sources=target.sources or None,
        auto_id=target.auto_id,
    )


def run(args):
    from desktop_action import SelectionError, append_jsonl, state_digest, write_json
    from desktop_observe import observe, save
    from execution_safety import Aborted, AbortFlag, DesktopLock, ExecutionBusy, listen_for_escape
    from flow_plan import (
        PlanError,
        assert_file,
        load_plan,
        parse_step,
        parse_target,
        validate_plan,
        validate_step,
    )
    from windows_capture import blocker_at, bring_to_front, capture_screen, click_screen, set_dpi_awareness

    set_dpi_awareness()
    plan = load_plan(args.plan)
    validate_plan(plan)
    if len(plan["steps"]) > args.max_steps:
        raise SystemExit(f"plan has {len(plan['steps'])} steps, exceeding the limit {args.max_steps}")

    variables = parse_variables(args.set, plan)
    # A plan whose first step is `launch` has no window until that step runs.
    args.defer_window = plan["steps"][0].get("action") == "launch"
    # Parse and validate every step *before* any window is touched: unresolved
    # ${vars} and tautological expects must fail here, not after step 3 already
    # clicked something real.
    parsed_steps = []
    for index, raw in enumerate(plan["steps"]):
        step = parse_step(raw, variables)
        validate_step(step, variables)
        parsed_steps.append(step)
    args.handle = resolve_handle(args)
    args.observation_dir.mkdir(parents=True, exist_ok=True)
    args.dry_run = not args.execute
    abort = AbortFlag(scope=str(args.handle) if args.handle else None)
    abort.clear()
    log_path = args.observation_dir / "log.jsonl"
    log = []
    # Any expect_file must see a file produced after this instant; leftovers
    # from earlier runs are not evidence that this run worked.
    args.run_started = time.time()
    plan_sha = hashlib.sha256(args.plan.read_bytes()).hexdigest()[:16]

    def record(step_name, status, **extra):
        # Error text can quote a target or value built from --set variables;
        # redact those before they reach stdout or log.jsonl.
        redacted = {}
        for key, value in extra.items():
            if isinstance(value, str):
                for original in sorted((str(v) for v in variables.values()), key=len, reverse=True):
                    if original:
                        value = value.replace(original, mask(original))
            redacted[key] = value
        entry = {"step": step_name, "status": status, **redacted}
        log.append(entry)
        append_jsonl(log_path, entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)

    try:
        with DesktopLock(owner=f"flow_run:{args.handle}"):
            # Truncate the log *inside* the lock: clearing it before acquiring
            # would let a second instance wipe the first's in-flight records.
            # Per-run JSONL log: O(1) append per step, crash-safe at line granularity.
            log_path.write_text("", encoding="utf-8")
            record(
                "plan",
                "loaded",
                sha256=plan_sha,
                steps=len(plan["steps"]),
                variables=sorted(variables),
                execute=bool(args.execute),
            )
            listen_for_escape(abort)
            if args.handle and not args.dry_run:
                # Dry-run is read-only by contract: no activation, no focus
                # stealing, no window restore. Just observe and resolve.
                bring_to_front(args.handle)
            for index, step in enumerate(parsed_steps):
                abort.check()
                started = time.monotonic()
                try:
                    result = execute_step(step, args, variables, abort, index)
                    if step.action == "launch" and result.get("handle"):
                        # Later steps must act on the window we just opened, not on
                        # whatever handle discovery originally resolved. The abort
                        # scope follows the handle so ESC keeps addressing this run.
                        args.handle = result["handle"]
                        abort = AbortFlag(scope=str(args.handle))
                        abort.clear()
                    record(step.name, "ok", **result)
                except Aborted:
                    # If the abort landed after the action was sent (click/key/fill)
                    # but before post-observation, mark the step so the next run
                    # can tell "action left the process" from "never started".
                    # Re-running the plan must treat this step as result-unknown.
                    record(step.name, "aborted_mid_step", action_sent=step.action in ("click", "double_click", "right_click", "fill", "key"))
                    raise
                except Exception as exc:
                    if step.optional:
                        record(step.name, "skipped", reason=str(exc), error_type=type(exc).__name__)
                        continue
                    record(step.name, "failed", error=str(exc), error_type=type(exc).__name__, retry="diagnose_first")
                    raise SystemExit(f"step {index} ({step.name}) failed: {exc}")
                finally:
                    record(step.name + ":timing", "done", seconds=round(time.monotonic() - started, 2))
    except Aborted as exc:
        record("abort", "cancelled", reason=str(exc))
        raise SystemExit(130)
    except ExecutionBusy as exc:
        record("lock", "busy", reason=str(exc))
        raise SystemExit(5)
    return log


def pause(seconds, abort, slice_seconds=0.1):
    """Sleep in small slices so ESC stays responsive during waits."""
    deadline = time.monotonic() + seconds
    while True:
        abort.check()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(slice_seconds, remaining))


def mask(value, keep=2):
    """Mask a business value before it reaches logs or evidence files."""
    text = str(value)
    if len(text) <= keep:
        return "*" * len(text)
    return text[:keep] + "*" * (len(text) - keep)


class NoStateChange(RuntimeError):
    """An action was sent but the re-observed state did not change."""


def execute_step(step, args, variables, abort, index):
    from desktop_action import SelectionError, select, state_digest
    from desktop_observe import observe, save
    from desktop_input import replace_text
    from flow_plan import PlanError, parse_target, wait_for_file
    from windows_capture import (
        blocker_at,
        bring_to_front,
        capture_screen,
        capture_window,
        click_screen,
        validate_point_in_window,
        window_process,
    )
    from windows_list import overlay_chain, wait_for_overlay

    if step.action == "wait":
        pause(step.wait, abort)
        return {"waited": step.wait}

    if step.action == "launch":
        from launch_app import find_app, launch, wait_for_window

        if not args.allow_launch:
            raise PlanError(
                f"step {step.name}: launch requires --allow-launch; starting an application "
                "changes machine state and must be explicitly permitted"
            )
        if args.dry_run:
            hits = find_app(step.app, exe_hint=step.exe or None) if step.app else []
            best = next((item for item in hits if item["exists"]), None)
            return {
                "would_launch": step.path or (best or {}).get("path"),
                "candidates": [item["path"] for item in hits[:5]],
                "action_sent": False,
            }
        if step.path:
            exe_path = step.path
        else:
            hits = find_app(step.app, exe_hint=step.exe or None)
            best = next(
                (item for item in hits if item["exists"] and item["rank"] <= 2),
                next((item for item in hits if item["exists"]), None),
            )
            if best is None:
                raise PlanError(f"step {step.name}: no installed app matched {step.app}")
            exe_path = best["path"]
        abort.check()
        pid = launch(exe_path)
        handle = None
        if step.window or step.process:
            handle = wait_for_window(
                title_contains=step.window or None,
                process_name=step.process or None,
                timeout=step.timeout,
            )
        return {"launched": exe_path, "pid": pid, "handle": handle, "action_sent": True}

    if step.action == "expect_file":
        expect = dict(step.expect)
        path = expect.pop("path", None)
        if not path:
            raise PlanError("expect_file requires expect.path")
        timeout = float(expect.pop("timeout", 0) or 0)
        if timeout > 0:
            checked = wait_for_file(
                path, expect, variables, timeout=timeout, not_before=args.run_started,
            )
        else:
            from flow_plan import assert_file

            checked = assert_file(path, expect, variables, not_before=args.run_started)
        return {"verified": True, "bytes": checked["bytes"]}

    if not args.handle:
        raise PlanError(
            f"step {step.name}: no target window; put a 'launch' step (with window/process) "
            "before any window action, or pass --app/--process"
        )
    observation = observe(args.handle)
    save(observation, args.observation_dir / f"step-{index:02d}-before.json")
    if args.evidence_screenshots:
        capture_window(args.handle).image.save(args.observation_dir / f"step-{index:02d}-before.png")

    if step.action == "assert_text":
        expected = parse_target(step.expect.get("target") or step.target, variables)
        if expected is None:
            raise PlanError("assert_text requires a target")
        resolve_target(expected, observation)
        return {"asserted": describe_target_masked(expected, variables), "snapshot": observation.snapshot_id}

    if step.action == "wait_text":
        expected = parse_target(step.expect.get("target") or step.target, variables)
        if expected is None:
            raise PlanError("wait_text requires a target")
        deadline = time.monotonic() + step.timeout
        while True:
            try:
                found = resolve_target(expected, observation)
                found_desc = describe_target_masked(expected, variables)
                return {"found": found_desc, "snapshot": observation.snapshot_id}
            except SelectionError:
                if time.monotonic() >= deadline:
                    raise PlanError(
                        f"timeout waiting for {describe_target_masked(expected, variables)} "
                        f"after {step.timeout}s"
                    )
                # Each observe() runs OCR; SKILL.md requires OCR polling at >=2s.
                # step.wait can only lengthen the interval, never shorten it.
                pause(max(2.0, step.wait), abort)
                abort.check()
                observation = observe(args.handle)

    target = resolve_target(step.target, observation)
    if target is None:
        raise PlanError(f"step {step.name}: action {step.action} requires a target")

    point = target.center
    if args.dry_run:
        return {"resolved": target.label, "screen": [round(point[0], 1), round(point[1], 1)], "action_sent": False}

    expected = None
    if step.expect.get("target"):
        expected = parse_target(step.expect["target"], variables)
        # not_in_before is a pre-action property of the page: it must be checked
        # against the observation taken *before* the click, so it runs now —
        # after the action fires there is nothing left to compare against.
        if step.expect.get("not_in_before"):
            try:
                resolve_target(expected, observation)
            except SelectionError:
                pass
            else:
                raise PlanError(
                    f"step {step.name}: expect.target {describe_target_masked(expected, variables)} already exists "
                    "before the action; not_in_before forbids treating this as a post-action assertion"
                )

    validate_point_in_window(point[0], point[1], args.handle)
    known_overlays = {w.handle for w in overlay_chain(args.handle)}
    allowed = tuple(known_overlays) if step.expect.get("overlay") else ()
    blocker = blocker_at(point[0], point[1], expected_handle=args.handle, allowed_handles=allowed)
    if blocker is not None and not args.allow_occlusion:
        raise PlanError(f"target {target.label!r} is covered by window {blocker}")

    # The user can hit ESC while observation/OCR is still running; the last
    # chance to honor it is right here, after all validation and before any
    # real input leaves the process.
    abort.check()

    if step.action in ("click", "double_click", "right_click"):
        button = "right" if step.action == "right_click" else "left"
        clicks = 2 if step.action == "double_click" else 1
        click_screen(
            point[0], point[1],
            window_handle=args.handle, button=button, clicks=clicks, allowed_handles=allowed,
        )
        # A click can open a dialog in another process (e.g. the downloader
        # showing Save As). Detecting it here prevents the next step from acting
        # on the stale main window and opening a second copy of the same dialog.
        overlay_timeout = 8.0 if step.expect.get("overlay") else 1.2
        popped = wait_for_overlay(args.handle, known_overlays, timeout=overlay_timeout)
        result_overlay = {}
        if popped is not None:
            result_overlay["overlay"] = {
                "handle": popped.handle,
                "title": popped.title,
                "class_name": popped.class_name,
                "process_id": popped.process_id,
                "rect": list(popped.rect),
            }
    elif step.action == "fill":
        click_screen(point[0], point[1], window_handle=args.handle, allowed_handles=allowed)
        # Typing goes to whatever owns the foreground; require the target itself,
        # not merely "some window of the same process", before ^a/^v leave us.
        bring_to_front(args.handle, require_exact=True)
        abort.check()
        replace_text(args.handle, step.value)
        result_overlay = {}
    elif step.action == "key":
        click_screen(point[0], point[1], window_handle=args.handle, allowed_handles=allowed)
        bring_to_front(args.handle, require_exact=True)
        abort.check()
        from pywinauto.keyboard import send_keys

        send_keys(step.value)
        result_overlay = {}
    else:
        raise PlanError(f"unsupported action {step.action}")

    abort.check()
    pause(step.wait, abort)
    # When a new overlay appeared, re-observe *it*: the change this action caused
    # lives in the dialog, not in the main window it now covers.
    observe_handle = result_overlay["overlay"]["handle"] if result_overlay.get("overlay") else args.handle
    after = observe(observe_handle)
    save(after, args.observation_dir / f"step-{index:02d}-after.json")
    if args.evidence_screenshots:
        capture_window(observe_handle).image.save(args.observation_dir / f"step-{index:02d}-after.png")
    if result_overlay.get("overlay"):
        # A new top-level window on top is by definition a state change; the
        # main window's digest cannot see it, so compare against the overlay's
        # own fresh observation instead of the stale pre-click page.
        observed = True
    else:
        observed = state_digest(observation.elements) != state_digest(after.elements)

    result = {
        "action": step.action,
        "target": target.label or target.identifier,
        "action_sent": True,
        "observed": observed,
        "snapshot": after.snapshot_id,
        **result_overlay,
    }
    if step.action == "fill":
        result["value"] = mask(step.value)
    asserted_ok = False
    if expected is not None:
        resolve_target(expected, after)
        result["asserted"] = describe_target_masked(expected, variables)
        asserted_ok = True
    if (
        not observed
        and not asserted_ok
        and step.action in ("click", "double_click", "right_click")
    ):
        # An unnoticed click must not silently unblock the rest of the plan:
        # diagnose focus/occlusion/input path before any retry or next step.
        # When the plan already asserted an expected post-state via expect.target
        # and that assertion passed, the click did land even if the digest did not
        # move (e.g. toggle controls whose labels/positions stay identical).
        raise NoStateChange(
            f"step {step.name}: {step.action} on {target.label!r} was sent but the re-observed state did not change"
        )
    return result


def main():
    args = parse_args()
    log = run(args)
    log_path = args.observation_dir / "log.jsonl"
    print(json.dumps({
        "completed": len([e for e in log if e["status"] == "ok"]),
        "log": str(log_path),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
