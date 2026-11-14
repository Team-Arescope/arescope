# HUD layering and texture quality (Unity / Quest)

## Always-on-top HUD

Symptom: HUD panels disappear behind the scan mesh or when the user leans toward a wall. The world-space canvas is depth-tested like any other geometry.

> Code example split: part 1/2 of the archived reference block; concatenate in order if needed.
```csharp
var canvas = GetComponentInChildren<Canvas>(true);
SetLayerRecursively(canvas.transform, hudLayer);          // e.g. 5 = UI
headCamera.cullingMask &= ~(1 << hudLayer);               // main camera stops drawing the HUD

var go = new GameObject("HUD Overlay Camera");
go.transform.SetParent(headCamera.transform, false);
var overlay = go.AddComponent<Camera>();
overlay.clearFlags      = CameraClearFlags.Depth;         // clears depth, keeps colour
overlay.cullingMask     = 1 << hudLayer;
overlay.depth           = headCamera.depth + 1;
overlay.stereoTargetEye = StereoTargetEyeMask.Both;       // stereo must not break
overlay.allowHDR        = false;
overlay.allowMSAA       = false;

var mainData    = headCamera.GetUniversalAdditionalCameraData();
```
> Code example split: part 2/2 of the archived reference block; concatenate in order if needed.
```csharp
var overlayData = overlay.GetUniversalAdditionalCameraData();
overlayData.renderType = CameraRenderType.Overlay;
overlayData.renderPostProcessing = false;
if (!mainData.cameraStack.Contains(overlay)) mainData.cameraStack.Add(overlay);
```

Notes that cost time otherwise:

- `mainData.cameraStack.Count == 1` after adding one overlay is correct; the base camera is not in its own stack.
- An overlay camera that is not added to `cameraStack` renders nothing and logs nothing.
- `stereoTargetEye` must stay `Both`, otherwise the HUD renders in one eye.
- Keep the HUD positioned against the head camera as before; only the depth ordering changes.

## Reading placement preferences

World-space HUD distance and lateral insets are comfort parameters, not aesthetics: users report edge blur at the lens periphery and strain when panels sit far away. Typical acceptable values on a Quest-class headset: follow distance ≈0.6 m, side panels ≈150 canvas units in from the edges on a 1280-wide canvas. Move panels inward before shrinking them — shrinking costs legibility, depth ordering does not.

## Texture refinement: is it the bake or the display?

Triage in this order; each step is one grep, and only the last one justifies changing settings.

| Check | Healthy log | Means |
|---|---|---|
| Module present | `[ARS] tex | refinement module present` | component exists in the scene |
| Atlas produced | `[TextureRefine] GPU compute bake complete: <W>x<H> atlas` | bake ran |
| Mesh carries UVs | `finalized mesh=<n> uv=yes renderer=yes` | the refined mesh is the one displayed |
| Registration health | `Registration: N refined, M rejected` | how many keyframes contributed |

A room scan commonly produces ~2200×2200 px and ~25k triangles. A high rejected count is the texture-quality limiter: the bake is only as good as the views that registered.

Knobs that raise density (change together, one build):

| Field | Default | Raise to | Effect |
|---|---|---|---|
| `simplifyBeforeUnwrap` | true | false | bake the dense mesh — roughly doubles texels per surface |
| `skipDenoise` | true | false | removes bake noise, avoids a speckled atlas |
| `maxViewsPerTexel` | 3 | 4 | better blend at grazing angles |
| `sharpenStrength` | 0.8 | 1.1 | recovers edge detail the low-res source loses |

Costs a few seconds of bake per scan on the headset GPU; it does not need a server round trip.

When the settings are already sane and the result is still soft, the source is the limiting factor (low-resolution camera passthrough), not the bake. Say so rather than promising photoreal output from a camera that cannot deliver it.
