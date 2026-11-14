---
name: quest-xr-diagnostics
description: Use when a Quest XR app crashes or gets no depth.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [quest, openxr, unity, android, diagnostics, adb]
---

# Quest XR runtime diagnostics

## When to Use

- A Quest APK builds and installs but aborts, hangs on a loading screen, or never produces scan/point data.
- Depth comes back as `sub=null`, `depthAvail=False`, or a scan starts and stays at 0%.
- You are about to add OpenXR packages or enable features on a Unity XR project and want to avoid a blind feature batch.

A green Unity build says nothing about whether the headset can run it. Work the chain in order; each step has a signature you can confirm from logs before spending a build on the next guess.

## Presentation, readback and finalize

Once the runtime is healthy, the remaining complaints are about what the user sees: a coloured SDK
mesh instead of a styled scan, an empty GPU readback, a finalize that hangs for minutes, or a HUD
that disappears behind geometry. Those recipes — render-mode switch, read-before-stop ordering,
skipping the texture bake, the URP overlay camera and per-panel contrast — are in
`references/unity-xr-render-and-finalize.md`.

## Order of operations

1. **Read the whole log before forming a theory.** Confirm the app version actually installed (`[ARS] boot | app=...`), the crash or hang timestamp, and whether *any* managed line exists. A process that dies ~1.5 s after launch has not run managed code, so no amount of in-app logging will explain it.
2. **Check the XR loader is automatic.** `Assets/XR/XRGeneralSettingsPerBuildTarget.asset` for Android needs `m_AutomaticLoading: 1` and `m_AutomaticRunning: 1`. With either at `0` the app runs flat: `No active XR loader`, MRUK `NotInitialized`, endless loading screen. Package upgrades reset these.
3. **Check the subsystem you actually need exists, not just the package.** Depth on Quest: `com.unity.xr.meta-openxr` must be installed, its AR Foundation features enabled for Android, **and its native bridge present inside the APK**. Otherwise `AROcclusionManager.subsystem` is null and the scan silently produces nothing. Confirm the shipped library directly: `unzip -l app.apk | grep libUnityARFoundationMeta.so` (or inspect the Gradle `merged_native_libs/` output). Presence in `Library/PackageCache` proves nothing.
4. **Bisect features only when steps 2–3 pass and it still crashes.** Native aborts at `xrCreateInstance` are feature-triggered; enable one feature per build and keep a known-good APK as the rollback point.
5. **Never ship an untested feature batch.** Enabling five OpenXR features at once turns one unknown into five and costs a build cycle per candidate.

Run `scripts/triage_logcat.py <logcat>` to normalise encoding (PowerShell writes UTF-16LE) and print crash blocks, `[ARS]`/`[RoomScan]` lines and the last OpenXR calls before an abort. It also flags the four common findings: no managed output, missing depth provider, no XR loader, XR inactive.

## Instrumenting the app when logs are sparse

Unity fills logcat with noise: every `Debug.Log` emits ~30 stack lines and the device log mixes in dozens of system tags. Make the app self-describing before you need it.

- **One tag, one line per event.** Prefix everything with `[ARS]` and write `area | key=value` lines so a whole run reduces to `grep '\[ARS\]'`.
- **Silence stacks.** `Application.SetStackTraceLogType(LogType.Log, StackTraceLogType.None)` and the same for `Warning`; keep `Error` at `ScriptOnly`. Without this the useful line is one in thirty.
- **Mirror to a file.** Append each line to `Application.persistentDataPath/arescope-debug.log` with a synchronous write; a breadcrumb file survives a native abort, a logcat buffer may not be flushed. Pull it with `adb pull /sdcard/Android/data/<pkg>/files/arescope-debug.log`.
- **Boot line via `[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]`** logging app version, device, OS, and the persistent path. If that line never appears, the process died before managed code and no in-app logging can help.
- **Heartbeat once per second while scanning** with phase, progress, uplink status and whether a renderer exists; add a one-shot snapshot of the subsystem state at start. A stalled counter is what distinguishes "no depth" from "slow depth".

## When the pipeline runs but the output looks wrong

XR is active and progress moves, yet the result is unusable. Separate the layers before touching quality settings:

- **A single stray point on a minimap, progress pinned at 0 %** → the TSDF is empty because no depth frame arrived; this is a provider problem, not a mapping or positioning bug. Go back to step 3.
- **Geometry appears but surfaces look like smeared blobs** → the app is showing the dense mesh with vertex colours, not the refined textured mesh. Check in order: the `TextureRefinement` module exists in the scene, the finalize log reports UVs (`mesh.uv.Length > 0`), and the refinement pass logged success. If any is missing, no atlas was produced and bake-quality knobs cannot help.
- **Only after both pass**, tune atlas resolution or bake settings. Logging the module's presence and the UV count at finalize turns this triage into one grep instead of a build cycle.
- **Bake succeeded but the result is still soft** → read the refinement log before touching knobs. A room-scale atlas around 2200×2200 px is normal, and heavy keyframe rejection (`N refined, M rejected` from the registration line) is the usual cause of patchy texture, not the bake settings. To raise density, change the whole set in one build: `simplifyBeforeUnwrap = false` (bake the dense mesh), `skipDenoise = false`, `maxViewsPerTexel` 3→4, `sharpenStrength` ≈1.1 — then **time one bake before shipping it**. On a Quest-class mobile chip that set can turn a seconds-long bake into minutes, which the user experiences as a hang after pressing finalize. Soft texture at 3 s is usually the better trade; if it is not, change the presentation instead of the bake (see the wireframe note below).

## Interface that must stay on top

A world-space HUD canvas lives in the same depth-tested scene as the scan mesh, so geometry closer than the canvas hides the interface — panels vanish when the user leans into a wall or the mesh grows past the HUD distance. Fix it with a dedicated URP overlay camera instead of nudging the canvas closer:

1. Move the canvas and all its children to a dedicated layer (`UI`/5 is fine).
2. Clear that bit from the main camera's `cullingMask`, so the HUD is drawn once.
3. Create a child camera on the head camera with `clearFlags = CameraClearFlags.Depth`, `cullingMask = 1 << layer`, `stereoTargetEye = StereoTargetEyeMask.Both`, and `renderType = CameraRenderType.Overlay` via `GetUniversalAdditionalCameraData()`.
4. Add it to the base camera's `cameraStack`. URP renders only cameras that are in the stack, so a valid camera that was never added renders nothing — and no error is logged.

**Make the backdrop react to the world — per panel, not globally.** Panels tuned for a dark room wash out on a white wall. Once per second, blit the passthrough frame into a small `RenderTexture` (32×32 is plenty), read it back with `AsyncGPUReadback`, and evaluate **each panel against its own screen rectangle** rather than the whole frame: `RectTransform.GetWorldCorners` → `Camera.WorldToViewportPoint` for the four corners → sample that sub-rect of the probe → fraction of pixels above a luminance threshold → raise *that* panel's alpha (0.25 → ~0.48). A global average darkens every element when a single bright corner lights up, which is exactly what the user notices; per-panel keeps the dark side untouched. Keep a per-key cache so the alpha is written only when the verdict flips, and skip while a readback is in flight — the probe must never stall the frame.

**What the user sees during a scan is a separate decision from the final result.** The SDK's default live presentation is the dense TSDF mesh with vertex colours (`Render mode: Vertex` in the log) — it looks like smeared blobs and reads as broken to anyone watching. To scan in the LAB style instead: call `RoomScanner.SetRenderMode(ScanRenderMode.None)` at scan start to suppress the SDK mesh, and draw your own presentation from sampled points (`LiveScanPoints`-style: billboarded quads on the same unlit transparent shader, a few hundred points, refresh ~2 Hz). Rebuilding a full line mesh on every tick is not worth it on a mobile chip — unique-edge extraction over tens of thousands of triangles at 2 Hz causes visible hitches; lines are for the finalized mesh, points are for the live one. Re-enable the SDK renderer (or swap to your wireframe) at finalize, and make sure the toggle path restores whatever the user expects to see.

**Prefer a translucent wireframe over textures when the source imagery is weak.** Quest passthrough cameras give a soft, low-resolution atlas; baking then costs time and still looks blurred. A minimal LAB-style presentation reads better and is cheap: unique triangle edges as a `MeshTopology.Lines` mesh at ~75 % transparency, plus one billboarded quad per vertex for points, both on an unlit transparent shader with `ZWrite Off`. Hide the SDK's textured renderer rather than deleting it, so the textured path stays available.

Recipe with the exact calls: `references/hud-and-texture-quality.md`.

## Finishing a scan without the texture pipeline

`FinalizeScanAsync` hard-requires the `TextureRefinement` module and waits up to five minutes for the atlas bake, so it is the wrong exit when the presentation is a wireframe or a point cloud. Disabling the component does not help: the check is on module presence, and a disabled module still throws "TextureRefinement module required for FinalizeScanAsync". Bypass the API, not the component.

Read the mesh yourself, and read it **while the scan is still live**: `StopScanning()` releases the GPU volumes, and a readback started afterwards returns zero vertices (`mesh readback empty`) however long you wait. Working order:

1. `MeshExtractor.Instance.ExtractForAuthoring()` — refreshes the Surface Nets buffers.
2. Read the counters, vertex and index buffers with `AsyncGPUReadback.RequestAsync`.
3. Only then stop the scanner and build your presentation from the CPU copy.

An empty readback on the first frame is a readiness problem, not a configuration one — check the vertex counter before rebuilding, rather than spending a build cycle on it.

## HUD placement that is comfortable on Quest optics

Numbers that survived review on a Quest 3S; start here instead of re-tuning from scratch.

- **Distance ~0.6 m from the eyes**, not ~1.1 m. A world-space HUD around a metre away reads as far and forces the eyes to converge; 0.62 m stays comfortable while the follow logic still fits the canvas to the FOV.
- **Pull side panels toward the centre, never toward the rim.** Quest lenses blur the periphery, so an element 40 units from the edge looks soft even at the right distance; ~150 units of inset reads sharp.
- **A minimap is a floor plan, not a point cloud.** Keep only points within ±0.10 m of head height and cap the count (~64). A ±1 m band fills the map with floor and ceiling and makes every room look identical.
- **Give the user an exit and a reset.** Toggle passthrough during a scan (the scan keeps integrating in the background) and bind a hold-to-reset; without them the only recovery from a bad scan is relaunching the app.

## Pitfalls

- **A diagnostic probe that searches differently than the code under test reports a false negative.** `AROcclusionManager.subsystem` logged as `null` while the SDK reported `sub=MetaOpenXROcclusionSubsystem, running=True` and 1100 depth frames: the probe used `FindAnyObjectByType<T>()` (active objects only) while the scanner used `FindObjectsInactive.Include`. Mirror the production lookup in diagnostics, or the log lies about a working subsystem.
- **A URP camera stack containing one overlay has `Count == 1`, not 2.** The base camera is not part of its own stack, so a health line asserting `== 2` reports failure on a correct setup. Log the stack contents, not an assumed total.
- **Managed logs cannot diagnose a native abort.** SIGABRT between `xrCreateInstance [end]` and the first frame kills the process before `RuntimeInitializeOnLoadMethod` runs; empty logs are evidence, not a logging bug.
- **`No active XR loader` is a configuration symptom, never a scene-wiring bug.** Fix the automatic loading flags first; MRUK `NotInitialized` and `xr=inactive` follow from it.
- **Missing depth bridge looks like a scanner bug.** `frames=0, depthAvail=False, sub=null` plus a later `NullReferenceException` in `AROcclusionManager.DestroyTextures` means no provider, not a broken scan loop. A minimap that shows a single point unrelated to the room is the same symptom: an empty TSDF, not a positioning bug.
- **A package's native plugin may never reach the APK.** A `.so` that exists only under `Library/PackageCache/<pkg>/Runtime/Plugins/...` can be skipped by the player build with no warning; at runtime the app throws `DllNotFoundException: libUnityARFoundationMeta` while every package and feature setting looks correct. Copy the library into `Assets/Plugins/Android/<abi>/` with a minimal `.meta` and verify it in the built APK. Sibling plugins do get packaged when they live in `Assets/Plugins`, which makes the omission look random.
- **Depth support is decided once, early, and the answer is cached.** `Failed to look up xrGetSystemProperties ... instanceProcAddr is null` immediately followed by `This OpenXR runtime doesn't support XR_META_environment_depth` means the check ran before the instance was valid. If OVRPlugin already listed the extension (`Name=XR_META_environment_depth SpecVersion=2`) and Unity later logs the same extension as enabled, the runtime does support it — the subsystem was just never created. Toggling `ARSession` does **not** clear this (verified: the subsystem stays absent after a restart). The root cause is usually the package's lifecycle feature left disabled, so the native function table never received `instanceProcAddr`; enable `MetaOpenXR-OpenXRLifeCycle` for the Android target, rebuild, and confirm the probe error is gone.
- **Duplicate defects mask each other.** A missing native library and a non-starting XR loader produce different symptoms but can coexist, so fixing one makes the app progress into a new failure that looks unrelated. Re-check every link of the chain after each fix instead of assuming the previous diagnosis is the whole story.
- **Some OpenXR features must be enabled through the settings asset.** Features are separate objects in `OpenXR Package Settings.asset`, one per build target; the typed runtime accessor does not reach them. See `references/quest-openxr-diagnostics.md`.
- **An installed package can make the build fail validation.** A dependency package can demand its matching OpenXR feature; the error is `OpenXR Build Failed` with the required feature named in the validation block.
- **Headless editor runs can silently skip the build method.** A leftover `Temp/UnityLockfile`, a malformed `.meta` GUID, or a first run that only imports packages all produce a short log with no marker line. See `references/unity-batchmode-pitfalls.md` before rebuilding.
- **Reinstall must bump `bundleVersionCode`.** Installing over an equal code keeps the old package on some launch paths and makes a fresh test indistinguishable from the broken one.
- **A build that ends in a profiler stack trace and no result line ran out of disk, not out of luck.** Unity fails late — after minutes of IL2CPP and Gradle work — while writing a profiler trace, and the tail reads like a tooling crash. `grep -c "No space left" <build log>` plus `df -h` settles it in one command; clean generated caches and rebuild instead of debugging the editor.
- **A shader loaded by name at runtime is stripped from the player.** `Shader.Find("Vendor/Name")` returns null in a build when nothing in an included scene or asset references that shader, and the failure is silent (no material, invisible geometry). Put runtime-loaded shaders under `Assets/Resources/` and fetch them with `Resources.Load<Shader>("...")`, keeping `Shader.Find` only as a fallback.
- **The scan's mesh dies with the scan.** Any presentation that needs vertex or index data must copy it before `StopScanning()`; after it, the TSDF volumes are released and the buffers read back empty. The same applies to finalization paths that skip the SDK's own export.
- **Scene references do not follow code changes.** Adding a component, renaming a `[SerializeField]`, or changing a package's serialized settings needs the project's own re-wire pass (a separate headless editor run) before the build; otherwise the APK is green and the feature is missing at runtime.

## References

- `references/quest-openxr-diagnostics.md` — depth chain, feature ids, enabling features headlessly, crash-before-managed-code triage.
- `references/unity-batchmode-pitfalls.md` — stale locks, `.meta` GUIDs, first-run import, render-to-texture traps.
- `references/hud-and-texture-quality.md` — always-on-top HUD via a URP overlay camera, and texture-bake knobs with the numbers a healthy bake logs.
