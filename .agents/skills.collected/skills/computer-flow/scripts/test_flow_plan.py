import os
import tempfile
import time
import unittest
from pathlib import Path

from flow_plan import (
    PlanError,
    assert_file,
    load_plan,
    parse_step,
    parse_target,
    substitute,
    validate_plan,
    validate_step,
    wait_for_file,
)


class TargetTests(unittest.TestCase):
    def test_string_target_defaults_to_exact(self):
        target = parse_target("查询", {})
        self.assertEqual(target.text, "查询")
        self.assertEqual(target.match, "exact")

    def test_variable_substitution(self):
        target = parse_target({"text": "${record_id}", "match": "contains"}, {"record_id": "A-1"})
        self.assertEqual(target.text, "A-1")
        self.assertEqual(target.match, "contains")

    def test_cjk_spaces_in_target_text_are_collapsed(self):
        # Plan-side normalize must match observation-side `_normalize`, otherwise
        # plans written from OCR dumps with embedded spaces never match.
        target = parse_target({"text": "查询 条件"}, {})
        self.assertEqual(target.text, "查询条件")
        self.assertEqual(parse_target("订单 编号", {}).text, "订单编号")

    def test_latin_spaces_in_target_text_are_kept(self):
        target = parse_target({"text": "hello world"}, {})
        self.assertEqual(target.text, "hello world")

    def test_auto_id_is_parsed_and_substituted(self):
        target = parse_target({"auto_id": "${field}_input"}, {"field": "username"})
        self.assertEqual(target.auto_id, "username_input")

    def test_target_with_only_auto_id_is_valid(self):
        target = parse_target({"auto_id": "btnSave"}, {})
        self.assertEqual(target.text, "")
        self.assertEqual(target.auto_id, "btnSave")

    def test_target_without_text_or_auto_id_is_rejected(self):
        with self.assertRaises(PlanError):
            parse_target({"match": "exact"}, {})

    def test_region_is_validated(self):
        with self.assertRaises(PlanError):
            parse_target({"text": "x", "region": [0, 0, 1]}, {})
        with self.assertRaises(PlanError):
            parse_target({"text": "x", "match": "unknown"}, {})

    def test_parse_target_is_idempotent(self):
        once = parse_target({"text": "查询"}, {})
        twice = parse_target(once, {"unused": "1"})
        self.assertIs(once, twice)
        self.assertEqual(twice.text, "查询")

    def test_missing_required_placeholder_fails_fast(self):
        # A literal "${record_id}" pasted into the target app is always wrong,
        # and it poisons later assertions. Fail before any real input.
        with self.assertRaises(PlanError) as ctx:
            substitute("${missing}", {})
        self.assertIn("missing", str(ctx.exception))
        self.assertEqual(substitute("id=${id}", {"id": "42"}), "id=42")

    def test_unresolved_placeholder_blocks_the_plan_before_acting(self):
        with self.assertRaises(PlanError):
            parse_step(
                {"action": "fill", "target": "字段", "value": "${record_id}"},
                {},
            )

    def test_tautological_expect_is_rejected_before_execution(self):
        step = parse_step(
            {
                "action": "click",
                "name": "run_search",
                "target": {"text": "查询"},
                "expect": {"target": {"text": "查询"}},
            },
            {},
        )
        with self.assertRaises(PlanError) as ctx:
            validate_step(step, {})
        self.assertIn("duplicates the click target", str(ctx.exception))

    def test_distinct_expect_is_accepted(self):
        step = parse_step(
            {
                "action": "click",
                "target": {"text": "查询"},
                "expect": {"target": {"text": "查询中", "match": "contains"}},
            },
            {},
        )
        validate_step(step, {})


class PlanTests(unittest.TestCase):
    def test_yaml_plan_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.yaml"
            path.write_text(
                "steps:\n  - action: click\n    target: {text: 查询}\n",
                encoding="utf-8",
            )
            plan = load_plan(path)
            validate_plan(plan)
            step = parse_step(plan["steps"][0], {})
            self.assertEqual(step.action, "click")
            self.assertEqual(step.target.text, "查询")

    def test_plan_must_have_steps(self):
        with self.assertRaises(PlanError):
            validate_plan({"steps": []})

    def test_unknown_action_rejected(self):
        with self.assertRaises(PlanError):
            validate_plan({"steps": [{"action": "shell"}]})

    def test_optional_step_can_be_skipped(self):
        step = parse_step({"action": "click", "target": "下载", "optional": True}, {})
        self.assertTrue(step.optional)


class ArtifactTests(unittest.TestCase):
    def test_missing_file_fails(self):
        with self.assertRaises(PlanError):
            assert_file("/nonexistent/place/none.pdf", {"magic": "%PDF-"}, {})

    def test_size_and_magic_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "ok.pdf"
            good.write_bytes(b"%PDF-1.4\nsome content")
            result = assert_file(good, {"magic": "%PDF-", "min_bytes": 4}, {})
            self.assertGreater(result["bytes"], 4)

            bad = Path(tmp) / "bad.pdf"
            bad.write_bytes(b"not a pdf")
            with self.assertRaises(PlanError):
                assert_file(bad, {"magic": "%PDF-"}, {})

    def test_required_text_must_be_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.txt"
            path.write_text("order ABC-1 completed", encoding="utf-8")
            assert_file(path, {"contains": ["ABC-1", "completed"]}, {})
            with self.assertRaises(PlanError):
                assert_file(path, {"contains": ["missing-token"]}, {})

    def test_placeholders_in_expected_file_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "A-1.txt"
            path.write_text("A-1", encoding="utf-8")
            result = assert_file(str(path), {"contains": ["${id}"]}, {"id": "A-1"})
            self.assertTrue(result["path"].endswith("A-1.txt"))

    def test_min_bytes_placeholder_is_substituted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "small.txt"
            path.write_text("x", encoding="utf-8")
            with self.assertRaises(PlanError):
                assert_file(path, {"min_bytes": "${minimum}"}, {"minimum": "10"})
            assert_file(path, {"min_bytes": "${minimum}"}, {"minimum": "1"})

    def test_magic_placeholder_is_substituted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.bin"
            path.write_bytes(b"MAGIC-rest")
            assert_file(path, {"magic": "${header}"}, {"header": "MAGIC"})
            with self.assertRaises(PlanError):
                assert_file(path, {"magic": "${header}"}, {"header": "OTHER"})

    def test_min_bytes_failure_reports_actual_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiny.bin"
            path.write_bytes(b"ab")
            with self.assertRaises(PlanError) as ctx:
                assert_file(path, {"min_bytes": 100}, {})
            self.assertIn("only", str(ctx.exception))

    def test_short_file_does_not_crash_magic_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.bin"
            path.write_bytes(b"M")
            with self.assertRaises(PlanError):
                assert_file(path, {"magic": "%PDF-"}, {})

    def test_size_limit_blocks_huge_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "big.bin"
            path.write_bytes(b"x" * 2048)
            with self.assertRaises(PlanError):
                assert_file(path, {"max_mb": 0}, {})

    def test_wait_for_file_polls_until_artifact_appears(self):
        import threading

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "late.txt"
            threading.Timer(0.3, lambda: path.write_text("ready", encoding="utf-8")).start()
            result = wait_for_file(str(path), {"contains": ["ready"]}, {}, timeout=3, interval=0.1)
            self.assertTrue(result["path"].endswith("late.txt"))

    def test_wait_for_file_times_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PlanError):
                wait_for_file(str(Path(tmp) / "never.txt"), {}, {}, timeout=0.2, interval=0.05)

    def test_leftover_file_from_an_earlier_run_is_rejected(self):
        # A skipped optional download plus an unconditional expect_file must not
        # "verify" yesterday's file that happens to sit at the same path.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.pdf"
            path.write_bytes(b"%PDF-1.4 stale")
            old = path.stat().st_mtime - 3600
            os.utime(path, (old, old))
            with self.assertRaises(PlanError) as ctx:
                assert_file(path, {"magic": "%PDF-"}, {}, not_before=time.time())
            self.assertIn("predates this run", str(ctx.exception))

    def test_fresh_file_passes_the_leftover_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "new.pdf"
            path.write_bytes(b"%PDF-1.4 fresh")
            assert_file(path, {"magic": "%PDF-"}, {}, not_before=time.time() - 60)

    def test_allow_existing_opts_out_of_the_leftover_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.pdf"
            path.write_bytes(b"%PDF-1.4 stale")
            old = path.stat().st_mtime - 3600
            os.utime(path, (old, old))
            assert_file(path, {"magic": "%PDF-", "allow_existing": True}, {}, not_before=time.time())


if __name__ == "__main__":
    unittest.main()
