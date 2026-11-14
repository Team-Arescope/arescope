# Arescope Unity HUD — component-level technique

Deep detail for the custom `MaskableGraphic` widgets behind the Quest HUD
(`/root/Developer/arescope-beta02-hud/Runtime/ArescopeHudController.cs`, mirrored to the
InstaBox project at `Assets/ArescopeHud/`). Read this when changing panel geometry,
transparency, minimap shape or the status rows; the SKILL.md keeps only the rules.

## Panels that stay translucent

Never use a UI `Outline` to draw a card border. `Outline`/`Shadow` re-emit the whole graphic
mesh four times at ±1 unit offsets, those copies sit behind the fill, and the near-opaque
`effectColor` ends up covering the card — the fill alpha then looks inert and the panel reads
as an opaque block even at 0.25. The symptom is a card whose colour barely changes when you
lower its alpha, plus a 1 px rim that looks like a drop shadow.

Draw the border inside the same mesh instead:

- chamfered card — build the outline polygon from the rect, then a second polygon inset by
  `borderWidth`, and stitch an 8-segment ring between them;
- circular card — fill a 56-segment fan, then an annulus between `radius` and `radius - w`.

Expose `borderColor` / `borderWidth` on the graphic and let the mesh's own fill alpha be the
only opacity knob. Coating the fill in `Outline` also silently defeats later transparency
requests, so fix this before tuning alpha again.

## Repeated hairlines

Emit compass ticks — and any grid that survives a review — from one mesh, not one `Image` per
line. A 1-unit-wide `Image` is subpixel at HUD render scale, so each line lands on a different
pixel phase: some read 1 px, some 2 px, and the drift is obvious inside a masked card. One
graphic drawing every line from the same loop at the same thickness keeps weight and spacing
identical. Same reason the minimap grid moved into a single `ArescopeMapGridGraphic` before
the user removed the grid entirely.

## Text contrast at high transparency

At roughly 75% transparency the fill cannot carry text contrast against bright passthrough.
Give glyphs their own dark edge (`Shadow`, black at ~0.7 alpha, `effectDistance` (1,-1))
rather than quietly raising panel alpha, which is the change the user asked to avoid. Verify
by rendering the light background (`ARESCOPE_PREVIEW_BG=light`): if the row is unreadable
there, the shadow is missing or too weak.

## Row text clipping

`VerticalWrapMode.Truncate` drops whole trailing rows when the card is a few units short
(Manrope 16 needs ~23 units per line plus padding), and a generated row rect shorter than one
line-height renders nothing at all — the panel comes out blank or icon-only. Give generated
row labels `verticalOverflow = Overflow` and at least one line-height of rect before blaming
the content. A right-aligned element inside the card (voice meter, state dot) steals width
from the text box: widen the card instead of letting the state word truncate.

## Status rows with icons

Five slots, header plus one icon+label row object each; more statuses need a layout change,
not another text line.

Icons come from a ready-made set, per user preference — do not hand-draw SVG geometry.

1. Fetch Tabler glyphs (MIT): `https://api.iconify.design/tabler/<name>.svg?color=%23ffffff&height=64`
   — `radar-2` (scan), `stack-2` (depth), `wifi` (link), `battery-3` (power),
   `microphone` (voice), `point` (fallback).
2. Rasterise with `cairosvg` to 64×64 PNG. Install it into the system python and run the
   converter through `terminal`: `execute_code`'s interpreter does not have it.
3. Ship the PNGs plus a licence file under `Assets/Resources/ArescopeIcons/`.
4. Pick the glyph by keyword in the row text: `scan`, `depth`, `link|net|ping`,
   `power|batt`, `voice|mic|asr`, else dot.
5. Load with `Resources.Load<Texture2D>` + `Sprite.Create`, because `Resources.Load<Sprite>`
   returns null when the PNG imported as a Default texture; tint through `Image.color` so
   icons follow the panel ink.

## Round minimap

A circular map needs a real stencil, not a rectangle mask: add a `MaskableGraphic` that fills
a circle as a 56-segment fan and put `Mask` on the same object with `showMaskGraphic = true`,
because `RectMask2D` only clips rectangles. Re-inset labels into the circular safe area (a
full-width header loses its corners), recentre markers and chevron, rescale the marker radius,
and drop the top copper hairline on the round card. The user removed the minimap grid outright
because it will collide with future map content: leave the circle face empty apart from
header, contacts and chevron, and do not reintroduce grid, rings or bearing ticks inside it.
