# 23 · Спецификация TSDF-объёма и Surface Nets

## TSDF volume defaults

- Voxel grid: `256 × 256 × 256 = 16,777,216` voxels. [ПРОВЕРЕНО: pinned `VolumeIntegrator` default]
- Voxel edge: `0.05 m`; nominal cube span `12.8 m` each dimension if no scene override. [ПРОВЕРЕНО: source; physical bounds placement should be verified]
- Truncation distance `voxelDistance=0.15 m`; lower/initial distance parameter `voxelMin=0.1`. [ПРОВЕРЕНО: source defaults; exact semantic units/usage partly depend compute shader]
- TSDF RenderTexture format comment: `R8G8_SNorm`, 2 bytes/voxel. [ПРОВЕРЕНО: VolumeIntegrator source]
- Color volume format comment: `RGBA8_UNorm`, 4 bytes/voxel. [ПРОВЕРЕНО]
- These two textures together are `16,777,216 × 6 = 100,663,296 bytes = 96 MiB`. [ПРОВЕРЕНО: arithmetic from source formats]

## Integration parameter defaults

| Parameter | Default | Meaning from source | Status |
|---|---:|---|---|
| `depthDisparityThreshold` | 0.5 | threshold for depth disparity/consistency | [ПРОВЕРЕНО: field/default; exact shader units require follow-through]
| `maxUpdateDist` | 5.0 m | maximum observation update distance | [ПРОВЕРЕНО: source default]
| `minUpdateDist` | 0.5 m | minimum observation update distance | [ПРОВЕРЕНО: source default]
| `maxFrustumPositions` | 1,000,000 | maximum allocated/generated frustum positions | [ПРОВЕРЕНО: source default]
| `blendRate` | 0.8 | blend/convergence strength | [ПРОВЕРЕНО: source default]
| `stability` | 2.5 | resistance to blending | [ПРОВЕРЕНО: source default]
| `weightGrowth` | 0.025/frame | voxel confidence growth | [ПРОВЕРЕНО: source default]
| `maxWeight` | 0.5 | maximum per-voxel confidence | [ПРОВЕРЕНО: source default]
| `minMeshWeight` | 0.08 | minimum confidence for Surface Nets meshing | [ПРОВЕРЕНО: source default]
| `cameraExposure` | 3.0 | exposure boost for camera colour input | [ПРОВЕРЕНО: source default]

Effective values after scene serialization overrides: данных нет. [ТРЕБУЕТ ПРОВЕРКИ]

## Integration model

```text
for each accepted depth observation:
  map voxel center into camera coordinates
  project into depth observation
  reject outside range/frustum/exclusion zones
  derive signed distance to observed surface
  truncate to configured distance band
  update TSDF and confidence weight using blend/convergence parameters
  if valid camera colour exists:
    sample colour and update RGBA colour volume
```

- The SDK source confirms GPU TSDF + colour volume integration, exclusion zones, convergence and freeze/unfreeze passes. [ПРОВЕРЕНО: source class/module descriptions]
- The formula for each exact update and projection convention must be taken from pinned SDK compute shaders, not inferred from this pseudocode. [ТРЕБУЕТ ПРОВЕРКИ: implementation source not embedded in archive]

## Surface Nets extraction sequence

The pinned shader orchestrator sequence is:

```text
1 ClearCounters
2 ClassifyAndEmit (3D dispatch over volume)
3 BuildVertexDispatchArgs
4 Optional: InitSmooth → N × SmoothVertices → ApplySmooth
5 Optional: TemporalBlend
6 GenerateIndices (indirect 1D dispatch over vertices)
7 BuildIndirectArgs
```

[ПРОВЕРЕНО: `SurfaceNetsExtract.compute` comments + `GPUSurfaceNets.Extract`]

- Counter slot 0 stores vertex count; slot 1 stores index count; slots 2..3 reserved. [ПРОВЕРЕНО: pinned shader]
- `CountersBuffer` has four 32-bit elements. [ПРОВЕРЕНО]
- Mesh extractor smoothing defaults: iterations 1; lambda 0.33; beta 0.5. [ПРОВЕРЕНО: `MeshExtractor.cs`]
- Temporal defaults: alpha max 0.85, min 0.1, decay 0.15, convergence threshold 0.005 m, deadzone 0.001 m. [ПРОВЕРЕНО]
- GPU vertex budget serialized default 0.08; `EnsureBuffers` parameter fallback default 0.05; `MeshExtractor.Init` passes its serialized value explicitly and inspected release scene serializes 0.08. [ПРОВЕРЕНО: source + scene]

## Memory estimate

At `256³`, source `GPUSurfaceNets` estimate includes coordinate map, vertex/index buffers, counters/indirect args, two smoothing float3 arrays and 16-byte temporal state per voxel. [ПРОВЕРЕНО: `totalBytes` source formula]

| Vertex budget | Max vertices | Max indices | Surface Nets estimate | + TSDF/color volumes | Combined approximate minimum |
|---:|---:|---:|---:|---:|---:|
| 0.05 | 838,860 | 15,099,480 | 456,340,208 B = 435.2 MiB | 96 MiB | 531.2 MiB |
| 0.08 | 1,342,177 | 24,159,186 | 528,817,856 B = 504.32 MiB | 96 MiB | 600.32 MiB |

[ПРОВЕРЕНО: source formulas + arithmetic; actual GPU/driver allocation overhead and scene value remain unknown]

- Texture refinement, passthrough camera, depth maps, MSAA, URP targets, Unity heap and XR runtime allocations are excluded from the table. [ПРОВЕРЕНО: estimate scope]
- No actual Quest 3S memory peak or thermal result is present. [ТРЕБУЕТ ПРОВЕРКИ]

## Consequences for performance investigation

- A 0.2 s request cadence with up to 12 MiB readback entails a theoretical cap of 60 MiB/s payload transfer before stalls/copies; this is not the same as 60 MiB/s of useful unique point data. [ПРОВЕРЕНО: arithmetic and source]; actual cadence/read bytes need profiler capture.
- The sampling code reads a contiguous prefix beginning at byte offset 0, then decimates within that prefix; it does not uniformly sample full active buffer if active bytes exceed 12 MiB. [ПРОВЕРЕНО: source]
- Proposed mitigation for a recreated client: GPU-side deterministic stratified sampling or compute shader into a small staging buffer, with counters/histogram measured on-device; this is a design proposal, not part of the current confirmed implementation. [ПРЕДПОЛОЖЕНИЕ]
