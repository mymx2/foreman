"""对照断言：tidy 产物是否词安全、文本守恒、伪影截短、check 合规。用法见 README.md。"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "subtitles"))
from srt import read_srt, visible_len

EPS = 1e-3


def visible_seq(text):
    return "".join(ch for ch in text if not ch.isspace())


def main(raw_path, out_path, max_chars=16, max_dur=6.0):
    raw = read_srt(Path(raw_path))
    out = read_srt(Path(out_path))
    results = []

    broken, conserved_bad = [], []
    for i, cue in enumerate(raw):
        # repair 只抬/收 end，不动 start；按起点区间归属 parts
        limit = raw[i + 1]["start"] - EPS if i + 1 < len(raw) else float("inf")
        parts = [o for o in out if cue["start"] - EPS <= o["start"] < limit]
        if not parts:
            conserved_bad.append(cue["text"])
            continue
        joined = "".join(p["text"] for p in parts)
        if visible_seq(joined) != visible_seq(cue["text"]):
            conserved_bad.append(cue["text"])
        for run in re.findall(r"[A-Za-z0-9]+", cue["text"]):
            if not any(run in p["text"] for p in parts):
                broken.append(run)
    results.append({"name": "ascii_runs_intact", "passed": not broken,
                    "evidence": f"count={len(broken)} broken={broken[:8]}"})
    results.append({"name": "visible_chars_conserved_per_cue",
                    "passed": not conserved_bad,
                    "evidence": f"bad={conserved_bad[:5]}"})

    uncapped = [c["text"] for c in out
                if visible_len(c["text"]) <= 2
                and c["end"] - c["start"] > max_dur + EPS]
    raw_artifacts = [c for c in raw if visible_len(c["text"]) <= 2
                     and c["end"] - c["start"] > max_dur + EPS]
    capped = [c for c in out if visible_len(c["text"]) <= 2
              and c["end"] - c["start"] <= 1.0 + EPS]
    results.append({"name": "short_artifacts_capped",
                    "passed": not uncapped and len(capped) >= len(raw_artifacts),
                    "evidence": f"raw_artifacts={len(raw_artifacts)} capped={len(capped)} uncapped={uncapped[:5]}"})

    wide = [c["text"] for c in out if visible_len(c["text"]) > max_chars]
    longish = [c["text"] for c in out if c["end"] - c["start"] > max_dur + EPS]
    overlaps = sum(1 for a, b in zip(out, out[1:]) if a["end"] > b["start"] + EPS)
    results.append({"name": "check_thresholds_met",
                    "passed": not wide and not longish and overlaps == 0,
                    "evidence": f"wide={wide[:3]} long={longish[:3]} overlaps={overlaps}"})
    ok = all(r["passed"] for r in results)
    print(json.dumps({"ok": ok, "lines": len(out), "assertions": results},
                     ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2],
                          int(sys.argv[3]) if len(sys.argv) > 3 else 16))