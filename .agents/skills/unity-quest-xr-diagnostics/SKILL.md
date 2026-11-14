---
name: unity-quest-xr-diagnostics
description: Diagnose Unity Quest XR that launches but never scans.
version: 1.0.0
author: hermes-curator
license: MIT
metadata:
  hermes:
    tags: [unity, quest, openxr, arfoundation, logcat, android]
---

# Unity Quest XR startup diagnostics

## When to Use

A Quest build installs and launches but XR is inactive, the scanner never starts, depth stays empty, or the app hangs on a loading screen. Also use when a newly enabled XR package feature crashes the app at startup. Assumes the APK already builds; for build-farm mechanics see the project's own build skill.

## Procedure

1. **Capture logs so they are readable.**
   - Clear, launch, reproduce, dump: `adb logcat -c` → `adb shell am start -n <pkg>/com.unity3d.player.UnityPlayerGameActivity` → `adb logcat -d -v time > log.txt`, plus `adb logcat -b crash -d`, `adb pull <persistentDataPath>/<app>.log`.
   - Windows PowerShell writes `logcat > file` as **UTF-16LE**; `grep` then matches nothing and the file looks like garbage. Convert first: `iconv -f UTF-16LE -t UTF-8 log.txt > log-utf8.txt`.
   - Do not capture screenshots with `adb exec-out screencap -p > file` in PowerShell — redirection corrupts the PNG. Use `adb shell screencap -p /sdcard/x.png` then `adb pull`.
2. **Classify the failure by where the log stops.**
   - Dies ~1-2 s in, no managed log lines at all → native abort in XR init (`libc++abi: terminating`, `SIGABRT`, backtrace inside `libil2cpp`/`libUnityOpenXR`). No app-level logging can help here.
   - Runs, but `XRSettings.isDeviceActive` stays false → loader never started or a subsystem failed to construct.
   - XR active, subsystems alive, but data empty (progress 0 %, one stray point, empty minimap) → the subsystem exists but receives no frames; check the capability gate below.
3. **Check the gates in this order.** Paths, feature ids and log signatures are in `references/openxr-settings.md`.
   - XR loader actually auto-starts for the Android target.
   - Every required native plugin is inside the APK (a plugin in `Library/PackageCache` can be silently dropped).
   - The XR package's lifecycle feature is enabled — without it the native function table has a null `instanceProcAddr`, every capability probe fails, and the failure is cached for the process.
   - The subsystem features (session, occlusion) are enabled for Android.
   - The runtime advertises the extension the feature needs.
4. **Verify the artifact, not the build result.** `aapt dump badging` for `launchable-activity` + `native-code`; `unzip -l app.apk | grep lib/arm64-v8a/` for each `.so`. Unity prints `Succeeded` with missing libraries.
5. **Rebuild and re-check the same signature.** A fix counts only when the log line that documented the failure disappears.

## Pitfalls

- **Stacked defects mask each other.** A loader that never starts hides a missing `.so`; a missing `.so` hides a disabled lifecycle feature. Each layer becomes visible only after the one below is fixed. Never conclude "feature X causes the crash" from one enable/disable comparison without confirming the layer beneath was healthy in both builds.
- **A diagnostics probe must search exactly like the production code.** `AROcclusionManager.subsystem` logged as null while the SDK reported `sub=MetaOpenXROcclusionSubsystem, running=True` with 1100 frames: the probe used `FindAnyObjectByType<T>()` (active objects only) while the scanner used `FindObjectsInactive.Include`. Mirror the lookup, or the log invents a failure that sends the next session chasing a fixed subsystem.
- **Capability verdicts are cached per process.** After a failed probe the subsystem is never created again in that session; restarting `ARSession` does not clear it. Fix the root cause and rebuild.
- **`This OpenXR runtime doesn't support <extension>` can be a false negative.** Cross-check the runtime's own enumeration in the same log (e.g. `OVRPlugin: Name=XR_META_environment_depth SpecVersion=2`) and Unity's feature list a moment later. If the runtime advertises it, the probe ran too early, not the headset lacking support.
- **OpenXR settings are per-build-target YAML blocks.** Hand-editing works, but each feature has its own block with `m_enabled`, and features may not exist in the asset until refreshed. Enable through the editor API (see the reference) and re-check the asset afterwards.
- **A package dependency can become a build-blocking validation rule.** Adding a package may require an extra OpenXR feature (e.g. Composition Layers Support) before the build passes validation; the error names the feature.
- **Design logging for the next failure, not this one.** One tag, `area | key=value` lines, `Application.SetStackTraceLogType(LogType.Log/Warning, StackTraceLogType.None)` (one Unity log otherwise drags ~30 stack lines), a 1 Hz heartbeat while the subsystem is active, and a size-capped append-only file in `persistentDataPath` so the last line survives a native abort.

## Related files

- `references/openxr-settings.md` — settings paths, feature ids, enable-features editor method, symptom-to-cause table.
- `scripts/triage-logcat.sh` — converts a captured log and prints the decisive lines.

Related: getting XR and depth alive is this skill's scope. For what to draw once they are alive — a HUD that scan geometry cannot occlude, and texture-bake triage — see the sibling `quest-xr-diagnostics` skill.
