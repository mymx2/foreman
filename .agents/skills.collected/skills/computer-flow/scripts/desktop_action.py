"""Application-agnostic action loop: observe -> resolve -> act -> assert.

No layout, window size, region or application name is baked in here. Callers give
a text selector plus optional constraints derived from their own observation.
"""

import hashlib
import json
import os
import sys
from dataclasses import dataclass

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

POSITION_BUCKET = 8


class SelectionError(RuntimeError):
    """Zero or multiple elements matched, or the element is outside the allowed area."""

    code = "NO_MATCH"


class StaleSnapshotError(RuntimeError):
    """The element was resolved from a snapshot that is no longer current."""

    code = "STALE_REF"


class OccludedError(RuntimeError):
    """The target point is covered by another window, so clicking would hit the wrong app."""

    code = "OCCLUDED"

    def __init__(self, message, blocker=None):
        super().__init__(f"OCCLUDED: {message}")
        self.blocker = blocker


RETRY_DISPOSITION = {
    "stale_snapshot": "safe",
    "no_match": "safe_after_reobserve",
    "ambiguous": "never",
    "occluded": "never",
    "assertion_failed": "never",
    "unchanged": "diagnose_first",
    "unknown": "never",
}


def normalize_region(region):
    if region is None:
        return None
    if len(region) != 4:
        raise ValueError("region needs four fractions: left, top, right, bottom")
    if any(value < 0 or value > 1 for value in region):
        raise ValueError(f"region must be fractions in [0, 1]: {region}")
    if region[0] >= region[2] or region[1] >= region[3]:
        raise ValueError(f"region needs left < right and top < bottom: {region}")
    return region


def assert_fresh(element, snapshot_id):
    """Refuse to act on an element resolved from a different snapshot."""
    if element.snapshot and snapshot_id and element.snapshot != snapshot_id:
        raise StaleSnapshotError(
            f"STALE_REF: element {element.label!r} belongs to snapshot {element.snapshot}, not {snapshot_id}"
        )


def _matches(element, text, match, minimum_confidence, sources, auto_id=""):
    if auto_id:
        # AutomationId is a stable native identifier; prefer it over label text.
        ok = element.identifier == auto_id
    else:
        label = element.label
        if match == "exact":
            ok = label == text
        elif match == "suffix":
            ok = label.endswith(text)
        elif match == "contains":
            ok = text in label
        else:
            raise ValueError(f"unknown match mode: {match}")
    return ok and element.confidence >= minimum_confidence and (not sources or element.source in sources)


def _inside(element, region, container):
    if region is None:
        return True
    left, top, width, height = container
    el, et, er, eb = element.rect
    return (
        el >= left + region[0] * width
        and et >= top + region[1] * height
        and er <= left + region[2] * width
        and eb <= top + region[3] * height
    )


def select(elements, text, container, match="exact", minimum_confidence=0.0, region=None, sources=None, auto_id=""):
    """Exactly one match or SelectionError. Never silently picks the first of many.

    When `auto_id` is given it wins over `text`: AutomationId is a stable native
    identifier, whereas labels are localized and can change between versions.
    """
    region = normalize_region(region)
    found = [
        element
        for element in elements
        if _matches(element, text, match, minimum_confidence, sources, auto_id)
        and _inside(element, region, container)
    ]
    if not found:
        wanted = f"auto_id={auto_id!r}" if auto_id else f"{text!r} (match={match})"
        raise SelectionError(f"no element matched {wanted} (region={region})")
    if len(found) > 1:
        spots = [tuple(round(v) for v in element.center) for element in found]
        raise SelectionError(f"{len(found)} elements matched {auto_id or text!r}; narrow the region: {spots}")
    return found[0]


def select_unique_by(elements, key, minimum_confidence=0.0):
    """Pick the single element carrying a unique identifier/label, e.g. an order number."""
    found = [element for element in elements if key in element.label and element.confidence >= minimum_confidence]
    if len(found) != 1:
        raise SelectionError(f"expected one element containing {key!r}, found {len(found)}")
    return found[0]


def state_digest(elements, bucket=POSITION_BUCKET):
    """Fingerprint of what is visible: labels plus quantised centres.

    Positions are included so scrolling, paging and layout movement register as
    change; otherwise an unchanged page and a scrolled page hash identically.
    """
    rows = sorted(
        (element.label, element.source, round(element.center[0] / bucket), round(element.center[1] / bucket))
        for element in elements
        if element.label
    )
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode("utf-8")).hexdigest()


@dataclass
class StallTracker:
    """Stop repeating the same action against a page that is not changing."""

    limit: int = 2

    def update(self, previous, digest, changed):
        """Count consecutive attempts that left the page unchanged.

        A first attempt that changes nothing is attempt 1; when the count reaches
        `limit` the caller must stop and diagnose rather than click again.
        """
        if previous and previous.get("digest") == digest and not changed:
            count = previous.get("count", 0) + 1
        elif not changed:
            count = 1
        else:
            count = 0
        return {"digest": digest, "count": count}, count >= self.limit


def load_state(path):
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path, state):
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def write_json(path, payload):
    """Atomic write via tmp+replace: a crash mid-write leaves the previous log
    intact instead of a truncated JSON blob. os.replace is atomic on Windows
    for same-directory renames."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=list), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        # Best-effort cleanup so a failed write does not accumulate orphan tmp
        # files in the observation directory.
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def append_jsonl(path, entry):
    """Append a single JSON line. O(1) per call, crash-safe at line granularity:
    a torn write affects at most the last line, which readers can skip."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False, default=list)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


@dataclass
class StepResult:
    text: str
    clicked: tuple
    before_digest: str
    after_digest: str
    changed: bool
    stall_count: int
    stalled: bool
    assertion: dict

    def as_dict(self):
        return {
            "text": self.text,
            "clicked": list(self.clicked),
            "before_digest": self.before_digest,
            "after_digest": self.after_digest,
            "changed": self.changed,
            "stall_count": self.stall_count,
            "stalled": self.stalled,
            "assertion": self.assertion,
        }
