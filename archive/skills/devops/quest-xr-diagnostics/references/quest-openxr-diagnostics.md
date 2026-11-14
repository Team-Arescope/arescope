# Quest OpenXR: depth chain and feature control

## The depth chain

`RoomScan DepthCapture` → `AROcclusionManager` → Meta OpenXR provider → `XR_META_environment_depth`.

Every link must exist:

1. `com.unity.xr.meta-openxr` in `Packages/manifest.json`, version paired with the project's OpenXR (2.4.1 pairs with OpenXR 1.15.1 / Unity 6000.2).
2. That package's AR features enabled for Android: session, occlusion, optionally anchor/plane/mesh.
3. `XR_META_environment_depth` in the OpenXR extension list — the occlusion feature adds it.
4. Runtime: `AROcclusionManager.subsystem != null` and running.

Symptom map:

| Log | Meaning |
|---|---|
| `DepthCapture: USE_SCENE ready` | scene permission fine, says nothing about depth |
| `frames=0, depthAvail=False, sub=null` | no provider: package missing or occlusion feature off |
| `[ARS] xr \| occlusion=no-subsystem` | same, seen from managed code |
| `NullReferenceException ... AROcclusionManager.DestroyTextures` | finalize after a scan that never produced depth |
| `Texture refinement failed: Mesh readback returned no vertices` | consequence of an empty TSDF, not a texture bug |

## Permissions on Horizon OS

Names that actually ship (assert with `aapt2 dump permissions <apk>` before debugging a permission theory):

- `com.oculus.permission.USE_SCENE` — scene model and depth
- `com.oculus.permission.USE_ANCHOR_API` — spatial anchors
- `horizonos.permission.HEADSET_CAMERA` — passthrough camera
- `android.permission.RECORD_AUDIO`, `android.permission.CAMERA`

The scene and anchor permissions are `com.oculus.*`, not `horizonos.*` — only the camera one uses the `horizonos` namespace. `pm grant` legitimately answers `not a changeable permission type` for some Horizon permissions; those are confirmed in-app on first run, so a failed grant there is normal and not evidence of a broken manifest.

Do not rewrite the depth source while the provider is simply missing. The SDK reads `AROcclusionManager`; replacing that path with raw `XR_META_environment_depth` is a multi-day rewrite, only justified after the package route is proven impossible.

## Enabling features headlessly

Features live as separate `MonoBehaviour` objects in `Assets/XR/Settings/OpenXR Package Settings.asset`, one per build target. `OpenXRSettings.GetFeatures<T>()` does not expose those per-target entries, and a freshly added package contributes no entries until features are refreshed.

```csharp
FeatureHelpers.RefreshFeatures(BuildTargetGroup.Android);
const string path = "Assets/XR/Settings/OpenXR Package Settings.asset";
foreach (var asset in AssetDatabase.LoadAllAssetsAtPath(path))
{
    var feature = asset as OpenXRFeature;
    if (feature == null || !feature.name.Contains("Android")) continue;
    var so = new SerializedObject(feature);
    var enabled = so.FindProperty("m_enabled");
    if (enabled != null && !enabled.boolValue) { enabled.boolValue = true; so.ApplyModifiedPropertiesWithoutUndo(); }
}
AssetDatabase.SaveAssets();
```

Feature ids: `com.unity.openxr.feature.arfoundation-meta-session`, `...-occlusion`, `...-anchor`, `...-plane`, `...-mesh`, and `com.unity.openxr.feature.compositionlayers`. One feature does not follow that naming: `MetaOpenXR-OpenXRLifeCycle` (match it on that exact `featureIdInternal`). Leave the lifecycle feature off and every other feature is inert — it is what hands the native library a valid `instanceProcAddr`.

**Composition Layers is mandatory while its package is installed.** `com.unity.xr.compositionlayers` arrives as a dependency of meta-openxr; until the `Composition Layers Support` feature is on, the build fails with `OpenXR Build Failed` and that feature named in the validation block. Its class may be compiled out, so flip `m_enabled` in the asset rather than enabling it through a typed reference.

## Crash before managed code

Signature: `xrCreateInstance [end]` → `OVRPlugin: Func_xrGetInstanceProcAddr: override ...` → `libc++abi: terminating` → `Fatal signal 6 (SIGABRT)` in `UnityMain`, all within ~1.5 s.

- No `[ARS]` lines, no `Player.log` breadcrumbs. Expected.
- Evidence is only the CRASH block and the last OpenXR/OVRPlugin lines above it.
- On a healthy run the first managed line appears ~10 s after launch, so their absence is itself a signal.

Bisect: disable every `arfoundation-meta-*` feature, confirm the app boots into XR (`xr=active`), then enable one feature per build. Keep the previously booting APK as the rollback.

## Native bridge must be in the APK

`com.unity.xr.meta-openxr` ships `Runtime/Plugins/android/arm64/libUnityARFoundationMeta.so` (~16 MB). Unity can leave it out of the player build even with the plugin's `.meta` marked Android/ARM64 enabled and no warning in the log.

Signatures:

- Runtime: `DllNotFoundException: Unable to load DLL 'libUnityARFoundationMeta'` inside `MetaOpenXRSessionSubsystem+NativeApi...Construct`; AR subsystems never start.
- Build output: the library is absent from `.../Gradle/*/build/intermediates/merged_native_libs/release/.../lib/arm64-v8a/` and from `unzip -l app.apk`.

Fix: put a copy under the project's own plugin folder so the asset pipeline owns it.

```sh
cp Library/PackageCache/com.unity.xr.meta-openxr*/Runtime/Plugins/android/arm64/libUnityARFoundationMeta.so \
   Assets/Plugins/Android/arm64-v8a/
printf 'fileFormatVersion: 2\nguid: %s' "$(uuidgen | tr -d - | tr 'A-Z' 'a-z')" \
   > Assets/Plugins/Android/arm64-v8a/libUnityARFoundationMeta.so.meta
```

A two-line `.meta` is enough: the `arm64-v8a` folder sets ABI/CPU and the path sets the platform. Sibling plugins (`libxatlas.so`) get packaged for exactly this reason, which is why the omission looks arbitrary. Assert the result before publishing: `unzip -l <apk> | grep -q libUnityARFoundationMeta.so`.

## Extension support is cached from the first query

meta-openxr asks the runtime about `XR_META_environment_depth` while the OpenXR instance is still being created. The lookup fails and the negative verdict sticks for the rest of the process:

```
OVRPlugin: Name=XR_META_environment_depth SpecVersion=2          <- runtime supports it
[OpenXR Meta] Failed to look up xrGetSystemProperties: instanceProcAddr is null
This OpenXR runtime doesn't support XR_META_environment_depth    <- cached verdict
XR_META_environment_depth: Version=2                             <- extension enabled anyway
```

Result: `AROcclusionManager.subsystem == null`, no depth frames, `progress=0%`, one meaningless point on the minimap.

Do not reach for an in-app retry here. Toggling `ARSession.enabled` once XR is live was measured against this exact log: the subsystem stayed absent (`[ARS] xr-boot | after restart occlusion=no-subsystem`) because the verdict is held for the process, while a later run that fixed the real cause reported `DepthCapture: frames=1100, depthAvail=True, sub=MetaOpenXROcclusionSubsystem, running=True`.

The actual cause was the package's lifecycle feature left disabled: its Android block carried `m_enabled: 0`, so the native function table never received `instanceProcAddr` and every capability probe failed. Enable it, rebuild, then confirm both that the probe error is gone and that the depth frame counter climbs. An in-app retry is only worth writing after that signature is healthy and the subsystem is still missing.

## Log encoding

PowerShell `>` writes UTF-16LE, so a plain `grep` finds nothing. Convert: `iconv -f UTF-16LE -t UTF-8 logcat.txt > log.txt`. Screenshots: `adb shell screencap -p /sdcard/x.png` then `adb pull`; `adb exec-out screencap -p > file` corrupts binary output under PowerShell.
