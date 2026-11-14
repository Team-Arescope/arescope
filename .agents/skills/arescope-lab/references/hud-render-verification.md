# HUD render: review fixture and numeric verification

## Two-stage check for every HUD iteration

1. Render the real Unity HUD, never an HTML mock: `-executeMethod RenderArescopeHudPreview.Run` with `DISPLAY=:1` and `ARESCOPE_HUD_PREVIEW_PATH`.
2. Measure the PNG in code, then look at it with vision for taste and legibility only.

## Fixture first

The empty state renders as `SYSTEM STATUS —` / `VOICE —` and cannot be judged for density. Seed a representative fixture: 3–4 status rows, an active voice state (`Listening`), a few minimap contacts, one Copilot sentence. Keep an env switch (`ARESCOPE_PREVIEW_EMPTY=1`) for the bare state and make the copy obviously synthetic (`PREVIEW:`), never live telemetry.

Keep fixture points away from the centre chevron: a contact sitting under the vehicle marker is invisible but still counted, so `CONTACTS 5` over four visible dots reads as a defect during review.

## Measure geometry with PIL

> Code example split: part 1/2 of the archived reference block; concatenate in order if needed.
```python
from PIL import Image
import numpy as np
im = Image.open(path).convert("RGB")
a = np.asarray(im).astype(int)
bg = a[5, 5]                                    # corner = background
mask = np.abs(a - bg).sum(axis=2) > 12
rows, cols = mask.sum(axis=1), mask.sum(axis=0)

def bands(profile, thr=1):
    out, start = [], None
    for i, v in enumerate(profile):
        if v >= thr and start is None: start = i
        elif v < thr and start is not None: out.append((start, i - 1)); start = None
    if start is not None: out.append((start, len(profile) - 1))
    return out
```
> Code example split: part 2/2 of the archived reference block; concatenate in order if needed.
```python

def bbox(x0, x1, y0, y1):                       # per card, from the column bands
    ys, xs = np.where(mask[y0:y1, x0:x1])
    return x0 + xs.min(), x0 + xs.max(), y0 + ys.min(), y0 + ys.max()
```

Read it as:

- Card height in pixels divided by the card's `sizeDelta` gives the render scale; use it to predict whether another text row fits before rendering again.
- A card whose measured height did not grow after you added a row is truncating. `VerticalWrapMode.Truncate` drops whole trailing rows silently, so grow `sizeDelta` height rather than shrinking type.
- Compare top and bottom margins: the user wants the bottom row lifted off the lower edge of vision, so an asymmetric margin (bottom clearly larger than top) is the goal, not a defect.
- Check card left edges share an `x`; mixed margins between the status and voice cards read as sloppy.

Measure before quoting any number to the user — render scale is not 1:1 with canvas units, and a vision model will mis-locate cards and mis-read crops. Use vision on a zoomed crop to confirm glyph clipping and to judge whether the palette and density look right.

## Circular minimap checklist

- Custom `MaskableGraphic` drawing a 56-segment triangle fan; `Mask` with `showMaskGraphic = true` on the same object. `RectMask2D` clips rectangles only.
- Shorten the copy to fit the stencil (`LOCAL MAP · ±10 m`, `CONTACTS n`) and shrink the type before insetting; the `F ↑` suffix is gone now that the compass carries real cardinals.
- Grid and marker radius recentred on the new circle; markers scale by radius (about 0.6 × diameter) to keep contacts off the rim.
- No copper top hairline on a round card; stroke the rim inside the circle mesh, never with `Outline`.
- Translucency is a per-card fill alpha, not a separate overlay, and it only survives when nothing opaque sits underneath: `Outline`/`Shadow` on the card emits four near-opaque copies behind the fill and silently cancels it.
- The user removed the minimap grid outright because it will collide with future map content. Emit any repeated hairlines you do need — compass ticks, a future grid — from one `MaskableGraphic` at equal thickness; separate 1-unit `Image` lines rasterize on different pixel phases at HUD scale and read as uneven.
- Glyphs carry their own `Shadow` (black, about 0.7 alpha, offset (1,-1)) once fill alpha drops to roughly 0.25.

## Verifying transparency

Linear colour space compresses the gamma-visible delta, so a 0.25 fill alpha over a 199-grey background lands near 175, not 153. Never read the raw pixel drop as the alpha value. Render the same scene twice (`ARESCOPE_PREVIEW_BG=light` and the dark default), sample a panel interior in both, and treat a card that returns the same value on both backgrounds as opaque no matter what its colour alpha claims.

## Verifying a ruler or any repeated hairline

Profile the strip instead of eyeballing it: crop a band that contains only the ticks (no letters, no markers), average brightness per column, and print the local maxima.

```python
band = gray[row_lo:row_hi, col_lo:col_hi]
col = band.mean(axis=0)
peaks = [i for i in range(1, len(col) - 1) if col[i] > col[i - 1] and col[i] >= col[i + 1] and col[i] > band.mean() + 2]
print(peaks, np.diff(peaks))
```

- Constant diffs mean the spacing matches the bearing mapping; varying diffs plus 1 px/2 px width changes mean subpixel phase drift, so the lines are separate `Image` objects and belong in one mesh.
- Text and marker pixels inside the band register as false peaks, which is why the band has to be chosen empty of them; otherwise "uneven grid" conclusions are noise.

## Telling a clipped label from a missing sprite

When icon rows render but their text does not, suspect the row rect before the loader: a null sprite leaves the label drawn with a smaller left inset, while a row rect shorter than the font's line height removes the glyphs entirely (`VerticalWrapMode.Truncate`). Set the generated row labels to `Overflow` and re-render; only if the text returns and the icon is still absent is the `Resources` path or `Sprite.Create` at fault.

