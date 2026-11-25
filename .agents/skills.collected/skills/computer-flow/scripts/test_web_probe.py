import json
import unittest
from unittest import mock

from web_probe import CDP, NeedMore, decode_frame, encode_frame, probe


class FakeCDP:
    """Stand-in for CDP: records clicks, returns a canned probe payload."""

    def __init__(self, payload):
        self.payload = payload
        self.clicks = []

    def click(self, x, y, button="left"):
        self.clicks.append((x, y, button))

    def evaluate(self, expression):
        return self.payload


def _menu_payload(menu_rect, viewport=(1600, 952)):
    return {"viewport": list(viewport), "menuRect": menu_rect, "menuItems": []}


class FrameTests(unittest.TestCase):
    def test_masked_short_frame_round_trip(self):
        frame = encode_frame(b"hello")
        fin, opcode, payload, used = decode_frame(frame)
        self.assertTrue(fin)
        self.assertEqual(opcode, 0x1)
        self.assertEqual(payload, b"hello")
        self.assertEqual(used, len(frame))

    def test_medium_frame_uses_16_bit_length(self):
        payload = b"x" * 200
        frame = encode_frame(payload, mask=False)
        self.assertEqual(frame[1] & 0x7F, 126)
        fin, opcode, decoded, used = decode_frame(frame)
        self.assertTrue(fin)
        self.assertEqual(decoded, payload)
        self.assertEqual(used, len(frame))

    def test_large_frame_uses_64_bit_length(self):
        payload = b"y" * 70000
        frame = encode_frame(payload)
        fin, opcode, decoded, used = decode_frame(frame)
        self.assertTrue(fin)
        self.assertEqual(decoded, payload)
        self.assertEqual(used, len(frame))

    def test_truncated_frame_needs_more(self):
        frame = encode_frame(b"hello", mask=False)
        with self.assertRaises(NeedMore):
            decode_frame(frame[:-1])


class VerdictTests(unittest.TestCase):
    def test_no_menu(self):
        cdp = FakeCDP({"viewport": [1600, 952], "menuRect": None})
        result = probe(cdp, 10, 20, settle=0)
        self.assertEqual(result["verdict"], "no-menu")
        self.assertEqual(cdp.clicks, [(10, 20, "right")])

    def test_fully_offscreen_below(self):
        cdp = FakeCDP(_menu_payload([684, 1407, 128, 178]))
        self.assertEqual(probe(cdp, 1, 2, settle=0)["verdict"], "offscreen")

    def test_fully_offscreen_above(self):
        cdp = FakeCDP(_menu_payload([3, -356, 122, 169]))
        self.assertEqual(probe(cdp, 1, 2, settle=0)["verdict"], "offscreen")

    def test_partially_offscreen(self):
        cdp = FakeCDP(_menu_payload([1500, 900, 128, 178]))
        self.assertEqual(probe(cdp, 1, 2, settle=0)["verdict"], "partially-offscreen")

    def test_visible(self):
        cdp = FakeCDP(_menu_payload([431, 636, 128, 178]))
        self.assertEqual(probe(cdp, 1, 2, settle=0)["verdict"], "visible")

    def test_zero_size_menu_is_no_size(self):
        cdp = FakeCDP(_menu_payload([431, 636, 0, 0]))
        self.assertEqual(probe(cdp, 1, 2, settle=0)["verdict"], "no-size")

    def test_hidden_menu_template_is_no_size(self):
        cdp = FakeCDP({"viewport": [1600, 952], "menuCount": 2, "menuRect": [0, 0, 0, 0]})
        self.assertEqual(probe(cdp, 1, 2, settle=0)["verdict"], "no-size")

    def test_unmeasurable_viewport_is_not_offscreen(self):
        cdp = FakeCDP({"viewport": [0, 0], "menuRect": [10, 10, 100, 40]})
        self.assertEqual(probe(cdp, 1, 2, settle=0)["verdict"], "viewport-unknown")


class _EventOnlyWebSocket:
    """Delivers unrelated CDP events forever and never the awaited response."""

    def send_text(self, text):
        pass

    def recv_text(self):
        return json.dumps({"method": "Runtime.consoleAPICalled", "params": {}})

    def close(self):
        pass


class CDPTests(unittest.TestCase):
    def test_send_gives_up_when_only_events_arrive(self):
        cdp = CDP.__new__(CDP)
        cdp._ws = _EventOnlyWebSocket()
        cdp._id = 0
        cdp._timeout = 10.0
        with mock.patch("web_probe.time.monotonic", side_effect=[0.0, 100.0]):
            with self.assertRaises(RuntimeError):
                cdp.send("Runtime.evaluate")


if __name__ == "__main__":
    unittest.main()
