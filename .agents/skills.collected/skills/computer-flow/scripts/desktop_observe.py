"""Observation: turn a window (and its overlays) into structured elements.

Elements carry physical screen rectangles so callers can act without assuming
any window size, DPI, layout or application version.
"""

import json
import re
import sys
from dataclasses import dataclass, field

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# OCR often inserts whitespace between CJK glyphs ("查询" → "查 询"). Strip
# whitespace that sits between two CJK characters so OCR labels line up with
# UIA labels; spaces between Latin/digit tokens are kept intact.
_CJK_SPACE = re.compile(
    r"(?<=[一-鿿　-〿＀-￯])\s+(?=[一-鿿　-〿＀-￯])"
)


@dataclass(frozen=True)
class Element:
    source: str
    label: str
    rect: tuple
    confidence: float = 1.0
    role: str = ""
    identifier: str = ""
    snapshot: str = ""

    @property
    def center(self):
        left, top, right, bottom = self.rect
        return ((left + right) / 2, (top + bottom) / 2)

    def as_dict(self):
        return {
            "source": self.source,
            "label": self.label,
            "rect": list(self.rect),
            "confidence": self.confidence,
            "role": self.role,
            "identifier": self.identifier,
            "snapshot": self.snapshot,
        }

    def bind_snapshot(self, snapshot_id):
        return Element(
            source=self.source,
            label=self.label,
            rect=self.rect,
            confidence=self.confidence,
            role=self.role,
            identifier=self.identifier,
            snapshot=snapshot_id,
        )


@dataclass
class Observation:
    handle: int
    rect: tuple
    image_size: tuple
    snapshot_id: str = ""
    window: list = field(default_factory=list)
    overlays: list = field(default_factory=list)

    @property
    def elements(self):
        return self.window + self.overlays

    def as_dict(self):
        return {
            "handle": self.handle,
            "rect": list(self.rect),
            "image_size": list(self.image_size),
            "snapshot_id": self.snapshot_id,
            "window": [element.as_dict() for element in self.window],
            "overlays": [element.as_dict() for element in self.overlays],
        }


def _normalize(text):
    base = " ".join((text or "").split())
    return _CJK_SPACE.sub("", base)


def ocr_elements(image):
    """OCR an image, returning elements in image-local pixels."""
    from rapidocr import RapidOCR

    result = RapidOCR()(image)
    if result.boxes is None or result.txts is None or result.scores is None:
        return []
    elements = []
    for box, text, score in zip(result.boxes, result.txts, result.scores):
        label = _normalize(text)
        if not label:
            continue
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        elements.append(
            {
                "label": label,
                "rect": (min(xs), min(ys), max(xs), max(ys)),
                "confidence": float(score),
            }
        )
    return elements


def window_scale(handle):
    """How much a window's captured bitmap is scaled compared to screen pixels.

    On a 200% display, PrintWindow returns a bitmap the size of the *physical*
    window, but its content is the application's layout rendered at the smaller
    logical size and then upscaled. So one bitmap pixel covers 0.5 screen pixels
    for a DPI-aware process. Treating bitmap coordinates as screen coordinates
    puts every click at twice the intended offset — the cursor lands inside the
    window, WindowFromPoint agrees, and nothing happens.

    Returns 1.0 on a 96 DPI window, 2.0 on a 192 DPI one.
    """
    try:
        import ctypes

        dpi = ctypes.windll.user32.GetDpiForWindow(handle)
        return max(dpi, 1) / 96.0
    except Exception:
        return 1.0


def _to_screen(elements, origin, scale=1.0):
    """Convert OCR rectangles from bitmap pixels to physical screen pixels."""
    return [
        Element(
            source="ocr",
            label=item["label"],
            rect=(
                origin[0] + item["rect"][0] / scale,
                origin[1] + item["rect"][1] / scale,
                origin[0] + item["rect"][2] / scale,
                origin[1] + item["rect"][3] / scale,
            ),
            confidence=item["confidence"],
        )
        for item in elements
    ]


def _uia_elements(handle):
    """Native accessibility elements when the app exposes them.

    Absence is normal for self-drawn UIs; it is reported as an empty list rather
    than an error so OCR can take over.
    """
    try:
        from pywinauto import Desktop

        window = Desktop(backend="uia").window(handle=handle)
        if not window.exists(timeout=1):
            return []
    except Exception:
        return []
    elements = []
    for element in window.descendants():
        try:
            label = _normalize(element.window_text())
            info = element.element_info
            role = info.control_type or ""
            identifier = getattr(info, "automation_id", "") or ""
            if not label and not identifier:
                continue
            rect = element.rectangle()
            elements.append(
                Element(
                    source="uia",
                    label=label,
                    rect=(rect.left, rect.top, rect.right, rect.bottom),
                    role=role,
                    identifier=identifier,
                )
            )
        except Exception:
            continue
    return elements


def _rect_iou(a, b):
    """Intersection-over-union of two (left, top, right, bottom) rects."""
    al, at, ar, ab = a
    bl, bt, br, bb = b
    il, it = max(al, bl), max(at, bt)
    ir, ib = min(ar, br), min(ab, bb)
    if ir <= il or ib <= it:
        return 0.0
    inter = (ir - il) * (ib - it)
    area_a = max(ar - al, 0) * max(ab - at, 0)
    area_b = max(br - bl, 0) * max(bb - bt, 0)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _rect_contains_center(outer, inner):
    """True when `inner`'s center lies inside `outer` (inclusive)."""
    ol, ot, or_, ob = outer
    il, it, ir, ib = inner
    cx, cy = (il + ir) / 2, (it + ib) / 2
    return ol <= cx <= or_ and ot <= cy <= ob


def _same_physical_control(a, b):
    """OCR reports the tight text box; UIA reports the whole control. For short
    text in a wide control their IoU is tiny, so instead require that one's
    center lies inside the other's rect, plus meaningful vertical overlap
    (they sit on the same line)."""
    if not (_rect_contains_center(a.rect, b.rect) or _rect_contains_center(b.rect, a.rect)):
        return False
    al, at, ar, ab = a.rect
    bl, bt, br, bb = b.rect
    overlap_top = max(at, bt)
    overlap_bottom = min(ab, bb)
    if overlap_bottom <= overlap_top:
        return False
    overlap = overlap_bottom - overlap_top
    min_height = max(min(ab - at, bb - bt), 1)
    return overlap / min_height >= 0.5


def merge_duplicates(elements, iou_threshold=None):
    """Collapse elements that describe the same physical control.

    OCR and UIA often both report the same button with the same label but very
    different rectangles (tight text box vs whole control). Feeding both to
    `select` would turn one real control into an ambiguity error. Two elements
    are treated as duplicates when their labels match and either center lies
    inside the other's rect with at least half the smaller rect's height in
    common. On a collision keep the higher-confidence source (UIA wins ties:
    native identifiers are more stable than OCR boxes).
    """
    merged = []
    rank = {"uia": 0, "ocr": 1}
    for element in sorted(elements, key=lambda e: (rank.get(e.source, 2), -e.confidence)):
        duplicate_of = None
        for kept in merged:
            if kept.label == element.label and _same_physical_control(kept, element):
                duplicate_of = kept
                break
        if duplicate_of is None:
            merged.append(element)
    return merged


def observe(handle, include_uia=True, include_overlays=True):
    """Capture the window and any overlay windows it owns, as screen-space elements.

    Every observation gets a stable `snapshot_id`; elements are bound to it so a
    stale snapshot can be rejected instead of clicked with outdated coordinates.
    """
    import hashlib
    import time

    from windows_capture import capture_window
    from windows_list import overlay_chain, window_rect_or_none

    window_frame = capture_window(handle)
    observation = Observation(
        handle=handle,
        rect=window_frame.origin + window_frame.size,
        image_size=window_frame.size,
    )

    # A screen-cropped frame is 1:1 with physical screen pixels, so bitmap
    # coordinates are already screen coordinates. Only a PrintWindow frame can
    # come back at the application's logical size (DPI-unaware process on a
    # scaled display) and needs dividing by the window scale.
    scale = window_scale(handle) if getattr(window_frame, "source", "screen") == "printwindow" else 1.0
    window_elements = _to_screen(ocr_elements(window_frame.image), window_frame.origin, scale)
    if include_uia:
        window_elements.extend(_uia_elements(handle))
    observation.window = merge_duplicates(window_elements)
    seen = {(element.label, element.rect) for element in observation.window}

    if include_overlays:
        for overlay in overlay_chain(handle):
            rect = window_rect_or_none(overlay.handle)
            if rect is None:
                continue
            try:
                frame = capture_window(overlay.handle)
            except RuntimeError:
                continue
            overlay_scale = window_scale(overlay.handle) if getattr(frame, "source", "screen") == "printwindow" else 1.0
            for element in _to_screen(ocr_elements(frame.image), frame.origin, overlay_scale):
                if (element.label, element.rect) not in seen:
                    observation.overlays.append(element)
                    seen.add((element.label, element.rect))

    snapshot_id = hashlib.sha256(
        f"{handle}:{window_frame.origin}:{window_frame.size}:{time.monotonic_ns()}".encode()
    ).hexdigest()[:16]
    observation.snapshot_id = snapshot_id
    observation.window = [element.bind_snapshot(snapshot_id) for element in observation.window]
    observation.overlays = [element.bind_snapshot(snapshot_id) for element in observation.overlays]
    return observation


def merge(observation, extra_elements):
    observation.overlays.extend(extra_elements)
    return observation


def save(observation, path):
    path.write_text(json.dumps(observation.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Observe a window and its overlays as structured elements.")
    parser.add_argument("--handle", type=int, required=True)
    parser.add_argument("--observation-dir", type=Path, required=True)
    parser.add_argument("--no-uia", action="store_true")
    parser.add_argument("--no-overlays", action="store_true")
    args = parser.parse_args()

    from windows_capture import bring_to_front, capture_screen, set_dpi_awareness

    set_dpi_awareness()
    args.observation_dir.mkdir(parents=True, exist_ok=True)
    activation = bring_to_front(args.handle)
    observation = observe(
        args.handle,
        include_uia=not args.no_uia,
        include_overlays=not args.no_overlays,
    )
    save(observation, args.observation_dir / "observation.json")
    capture_screen().image.save(args.observation_dir / "screen.png")
    print(
        json.dumps(
            {
                "handle": args.handle,
                "rect": list(observation.rect),
                "window_elements": len(observation.window),
                "overlay_elements": len(observation.overlays),
                "activation": activation,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
