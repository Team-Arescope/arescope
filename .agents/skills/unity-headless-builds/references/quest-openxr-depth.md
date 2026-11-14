# Quest depth through AR Foundation (OpenXR)

Spatial scanning on Quest reads depth through `AROcclusionManager`. That subsystem is not part of the scanning SDK and not part of AR Foundation's core: it arrives with the Unity Meta OpenXR provider package, and it only comes up when four independent things are right.

## Symptom of a missing provider

- Build is green, the app launches, the scan "starts" and allocates its volume (`TSDF volume: int3(256,256,256) ... 32MB`), then nothing progresses.
- Every five seconds in logcat: `[RoomScan] DepthCapture: frames=0, depthAvail=False, sub=null`.
- On stop/finalize: `NullReferenceException at AROcclusionManager.DestroyTextures()` and then `Mesh readback returned no vertices`. That exception is a side effect, not the cause: the manager never created the textures it is now destroying.
- No `Scan failed:` line exists, because nothing threw on start.

`sub=null` plus `frames=0` is the tell: the occlusion subsystem was never created.

## The four layers, in the order they must be checked

These fail independently and each one hides the next. Fix one, rebuild, verify in the log, then move on — batching them makes the log unreadable and the bisect meaningless.

### 1. The XR loader must auto-start

`Assets/XR/XRGeneralSettingsPerBuildTarget.asset`, Android block: `m_AutomaticLoading: 1`, `m_AutomaticRunning: 1`. Package upgrades reset both to `0`, and the symptom is not a crash: the app runs flat, `XRSettings.isDeviceActive` stays false, the SDK logs `[RoomScan] ... No active XR loader`, MRUK returns `NoRoomsFound ... NotInitialized`, and the user sees an endless loading screen.

### 2. The native bridge must be in the APK

`DllNotFoundException: Unable to load DLL 'libUnityARFoundationMeta'` at `MetaOpenXRSessionSubsystem+NativeApi.UnityOpenXRMeta_Session_Construct`. The `.so` ships inside `com.unity.xr.meta-openxr/Runtime/Plugins/android/arm64/` but the build silently skips it — the subsystems manifest is copied, the library is not.

Fix: copy it into `Assets/Plugins/Android/arm64-v8a/libUnityARFoundationMeta.so` (a minimal two-line `.meta` with just `fileFormatVersion` and `guid` is enough; Unity infers platform and CPU from the folder). This is the same mechanism that makes `libxatlas.so` ship. Verify inside the built APK with `unzip -l <apk> | grep UnityARFoundationMeta`, not in the Gradle staging tree.

### 3. The lifecycle feature must be enabled

The bridge also needs `MetaOpenXR-OpenXRLifeCycle` (feature id `MetaOpenXR-OpenXRLifeCycle`) enabled for Android. Without it the native func table is never initialised, and the log shows:

```
[XR] [OpenXR Meta] [XrFuncTable] Failed to look up OpenXR function because instanceProcAddr is null.
[XR] [OpenXR Meta] SystemPropertiesUtility: Failed to get system properties: XR_ERROR_INITIALIZATION_FAILED
This OpenXR runtime doesn't support XR_META_environment_depth.
```

That last line is a lie: seconds earlier the runtime logged `Name=XR_META_environment_depth SpecVersion=2`, and later in the same init it lists the extension as enabled. The capability probe ran before the instance was bound and the negative result is cached for the process, so restarting `ARSession` at runtime does not recover. Fix the feature, not the timing.

### 4. The depth feature itself

Add `com.unity.xr.meta-openxr` to `Packages/manifest.json`. Choose the release whose `com.unity.xr.openxr` dependency **equals** the project's OpenXR version; querying `https://packages.unity.com/com.unity.xr.meta-openxr` lists each version's dependencies. Jumping to the newest release silently upgrades OpenXR and AR Foundation, which is a much larger change than fixing depth.

Run the editor once (batchmode is fine) so the package resolves and the feature assets are created, then enable for Android:

- `com.unity.openxr.feature.arfoundation-meta-session`
- `com.unity.openxr.feature.arfoundation-meta-occlusion`
- `com.unity.openxr.feature.arfoundation-meta-anchor`
- `com.unity.openxr.feature.arfoundation-meta-plane`
- `com.unity.openxr.feature.arfoundation-meta-mesh`
- `MetaOpenXR-OpenXRLifeCycle`

Anchors, planes and mesh can wait until something needs them; session and occlusion are the minimum for depth.

## Enabling features from a batchmode script

> Code example split: part 1/2 of the archived reference block; concatenate in order if needed.
```csharp
FeatureHelpers.RefreshFeatures(BuildTargetGroup.Android);   // UnityEditor.XR.OpenXR.Features
const string path = "Assets/XR/Settings/OpenXR Package Settings.asset";
foreach (var asset in AssetDatabase.LoadAllAssetsAtPath(path))
{
    if (asset is not OpenXRFeature feature) continue;
    var idField = feature.GetType().GetField("featureId",
        BindingFlags.Public | BindingFlags.Static | BindingFlags.FlattenHierarchy);
    string id = idField?.GetValue(null) as string;
    if (id == null || !Wanted.Contains(id) || !feature.name.Contains("Android")) continue;

    var so = new SerializedObject(feature);
    var enabled = so.FindProperty("m_enabled");
    if (enabled != null && !enabled.boolValue)
    {
        enabled.boolValue = true;
```
> Code example split: part 2/2 of the archived reference block; concatenate in order if needed.
```csharp
        so.ApplyModifiedPropertiesWithoutUndo();
    }
}
AssetDatabase.SaveAssets();
```

Two API traps in OpenXR 1.15 that cost time:

- `OpenXRSettings` has **no `m_features` serialized array** — the features are separate objects in the settings asset. Enumerating `AssetDatabase.LoadAllAssetsAtPath` is the reliable route.
- `settings.GetFeatures<OpenXRFeature>()` returns items that do not support tuple deconstruction in this version; writing `foreach (var (group, feature) in ...)` fails to compile with `CS1061 Deconstruct`.

## Composition Layers validation blocker

`meta-openxr` depends on `com.unity.xr.compositionlayers`, and the OpenXR preprocess build step then aborts with:

```
The Composition Layers Support feature is required to use the Composition Layers package.
BuildFailedException: OpenXR Build Failed.
```

Enable `com.unity.openxr.feature.compositionlayers`. Its class is compiled only under the `XR_COMPOSITION_LAYERS` define, so in batchmode it can be absent from `LoadAllAssetsAtPath` results and the script above will not find it. In that case set the flag in the YAML directly: locate `m_Name: OpenXRCompositionLayersFeature Android` in the settings asset and set the following `m_enabled: 1`. The build then passes.

## Verification after installing the APK

- logcat: `[RoomScan] DepthCapture: frames=NN, depthAvail=True, sub=MetaOpenXROcclusionSubsystem, running=True`; the HUD percentage advances.
- Diagnose with the SDK's own lookup, not a naive one: the SDK finds the manager with `FindAnyObjectByType<AROcclusionManager>(FindObjectsInactive.Include)`. `FindFirstObjectByType` skips the inactive manager and reports `no-subsystem` while depth is flowing.
- `aapt2 dump permissions <apk>` should list `com.oculus.permission.USE_SCENE`, `com.oculus.permission.USE_ANCHOR_API` and `horizonos.permission.HEADSET_CAMERA`. Note the two prefixes: scene and anchor permissions are `com.oculus.*`, only the camera is `horizonos.*`. Deriving grant commands from memory sends `pm grant` into `not a changeable permission type`.

## Finalize blocks on texture refinement even when it is not used

`RoomScanSession.FinalizeScanAsync` requires the texture module and waits up to five minutes for the atlas bake (`Texture refinement timed out (5 min)`). Disabling the `TextureRefinement` component does not skip it: the call still runs xatlas and then bakes every keyframe — ~30 s of unwrap plus seconds per keyframe, which is the "finalize takes minutes" report.

When the app does not display textures, do not call it. Stop the scanner and read the mesh directly from the GPU buffers:

```csharp
scanner.StopScanning();
var meshData = await ArescopeMeshExport.ReadAsync(200000);   // package-side patch over GPUSurfaceNets
mesh.SetVertices(meshData.Positions);
mesh.SetIndices(meshData.Indices, MeshTopology.Triangles, 0, true);
```

Result: seconds instead of minutes. Keep the textured path only when the atlas is actually shown.

Texture-quality knobs, if the atlas is shown: `simplifyBeforeUnwrap=false` (bake the dense mesh), `maxViewsPerTexel=4`, `skipDenoise=false`, `sharpenStrength` around 1.1. These push a room bake from seconds into minutes on XR2 — measure before shipping them.

## Reading device logs before blaming the app

- `adb logcat > file` under Windows PowerShell 5.1 writes **UTF-16LE**. Grep and tag filters then match nothing because every byte is padded with NUL. Convert first: `iconv -f UTF-16LE -t UTF-8`.
- Capture with `Out-File -Encoding utf8`, and pull screenshots with `adb shell screencap -p /sdcard/x.png` + `adb pull`, never with shell redirection (PowerShell corrupts binary streams).
- Launch through `adb shell am start -n <pkg>/<activity>`; the activity is visible in `aapt2 dump badging`.
- Ask for a scripted repro (start scan → leave the room boundary → hold reset → finalize) rather than an unfiltered dump; 20k lines hide the single line that matters.

## Instrument the app instead of guessing

- One tag for the whole app (`[ARS] area | key=value`) plus `Application.SetStackTraceLogType(Log, None)` at boot. A single `Debug.Log` otherwise drags ~30 stack frames into logcat and buries the signal. Keep stacks for `Error` only.
- Mirror the same lines to `Application.persistentDataPath/<app>-debug.log` synchronously, so a native `SIGABRT` before managed code still leaves evidence; pull it with `adb pull /sdcard/Android/data/<pkg>/files/<app>-debug.log`.
- Log a one-per-second heartbeat while scanning (phase, percent, uplink status) and one snapshot of the XR stack at start. That single line usually identifies which of the four layers above is broken.

## Preview renders of a world-space HUD

When rendering the HUD canvas into a RenderTexture for review, set `camera.aspect` to the target width/height and rebuild the projection matrix before `Camera.Render()`. Without it the canvas is projected with a stale aspect, rows collapse and panels overlap — a preview-only artifact that looks exactly like a CSS/layout regression and is not reproducible in the headset.

Finding a light by type matters too: after adding a lamp to the scene, `FindFirstObjectByType<Light>()` returns that lamp, not the sun. Filter `FindObjectsByType<Light>()` for `LightType.Directional` when adjusting the key light.

## HUD that must never be occluded by scan geometry

A world-space canvas is ordinary transparent geometry, so the scan mesh hides it whenever the user stands close to a surface. Put the canvas on its own layer and render it with a URP overlay camera that clears depth:

1. Recursively set the canvas subtree to layer `UI` (5) and clear that bit from the main camera's `cullingMask`.
2. Create a child camera with `clearFlags = Depth`, `cullingMask = 1 << 5`, `stereoTargetEye = Both`.
3. `overlayData.renderType = CameraRenderType.Overlay` and `mainData.cameraStack.Add(overlay)`.

Note the semantics: after adding one overlay, `cameraStack.Count` is `1` — the base camera is not in the list. A `count == 1` log line means success, not failure.

## Per-panel backdrop contrast

To keep translucent HUD panels readable over bright surfaces without darkening everything, sample the passthrough camera frame once per second (`Graphics.Blit` to a 32x32 `RenderTexture`, `AsyncGPUReadback`), project each panel's world corners to viewport coordinates, and average only that rectangle. Above ~70 % bright pixels, raise that panel's backdrop alpha; otherwise leave it. Each panel keeps its own state so one bright corner does not dim the whole interface.

`AsyncGPUReadback.Request(...).GetData<Color32>()` returns a `NativeArray<Color32>`, not an array — a helper taking `Color32[]` fails to compile with `CS1503`.
