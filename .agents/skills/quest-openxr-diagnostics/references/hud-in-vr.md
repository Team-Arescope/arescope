# HUD legibility in VR

## A world-space HUD gets occluded by scene geometry

A world-space canvas sits in the depth buffer like any other object, so a scan mesh or a wall closer than the canvas hides the panels. `sortingOrder` does not help.

Fix — render the canvas from a dedicated URP overlay camera:

1. Move the whole canvas hierarchy to a dedicated layer (`UI`, index 5).
2. Remove that layer from the head camera's `cullingMask`.
3. Create a child camera under the head camera: `clearFlags = Depth`, `cullingMask = 1 << layer`, `depth = head.depth + 1`, `stereoTargetEye = Both`.
4. Set its `UniversalAdditionalCameraData.renderType = Overlay` and add it to the head camera's `cameraStack`.

A base camera with one overlay reports `cameraStack.Count == 1` — that is success, not failure. If panels vanish entirely the overlay was not accepted: fall back to a UI material compiled with `ZTest Always`.

## Preview renders squeeze the HUD

Rendering to a `RenderTexture` while the camera keeps a stale `aspect` compresses the canvas vertically and makes panels overlap. Set `camera.aspect = width / height` and rebuild the projection matrix **before** `camera.Render()`, and again when the target texture is assigned.

## Adaptive contrast per panel

Sampling the whole frame and darkening every panel at once reads as a global flicker. Sample per panel instead: project each panel's world corners to viewport coordinates with the head camera, read the matching sub-rectangle of a downsampled passthrough frame (32×32 is enough), and darken only panels whose own area is mostly bright (≈70% of pixels above the luminance threshold). Log the decision per panel — `[TAG] hud | <panel>: backdrop=0.48 bright=82%` — so a wrong mapping is visible in the log rather than only on the headset.

## Sizing and comfort

Side panels pulled toward the centre and a canvas at arm's length read comfortably; edge-of-FOV panels are blurred by the optics. When the user asks for "closer" after a change, move the follow distance and the side insets together, and re-render before reporting.

## Presentation style for scanned geometry

Baked textures from passthrough cameras look poor at close range and cost minutes of bake time. A translucent polygon wireframe with soft vertices reads better and finalises in seconds: 75%-transparent lines, slightly denser points, copper/warm-white palette. Build it from the live GPU mesh before stopping the scan; skip the texture-refinement stage entirely when it is not displayed.
