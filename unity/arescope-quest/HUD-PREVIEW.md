# Arescope World-Space HUD Offline Preview

Offline batchmode rendering renders the real Unity `ArescopeHudController` hierarchy to a 1600 × 900 PNG without modifying `Assets/Scenes/QuestRoomScan-REVIEW-ONLY.unity`. This provides fast layout, clipping, transparency, and typography verification before committing to an Android IL2CPP build.

## Entry Points

1. **Flat-background HUD render** (`Assets/Editor/RenderArescopeHudPreview.cs`):
   - Menu: `Arescope > Render HUD Preview`
   - Batchmode:
     ```bash
     DISPLAY=:1 ARESCOPE_HUD_PREVIEW_PATH=Build/hud-preview.png \
       /data/home/Unity/Hub/Editor/6000.2.9f1/Editor/Unity \
       -batchmode -quit -projectPath /path/to/unity/arescope-quest \
       -executeMethod Arescope.Editor.RenderArescopeHudPreview.Run \
       -logFile Build/hud-preview.log
     ```
2. **Mars terrain composition render** (`Assets/Editor/BuildSimScenes.cs`):
   - Menu: `Arescope > Sim > Render Mars HUD`
   - Batchmode: `-executeMethod Arescope.Editor.BuildSimScenes.RenderMarsHud`
   - Swaps the terrain material temporarily to `Universal Render Pipeline/Unlit` preserving `_BaseMap` and texture tiling so facing slopes remain readable regardless of sun angle. Note that this is an albedo composition check, not a lighting study.

## Environment Variables

| Variable | Values | Effect |
|---|---|---|
| `ARESCOPE_HUD_PREVIEW_PATH` | File path (default `Build/hud-preview.png`) | Output PNG path for `RenderArescopeHudPreview.Run` |
| `ARESCOPE_MARS_HUD_PATH` | File path (default `Build/mars-hud-preview.png`) | Output PNG path for `BuildSimScenes.RenderMarsHud` |
| `ARESCOPE_PREVIEW_MAP` | `walls` (default: contacts) | Seeds synthetic room wall outline points (`scanCloud = true`) into the circular minimap |
| `ARESCOPE_PREVIEW_EMPTY` | `1` | Renders the bare empty HUD state (`—`, `VOICE -`, `No response yet`) instead of the preview fixture |
| `ARESCOPE_PREVIEW_BG` | `light` (default: dark) | Switches preview camera clear color to light grey `(0.78, 0.78, 0.78)` to verify translucency and glyph shadow contrast |

## Edit-Mode Lifecycle Notes

- Edit-mode scripts do not automatically trigger `MonoBehaviour.Awake()` or `LateUpdate()`. Both preview runners invoke `Awake` and `LateUpdate` via reflection so `worldCanvas` is constructed and snapped in front of the camera before rendering.
- `cam.aspect` is explicitly forced to `1600f / 900f` and `cam.projectionMatrix` rebuilt immediately before `cam.Render()`, preventing stale editor aspect ratios from squeezing the world-space canvas.
- Output `RenderTexture` uses `RenderTextureReadWrite.sRGB` so Linear color-space projects export properly gamma-encoded PNGs.

## Numeric Verification Recipe

Measure card bounding boxes, row line counts, and transparency numerically with Python (`PIL` + `numpy`) before reviewing visually:

```python
import numpy as np
from PIL import Image

im = Image.open("Build/hud-preview.png").convert("RGB")
arr = np.asarray(im).astype(int)
bg = arr[5, 5]
mask = np.abs(arr - bg).sum(axis=2) > 12

# Verify translucency by comparing dark vs ARESCOPE_PREVIEW_BG=light interior samples:
# A 0.25 alpha fill in Linear space shifts light grey (~199) toward ~175;
# identical pixel values across dark and light renders indicate an opaque card.
```

## Limitations

A mono 1600 × 900 flat or albedo-terrain render verifies panel alignment, 112-unit side insets, row overflow, and glyph shadow legibility, but cannot substitute for Quest 3S testing of stereo IPD comfort, live passthrough exposure, head-follow motion, or optical lens edge blur.
