# Evidence

Read this when the task asks for screenshots, screen recording, visual
regression evidence, or an explanation of what appeared on the device. Use
[CLI](cli.md) for the command and plan schemas.

## Keep the claims separate

Report these as different evidence layers:

- **Captured**: the operation receipt succeeded and contains the artifact URI,
  SHA-256 digest, media type, size, source, target, and revision.
- **Visually inspected**: an image- or video-capable tool actually opened the
  returned artifact and evaluated its visible content. A text reader is not an
  image viewer; a digest is not inspection.
- **Behavior verified**: a semantic `assert` or one exact native test
  established the behavior. Pixels alone do not establish this layer.

## Artifact integrity

The Skill-local `scripts/verify-artifact-receipt.mjs` independently recomputes
a local artifact's byte size and SHA-256 digest against a saved receipt:

```bash
node "/absolute/loaded-skill/scripts/verify-artifact-receipt.mjs" \
  "/absolute/path/to/mobile-use-receipt.json"
```

Exit classes: `0` every discovered local artifact matches; `2` invalid
arguments or unreadable JSON; `3` file missing or not a local `file:` URI; `4`
size/digest differs. A verified result supports **local bytes match the
receipt** — not **visually inspected** and not **behavior passed**. It does not
open, copy, or decode media.

Artifacts are written under the system temp `mobile-use-artifacts/<device>/`
directory (override with `MOBILE_USE_ARTIFACT_DIR`) and carry `uri`, `digest`,
`mediaType`, `size`, `source`, `platform`, and `targetId`.

## Screenshots and recordings

Use an explicit `capture_screenshot` plan step for a named milestone or final
state. For diagnostics set `{"evidence":{"screenshots":"on-failure"}}`. Prefer
transactional plan recording `{"evidence":{"recording":"native"}}` on Android;
the plan starts recording before its first step and stops it on success or
failure before session cleanup.

Raw MP4 capture is not automatically model-visible — pair recordings with
screenshots at the key states when the visual content must be reviewed.

## Privacy and retention

Device media can contain account data, notifications, typed text, tokens, or
customer content. Capture only when material to the task. Do not publish,
upload, or open media in another application unless the request authorizes it.
Preserve provenance metadata in the verification record.
