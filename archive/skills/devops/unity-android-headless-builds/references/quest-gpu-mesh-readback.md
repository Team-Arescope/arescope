# Reading an SDK's GPU mesh on Quest

Rules for turning a scanner's GPU buffers (Surface Nets, TSDF, anything built
in compute) into a mesh, a point cloud or a wireframe on device. Applies when
the buffers live inside a package assembly and are exposed only through a small
bridge file compiled into that package.

## Read only what the counters claim

Requesting a whole structured buffer is the usual first bug. A room-sized
vertex buffer reaches 60–100 MB; the Quest driver rejects that readback,
`hasError` comes back, and the caller logs something useless like "readback
empty". Read the counter buffer first, then request exactly `count * stride`
bytes at offset 0.

```csharp
var req = await AsyncGPUReadback.RequestAsync(surface.VertexBuffer, count * stride, 0);
if (req.hasError) { /* report size and step, not just "failed" */ }
```

Cap the window anyway (12 MB is a safe ceiling): rooms differ, and a later
build should not die on a bigger scan.

## Clamp counters by buffer capacity

Counters are GPU-side and survive a reset longer than the buffers do. Always
`Math.Min(counter, buffer.count)` for both vertex and index counts; otherwise
the readback request exceeds the buffer and fails outright, which reads as "no
geometry" rather than "stale counter".

## Sanitize triangles before presenting them

A partially filled or zeroed index buffer produces triangles that reference
index 0, so the view fills with lines fanning out from one point. A naive
"drop indices past the read range" filter does not catch it, because 0 is in
range. Two filters, both needed:

- drop degenerate triangles (repeated vertex) and NaN positions;
- drop triangles whose longest edge exceeds a threshold derived from the mesh
  itself — median edge length over a sample, times ~4, clamped to
  `[0.06 m, 0.30 m]`. A fixed 0.5 m cap lets 20–40 cm bridges through, and those
  are exactly the "lines across the room" the user sees.

Log the split every time: `verts, tris raw, kept, median, limit, degenerate,
stretched, outOfRange`. Without it the next report is guesswork.

## Do not decimate by stride to cut triangle count

Keeping every N-th triangle leaves random holes: neighbouring points lose the
edge between them, so surfaces look torn while stray triangles still connect
distant points. The wireframe line mesh shares the source vertex array, so a
full room (100–200k triangles) is affordable — cap by a high budget, not by
sampling.

## Slice the index buffer to the uploaded vertices

When a dynamic mesh (point billboards, filtered quads) is rebuilt each tick,
`SetVertices` shrinks the vertex count but a full-capacity index buffer stays.
The GPU then reads past the uploaded range and draws garbage. Always set the
slice:

```csharp
mesh.SetIndices(indices, 0, points * 6, MeshTopology.Triangles, 0, false);
```

The overload is `(array, start, length, topology, submesh, calculateBounds)` —
passing `calculateBounds` where `submesh` belongs fails to compile with a
confusing "cannot convert MeshTopology to int".

## Keep the old signature when a package bridge gains parameters

Bridges live in the package cache and are called from `Assets/` scripts.
Adding a parameter to `SampleAsync` breaks every caller at once (minimap,
frame sender, uploader). Add the new overload and keep a thin forwarding
overload with the previous shape, so unrelated features keep compiling.

## Place baked geometry with a relocation matrix

Vertex arrays are baked in the world frame of the capture moment. Parenting
them to a transform is not enough: when the runtime re-centres the tracking
origin (leaving the play area, waking the headset), the mesh appears rotated —
the cupboard that was on the left ends up behind you. If the SDK exposes a
spatial-anchor matrix and a relocation helper, store the anchor at capture and
apply `R = A_now * inverse(A_capture)` to the visual root (position and
rotation, no parent), and re-apply when `A_now` changes.

Avoid calling the SDK's relocation helper every frame: it usually logs. Cache
the last anchor matrix and recompute only when it actually moved.

## Give the readback a reason channel

Expose a `LastReason` string from the bridge and log it once per failure
instead of every tick. "readback empty" without a reason costs a headset round
trip; "vertex readback hasError (bytes=12582912)" answers the question
immediately.
