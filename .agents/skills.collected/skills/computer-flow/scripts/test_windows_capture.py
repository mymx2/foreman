import unittest

from windows_capture import MOUSE_FLAGS, visibility_of


class FakeFrame:
    """Minimal stand-in for Frame: image pixels + origin + size."""

    def __init__(self, pixels, origin=(0, 0)):
        self._pixels = pixels
        self.origin = origin
        height = len(pixels)
        width = len(pixels[0]) if height else 0
        self.size = (width, height)

    @property
    def width(self):
        return self.size[0]

    @property
    def height(self):
        return self.size[1]

    class _Loader:
        def __init__(self, pixels):
            self._pixels = pixels

        def __getitem__(self, xy):
            x, y = xy
            return self._pixels[y][x]

    @property
    def image(self):
        return self

    def load(self):
        return FakeFrame._Loader(self._pixels)


def _solid(width, height, rgb):
    return [[rgb for _ in range(width)] for _ in range(height)]


class VisibilityTests(unittest.TestCase):
    def test_identical_frames_look_visible(self):
        window = FakeFrame(_solid(16, 16, (200, 100, 50)))
        screen = FakeFrame(_solid(16, 16, (200, 100, 50)))
        result = visibility_of(window, screen, step=2)
        self.assertTrue(result["comparable"])
        self.assertTrue(result["looks_visible"])
        self.assertEqual(result["mean_abs_diff"], 0)

    def test_covered_window_looks_invisible(self):
        window = FakeFrame(_solid(16, 16, (255, 255, 255)))
        screen = FakeFrame(_solid(16, 16, (0, 0, 0)))
        result = visibility_of(window, screen, step=2)
        self.assertTrue(result["comparable"])
        self.assertFalse(result["looks_visible"])
        self.assertGreater(result["mean_abs_diff"], 12.0)

    def test_window_off_screen_is_not_comparable(self):
        # Window sits fully to the right of a 16px screen.
        window = FakeFrame(_solid(8, 8, (255, 0, 0)), origin=(100, 0))
        screen = FakeFrame(_solid(16, 16, (255, 255, 255)))
        result = visibility_of(window, screen, step=2)
        self.assertFalse(result["comparable"])
        self.assertTrue(result["clipped"])

    def test_partially_clipped_window_is_compared_on_visible_part(self):
        # Left half of the window hangs off the left edge of the screen.
        window = FakeFrame(_solid(16, 16, (10, 20, 30)), origin=(-8, 0))
        screen = FakeFrame(_solid(32, 16, (10, 20, 30)))
        result = visibility_of(window, screen, step=2)
        self.assertTrue(result["clipped"])
        self.assertTrue(result["comparable"])
        self.assertTrue(result["looks_visible"])


class MouseButtonTests(unittest.TestCase):
    def test_each_button_has_distinct_down_and_up_flags(self):
        self.assertEqual(MOUSE_FLAGS["left"], (0x0002, 0x0004))
        self.assertEqual(MOUSE_FLAGS["right"], (0x0008, 0x0010))
        self.assertEqual(MOUSE_FLAGS["middle"], (0x0020, 0x0040))

    def test_right_click_is_not_left_click(self):
        self.assertNotEqual(MOUSE_FLAGS["right"], MOUSE_FLAGS["left"])

    def test_flags_cover_every_supported_button(self):
        for name in ("left", "right", "middle"):
            down, up = MOUSE_FLAGS[name]
            self.assertNotEqual(down, up, f"{name} press and release flags must differ")


if __name__ == "__main__":
    unittest.main()
