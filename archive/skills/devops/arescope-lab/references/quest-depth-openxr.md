# Quest depth for RoomScan (OpenXR)

Depth capture on Quest goes `XR_META_environment_depth` → `com.unity.xr.meta-openxr` → AR Foundation `AROcclusionManager` → `Genesis.RoomScan.DepthCapture`. A missing link anywhere below AR Foundation leaves a scanner that starts, allocates its TSDF volume and then never receives a frame.

## Three gates below AR Foundation — check in this order

1. **The XR loader auto-starts.** `Assets/XR/XRGeneralSettingsPerBuildTarget.asset` must carry `m_AutomaticLoading: 1` and `m_AutomaticRunning: 1` for Android. A package upgrade can reset them to `0` while the loader stays listed; the app then renders flat and logs `[RoomScan] DepthCapture: No active XR loader` plus `XRSettings.isDeviceActive == false`.
2. **Every native plugin is inside the APK.** `libUnityARFoundationMeta.so` can be omitted from the package even when its `.meta` marks Android/ARM64 — copy it to `Assets/Plugins/Android/arm64-v8a/` and assert `unzip -l <apk> | grep libUnityARFoundationMeta.so`. Missing it throws `DllNotFoundException` at the first subsystem construction, which the scanner reports as a plain `sub=null`.
3. **The lifecycle feature is enabled.** `MetaOpenXR-OpenXRLifeCycle` binds the native function table. With it off (a fresh install leaves it `m_enabled: 0`), every capability probe sees `instanceProcAddr is null`, logs `This OpenXR runtime doesn't support XR_META_environment_depth`, and the occlusion subsystem is never created — while the same log, a second later, shows `OVRPlugin: Name=XR_META_environment_depth SpecVersion=2` and the feature in the enabled list. The verdict is cached for the process, so restarting `ARSession` at runtime does not clear it; only a rebuild with the feature enabled does.

## Symptom table

| Log line | Meaning |
|---|---|
| `DepthCapture: frames=0, depthAvail=False, sub=null` | no `XRDepthSubsystem` was created: AR Foundation has no provider for Meta depth |
| `NullReferenceException … AROcclusionManager.DestroyTextures` on finalize | depth textures were never created — same root cause, one step later |
| `Texture refinement failed: Mesh readback returned no vertices` | consequence: nothing was integrated, so the GPU mesh is empty |
| `libc++abi: terminating` right after `xrCreateInstance` / the `OVRPlugin: Func_xrGetInstanceProcAddr: override …` block, with **zero** `[RoomScan]` lines | the app dies in OpenXR feature init, before any scene script runs — suspect the features you just enabled, not the scanner |

Read the log with the app PID (`adb logcat -d -v time --pid=$(adb shell pidof -s <pkg>)`); a system-wide buffer buries these lines, and a PowerShell `>` redirect writes UTF-16LE, so convert with `iconv -f UTF-16LE -t UTF-8` before grepping.

## Fix

1. Add the plugin to `Packages/manifest.json`:

```json
"com.unity.xr.meta-openxr": "2.4.1"
```

   2.4.1 pairs with OpenXR 1.15.1; it upgrades `com.unity.xr.arfoundation` to 6.4.0 and adds `com.unity.xr.compositionlayers` 2.2.0 as side effects. Treat the ARF jump as a risk, not a detail. Newer 2.6/2.7 require OpenXR 1.18 — do not take them without upgrading OpenXR deliberately.

2. Enable the AR Foundation Meta features for Android.

| Feature id | Needed for |
|---|---|
| `com.unity.openxr.feature.arfoundation-meta-session` | AR session plumbing |
| `com.unity.openxr.feature.arfoundation-meta-occlusion` | depth; declares `XR_META_environment_depth` |
| `com.unity.openxr.feature.arfoundation-meta-plane` | MRUK room data |
| `com.unity.openxr.feature.arfoundation-meta-mesh` | MRUK scene mesh |
| `com.unity.openxr.feature.arfoundation-meta-anchor` | spatial anchors |
| `com.unity.openxr.feature.compositionlayers` | required by build validation once the composition-layers package is present |
| `MetaOpenXR-OpenXRLifeCycle` | binds the native func table; without it every depth probe fails and is cached |

3. Enable them from an editor method instead of clicking the settings UI.

   Features are **separate objects inside the settings asset**, one per build target, not a list on `OpenXRSettings`. `OpenXRSettings.GetFeatures<T>()` also does not hand back `(buildTargetGroup, feature)` pairs in OpenXR 1.15.1, so tuple deconstruction fails to compile, and the settings object has no `m_features` property to walk. What works:

```csharp
FeatureHelpers.RefreshFeatures(BuildTargetGroup.Android);
const string path = "Assets/XR/Settings/OpenXR Package Settings.asset";
foreach (var asset in AssetDatabase.LoadAllAssetsAtPath(path)) {
    var feature = asset as OpenXRFeature;
    if (feature == null || !feature.name.Contains("Android")) continue;
    var id = (string)feature.GetType()
        .GetField("featureId", BindingFlags.Public | BindingFlags.Static | BindingFlags.FlattenHierarchy)
        ?.GetValue(null);
    if (IdList.Contains(id)) {
        var so = new SerializedObject(feature);
        so.FindProperty("m_enabled").boolValue = true;
        so.ApplyModifiedPropertiesWithoutUndo();
    }
}
AssetDatabase.SaveAssets();
```

   If a feature's class compiles under a package define and the loop cannot see it, flip `m_enabled` for that entry directly in the asset and rebuild — build validation reads the serialized flag.

4. Rebuild and verify the extension list contains `XR_META_environment_depth` for the Android entry.

## Bisect features only after the baseline boots

A deterministic `SIGABRT` at `xrCreateInstance` with zero `[RoomScan]` lines is a failure of gates 1–3 above, not proof that one of the AR features is unsafe: in one run the same abort was produced by a missing native library and a disabled lifecycle feature, and disabling occlusion only stopped it by preventing the loader from starting. Re-check the three gates first. Once the app boots and `xr=active` with `occlusion=running`, adding plane/mesh/anchor one at a time is still cheap insurance — each extra feature is a new crash surface — but do not conclude "feature X crashes" from a single enable/disable pair without confirming the layer beneath was healthy in both builds.

## Build-validation trap

With `com.unity.xr.compositionlayers` installed, `OpenXRProjectValidationBuildStep` fails the build with `The Composition Layers Support feature is required to use the Composition Layers package` — the dependency arrives with meta-openxr, so the feature is not optional. Enable `com.unity.openxr.feature.compositionlayers` and rebuild; the error appears only at build time, after a successful compile.

## Device verification

Success looks like:

```
[RoomScan] DepthCapture: subsystem started
[RoomScan] DepthCapture: frames=NN, depthAvail=True, sub=<provider>
```

`frames` must keep growing while the headset moves. A start with `sub=null` and a frozen counter is the missing-provider case above, not slow warm-up. Probe permission state with `adb shell dumpsys package <pkg> | grep -A3 "runtime permissions"` — expectations are `RECORD_AUDIO`, `CAMERA`, `horizonos.permission.HEADSET_CAMERA`, `com.oculus.permission.USE_SCENE`, `com.oculus.permission.USE_ANCHOR_API`; `pm grant` on the `com.oculus.*` entries commonly answers `not a changeable permission type`, which is normal, they are granted in-app.
