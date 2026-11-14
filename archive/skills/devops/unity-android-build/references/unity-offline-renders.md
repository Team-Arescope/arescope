# Offline Unity renders for review

Use when a Unity scene must produce a PNG for design review (HUD on a background, terrain shots, before/after comparisons) without a headset or a play-mode session.

## Render the right thing

- **Set the camera aspect before rendering to a RenderTexture.** `camera.aspect` is stale when you render into an RT of a different size, and a world-space Canvas laid out for 16:9 is then squeezed: text lines collide, icon gaps collapse, panels overlap. Preview scripts that assign `aspect` explicitly look correct; ad-hoc `camera.Render()` methods do not. Fix in both places:

```csharp
cam.aspect = width / (float)height;
cam.projectionMatrix = Matrix4x4.Perspective(cam.fieldOfView, cam.aspect, cam.nearClipPlane, cam.farClipPlane);
cam.targetTexture = rt;
cam.Render();
```

Symptom that identifies this bug: the same HUD looks correct in a dedicated preview render and "compressed" in a scene render. Compare a crop of the panel row from both images before concluding the layout is wrong — a real layout bug and a projection bug look identical to the eye.

- **In edit mode, `Awake`/`Start` do not run.** A component that builds its own canvas or caches references is inert when the scene is only opened, not played. Invoke the lifecycle method explicitly before driving it:

```csharp
var awake = typeof(MyController).GetMethod("Awake",
    System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
awake?.Invoke(component, null);
```

Then call `Canvas.ForceUpdateCanvases()` before `Render`, or a world-space canvas positions itself a frame late.

## Lighting: pick the deliverable first

- **A design-review shot needs readable surfaces, not a lighting study.** When the terrain or geometry is backlit, the frame turns into a black silhouette and the reviewer cannot judge anything. Two honest options: move the sun so it lights what the camera looks at (compute the light rotation from the camera forward vector), or swap the terrain material for `Universal Render Pipeline/Unlit` with the same `_BaseMap` for the shot and restore the original afterwards. Say which one you did — an unlit albedo pass has no cast shadows and must not be presented as a realistic render.
- **Hard shadows on height-map terrain read as black wedges.** For previews set the directional light to `LightShadows.None` instead of raising ambient until the shading is flat and fake.
- **Choose vantage points from the data, not by guessing coordinates.** Sample the height grid for slope, rise ahead, and drop ahead, then place the eye a realistic height above the interpolated surface. Bilinear interpolation matters: the nearest-vertex height can sit below the surface and put the camera inside the mesh, which renders as an unexplained black mass.

## Verify before delivering

- Render at the same size as the reference image, crop the identical region from both, stack them into one image, and look at the pair. Judging a single frame in isolation is how a squeezed UI passes review.
- Where the claim is geometric ("panels overlap", "the grid is missing"), measure it: element rects and `scrollWidth - clientWidth` for DOM, or pixel-column histograms for images. A camera with a zero-height grid layer looks exactly like a missing grid.
- Send the image to the user as a document and state plainly what is a composition render and what is an in-device screenshot. They are not interchangeable evidence.
