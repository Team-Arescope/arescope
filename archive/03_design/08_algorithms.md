# 08 · Алгоритмы и проектные решения

## 8.1 Старт и остановка сканирования

**Входы:** левый контроллер `primaryButton` (X), `secondaryButton` (Y), `RoomScanSession.Instance`, `RoomScanner`, GPU Surface Nets. [ПРОВЕРЕНО: `ScanModeBridge.cs`]

```text
on X rising edge:
  if busy: ignore
  if not scanning:
    capture spatial frame
    await StartScanAsync
    if scanner.IsScanning:
      set SDK render mode None
      hide old wireframe
      enable live points; select live minimap source
  else:
    disable live points
    attempt mesh export while scanner still alive
    choose SDK refined mesh fallback if available
    StopScanning
    if valid mesh:
      build mesh; show wireframe; switch minimap to final mesh
    else:
      show error with export reason
```

- `resetHoldSeconds=1.2`. [ПРОВЕРЕНО]
- Scanner stop releases GPU volumes, therefore readback must occur before stop. [ПРОВЕРЕНО: client code comments/SDK behavior]
- `StartScanAsync`/`StopScanning` interaction and callback ordering on Quest 3S remains to verify. [ТРЕБУЕТ ПРОВЕРКИ]

## 8.2 GPU vertex readback

- Vertex stride 48 bytes; position float3 at byte offset 0; packed color u32 at byte offset 36. [ПРОВЕРЕНО: pinned SDK]
- Read counters; clamp counts to actual buffer capacity; request only used byte range; attempt async GPU readback then synchronous `GraphicsBuffer.GetData` fallback. [ПРОВЕРЕНО: `ArescopeMeshExport.cs`]
- Vertex limit 200,000; index limit 600,000 in caller `ScanModeBridge`; separate MeshUploader max vertices defaults 400,000. [ПРОВЕРЕНО: code defaults]
- Live cloud read is capped at 12 MiB and runs nominally each 0.2 s with sampling array size 6000 in current LiveScanPoints. [ПРОВЕРЕНО: code defaults]

## 8.3 Triangle filtering

Input: arrays of positions and `uint32` indices; max index range clipped by count/capacity. Output: valid triangle index list plus counters for rejected categories. [ПРОВЕРЕНО]

```text
sample at most 20,000 triangles (edgeSample cap 60,000 lengths)
keep only in-range triangles for edge sample
medianEdge = sorted edge lengths[mid]
limit = clamp(medianEdge * 4, 0.06 m, 0.30 m)
for each triangle:
  reject out-of-range indices
  reject repeated indices
  reject NaN x coordinate
  reject if any edge length > limit
  otherwise keep triangle
log raw, kept, median, limit, degenerate, stretched, outOfRange
```

- Exact code sample condition: `edgeSample.Count < 60000`; factor 4; clamp min 0.06 m/max 0.30 m. [ПРОВЕРЕНО]
- `ReadAsync` signature accepts a `maxEdge` parameter defaulting to `0.5 m`, but current filter computes `limit` from median and does not use the `maxEdge` argument. [ПРОВЕРЕНО: source inspection; API parameter is currently ineffective]
- Filter only tests `NaN` on X component; it does not explicitly test Infinity, NaN in Y/Z, zero-area triangles with distinct indices, triangle normals, or connected-component consistency. [ПРОВЕРЕНО: source inspection]
- Median can be biased by invalid triangles included in edge sample; thresholds can erase valid large triangles or retain semantically wrong medium-distance bridges. [ПРЕДПОЛОЖЕНИЕ: algorithmic risk]

## 8.4 Wireframe construction and decimation

- Current `maxTriangles=200000`; `Compact` chooses `stride=ceil(triangleCount/triBudget)`, selects each stride-th triangle, remaps referenced vertices. [ПРОВЕРЕНО]
- Since current budget equals or exceeds caller mesh limit 200,000, this usually does not decimate caller output. [ПРОВЕРЕНО: formulas and callers]
- `BuildLines` deduplicates undirected edges using `HashSet<long>` keyed by sorted pair of vertex indices; each surviving triangle contributes 3 candidate edges. [ПРОВЕРЕНО]
- `BuildPoints` emits up to 12,000 billboard quads; point diameter parameter 0.006 m in wireframe; line color alpha 0.25, point alpha 0.55. [ПРОВЕРЕНО: serialized defaults]
- Large CPU allocation/time from `Mesh.vertices`, `Mesh.triangles`, `HashSet`, and remap dictionary is not profiled on Quest. [ТРЕБУЕТ ПРОВЕРКИ]

## 8.5 Live point cloud and frustum culling

- Sample count request = 6000 per cycle, nominal period 0.2 s; cache capacity 60,000, quantization voxel size 0.035 m. [ПРОВЕРЕНО: fields]
- Key = floor(position/voxelSize) in each axis, packed as 21 bits each; point is added only if key is not already in dictionary. [ПРОВЕРЕНО]
- Render capacity 16,000; point size 0.0045 m; max distance 9 m; cull by 6 camera frustum planes when camera exists. [ПРОВЕРЕНО]
- Culling occurs after CPU GPU-readback/sample and before publishing/render mesh; it does not prevent GPU extraction or readback of source vertices. [ПРОВЕРЕНО: call order]
- `Add(count)` updates voxel dictionary/cache before `Publish()` evaluates frustum/distance. Therefore off-screen points are still CPU-processed and accumulated; current culling saves render geometry, not readback, extraction, or cache work. [ПРОВЕРЕНО: `LiveScanPoints` call order]
- A true off-screen compute culler would need camera view/projection passed to a GPU compute stage and would alter which points survive sampling; this is not part of the current implementation. [ПРЕДПОЛОЖЕНИЕ: proposed design]
- Cache does not evict or refresh voxel color/position once at capacity; scan coverage can saturate or preserve early values. [ПРОВЕРЕНО: source]; desired lifecycle requires test.
- Sample uses prefix/stride sampling in SDK buffer; spatial coverage can be uneven if buffer ordering clusters by voxel/cell. [ПРЕДПОЛОЖЕНИЕ]

## 8.6 Live minimap and final-mesh source

- Coordinate frame uses headset current world position, horizontal projection of `headset.forward`, `right=cross(up,forward)`, map range 10 m. [ПРОВЕРЕНО]
- Vertical acceptance: `abs(point.y-headset.y) <= 0.03 m`, i.e. 0.06 m total band. [ПРОВЕРЕНО]
- Live sampling buffer budget 768 points per update; max rendered map points 96; nominal interval 1.5 s. [ПРОВЕРЕНО]
- After finalization, minimap stores a `Mesh` reference and samples up to 20,000 vertices with stride to produce at most 96 map points. [ПРОВЕРЕНО]
- For final mesh, the current code applies `ArescopeFrame.Relocation()` to mesh vertex coordinates, then compares with headset world position. [ПРОВЕРЕНО: source]; correctness depends on mesh coordinates and anchor matrix sharing the assumed capture frame. [ТРЕБУЕТ ПРОВЕРКИ]
- The minimap uses height band, not gaze pitch; looking down does not rotate the band toward the floor. [ПРОВЕРЕНО: code geometry]

## 8.7 Adaptive HUD backdrop

- `HudContrast` samples passthrough using downsampled 32×32 data, updates nominally every 1 s, computes per-panel brightness and applies alpha 0.25/0.48 according to threshold logic. [ПРОВЕРЕНО: code state from project history; re-check exact current source before reimplementation]
- Panel-specific bright fraction threshold 0.7 and luminance threshold 0.62 are historical implementation values. [ПРОВЕРЕНО: prior code summary; [ТРЕБУЕТ ПРОВЕРКИ] current exact serialization/implementation]
- If passthrough texture read is unavailable, panel contrast behaviour needs a fallback and device test. [ТРЕБУЕТ ПРОВЕРКИ]

## 8.8 Spatial anchor relocation

- On scan start, `ArescopeFrame.Capture()` stores `RoomAnchorManager.SpatialAnchorMatrix`; on changes, relocation is `A_now * inverse(A_capture)`. [ПРОВЕРЕНО: current source]
- Matrix change threshold: any of 16 elements changes by >0.0005; current frame-to-frame matrix comparison. [ПРОВЕРЕНО: source]
- Visual root application converts relocation matrix translation and rotation to root transform, scale forced to 1. [ПРОВЕРЕНО]
- It is unverified that capture matrix is non-identity, persisted across sleep, and compatible with the local coordinate space used in exported mesh positions. [ТРЕБУЕТ ПРОВЕРКИ]
- If no active anchor manager is available, current code returns identity; therefore no cross-origin correction is applied. [ПРОВЕРЕНО: source]

## 8.9 Known algorithm failure modes

- Corrupt/high-volume index count → range clamp/readback failure. [ПРОВЕРЕНО: guard code; failure branch needs tests]
- Median contaminated by garbage edges → threshold too permissive. [ПРЕДПОЛОЖЕНИЕ]
- Strict median threshold → valid long triangles dropped. [ПРЕДПОЛОЖЕНИЕ]
- Relocation frame mismatch → rotated/translated cloud/mesh. [ТРЕБУЕТ ПРОВЕРКИ]
- Voxel cache saturation (60,000) → later observed space not added. [ПРОВЕРЕНО: capacity guard]
- Camera reference missing → frustum test skipped, only distance culling remains. [ПРОВЕРЕНО: source]
