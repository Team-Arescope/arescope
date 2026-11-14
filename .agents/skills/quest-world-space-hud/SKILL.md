---
name: quest-world-space-hud
description: Use when placing a world-space HUD in a Quest app.
version: 1.0.0
author: hermes-curator
license: MIT
metadata:
  hermes:
    tags: [unity, quest, xr, hud, ui, world-space, canvas]
---

# World-space HUD in a Quest app

## When to use

A headset HUD feels far away, its cards sit near the lens rim and blur, panels collide after a layout change, or a minimap/overlay card is too dense to read. Also before any offline HUD preview render.

## Placement rules

- **Distance to the face ≈ 0.6 m.** At 1.1–1.2 m the canvas reads as a distant wall. Do not shrink cards to compensate for a far canvas; move the canvas closer and let it scale.
- **Keep panels inside the central ~75 % of the canvas width.** Quest lens edges blur, so a card that looks crisp in an offline screenshot is unreadable when it sits near the rim. When the user says "move the side elements closer to the centre", increase the inset again (this project went 40 → 112 → 150 canvas units).
- **Size against the field of view, not arbitrary units.** Parent the canvas to the camera at the chosen distance and derive its height from the FOV so the layout fits the same way at any distance.
- **Overlay cards need their own contrast.** Semi-transparent panels over a lit real-world view need an outline (`Shadow`, 1 px, black, ~0.7 alpha) on glyphs; white text alone disappears against a bright sky.
- **A minimap is a slice, not a cloud.** Filter points to a narrow band around eye height (≈ ±0.10 m) and cap the point count (≈ 64). A ±1 m band fills the map with floor and ceiling and reads as noise.

## Procedure

1. Change distance and insets in the HUD controller (`followDistance`, per-card x offsets), not in the prefab, so the preview and the device stay in sync.
2. Render an offline preview at the target resolution and judge placement against a real scene, not a flat grey background (recipe: `references/offline-hud-preview.md`).
3. Check three things in the render: cards do not overlap, the top row does not sit on the brightest part of the sky, and nothing important lands in the outer 10 % of the frame.
4. Ship one build per placement change and ask for a headset check — placement is a comfort judgement the screenshot cannot settle.

## Pitfalls

- **A world-space canvas rendered to a `RenderTexture` gets squeezed when `camera.aspect` is stale.** The panels overlap and the type looks vertically compressed while the layout is fine on device. Set `camera.aspect = width / height` (and rebuild the projection matrix) immediately before `Render()`. A byte-identical screenshot before and after a change is the tell that the render never picked up the new state.
- **A flat colour background hides legibility failures.** A HUD that reads well on dark grey can vanish over a bright sky or a sunlit surface. Preview over the actual scene.
- **Do not tune placement from a 16:9 monitor screenshot alone.** Peripheral cards that look comfortably inset on a flat screen still sit in the blurred rim region of the headset.

## Related files

- `references/offline-hud-preview.md` — edit-mode render recipe: scene camera, HUD lifecycle init, aspect, canvas update, PNG out.
