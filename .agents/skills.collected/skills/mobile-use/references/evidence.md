# Evidence

Read this when the task asks for screenshots, screen recording, visual
regression evidence, or an explanation of what appeared on the device. Use
[CLI](cli.md) for the command and plan schemas.

## Keep the claims separate

Report these as different evidence layers. A higher layer never implies a lower
one, and passing one layer is not proof of another:

| Layer | 成立条件 | 不能说明什么 |
|---|---|---|
| **Build** | 选定的 project / target 编译成功 | 没证明装上了、没证明能跑 |
| **Captured** | 操作回执成功，含 artifact URI、SHA-256、media type、size、source、target、revision | 没证明有人看过内容 |
| **Visually inspected** | 真正用图像/视频工具打开了产物并评估可见内容（文本读取器不算图像查看器，摘要不等于检查） | 没证明行为正确 |
| **Interactive** | 实时设备界面完成了语义化操作流程 | 没证明断言通过 |
| **Native test** | 某个精确 selector 返回 `data.output.outcome == "passed"` | 没覆盖其他场景 |
| **Repair** | 同一冻结契约在修复前失败、修复后通过 | 没证明其他契约也好了 |

像素不能建立行为层；断言通过不能建立视觉层。声明结论时说清是哪一层，缺的层明确标为未验证。

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
