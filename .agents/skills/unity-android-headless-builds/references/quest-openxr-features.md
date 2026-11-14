# Quest OpenXR feature wiring (Unity 6, meta-openxr)

## Where the toggles actually live

`Assets/XR/Settings/OpenXR Package Settings.asset` stores one MonoBehaviour
sub-asset per feature **per build target**: `AROcclusionFeature Android`,
`AROcclusionFeature Standalone`, and so on. Enabling a feature for a device
build means setting `m_enabled: 1` on the *Android* sub-asset.

OpenXR 1.15 does not expose a serialized `m_features` list on the settings
object, so `new SerializedObject(settings).FindProperty("m_features")` returns
null. Enumerate the asset instead:

```csharp
foreach (var asset in AssetDatabase.LoadAllAssetsAtPath(
             "Assets/XR/Settings/OpenXR Package Settings.asset"))
{
    var feature = asset as OpenXRFeature;
    if (feature == null || !feature.name.Contains("Android")) continue;
    var so = new SerializedObject(feature);
    var enabled = so.FindProperty("m_enabled");
    if (enabled != null && !enabled.boolValue)
    {
        enabled.boolValue = true;
        so.ApplyModifiedPropertiesWithoutUndo();
    }
}
AssetDatabase.SaveAssets();
```

Feature ids are `public const string featureId` statics on each feature class;
read them by reflection when the type is not directly referenced.
`OpenXRSettings.GetFeatures<T>()` is not reliable here — in this version it does
not hand back build-target pairs you can filter on.

## Features compiled under a define

Some feature classes sit inside `#if XR_COMPOSITION_LAYERS` (Composition Layers
Support). The sub-asset exists but cannot be seen as a typed `OpenXRFeature`,
so a scripted enable pass skips it silently. Set that one directly in the YAML
by locating its `m_Name` block and rewriting the following `m_enabled:` line,
then let the editor reimport the asset.

## Chapter and verse: ids worth knowing

- `com.unity.openxr.feature.arfoundation-meta-session`
- `com.unity.openxr.feature.arfoundation-meta-occlusion`
- `com.unity.openxr.feature.arfoundation-meta-anchor`
- `com.unity.openxr.feature.arfoundation-meta-plane`
- `com.unity.openxr.feature.arfoundation-meta-mesh`
- `com.unity.openxr.feature.compositionlayers` — required whenever
  `com.unity.xr.compositionlayers` is installed; the build preprocess step
  hard-fails with "The Composition Layers Support feature is required".
- `com.unity.openxr.feature.metaquest` — Meta Quest Support.
- `com.meta.openxr.feature.metaxr` — Meta XR SDK's own feature.

## Depth for an AR Foundation based scanner

Packages that integrate a depth sensor read it through `AROcclusionManager`.
Without `com.unity.xr.meta-openxr` installed and its occlusion feature enabled,
the subsystem is null and no frame ever arrives: the SDK logs
`DepthCapture: frames=0, depthAvail=False, sub=null` while the scan still
"starts" and reports progress 0 forever.

`com.unity.xr.meta-openxr` 2.4.1 pairs with OpenXR 1.15.1 and pulls AR
Foundation 6.4.0 plus composition layers 2.2.0 — expect those upgrades, and
re-verify package-cache patches after the resolve.

Do not assume the Meta SDK offers a shortcut. Check before promising one:
searching `com.meta.xr.sdk.core` and `com.meta.xr.mrutilitykit` for
`EnvironmentDepth|DepthTexture|depthFrame` returns nothing in the 205 line, so
"read depth straight from the Meta SDK" means writing native
`XR_META_environment_depth` swapchain code (acquire images, convert to the
format the integrator expects, per-frame pose and intrinsics), not calling an
existing API.

## Sequencing

Add one feature group, build, launch, then add the next. A rejected set aborts
inside `xrCreateInstance` roughly a second in, printing
`libc++abi: terminating` followed by SIGABRT in `UnityMain`, with no managed
log line at all. That symptom is the signal to bisect features, not to add
diagnostics to the game.

After enabling anything, commit the settings asset — the change lives in YAML
and is easy to lose in a cache cleanup.
