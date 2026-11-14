# OpenXR settings and the three gates

## 1. Loader auto-start (Unity XR Plug-in Management)

File: `Assets/XR/XRGeneralSettingsPerBuildTarget.asset`

```yaml
m_InitManagerOnStart: 1          # must be 1
m_AutomaticLoading: 1            # must be 1  <- silently 0 after package upgrades
m_AutomaticRunning: 1            # must be 1
m_Loaders:
- {fileID: 11400000, guid: <OpenXRLoader.asset guid>, type: 2}
```

Log signature when this gate is broken:

```
[RoomScan] DepthCapture: No active XR loader (Editor without Quest provider)
XRSettings.isDeviceActive == false, app renders flat and looks like an endless loading screen
```

A package upgrade (AR Foundation / XR Management) can reset these to `0` without touching the loader list; the loader stays listed but never runs.

## 2. Native plugin actually packaged

Native plugins shipped inside a package (`Library/PackageCache/<pkg>/Runtime/Plugins/android/arm64/*.so`) are not guaranteed to reach the APK. When one is missing the build still reports success.

Check, in order:

```sh
apt dump badging Build/QuestRoomScan.apk | grep -E "^package:|launchable-activity|native-code"
unzip -l Build/QuestRoomScan.apk | grep "lib/arm64-v8a/"
# also check the intermediate Gradle output, which shows what Unity actually handed over
ls Library/Bee/Android/Prj/IL2CPP/Gradle/*/build/intermediates/merged_native_libs/release/*/out/lib/arm64-v8a/
```

Fix: copy the `.so` into `Assets/Plugins/Android/arm64-v8a/` with a minimal meta next to it (folder name sets CPU and platform):

```
fileFormatVersion: 2
guid: <32 hex chars>
```

Log signature when missing: `DllNotFoundException: Unable to load DLL 'libUnityARFoundationMeta'` at the first subsystem construction, followed by the whole AR Foundation subsystem list failing to create.

## 3. Lifecycle feature and subsystem features

File: `Assets/XR/Settings/OpenXR Package Settings.asset` — one `MonoBehaviour` block per feature per build target, each with `m_enabled`, `featureIdInternal`, `openxrExtensionStrings`.

Feature ids that matter for Quest depth/AR:

| Feature | featureIdInternal |
|---|---|
| Lifecycle (initialises the native func table) | `MetaOpenXR-OpenXRLifeCycle` |
| AR session | `com.unity.openxr.feature.arfoundation-meta-session` |
| Occlusion / environment depth | `com.unity.openxr.feature.arfoundation-meta-occlusion` |
| Planes / anchors / mesh / camera | `...-meta-plane`, `...-meta-anchor`, `...-meta-mesh`, `...-meta-camera` |
| Composition layers (validation-required when the package is present) | `com.unity.openxr.feature.compositionlayers` |
| Meta XR SDK core (OVRPlugin hooks) | `com.meta.openxr.feature.metaxr` |

Without the lifecycle feature the log shows, immediately after loader init:

```
[XR] [OpenXR Meta] [XrFuncTable] Failed to look up OpenXR function because instanceProcAddr is null.
[OpenXR Meta] [SystemPropertiesUtility] Failed to get system properties: XR_ERROR_INITIALIZATION_FAILED
This OpenXR runtime doesn't support XR_META_environment_depth. The XROcclusionSubsystem won't be created
```

while the same log, one second later, shows the extension as available:

```
OVRPlugin:  Name=XR_META_environment_depth SpecVersion=2
XR_META_environment_depth: Version=2
Meta Quest: Occlusion: Version=0.1.0
```

That contradiction is the tell: the probe ran before the function table was bound, and the verdict is cached for the process. Restarting `ARSession` at runtime does not clear it — rebuild with the lifecycle feature enabled.

## Enabling features from an editor script

`OpenXRSettings.GetFeatures<T>()` does not expose build-target pairs in every version; walk the serialized assets instead.

> Code example split: part 1/3 of the archived reference block; concatenate in order if needed.
```csharp
using System.Linq;
using UnityEditor;
using UnityEditor.XR.OpenXR.Features;
using UnityEngine;
using UnityEngine.XR.OpenXR.Features;

static readonly string[] Wanted = {
  "MetaOpenXR-OpenXRLifeCycle",
  "com.unity.openxr.feature.arfoundation-meta-session",
  "com.unity.openxr.feature.arfoundation-meta-occlusion",
  "com.unity.openxr.feature.compositionlayers",
};

FeatureHelpers.RefreshFeatures(BuildTargetGroup.Android);   // creates entries for newly installed packages
const string path = "Assets/XR/Settings/OpenXR Package Settings.asset";
```
> Code example split: part 2/3 of the archived reference block; concatenate in order if needed.
```csharp

foreach (var asset in AssetDatabase.LoadAllAssetsAtPath(path))
{
    if (asset is not OpenXRFeature feature) continue;
    if (!feature.name.Contains("Android")) continue;        // separate block per build target
    var id = feature.GetType()
        .GetField("featureId", System.Reflection.BindingFlags.Public |
                               System.Reflection.BindingFlags.Static |
                               System.Reflection.BindingFlags.FlattenHierarchy)
        ?.GetValue(null) as string;
    if (id == null || !Wanted.Contains(id)) continue;

    var so = new SerializedObject(feature);
    var enabled = so.FindProperty("m_enabled");
    if (enabled != null && !enabled.boolValue) { enabled.boolValue = true; so.ApplyModifiedPropertiesWithoutUndo(); }
```
> Code example split: part 3/3 of the archived reference block; concatenate in order if needed.
```csharp
}
AssetDatabase.SaveAssets();
```

Run it with `-executeMethod <Class>.Run` in batchmode, then grep the asset to confirm each `m_enabled: 1`.

A feature whose class is compiled out (guarded by a package define) will not appear in `LoadAllAssetsAtPath` as its concrete type; flip its `m_enabled` in the YAML directly and confirm the build validation accepts it.

## Runtime probe for the app itself

Log once at startup, and every second while scanning:

- `AROcclusionManager.subsystem` null / stopped / running
- `currentEnvironmentDepthMode`
- `ARSession.enabled` and `XRSettings.isDeviceActive`
- scanner phase and progress, whether the refined renderer exists
- uplink status from the sender's last HTTP code

A useful heartbeat line: `[ARS] scan | t=12s phase=Scanning progress=41% uplink=200/2s ago/stored renderer=no`. A stall warning after ~8 s with 0 % progress turns a vague "scan does not start" into a single grep.
