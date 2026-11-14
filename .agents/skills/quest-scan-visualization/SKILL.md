---
name: quest-scan-visualization
description: Use when drawing scanned room geometry on Quest XR.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [unity, quest, xr, mesh, roomscan, rendering]
---

# Presenting scanned geometry on Quest

## When to Use

Rendering the mesh or live point cloud of a room-scanning XR app (RoomScan / Surface Nets / TSDF pipelines) on Quest hardware, especially when the result looks wrong on the headset but the code builds fine.

## Rules

1. **Read the counters first, then only the used range.** `AsyncGPUReadback` of a whole structured buffer (tens of MB) comes back with `hasError` on Quest and the caller sees an unexplained empty mesh. Read the counter buffer (16 bytes) to get the vertex and index counts, then request exactly `count * stride` bytes at offset 0. Log the reason for every failure branch — `hasError`, short read, zero counter — or the only symptom you get is "empty".
2. **Sanitise topology before building any render mesh.** Drop indices outside the read range, triangles with a repeated vertex, NaN positions, and any triangle with an edge longer than a room-scale threshold (~0.5 m). A partially filled index buffer is full of zeros and every stray triangle fans to vertex 0, which reads on the headset as a tangle of lines across the whole room.
3. **Check the edge/triangle ratio before blaming the renderer.** A healthy closed room mesh has roughly 1.5 unique edges per triangle; a ratio near 0.5 means most triangles are degenerate. Log `raw`, `kept`, `degenerate`, `stretched` counts on every read so the next headset log answers the question without a rebuild.
4. **Decimate before building presentation meshes.** A 200k-vertex room expands to ~800k vertices and millions of indices once every triangle becomes three line edges and every vertex becomes a four-vertex billboard, which stalls the headset. Budget around 45–60k triangles for the wireframe and ~12k points for the cloud, dedupe edges with a hash set, and remap only the vertices actually used.
5. **Anchor visuals to the transform the SDK renders its own mesh from** (for example `MeshExtractor.Instance.transform`), not to your own component's transform. Scan volumes get re-anchored on relocalisation; a visual parented elsewhere keeps its own pose and the room appears to rearrange itself when the user leaves and re-enters.
6. **Cull before upload, not with renderer settings.** Transform sample points into world space, drop those outside the camera frustum (`GeometryUtility.CalculateFrustumPlanes`) and beyond a distance cap (~9 m), then upload with `SetVertices/SetColors(array, 0, count)` subranges. Culling after upload still pays the upload and draw cost.
7. **Log pose and anchor changes.** Anything above ~1 cm or ~1° per update is a relocalisation event worth a line in the log; without it, coordinate-frame bugs are invisible in device logs.
8. **Take colours from the scanner's packed vertex colour** (stride 48, packed `0xAABBGGRR` at offset 36) instead of a flat tint, and gate it in the shader with a `_UseVertexColor` float so flat-tinted line meshes keep working.

## Reference

`references/surface-nets-readback.md` — concrete readback recipe, buffer layout, symptom table and the shader billboard trick.
