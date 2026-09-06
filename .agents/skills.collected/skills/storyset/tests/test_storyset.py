"""Offline unit tests for scripts/storyset.py — no live network required.

Run:  python -m unittest discover -s tests   (from the skill directory)
  or: python tests/test_storyset.py
"""
import email.message
import io
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import storyset  # noqa: E402

SAMPLE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 500">'
          '<g id="Background"><rect x="1" y="1" width="9" height="9" style="fill:#ebebeb"/></g>'
          '<g id="Character"><circle cx="50" cy="50" r="20" style="fill:#BA68C8"/></g>'
          '<linearGradient id="abc123"/><rect fill="url(#abc123)" href="#abc123" width="5" height="5"/>'
          '</svg>')


class TestColorParsing(unittest.TestCase):
    def test_norm_hex(self):
        self.assertEqual(storyset.norm_hex("#FFF"), "#ffffff")
        self.assertEqual(storyset.norm_hex("BA68C8"), "#ba68c8")

    def test_parse_color_map_style_shorthand(self):
        m = storyset.parse_color_map("amico=#2196F3")
        self.assertEqual(m, {"#ba68c8": "#2196f3"})

    def test_parse_color_map_3digit_dst_expands(self):
        self.assertEqual(storyset.parse_color_map("#fff=#000"), {"#ffffff": "#000000"})

    def test_parse_color_map_rejects_malformed(self):
        for bad in ("foo", "#zzz=#fff", "amico=", "=#fff", "#12345=#fff"):
            with self.assertRaises(SystemExit, msg=bad):
                storyset.parse_color_map(bad)

    def test_apply_recolor_counts_and_preserves_refs(self):
        out, stats = storyset.apply_recolor(SAMPLE, {"#ba68c8": "#2196f3"})
        self.assertEqual(stats["#ba68c8"], 1)
        self.assertIn("#2196f3", out)
        # fragment references are ids, not colors — must stay untouched
        self.assertIn("url(#abc123)", out)
        self.assertIn('href="#abc123"', out)
        self.assertIn("#ebebeb", out)  # unmapped color untouched

    def test_recolor_preserves_ref_variants(self):
        svg = ('<svg><defs><linearGradient id="abc123"/></defs>'
               "<rect fill=\"url('#abc123')\"/><rect fill='url(#ABC)'/>"
               '<a href = "#abc123">x</a><b xlink:href = "#def456"/>'
               '<c fill="Url(#def456)"/></svg>')
        out, stats = storyset.apply_recolor(
            svg, {"#abc123": "#000000", "#def456": "#111111"})
        self.assertEqual(stats["#abc123"], 0)  # only refs existed
        self.assertIn("url('#abc123')", out)
        self.assertIn("url(#ABC)", out)
        self.assertIn('href = "#abc123"', out)
        self.assertIn('xlink:href = "#def456"', out)
        self.assertIn("Url(#def456)", out)

    def test_iter_colors_skips_refs(self):
        colors = list(storyset.iter_colors(SAMPLE))
        self.assertIn("#ba68c8", colors)
        self.assertNotIn("#abc123", colors)  # gradient id, not a color


class TestAnimationInjection(unittest.TestCase):
    def test_multi_element_selectors_are_all_scoped(self):
        css = storyset.build_animation_style("SID", ["Char", "Plant"], "fadeIn", None)
        self.assertIn("svg#SID.animated #Char, svg#SID.animated #Plant", css)
        self.assertIn("svg#SID:not(.animated) #Char, svg#SID:not(.animated) #Plant", css)
        self.assertNotIn(", #Plant", css)  # no unscoped global selector

    def test_entrance_prehides_loop_does_not(self):
        self.assertIn(":not(.animated)", storyset.build_animation_style("SID", [], "fadeIn", None))
        self.assertNotIn(":not(.animated)", storyset.build_animation_style("SID", [], "float", None))

    def test_validate_elements_rejects_breakout_and_empties(self):
        self.assertEqual(storyset.validate_elements("Floor,,Plant"), ["Floor", "Plant"])
        with self.assertRaises(SystemExit):
            storyset.validate_elements("x{}</style><script>")

    def test_validate_bg_rejects_breakout(self):
        self.assertEqual(storyset.validate_bg("#FFFFFF"), "#FFFFFF")
        with self.assertRaises(SystemExit):
            storyset.validate_bg("#fff}</style><script>")

    def test_ensure_svg_id(self):
        svg, sid = storyset.ensure_svg_id(SAMPLE.replace('viewBox', 'id="KeepMe" viewBox', 1), "fb")
        self.assertEqual(sid, "KeepMe")
        svg2, sid2 = storyset.ensure_svg_id(SAMPLE, "freepik_stories-my pic")
        self.assertEqual(sid2, "freepik_stories-my-pic")  # sanitized
        self.assertIn(f'id="{sid2}"', svg2)

    def test_ensure_svg_id_single_quotes_no_duplicate(self):
        svg, sid = storyset.ensure_svg_id("<svg id='sq' viewBox='0 0 1 1'></svg>", "fb")
        self.assertEqual(sid, "sq")
        self.assertEqual(svg.count("id="), 1)

    def test_set_svg_class(self):
        out = storyset.set_svg_class('<svg class="icon" viewBox="0 0 1 1"></svg>', "animated")
        self.assertIn('class="icon animated"', out)
        out2 = storyset.set_svg_class("<svg class='icon' viewBox='0 0 1 1'></svg>", "animated")
        self.assertIn('class="icon animated"', out2)
        out3 = storyset.set_svg_class(SAMPLE, "animated")
        self.assertIn('class="animated"', out3)


class TestNetworkGuards(unittest.TestCase):
    def test_check_asset_url(self):
        storyset.check_asset_url("https://stories.freepiklabs.com/storage/1/x.svg")
        for bad in ("file:///d:/x", "http://stories.freepiklabs.com/x",
                    "https://169.254.169.254/latest", "https://evil.com/x.svg"):
            with self.assertRaises(SystemExit, msg=bad):
                storyset.check_asset_url(bad)

    def test_safe_stem_blocks_traversal(self):
        s = storyset.safe_stem("../../evil")
        self.assertNotIn("/", s)
        self.assertNotIn("\\", s)
        self.assertNotIn(s, (".", ".."))  # only exact ".." components traverse
        self.assertEqual(storyset.safe_stem("..."), "storyset")

    def test_validate_render_blob(self):
        storyset.validate_render_blob("image/gif", b"GIF89a....", "gif")
        storyset.validate_render_blob("video/mp4", b"\x00\x00\x00\x18ftypisom", "mp4")
        with self.assertRaises(SystemExit):  # 200 + JSON error body must not "succeed"
            storyset.validate_render_blob("application/json", b'{"error":1}', "gif")
        with self.assertRaises(SystemExit):
            storyset.validate_render_blob("text/html; charset=UTF-8", b"<html>", "gif")
        with self.assertRaises(SystemExit):
            storyset.validate_render_blob("image/gif", b"", "gif")

    @staticmethod
    def _429(retry_after=None):
        hdrs = email.message.Message()
        if retry_after is not None:
            hdrs["Retry-After"] = str(retry_after)
        return urllib.error.HTTPError("https://x", 429, "Too Many", hdrs, io.BytesIO(b"err"))

    def test_get_json_retries_429_and_clamps_wait(self):
        ok = mock.MagicMock()
        ok.__enter__.return_value.read.return_value = b'{"data": []}'
        with mock.patch.object(storyset, "_req",
                               side_effect=[self._429(999), ok]) as req, \
             mock.patch.object(storyset.time, "sleep") as sleep:
            self.assertEqual(storyset._get_json("https://x"), {"data": []})
        self.assertEqual(req.call_count, 2)
        sleep.assert_called_once_with(120.0)  # Retry-After clamped to MAX_RETRY_AFTER

    def test_get_json_gives_up_after_retries(self):
        with mock.patch.object(storyset, "_req",
                               side_effect=[self._429(1)] * 3) as req, \
             mock.patch.object(storyset.time, "sleep"):
            with self.assertRaises(SystemExit):
                storyset._get_json("https://x")
        self.assertEqual(req.call_count, 3)

    def test_retry_after_http_date_and_negative_no_crash(self):
        ok = mock.MagicMock()
        ok.__enter__.return_value.read.return_value = b'{"data": []}'
        # RFC 7231 HTTP-date form: unparseable as float → default 20s
        with mock.patch.object(storyset, "_req",
                               side_effect=[self._429("Sun, 06 Nov 1994 08:49:37 GMT"), ok]), \
             mock.patch.object(storyset.time, "sleep") as sleep:
            storyset._get_json("https://x")
        sleep.assert_called_once_with(20.0)
        # negative value clamps to 0 instead of crashing time.sleep
        with mock.patch.object(storyset, "_req",
                               side_effect=[self._429(-5), ok]), \
             mock.patch.object(storyset.time, "sleep") as sleep:
            storyset._get_json("https://x")
        sleep.assert_called_once_with(0.0)

    def test_set_svg_class_self_closing_root(self):
        out = storyset.set_svg_class('<svg viewBox="0 0 1 1"/>', "animated")
        self.assertIn('class="animated"/>', out)

    def test_injections_ignore_commented_svg_tag(self):
        svg = '<!-- <svg id="fake"></svg> --><svg viewBox="0 0 1 1"><rect/></svg>'
        out, sid = storyset.ensure_svg_id(svg, "fb")
        self.assertIn('--><svg id="fb"', out)  # id lands on the REAL tag
        out2 = storyset.set_svg_class(svg, "animated")
        # class lands on the real tag (after the comment), not the fake one
        self.assertIn('--><svg viewBox="0 0 1 1" class="animated">', out2)
        self.assertIn('<svg id="fake"></svg> ', out2)  # comment untouched

    def test_validate_bg_rejects_trailing_newline(self):
        with self.assertRaises(SystemExit):
            storyset.validate_bg("#fff\n")

    def test_api_search_paginates_and_trims(self):
        def item(i):
            return {"src": f"https://s/{i}.svg", "style": "cuate",
                    "illustration": {"slug": f"s{i}", "name": f"n{i}"}, "tags": []}
        page1 = {"data": [item(i) for i in range(30)], "links": {"next": "u2"}}
        page2 = {"data": [item(i) for i in range(30, 40)], "links": {"next": None}}
        with mock.patch.object(storyset, "_get_json", side_effect=[page1, page2]) as gj, \
             mock.patch.object(storyset.time, "sleep") as sleep:
            out = storyset.api_search("q", "cuate", 35)
        self.assertEqual(len(out), 35)
        self.assertEqual(out[0]["slug"], "s0")
        self.assertEqual(out[34]["slug"], "s34")
        self.assertEqual(gj.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_resolve_item_not_found_lists_near_matches(self):
        page = {"data": [{"src": "u", "style": "cuate",
                          "illustration": {"slug": "other", "name": "o"}, "tags": []}],
                "links": {"next": None}}
        with mock.patch.object(storyset, "_get_json", return_value=page):
            with self.assertRaises(SystemExit) as ctx:
                storyset.resolve_item("nope-nothing", "cuate")
        self.assertIn("Near matches: other/cuate", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
