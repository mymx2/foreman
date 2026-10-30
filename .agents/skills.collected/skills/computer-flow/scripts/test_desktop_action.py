import tempfile
import unittest
from pathlib import Path

from desktop_action import (
    SelectionError,
    StallTracker,
    StaleSnapshotError,
    append_jsonl,
    assert_fresh,
    normalize_region,
    select,
    state_digest,
    write_json,
)
from desktop_observe import Element, _normalize, merge_duplicates


def element(label, rect, confidence=0.99, source="ocr", snapshot="", identifier=""):
    return Element(source=source, label=label, rect=rect, confidence=confidence, snapshot=snapshot, identifier=identifier)


CONTAINER = (0, 0, 1000, 1000)


class SnapshotTests(unittest.TestCase):
    def test_same_snapshot_is_accepted(self):
        assert_fresh(element("save", (0, 0, 10, 10), snapshot="s1"), "s1")

    def test_different_snapshot_is_rejected(self):
        with self.assertRaises(StaleSnapshotError):
            assert_fresh(element("save", (0, 0, 10, 10), snapshot="s1"), "s2")

    def test_unbound_element_is_allowed_for_legacy_callers(self):
        assert_fresh(element("save", (0, 0, 10, 10)), "s1")

    def test_binding_preserves_identity(self):
        bound = element("save", (1, 2, 3, 4)).bind_snapshot("snap-x")
        self.assertEqual(bound.snapshot, "snap-x")
        self.assertEqual(bound.label, "save")
        self.assertEqual(bound.rect, (1, 2, 3, 4))


class SelectTests(unittest.TestCase):
    def test_returns_the_only_match(self):
        target = select([element("save", (100, 100, 140, 130))], "save", CONTAINER)
        self.assertEqual(target.center, (120, 115))

    def test_rejects_zero_and_multiple_matches(self):
        for items, text in (
            ([], "save"),
            ([element("save", (0, 0, 40, 30)), element("save", (500, 500, 540, 530))], "save"),
        ):
            with self.subTest(items=items), self.assertRaises(SelectionError):
                select(items, text, CONTAINER)

    def test_low_confidence_is_rejected(self):
        with self.assertRaises(SelectionError):
            select([element("save", (0, 0, 40, 30), confidence=0.4)], "save", CONTAINER, minimum_confidence=0.8)

    def test_region_uses_the_observed_container(self):
        items = [
            element("save", (10, 10, 40, 40)),
            element("save", (700, 700, 730, 730)),
        ]
        right = select(items, "save", CONTAINER, region=(0.5, 0, 1, 1))
        self.assertEqual(right.center, (715, 715))
        with self.assertRaises(SelectionError):
            select(items, "save", CONTAINER, region=(0.2, 0.2, 0.3, 0.3))

    def test_region_must_be_fractions(self):
        for bad in ((-0.1, 0, 1, 1), (0, 0, 2, 1), (0.5, 0, 0.2, 1), (0, 0.9, 1, 0.2), (0, 0, 1)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                normalize_region(bad)
        self.assertIsNone(normalize_region(None))

    def test_suffix_and_contains_are_distinct(self):
        items = [element("icon 保存", (0, 0, 80, 30))]
        self.assertIsNotNone(select(items, "保存", CONTAINER, match="suffix"))
        self.assertIsNotNone(select(items, "存", CONTAINER, match="contains"))
        with self.assertRaises(SelectionError):
            select(items, "保存", CONTAINER, match="exact")

    def test_source_filter(self):
        uia = element("save", (0, 0, 40, 30), source="uia")
        ocr = element("save", (0, 0, 40, 30), source="ocr")
        self.assertEqual(select([uia, ocr], "save", CONTAINER, sources=["uia"]).source, "uia")


class AutoIdTests(unittest.TestCase):
    def test_auto_id_matches_identifier_not_label(self):
        target = element("Save", (0, 0, 40, 30), source="uia", identifier="btnSave")
        found = select([target], "", CONTAINER, auto_id="btnSave")
        self.assertEqual(found.identifier, "btnSave")

    def test_auto_id_wins_over_text(self):
        # Same label, different ids: auto_id must disambiguate.
        a = element("确定", (0, 0, 40, 30), source="uia", identifier="btnOK")
        b = element("确定", (100, 0, 140, 30), source="uia", identifier="btnCancel")
        found = select([a, b], "", CONTAINER, auto_id="btnCancel")
        self.assertEqual(found.identifier, "btnCancel")

    def test_auto_id_beats_localized_label_change(self):
        # Label changed between versions; the id still resolves it.
        target = element("保存并关闭", (0, 0, 40, 30), source="uia", identifier="btnSave")
        self.assertIsNotNone(select([target], "", CONTAINER, auto_id="btnSave"))

    def test_unknown_auto_id_raises_with_hint(self):
        target = element("Save", (0, 0, 40, 30), source="uia", identifier="btnSave")
        with self.assertRaises(SelectionError) as ctx:
            select([target], "", CONTAINER, auto_id="btnNope")
        self.assertIn("btnNope", str(ctx.exception))

    def test_auto_id_still_respects_region(self):
        target = element("Save", (0, 0, 40, 30), source="uia", identifier="btnSave")
        with self.assertRaises(SelectionError):
            select([target], "", CONTAINER, region=(0.5, 0, 1, 1), auto_id="btnSave")

    def test_ocr_elements_have_no_identifier(self):
        # OCR can never satisfy an auto_id lookup, by construction.
        target = element("Save", (0, 0, 40, 30), source="ocr")
        with self.assertRaises(SelectionError):
            select([target], "", CONTAINER, auto_id="btnSave")


class MergeDuplicatesTests(unittest.TestCase):
    def test_ocr_and_uia_same_button_collapse(self):
        ocr = element("保存", (98, 100, 142, 132), confidence=0.9, source="ocr")
        uia = element("保存", (100, 100, 140, 130), confidence=1.0, source="uia")
        merged = merge_duplicates([ocr, uia])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].source, "uia")

    def test_distinct_labels_are_kept(self):
        a = element("保存", (0, 0, 40, 30))
        b = element("取消", (0, 0, 40, 30))
        self.assertEqual(len(merge_duplicates([a, b])), 2)

    def test_same_label_far_apart_is_kept(self):
        a = element("保存", (0, 0, 40, 30), source="ocr")
        b = element("保存", (500, 500, 540, 530), source="uia")
        merged = merge_duplicates([a, b])
        self.assertEqual(len(merged), 2)

    def test_vertically_adjacent_rows_stay_separate(self):
        # Same x-center, y-center outside each other's rect → not duplicates.
        a = element("删除", (100, 100, 200, 130), source="uia")
        b = element("删除", (100, 200, 200, 230), source="ocr")
        self.assertEqual(len(merge_duplicates([a, b])), 2)

    def test_uia_control_box_with_ocr_text_box_collapses(self):
        # Review counterexample: UIA reports the whole 500x30 control, OCR reports
        # the tight 80x20 text box inside it. IoU is ~0.107 but they are the same
        # physical button.
        uia = element("保存", (0, 100, 500, 130), confidence=1.0, source="uia")
        ocr = element("保存", (10, 105, 90, 125), confidence=0.92, source="ocr")
        merged = merge_duplicates([ocr, uia])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].source, "uia")

    def test_merged_element_survives_select(self):
        ocr = element("保存", (98, 100, 142, 132), confidence=0.9, source="ocr")
        uia = element("保存", (100, 100, 140, 130), confidence=1.0, source="uia")
        merged = merge_duplicates([ocr, uia])
        target = select(merged, "保存", CONTAINER)
        self.assertEqual(target.source, "uia")


class DigestTests(unittest.TestCase):
    def test_same_observation_is_stable(self):
        items = [element("save", (0, 0, 40, 30))]
        self.assertEqual(state_digest(items), state_digest(items))

    def test_position_change_counts_as_change(self):
        self.assertNotEqual(
            state_digest([element("save", (0, 0, 40, 30))]),
            state_digest([element("save", (0, 500, 40, 530))]),
        )

    def test_text_change_counts_as_change(self):
        self.assertNotEqual(
            state_digest([element("save", (0, 0, 40, 30))]),
            state_digest([element("save as", (0, 0, 40, 30))]),
        )


class StallTests(unittest.TestCase):
    def test_second_unchanged_attempt_stops(self):
        tracker = StallTracker(limit=2)
        first, stalled = tracker.update(None, "abc", changed=False)
        self.assertFalse(stalled)
        self.assertEqual(first["count"], 1)
        second, stalled = tracker.update(first, "abc", changed=False)
        self.assertTrue(stalled)
        self.assertEqual(second["count"], 2)
        third, stalled = tracker.update(second, "abc", changed=False)
        self.assertTrue(stalled)
        self.assertEqual(third["count"], 3)

    def test_change_resets_stall(self):
        tracker = StallTracker(limit=2)
        previous, _ = tracker.update(None, "abc", changed=False)
        next_state, stalled = tracker.update(previous, "def", changed=True)
        self.assertFalse(stalled)
        self.assertEqual(next_state["count"], 0)


class NormalizeTests(unittest.TestCase):
    def test_cjk_spaces_are_collapsed(self):
        self.assertEqual(_normalize("查 询"), "查询")
        self.assertEqual(_normalize("保存  成功"), "保存成功")
        self.assertEqual(_normalize("订单 编号： ABC-1"), "订单编号： ABC-1")

    def test_latin_spaces_are_kept(self):
        self.assertEqual(_normalize("hello world"), "hello world")
        self.assertEqual(_normalize("foo 中文 bar"), "foo 中文 bar")

    def test_empty_and_none(self):
        self.assertEqual(_normalize(""), "")
        self.assertEqual(_normalize(None), "")


class JsonlTests(unittest.TestCase):
    def test_append_jsonl_appends_each_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "log.jsonl"
            append_jsonl(path, {"step": "a", "status": "ok"})
            append_jsonl(path, {"step": "b", "status": "ok"})
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn('"a"', lines[0])
            self.assertIn('"b"', lines[1])

    def test_write_json_cleans_up_tmp_on_serialization_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "log.json"
            with self.assertRaises(TypeError):
                write_json(path, {"bad": object()})
            self.assertFalse((Path(tmp) / "log.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
