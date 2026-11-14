# Live scan feed into the Arescope HUD minimap

How the Quest app turns the in-progress room scan into minimap points, and the traps
that make an apparently-correct implementation silently do nothing.

## Why the bridge must live inside the package

`GPUSurfaceNets` and `PointCloudExporter` are `internal` to the `Genesis.RoomScan`
assembly, and `MeshExtractor.GpuSurfaceNets` is an `internal` property. Nothing in
`Assembly-CSharp` can reach the vertex buffer. The working shape is a public static
class compiled *inside* the package:

- repo copy: `PackagePatches/ArescopeLiveCloud.cs` (+ `.cs.meta`)
- installed at: `Library/PackageCache/com.genesis.roomscan@<hash>/Runtime/Utils/ArescopeLiveCloud.cs`
- installed by `patch_roomscan_editor.py`, which takes the package root as its first
  argument, so the `@<hash>` suffix never has to be hardcoded in a build step.

`Runtime/InternalsVisibleTo.cs` grants access only to the package's own Editor, GSplat
and AIDetection assemblies. Do not add `Assembly-CSharp` there; it is vendor code and
will be lost on re-resolve.

## Readback shape

```csharp
public static bool Ready => MeshExtractor.Instance?.GpuSurfaceNets?.VertexBuffer != null;

public static async Task<int> SampleAsync(Vector3[] destination, int maxPoints)
{
    // 1. counters buffer -> active vertex count (int at index 0)
    // 2. AsyncGPUReadback.RequestAsync(surface.VertexBuffer)
    // 3. count = active > 0 && active <= capacity ? active : capacity
    // 4. step = max(1, count / wanted); walk i += step, no copy of the whole buffer
    // 5. unsafe: float* p = (float*)(start + i * 48); position = p[0..2]
}
```

- Stride is 48 bytes, position at offset 0, normal at 16, packed colour at 32.
- Guard with a `_busy` flag: a second readback while one is in flight wastes frames.
- Read floats through an unsafe pointer; `NativeArray<byte>` plus `BitConverter`
  needs a full copy and allocates every sample.
- Positions are scan-space metres at world origin, which is what the head-relative
  projection wants. Re-check this after relocalisation.

## Consumer component

`Assets/Arescope/LiveScanMinimap.cs`:

- throttled (~1.5 s) rather than per frame; the map is a status instrument, not a view
- height band ±1.4 m around the head removes floor and ceiling. Furniture in the band
  still shows, so never call the band "wall detection"
- radius cull in metres, not a clamp to the map edge
- project with `right = Vector3.Cross(Vector3.up, forward)` and
  `flat = (Dot(delta, right), Dot(delta, forward))`, so the chevron stays up and the
  map stays head-relative
- call `hud.SetMapPoints(points, rangeMeters, scanCloud: true)`

## HUD side

Contacts and a scan cloud are not the same visual object: contacts are few, discrete
markers; a cloud is many small ones.

- marker size 3.2 units for a cloud, 9 for contacts. At HUD scale the 9-unit squares
  overlap at ~0.5 m point spacing and render as a solid wall bar
- cap 192 markers for a cloud, 64 for contacts
- label `POINTS n` for a cloud and `CONTACTS n` for contacts; a cloud labelled
  `CONTACTS 70` reads as 70 detected objects
- keep the duplicates filter in `SetMapPoints`; dense vertex output otherwise spends
  the whole budget on near-identical positions

## Verifying without a headset

The editor has no live scan, so a render only proves layout. Two honest checks:

1. `WireArescopeScene.Run` in batchmode — proves the bridge compiles inside the
   package assembly and the scene saved with the component (grep the scene for the
   component GUID, expect `refs=1`).
2. `ARESCOPE_PREVIEW_MAP=walls` — a synthetic room outline at ~0.55 m spacing that
   shows how a cloud reads. Label it as a fixture in the reply.

Still unverified until a device run: readback cost against the scan loop, the actual
frame rate, coordinate behaviour after relocalisation, and whether the surface-nets
buffer is populated at all on Quest 3S during capture.
