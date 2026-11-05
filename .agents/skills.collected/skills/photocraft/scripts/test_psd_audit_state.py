#!/usr/bin/env python3
"""psd_audit --state-snapshot 合并逻辑的最小测试。"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psd_audit  # noqa: E402


class MergeStateSnapshotTest(unittest.TestCase):
    def _write(self, payload):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        self.addCleanup(os.unlink, path)
        return path

    def _result(self):
        return {"issues": [], "summary": {}, "stats": {}}

    def test_good_snapshot_adds_no_high(self):
        path = self._write({
            "states": ["default"],
            "layerComps": ["default"],
            "applyResults": {"default": {"missingLayers": 0}},
        })
        merged = psd_audit.merge_state_snapshot(self._result(), path)
        self.assertEqual(merged["summary"]["HIGH"], 0)
        self.assertTrue(merged["summary"]["ok"])
        self.assertEqual(merged["stats"]["stateSnapshot"]["errors"], 0)

    def test_bad_snapshot_adds_state_high(self):
        path = self._write({
            "states": ["default", "hover"],
            "layerComps": ["default"],
            "applyResults": {"default": {"missingLayers": 0}},
        })
        merged = psd_audit.merge_state_snapshot(self._result(), path)
        codes = {i["code"] for i in merged["issues"]}
        self.assertGreater(merged["summary"]["HIGH"], 0)
        self.assertIn("STATE_COMP_MISSING", codes)
        self.assertFalse(merged["summary"]["ok"])

    def test_array_snapshot_is_rejected(self):
        path = self._write([])
        with self.assertRaises(ValueError):
            psd_audit.merge_state_snapshot(self._result(), path)

    def test_markdown_escapes_carriage_return(self):
        self.assertNotIn("\r", psd_audit._md("a\rb|c"))

    def test_invalid_state_shape_is_an_input_error(self):
        path = self._write({"states": [], "layerComps": ["default"], "applyResults": {}})
        with self.assertRaises(ValueError):
            psd_audit.merge_state_snapshot(self._result(), path)

    def test_compare_merges_old_and_new_independently(self):
        bad = self._write({
            "states": ["default", "hover"],
            "layerComps": ["default"],
            "applyResults": {"default": {"missingLayers": 0}},
        })
        good = self._write({
            "states": ["default"],
            "layerComps": ["default"],
            "applyResults": {"default": {"missingLayers": 0}},
        })
        old_result = self._result()
        new_result = self._result()
        old, new = psd_audit.merge_compare_snapshots(old_result, new_result, bad, good)
        old_codes = {i["code"] for i in old["issues"]}
        new_codes = {i["code"] for i in new["issues"]}
        self.assertIn("STATE_COMP_MISSING", old_codes)
        self.assertNotIn("STATE_COMP_MISSING", new_codes)
        self.assertIn("stateSnapshot", old["stats"])
        self.assertIn("stateSnapshot", new["stats"])
        self.assertTrue(new["summary"]["ok"])


if __name__ == "__main__":
    unittest.main()
