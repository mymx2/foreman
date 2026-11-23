#!/usr/bin/env python3
"""两脚本的纯函数契约测试：零依赖，不需要 WPS / 云环境 / 样例工作簿。

从技能目录运行：
    python -m unittest discover -s tests -v

覆盖的是改动后最容易静默漂移的不变量，COM 与云端行为仍按 SKILL.md
的 Verification 节人工复验。
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import parse_workbook as pw
import wps_com as wc

SECRET = "SECRETVALUE"
URL = "https://x.example.com/a.xlsx?Signature=" + SECRET


class RedactContract(unittest.TestCase):
    def test_is_download_url_variants(self):
        shapes = (URL, " " + URL + " ", '"' + URL + "'", "http:/" + URL.split("//")[1])
        for shape in shapes:
            self.assertTrue(pw._is_download_url(shape), shape)
            self.assertTrue(wc._is_download_url(shape), shape)
        self.assertTrue(wc._is_download_url("D:/报表.xlsx?Signature=" + SECRET))
        self.assertFalse(pw._is_download_url("D:/报表/signature=1.xlsx"))

    def test_redact_hides_signature_but_keeps_plain_names(self):
        for mod in (pw, wc):
            self.assertNotIn(SECRET, mod._redact(URL))
            self.assertNotIn(SECRET, mod._redact("'" + URL + '"'))
        self.assertEqual(pw._redact("汇总?2026"), "汇总?2026")
        self.assertEqual(wc._redact("普通错误说明"), "普通错误说明")

    def test_main_rejects_url_without_leaking(self):
        # 绕过缺依赖守卫，只测 URL 拒绝分支；UsageError 在 __main__ 块才转退出码
        old_missing, old_wb = pw._DEP_MISSING, pw.CalamineWorkbook
        pw._DEP_MISSING, pw.CalamineWorkbook = False, object()
        try:
            with self.assertRaises(pw.UsageError) as cm:
                pw.main([URL, "--list"])
            self.assertNotIn(SECRET, str(cm.exception))
        finally:
            pw._DEP_MISSING, pw.CalamineWorkbook = old_missing, old_wb

        for target in (URL, '"' + URL + '"'):
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                code = wc.main(["read", "--file", target])
            self.assertEqual(code, 2)
            self.assertNotIn(SECRET, buf.getvalue())


class AsTextContract(unittest.TestCase):
    def test_formula_prefixes_under_text_only(self):
        self.assertEqual(wc._as_text("=1+1", False), "=1+1")  # 公式能力保留
        self.assertEqual(wc._as_text("=1+1", True), "'=1+1")
        for v in ("+HYPERLINK(\"http://x\",\"x\")", "@SUM(A1)", "-5", "=待定"):
            self.assertTrue(wc._as_text(v, True).startswith("'"), v)

    def test_date_like_always_quoted_and_numbers_untouched(self):
        for v in ("2021-12-16", "20211216.0", "12:30", "TRUE", "12%"):
            self.assertTrue(wc._as_text(v, False).startswith("'"), v)
        self.assertEqual(wc._as_text(5, True), 5)
        self.assertEqual(wc._as_text(1.5, False), 1.5)


class ValuesEqualContract(unittest.TestCase):
    def test_none_empty_bool_and_tolerance(self):
        self.assertTrue(wc.values_equal(None, ""))
        self.assertTrue(wc.values_equal("", None))
        self.assertTrue(wc.values_equal(True, 1))
        self.assertTrue(wc.values_equal(1.0, 1.0000000001))
        self.assertFalse(wc.values_equal("100", "101"))
        self.assertEqual(wc.values_equal("100", "100"), True)


class NormalizeContract(unittest.TestCase):
    def test_date_number_text_empty(self):
        self.assertEqual(pw.normalize(20211216), ("date", "2021-12-16"))
        self.assertEqual(pw.normalize(20211216.0), ("date", "2021-12-16"))
        self.assertEqual(pw.normalize(20211399), ("number", "20211399"))
        self.assertEqual(pw.normalize("特惠"), ("text", "特惠"))
        self.assertEqual(pw.normalize(None), ("empty", ""))
        self.assertEqual(pw.normalize(True), ("text", "TRUE"))
        self.assertEqual(pw.normalize("2026/1/2"), ("date", "2026-01-02"))


class MatcherContract(unittest.TestCase):
    def test_empty_tokens_and_date_fragment(self):
        self.assertTrue(pw.make_matcher(0, "=", "空", True)([None]))
        self.assertFalse(pw.make_matcher(0, "=", "空", True)(["杂"]))
        self.assertTrue(pw.make_matcher(0, "!=", "空", True)(["杂"]))
        self.assertTrue(pw.make_matcher(0, "~", "空", True)(["杂空框"]))
        self.assertFalse(pw.make_matcher(0, "~", "空", True)(["杂框"]))
        self.assertEqual(pw._fold_date_fragment("2026/1"), "2026-01")
        self.assertEqual(pw._fold_date_fragment("2026.1.2"), "2026-01-02")

    def test_parse_where_op_precedence(self):
        hdr = ["列A", "出库时间"]
        self.assertEqual(pw.parse_where("列A=A~B", hdr), ("列A", "=", "A~B"))
        self.assertEqual(pw.parse_where("列A!=x", hdr)[1], "!=")
        with self.assertRaises(pw.UsageError):
            pw.parse_where("列A~", hdr)


class GuardContract(unittest.TestCase):
    def test_guard_out_path(self):
        with tempfile.TemporaryDirectory() as d:
            book = os.path.join(d, "a.xlsx")
            Path(book).write_bytes(b"PK\x03\x04")
            with self.assertRaises(pw.UsageError):
                pw.guard_out_path(SimpleNamespace(out=book, book=book))
            for bad in (URL, "b.xlsx"):
                with self.assertRaises(pw.UsageError):
                    pw.guard_out_path(SimpleNamespace(out=bad, book=book))

    def test_lock_files_exact_match(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "报表.xlsx").write_bytes(b"x")
            Path(d, "~$报表.xlsx").write_bytes(b"x")
            Path(d, "~$旧报表.xlsx").write_bytes(b"x")
            hits = wc.lock_files(os.path.join(d, "报表.xlsx"))
            self.assertEqual(len(hits), 1)
            self.assertTrue(hits[0].endswith("~$报表.xlsx"))

    def test_export_pdf_rejects_spreadsheet_out(self):
        with tempfile.TemporaryDirectory() as d:
            book = os.path.join(d, "a.xlsx")
            Path(book).write_bytes(b"PK\x03\x04")
            out = os.path.join(d, "b.xlsx")
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                code = wc.main(["export-pdf", "--file", book, "--out", out, "--force"])
            self.assertEqual(code, 2)
            self.assertIn("表格文件", buf.getvalue())

    def test_in_place_rejects_out(self):
        with tempfile.TemporaryDirectory() as d:
            book = os.path.join(d, "a.xlsx")
            Path(book).write_bytes(b"PK\x03\x04")
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                code = wc.main(["write", "--file", book, "--json", '[["x"]]',
                                "--in-place", "--i-know-this-modifies-original",
                                "--out", os.path.join(d, "b.xlsx")])
            self.assertEqual(code, 7)

    def test_discard_failed_copy_removes_partial(self):
        # 副本 copy2 中断时清理半成品；已 Save 过的产物一律保留
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "副本.xlsx")
            Path(target).write_bytes(b"partial")
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                wc.discard_failed_copy(target, True, saved=False)
            self.assertFalse(os.path.exists(target))
            self.assertIn("已清理", buf.getvalue())
            Path(target).write_bytes(b"saved")
            wc.discard_failed_copy(target, True, saved=True)
            self.assertTrue(os.path.exists(target))


if __name__ == "__main__":
    unittest.main(verbosity=2)
