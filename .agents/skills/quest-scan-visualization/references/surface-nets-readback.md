# Reading and drawing Surface Nets geometry on Quest

Buffer layout used by the RoomScan-style Surface Nets pipeline (`GPUSurfaceNets`):

| Buffer | Stride | Meaning |
|---|---|---|
| `CountersBuffer` | 4 × uint | `[0]` vertex count, `[1]` index count, `[2..3]` reserved |
| `VertexBuffer` | 48 B | position at 0, normal at 12, packed colour at 36 (`0xAABBGGRR`) |
| `IndexBuffer` | 4 B | triangle list, 3 uint per triangle |
| `DrawIndirectArgs` | 5 × uint | `[0]` index count, `[1]` instance count |

## Bounded readback recipe

```csharp
int vertexCount = 0, indexCount = 0;
var counters = new int[4];
surface.CountersBuffer.GetData(counters);      // 16 bytes, synchronous is fine
vertexCount = counters[0]; indexCount = counters[1];

int verts = Mathf.Min(vertexCount, maxVertices);
var vertexReq = await AsyncGPUReadback.RequestAsync(surface.VertexBuffer, verts * 48, 0);
if (vertexReq.hasError) { /* log and fall back */ }

int indices = Mathf.Min(indexCount, maxIndices) / 3 * 3;
var indexReq = await AsyncGPUReadback.RequestAsync(surface.IndexBuffer, indices * 4, 0);
```

`GetData<byte>()` works on a 48-byte-stride structured buffer; copy out of the `NativeArray` immediately because it is only valid for the current frame. Keep a synchronous `GraphicsBuffer.GetData` call as the last resort, and treat a shorter-than-requested array as a failure — the remaining bytes are zeros.

## Symptom table

| On the headset | In the log | Cause |
|---|---|---|
| Nothing appears | `mesh readback empty` with no reason | Whole-buffer readback rejected; add bounded reads and per-branch reasons |
| Tangle of lines through the room | many tris, few unique edges (ratio ~0.5) | Zero-filled index tail; filter degenerate and over-long triangles |
| Room visible but in the wrong place after walking out and back | anchor pose changes, mesh does not | Visual parented to its own object, not the SDK's render mesh transform |
| Frame rate collapses after finalise | hundreds of thousands of tris | No decimation before building edges and billboards |
| Grey sparse dots during scan | flat `_Color`, low `maxPoints` | Not reading packed vertex colour; sample budget too small |

## Billboard points in URP

Points are quads with `uv` holding the corner offset; the vertex shader billboards them in view space, which keeps a constant screen size:

```hlsl
float depth = max(0.05, -viewPos.z);
viewPos.xy += v.uv * _PointSize * depth;
```

then tint in the fragment shader with `lerp(1, vertexColor, _UseVertexColor)` so line meshes without colours stay flat.

## Order of operations on finalise

1. Stop presenting the live cloud, keep the scanner running.
2. Extract once more (`ExtractForAuthoring`) so the GPU buffers match the final volume.
3. Read counters, then the bounded vertex and index ranges.
4. Sanitise triangles; log raw/kept/degenerate/stretched.
5. Optionally fall back to the SDK's own CPU mesh if it already exists.
6. Stop the scanner only after the read returns — stopping releases the GPU volumes.
7. Build the presentation mesh under the SDK's render transform.
