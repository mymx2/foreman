import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def ocr_elements(result):
    """Empty result is normal (blank window, no text); return []."""
    if result.boxes is None or result.txts is None or result.scores is None:
        return []
    return [
        {"label": text, "bounds": box.tolist(), "confidence": score, "source": "ocr"}
        for box, text, score in zip(result.boxes, result.txts, result.scores)
    ]


def main():
    parser = argparse.ArgumentParser(description="Locate exact text in a window image with OCR.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from rapidocr import RapidOCR

    elements = ocr_elements(RapidOCR()(args.image))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(elements, ensure_ascii=False, indent=2)
    args.output.write_text(serialized, encoding="utf-8")
    print(json.dumps({"artifact": str(args.output), "element_count": len(elements), "sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
