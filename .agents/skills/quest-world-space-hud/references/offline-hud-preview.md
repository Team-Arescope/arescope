# Offline preview render for a world-space HUD

Purpose: judge distance, insets and legibility without putting on the headset.

## Recipe

1. Open the scene that holds the real background (terrain, room, whatever the HUD will overlay).
2. Find the camera the HUD follows and place it at the target viewpoint; set `farClipPlane` to cover the scene.
3. In **edit mode** the HUD's `Awake` does not run. Invoke it explicitly before driving the HUD:

   ```csharp
   var awake = typeof(HudController).GetMethod("Awake",
       BindingFlags.Instance | BindingFlags.NonPublic);
   awake?.Invoke(hud, null);
   ```

   Without this the canvas field is unassigned and the render throws `UnassignedReferenceException`.
4. Drive the HUD into the state you want to judge (statuses, assistant text, voice level, map points), then call its `LateUpdate` the same way so the canvas is positioned for the new camera pose.
5. Set the aspect **before** rendering, or the canvas is projected squeezed:

   ```csharp
   cam.aspect = 1600f / 900f;
   cam.ResetProjectionMatrix();
   cam.projectionMatrix = Matrix4x4.Perspective(cam.fieldOfView, cam.aspect, cam.nearClipPlane, cam.farClipPlane);
   ```
6. `Canvas.ForceUpdateCanvases()`, then render into a `RenderTexture`, `ReadPixels` into a `Texture2D`, and `EncodeToPNG`.
7. Destroy any temporary lights/materials created for the shot (restore the original material first) so the scene stays unchanged.

## Making the background readable

- To show terrain albedo reliably even when the sun is behind a ridge, temporarily swap the terrain material for an unlit material with the same base map; restore it afterwards and state in the report that it was a composition render, not a lighting study.
- Sampling terrain height at the nearest vertex can put the camera inside a coarse mesh. Interpolate bilinearly over the grid before adding eye height.
- Disable hard cast shadows for UI-composition shots; a shadowed slope reads as a black wedge and hides the panel you are judging.
- Give a directional light an explicit direction instead of toggling features blindly: when a scene keeps rendering black, verify the light actually faces the surfaces in view before touching materials.
