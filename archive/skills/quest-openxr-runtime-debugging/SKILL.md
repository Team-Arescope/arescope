---
name: quest-openxr-runtime-debugging
description: Use when a Quest/OpenXR build runs but XR or depth fails.
metadata:
  hermes:
    tags: [unity, quest, openxr, meta, arfoundation, debugging]
---

# Quest / OpenXR runtime debugging

## When to Use

A Quest APK builds and installs, but in the headset it never enters VR, hangs on
loading, crashes at startup, never receives depth, renders the wrong mesh, or the
UI disappears behind geometry. Also use when a scan/AR feature "does not start"
while logs show no exception.

## Order of checks

Work top to bottom. These failures mask each other: a missing XR loader hides a
missing native plugin, which hides a disabled OpenXR feature, which hides a real
app bug. Fix one, rebuild, confirm, continue.

1. **Does XR start at all?** Look for `No active XR loader`, `xr=inactive`, and an
   endless loading screen. Check `Assets/XR/XRGeneralSettingsPerBuildTarget.asset`
   for the target platform: `m_AutomaticLoading` and `m_AutomaticRunning` must be
   `1`. Package upgrades (AR Foundation, XR Management) can silently reset them.
2. **Did every native plugin reach the APK?** `DllNotFoundException` naming a
   `.so` that exists in a package means Unity skipped it. Copy that file into
   `Assets/Plugins/Android/arm64-v8a/` with a minimal `.meta` and prove it with
   `unzip -l <apk> | grep lib/arm64`. Package libraries are not reliably packaged
   from `Library/PackageCache`; the `Assets/Plugins` copy is.
3. **Are the OpenXR features enabled for that build target?** Features are
   separate objects in `Assets/XR/Settings/OpenXR Package Settings.asset`, one per
   platform, each with `m_enabled`. `MetaOpenXR-OpenXRLifeCycle` must be on, or the
   native func table keeps `instanceProcAddr == null`, every capability probe
   reports "runtime doesn't support X", and that verdict is cached for the whole
   process. Any feature whose package is installed but disabled can also fail
   build validation outright.
4. **Is the diagnosis itself wrong?** Sample the same objects the SDK samples:
   `FindAnyObjectByType<AROcclusionManager>(FindObjectsInactive.Include)`. A plain
   `FindFirstObjectByType` can pick an inactive manager and report `subsystem ==
   null` while depth frames are arriving normally.

## Editing OpenXR feature flags without the editor UI

In batch mode the settings file is a list of MonoBehaviour blocks, one per feature
per platform (`m_Name: X Android`, `m_enabled`, `featureIdInternal`). Locate the
block by `featureIdInternal` and flip the nearest preceding `m_enabled`. Use
`UnityEditor.XR.OpenXR.Features.FeatureHelpers.RefreshFeatures(BuildTargetGroup.Android)`
to materialise missing entries. Feature classes guarded by version defines expose no
typed accessor from a build script — edit the YAML and let the build validate it.

## Scan / AR pipeline rules

- A `FinalizeScan` that waits minutes is usually running an optional post-process
  (UV unwrap + texture bake) that also hard-requires its module. When the product
  does not show textures, bypass finalize: read geometry first, stop the scanner
  second.
- Stopping the scanner releases GPU volumes; any readback started afterwards
  returns zero. Force a fresh extraction, read, then stop.
- The SDK may render the live mesh in a vertex-colour mode that reads as coloured
  blobs. Switch it to a null render mode and draw your own presentation.
- A world-space UI canvas is occluded by scene geometry. Put it on its own layer
  and render it through a URP overlay camera that clears depth and is added to the
  base camera stack; UI then always draws on top of mesh and passthrough.
- Per-element backdrop contrast: downsample the passthrough frame once per second,
  project each panel's world corners to viewport space, and score only that
  rectangle. One bright corner must not darken the whole interface.

## Log collection

- PowerShell redirection produces UTF-16; run `iconv -f UTF-16LE -t UTF-8` before
  `grep`, otherwise every search returns zero matches on a file that looks fine.
- In-app: one `[TAG] area | key=value` line per event,
  `Application.SetStackTraceLogType(Log, None)` so a line does not drag 30 stack
  frames, and mirror lines to a file under `persistentDataPath` so a native abort
  still leaves the last breadcrumb.
- Capture: `adb logcat -c`, launch with
  `am start -n <pkg>/com.unity3d.player.UnityPlayerGameActivity`, reproduce,
  `adb logcat -d -v time > file`, then `adb pull` the breadcrumb file.
- High-signal greps: `DllNotFound`, `doesn't support`, `No active XR loader`,
  `Render mode:`, plus the app's own tag.

## Pitfalls

- **A green build proves nothing about runtime.** Validate the artifact itself:
  `aapt2 dump badging` for launchable activity and ABI, `unzip -l` for each expected
  `.so`.
- **Do not bisect by enabling features one at a time from a broken baseline.**
  Establish a running build first (loader on, plugins present), then add capability
  features; otherwise every variant shares the same invisible defect.
- **`SIGABRT` before any managed log is a setup problem, not app logic.** No app
  log lines at all means the crash happens during loader init — read the
  OpenXR/OVRPlugin lines immediately before the abort instead of hunting app code.
- **A capability check that fails once stays failed.** Restarting the AR session
  does not clear it; the feature must be enabled before the instance is created.
