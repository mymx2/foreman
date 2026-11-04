# Mobile App — Local Additions (Design-time only)

These are local additions; the upstream mobile prompt (`guidelines-mobile-app.md`) is otherwise unchanged.

## Touch Targets

- Touch target ≥44×44 (iOS HIG / WCAG 2.5.5), Android 48×48.
- If the platform is undeclared, use 48×48.
- Visual icons may be smaller than the hit area; bind the hit area to a frame's `width` / `height` so `batch_read` can verify it.
- Verification: iOS 44×44 pass; Android or undeclared 48×48 required; an Android frame at 44×44 fails; an undeclared-platform frame at 44×44 also fails.
