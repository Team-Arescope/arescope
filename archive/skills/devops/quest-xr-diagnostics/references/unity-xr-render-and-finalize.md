# Unity XR: live scan presentation, mesh readback, finalize

Patterns for apps built on the QuestRoomScan-style SDK (GPU TSDF + Surface Nets) that fetch their
mesh over HTTP. Each item was learned by shipping a build and reading the device log.

## Live scan looks like a coloured blob

The SDK renders the growing mesh in `ScanRenderMode.Vertex` by default. To present your own look:

```csharp
roomScanner.SetRenderMode(ScanRenderMode.None);   // hides SDK mesh, scan keeps integrating
```

Keep the scan running and draw your own geometry (points are cheap; rebuilding an edge mesh every
second on XR2 is not). Log the switch (`SDK live mesh hidden`) so the next log proves it happened.

## GPU mesh readback returns empty

`AsyncGPUReadback` on the Surface Nets buffers returns nothing if you stop the scanner first —
`StopScanning()` releases the volumes. Correct order:

1. call `MeshExtractor.Instance.ExtractForAuthoring()` so the buffers are current,
2. read counters, vertex buffer and index buffer,
3. only then stop the scanner.

If the readback is still empty, do not keep retrying: read the SDK's own `MeshFilter.sharedMesh`
instead — it is already populated and costs no GPU round-trip.

## Finalize can take minutes (and is avoidable)

`RoomScanSession.FinalizeScanAsync()` **requires** the `TextureRefinement` module and waits for the
atlas bake with a timeout measured in minutes. When the app does not show textures, skip finalize:
stop the scanner yourself, read the mesh (above) and build your own visualisation. Finalize drops
from minutes to about a second. Validate before blaming the device — the delay is in the bake, not
the scan.

## HUD that cannot be covered by geometry

A world-space canvas sits in the same depth buffer as the scan and disappears behind it. Put the
HUD on its own layer and render it with a URP overlay camera:

- move the canvas hierarchy to the UI layer,
- remove that layer from the main camera's `cullingMask`,
- add a child camera: `clearFlags = Depth`, `cullingMask = 1 << uiLayer`,
  `stereoTargetEye = Both`, `GetUniversalAdditionalCameraData().renderType = Overlay`,
- push it into `mainCamera.GetUniversalAdditionalCameraData().cameraStack`.

Log `stack=<count>` after adding — a stack of 1 means only the base camera is present and the
overlay silently does nothing.

## Per-panel HUD contrast on passthrough

To darken only the panels standing on a bright surface: blit the passthrough frame to a 32×32 RT,
read it back once per second, project each panel's world corners to viewport coordinates, compute
the bright fraction inside that rectangle, and raise that panel's backdrop alpha only when the
fraction exceeds the threshold (~70%). One global flag darkens the whole HUD and reads as a bug
when a single corner is bright.

## Device logs without adb

Shipping the log from inside the app removes the USB/logcat loop: write lines to a file (flush per
line so a native crash cannot lose them), POST the tail on app pause, on a held button combo, and on
the next launch when a `*.running` marker file proves the previous run died; delete the marker after
a successful upload. Serve a producer-authenticated upload endpoint and a viewer-authenticated list
so the same panel can show the file.
