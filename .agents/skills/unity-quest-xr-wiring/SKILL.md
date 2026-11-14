---
name: unity-quest-xr-wiring
description: Use when wiring OpenXR depth for Unity Quest builds.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, windows, macos]
metadata:
  hermes:
    tags: [unity, quest, openxr, arfoundation, depth, build]
---

# Unity + Quest OpenXR wiring

## When to Use

- A Quest app using AR Foundation (`AROcclusionManager`, depth capture, MRUK) builds but the scan/reconstruction never progresses.
- Adding `com.unity.xr.meta-openxr` to an existing Unity 6 project.
- Debugging `DllNotFoundException`, `No active XR loader`, `occlusion=no-subsystem`, or `sub=null` in device logs.

## Four faults, in this order

Each one hides the next; fix them in sequence and re-test on device after each build.

1. **XR must auto-start.** In `Assets/XR/XRGeneralSettingsPerBuildTarget.asset`, the Android block needs `m_AutomaticLoading: 1` and `m_AutomaticRunning: 1`. With either 0 the app runs flat: `[RoomScan] No active XR loader`, `XRSettings.isDeviceActive == false`, and the UI sits in a loading state forever.
2. **Native bridge must reach the APK.** `com.unity.xr.meta-openxr` ships `Runtime/Plugins/android/arm64/libUnityARFoundationMeta.so`, but Unity does not package it from `Library/PackageCache`. Copy the file to `Assets/Plugins/Android/arm64-v8a/` (a minimal `.meta` with a GUID is enough) and verify it is present in the built APK. Without it: `DllNotFoundException: 'libUnityARFoundationMeta'` and the occlusion subsystem never appears.
3. **Lifecycle feature must be enabled.** In `Assets/XR/Settings/OpenXR Package Settings.asset`, enable `MetaOpenXR-OpenXRLifeCycle` together with the AR Foundation Meta features (session, occlusion, plus plane/mesh/anchor if the SDK needs them). Without the lifecycle feature the native func table never gets `instanceProcAddr`, every capability probe fails with `Failed to look up OpenXR function because instanceProcAddr is null`, and `AROcclusionManager` is built with no subsystem.
4. **The capability verdict is cached for the process.** Once the runtime is judged to lack `XR_META_environment_depth`, restarting `ARSession` does not recover it. The features must be correct at build time; runtime retries are a dead end.

Healthy run looks like: `DepthCapture: frames=N, depthAvail=True, sub=MetaOpenXROcclusionSubsystem` with `frames` climbing.

## Presentation and finalize

- **`FinalizeScanAsync` requires the texture-refinement module** and waits up to five minutes for the atlas bake. If the product shows a wireframe rather than textures, skip it: stop the scanner, read the mesh from the GPU buffers, and build line/point meshes directly.
- **Read GPU buffers while the scan is still live.** Stopping the scanner releases the TSDF volumes; a readback issued afterwards returns empty.
- For a HUD that must never be covered by geometry, put the canvas on its own layer and render it with a URP overlay camera that clears depth, added to the main camera's stack.

### Reading the Surface Nets mesh off the GPU

1. `extractor.ExtractForAuthoring()`, `await Task.Yield()`, then read the counters buffer. If the vertex counter is still 0, extract again (up to ~3 attempts): the compute can land a frame late.
2. Request only the used range: `AsyncGPUReadback.RequestAsync(buffer, count * stride, 0)`. Asking for the whole structured buffer (tens of megabytes on a room-scale grid) makes the Quest driver answer `hasError`, and the caller sees only "readback empty" with no reason. Cap every read (~12 MB) and decimate inside the window.
3. Clamp counts to the buffers: `Mathf.Min(vertexCount, surface.VertexBuffer.count)` and the same for the index buffer. After a scan reset the counters can outrun the allocated buffers and the readback fails outright.
4. Sanitize triangles before meshing: drop indices past the vertex count, repeated-vertex triangles, NaN positions, and any edge longer than ~0.5 m. A zero-filled index tail otherwise fans stray vertices to index 0, which renders as a tangle of lines across the whole room. Diagnostic ratio: unique edges / triangles for a closed mesh is ~1.5; around 0.5 means most triangles are degenerate.
5. Keep the index buffer in step with the vertices actually uploaded. Building one index array for the full capacity and then uploading fewer vertices makes the GPU read past the buffer. Use `mesh.SetIndices(indices, 0, points * 6, MeshTopology.Triangles, 0, false)` — (array, start, length, topology, submesh, calculateBounds); the (array, start, length, topology, bool, int) order does not exist.
6. Decimate before drawing: a full-room wireframe turns every triangle into edges and every vertex into a billboarded quad. Cap triangles (~45k) and points (~12k) or the headset stalls.
7. Parent the wireframe and point objects to the transform the SDK renders its own mesh from (`MeshExtractor.Instance.transform`), not an app-local object, and log that transform's pose when it moves by more than ~1 cm or 1°. Otherwise a relocalisation rotates the visuals away from the room and the room looks re-arranged.

### Live point cloud while scanning

- Sample by stride from the used range; do not rebuild the cloud from random indices.
- The packed vertex colour is `0xAABBGGRR` (red in the low byte). Feed it through a shader that multiplies `_Color` by an optional vertex colour (`_UseVertexColor`), and set `Color32` per vertex.
- Cull by camera frustum and a max distance before upload; culling the readback itself needs a compute-shader change inside the SDK.
- Keep a position-only overload of the sampler — the minimap and the frame sender call the same entry point.
- Log `raw/kept/degenerate/stretched` triangle counts and the sampler's failure reason on device; without them an empty or garbled result is indistinguishable from a data problem.

## Build verification

```sh
aapt2 dump badging Build/QuestRoomScan.apk | grep -E "^package:|launchable-activity|native-code"
unzip -l Build/QuestRoomScan.apk | grep -E "lib/arm64-v8a/libUnityARFoundationMeta.so"
```

A `Succeeded` build with the `.so` missing is a broken app; check the APK contents, not the exit code.
