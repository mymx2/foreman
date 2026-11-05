#!/usr/bin/env python3
"""verify_token_table.py 的独立测试。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_token_table  # noqa: E402


def payload(**overrides):
    base = {
        "revision": "r1",
        "expected": [{"role": "text-primary", "value": "#18191C"}, {"role": "spacing-md", "value": 16}],
        "measured": {"revision": "r1", "tokens": {"text-primary": "#18191c", "spacing-md": "16"}},
        "aliases": [{"alias": "body-text", "role": "text-primary"}],
    }
    base.update(overrides)
    return base


def codes(result):
    return {i["code"] for i in result["issues"]}


class VerifyTokenTableTest(unittest.TestCase):
    def test_good_snapshot(self):
        result = verify_token_table.verify(payload())
        self.assertTrue(result["ok"])
        self.assertEqual(result["issues"], [])

    def test_missing_and_mismatched_tokens(self):
        result = verify_token_table.verify(payload(
            expected=[{"role": "text-primary", "value": "#000000"}, {"role": "missing", "value": 1}]
        ))
        self.assertFalse(result["ok"])
        self.assertIn("TOKEN_MISSING", codes(result))
        self.assertIn("TOKEN_MISMATCH", codes(result))

    def test_duplicate_and_extra_tokens(self):
        result = verify_token_table.verify(payload(
            expected=[{"role": "text-primary", "value": "#18191C"}, {"role": "text-primary", "value": "#18191C"}],
            measured={"revision": "r1", "tokens": {"text-primary": "#18191C", "extra-token": "x"}},
        ))
        self.assertIn("TOKEN_DUPLICATE", codes(result))
        self.assertIn("TOKEN_EXTRA", codes(result))

    def test_revision_and_measured_shape(self):
        result = verify_token_table.verify(payload(measured={"revision": "r2", "tokens": {}}))
        self.assertIn("REVISION_MISMATCH", codes(result))
        result = verify_token_table.verify(payload(measured="oops"))
        self.assertIn("MEASURED_INVALID", codes(result))

    def test_alias_target_warning(self):
        result = verify_token_table.verify(payload(aliases=[{"alias": "x", "role": "unknown"}]))
        self.assertTrue(result["ok"])
        self.assertIn("ALIAS_TARGET", codes(result))

    def test_numeric_tolerance(self):
        result = verify_token_table.verify(payload(
            expected=[{"role": "spacing-md", "value": 16}],
            measured={"revision": "r1", "tokens": {"spacing-md": "16.0000000001"}},
        ))
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
