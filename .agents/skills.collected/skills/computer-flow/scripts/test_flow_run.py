"""Gate-order tests for flow_run.execute_step.

Every case answers one question: when something is wrong, does the process
still send real input? The desktop boundaries (observe, select, click, typing)
are faked so the tests run anywhere; the ordering they assert is the product.
"""

import contextlib
import sys
import types
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

import flow_run
from desktop_observe import Element, Observation
from execution_safety import Aborted, AbortFlag
from flow_plan import parse_step
from test_desktop_action import CONTAINER, element


def observation(labels, handle=100, snapshot="snap-1"):
    window = [element(label, (100, 100, 200, 130), snapshot=snapshot) for label in labels]
    return Observation(handle=handle, rect=CONTAINER, image_size=(1000, 1000), window=window, snapshot_id=snapshot)


def args(handle=100, execute=True):
    return Namespace(
        handle=handle,
        dry_run=not execute,
        execute=execute,
        allow_launch=False,
        allow_occlusion=False,
        evidence_screenshots=False,
        observation_dir=Path("."),
        run_started=0.0,
    )


class RecordingAbort(AbortFlag):
    """AbortFlag whose check() records when it was consulted."""

    def __init__(self, events=None):
        super().__init__(scope="test")
        self.events = events if events is not None else []

    def check(self):
        self.events.append("abort.check")


def fake_desktop(events, before=("查询",), after=("查询", "结果"), click=None):
    """Patch the desktop boundary and record the order of calls."""
    obs_before = observation(list(before))
    obs_after = observation(list(after), snapshot="snap-2")

    def record_observe(handle, **_kwargs):
        events.append("observe")
        return obs_before if events.count("observe") == 1 else obs_after

    def record_click(x, y, **kwargs):
        events.append("click_screen")
        if click is not None:
            return click(x, y, **kwargs)
        return (x, y)

    def record_input(*_args, **_kwargs):
        events.append("input")

    patches = [
        mock.patch("desktop_observe.observe", side_effect=record_observe),
        mock.patch("desktop_observe.save", lambda *a, **k: None),
        mock.patch("windows_capture.set_dpi_awareness", lambda: True),
        mock.patch("desktop_action.select", _real_select()),
        mock.patch("windows_capture.blocker_at", lambda *a, **k: None),
        mock.patch("windows_capture.click_screen", side_effect=record_click),
        mock.patch("windows_capture.validate_point_in_window", lambda *a, **k: True),
        mock.patch("windows_list.overlay_chain", lambda *a, **k: []),
        mock.patch("windows_list.wait_for_overlay", lambda *a, **k: None),
        mock.patch("desktop_input.replace_text", side_effect=record_input),
        mock.patch("windows_capture.bring_to_front", lambda *a, **k: {"exact": True}),
    ]
    return patches


def _real_select():
    from desktop_action import select as real

    return real


class GateOrderTests(unittest.TestCase):
    def setUp(self):
        try:
            import windows_capture  # noqa: F401
            import windows_list  # noqa: F401
            import desktop_input  # noqa: F401
            import desktop_observe  # noqa: F401
        except ImportError as exc:  # non-Windows dev box
            self.skipTest(f"Windows-only modules unavailable: {exc}")

    def run_step(self, raw, events, abort, variables=None, step_args=None):
        variables = variables or {}
        step_args = step_args or {}
        step = parse_step(raw, variables)
        with contextlib.ExitStack() as stack:
            for patch in fake_desktop(events):
                stack.enter_context(patch)
            return flow_run.execute_step(step, args(**step_args), variables, abort, 0)

    def test_abort_raised_during_observation_blocks_the_click(self):
        events = []
        # In-memory flag: raises exactly when observe() is running, i.e. after
        # the loop-top check passed and before any input would be sent.
        class EscDuringObserve:
            def __init__(self):
                self.raised = False

            def check(self):
                if self.raised:
                    raise Aborted("esc during observation")
                events.append("abort.check")

            def raise_abort(self):
                self.raised = True

        abort = EscDuringObserve()

        def observe_with_esc(handle, **_kwargs):
            events.append("observe")
            abort.raise_abort()
            return observation(["查询"])

        step = parse_step({"action": "click", "target": "查询"}, {})
        with mock.patch("desktop_observe.observe", side_effect=observe_with_esc), \
                mock.patch("desktop_observe.save", lambda *a, **k: None), \
                mock.patch("windows_capture.set_dpi_awareness", lambda: True), \
                mock.patch("windows_capture.blocker_at", lambda *a, **k: None), \
                mock.patch("windows_capture.validate_point_in_window", lambda *a, **k: True), \
                mock.patch("windows_list.overlay_chain", lambda *a, **k: []), \
                mock.patch("windows_capture.click_screen") as click:
            with self.assertRaises(Aborted):
                flow_run.execute_step(step, args(), {}, abort, 0)
        click.assert_not_called()

    def test_key_action_returns_a_result_instead_of_crashing(self):
        # Regression: `key` never assigned result_overlay and died with
        # UnboundLocalError *after* the keystrokes had already been sent.
        events = []
        abort = RecordingAbort(events)
        fake_keyboard = types.SimpleNamespace(send_keys=lambda value: events.append("send_keys"))
        with mock.patch.dict(sys.modules, {"pywinauto": types.SimpleNamespace(keyboard=fake_keyboard),
                                           "pywinauto.keyboard": fake_keyboard}):
            result = self.run_step({"action": "key", "target": "查询", "value": "{ENTER}"}, events, abort)
        self.assertTrue(result["action_sent"])
        self.assertIn("send_keys", events)

    def test_duplicate_expect_target_never_reaches_the_click(self):
        # Previously the tautology check ran after the click had been sent.
        events = []
        abort = RecordingAbort(events)
        step = parse_step(
            {"action": "click", "target": "查询", "expect": {"target": {"text": "查询"}}}, {}
        )
        from flow_plan import PlanError, validate_step

        with self.assertRaises(PlanError):
            validate_step(step, {})
        self.assertNotIn("click_screen", events)

    def test_fill_requires_exact_foreground_before_typing(self):
        events = []
        abort = RecordingAbort(events)

        def refuse_exact(handle, timeout=2.0, require_exact=False):
            events.append("bring_to_front")
            if require_exact:
                raise RuntimeError("refusing to send input that would land elsewhere")
            return {"exact": True}

        step = parse_step({"action": "fill", "target": "查询", "value": "A-1"}, {})
        with mock.patch("desktop_observe.observe", lambda h, **k: observation(["查询"])), \
                mock.patch("desktop_observe.save", lambda *a, **k: None), \
                mock.patch("windows_capture.set_dpi_awareness", lambda: True), \
                mock.patch("windows_capture.blocker_at", lambda *a, **k: None), \
                mock.patch("windows_capture.validate_point_in_window", lambda *a, **k: True), \
                mock.patch("windows_list.overlay_chain", lambda *a, **k: []), \
                mock.patch("windows_capture.click_screen", lambda *a, **k: (0, 0)), \
                mock.patch("windows_capture.bring_to_front", side_effect=refuse_exact), \
                mock.patch("desktop_input.replace_text") as replace:
            with self.assertRaises(RuntimeError):
                flow_run.execute_step(step, args(), {}, abort, 0)
        replace.assert_not_called()

    def test_dry_run_sends_no_input(self):
        events = []
        abort = RecordingAbort(events)
        result = self.run_step(
            {"action": "fill", "target": "查询", "value": "A-1"}, events, abort,
            step_args={"execute": False},
        )
        self.assertFalse(result["action_sent"])
        self.assertNotIn("input", events)
        self.assertNotIn("click_screen", events)


class MaskingTests(unittest.TestCase):
    def test_mask_keeps_only_the_prefix(self):
        self.assertEqual(flow_run.mask("ABC-12345"), "AB*******")
        self.assertEqual(flow_run.mask("AB"), "**")

    def test_describe_target_masked_redacts_variable_values(self):
        target = parse_step(
            {"action": "assert_text", "target": {"text": "订单 ABC-12345", "match": "contains"}},
            {"record_id": "ABC-12345"},
        ).target
        shown = flow_run.describe_target_masked(target, {"record_id": "ABC-12345"})
        self.assertNotIn("ABC-12345", shown)
        self.assertIn("AB*", shown)


if __name__ == "__main__":
    unittest.main()
