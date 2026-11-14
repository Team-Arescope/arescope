---
name: quest-openxr-diagnostics
description: Use when a Quest XR app builds but fails at runtime.
metadata:
  hermes:
    tags: [unity, quest, openxr, android, logcat, diagnostics]
  version: 1.0.0
  author: hermes-curator
  license: MIT
---

# Quest OpenXR diagnostics

Green Android build and a working headset app are different claims. This skill is the triage order for the gap: install, capture, read the ordered signals, fix the earliest broken layer, re-verify the artifact.

## When to use
- APK installs but crashes within a couple of seconds of launch.
- App runs but never leaves the loading state.
- `XRSettings.isDeviceActive` false, or RoomScan/AR Foundation logs `No active XR loader`.
- Depth never arrives: `frames=0`, `depthAvail=False`, `occlusion=no-subsystem`.
- `DllNotFoundException` for a native plugin that the build log never mentioned.
- No scan progress, or geometry looks wrong in the headset while logs claim success.

## Procedure
1. **Confirm which build is on the device.** Add a boot line (`[RuntimeInitializeOnLoadMethod(BeforeSceneLoad)]`) printing `Application.version`, device model and OS. Any log without it is from an earlier APK and cannot be trusted.
2. **Capture.** `adb logcat -c`, launch with `adb shell am start -n <pkg>/com.unity3d.player.UnityPlayerGameActivity`, reproduce, then `adb logcat -d -v time --pid=$(adb shell pidof -s <pkg>)`. Pull the app's crash-surviving journal from `<persistentDataPath>` and `Player.log`. Logcat from PowerShell is UTF-16 — convert before grepping.
3. **Read the signals in layer order** — the first failure masks everything after it: native loading → XR loader → subsystem creation → depth frames → app logic. Mapping: `references/quest-log-signals.md`.
4. **Fix the earliest broken layer only**, rebuild, re-verify the artifact before installing.
5. **Verify the APK contents, not the build result.** `aapt2 dump badging` for `launchable-activity` and `native-code`, then `unzip -l app.apk | grep 'lib/arm64-v8a/'` and check every `DllImport` target is present.

## Always-on rules
- **A package native plugin may be silently dropped.** A `.so` that exists only in `Library/PackageCache` (e.g. `libUnityARFoundationMeta.so` from `com.unity.xr.meta-openxr`) is absent from `jniLibs`, `merged_native_libs` and the APK while the build stays green. Copy it to `Assets/Plugins/Android/arm64-v8a/` with a sidecar `.meta` (minimal `fileFormatVersion` + `guid` pair suffices); plugins under `Assets/Plugins/Android` do get packaged. Verify by listing the APK, never by reading the plugin's import settings.
- **Trim the log before reasoning.** Silence stack traces for `Log`/`Warning` (`Application.SetStackTraceLogType`) and emit one `[TAG] area | key=value` line per event; a single `Debug.Log` otherwise drags ~30 stack lines.
- **Mirror the journal to disk.** Append each line under `persistentDataPath` and flush — a SIGABRT leaves logcat truncated but the file survives. Logging must never throw; wrap the write.
- **Look up objects the way the SDK does** (`FindAnyObjectByType<T>(FindObjectsInactive.Include)`), or a diagnostic reports `null` while the subsystem is actually running.
- **Read GPU buffers before stopping the producer.** Stop/release frees the volumes and the readback returns zero vertices.
- **Name the layer you fixed, and state what is still unverified on device.** Do not present a green build as a working app.

## Rebuild hygiene that blocks triage
- A stale editor process holding `Temp/UnityLockfile` makes the next batch run exit in ~2 s with no useful log. Kill editor processes, delete the lock, rerun.
- A full disk presents as a crash inside a file-write stack trace (`No space left on device`), not a clean build error. Clean `Library/Bee`, `Library/Artifacts`, `Library/il2cppBuildCache`, `Temp`, `obj`, Gradle caches and old staging APKs first.
- A `.meta` GUID must be exactly 32 hex characters; a non-hex GUID makes import fail while the editor exits quietly.

## References
- `references/quest-log-signals.md` — log line → root cause → fix table for the Quest XR/depth stack, plus packaging checks.
- `references/hud-in-vr.md` — making a world-space HUD immune to scene geometry, preview-render pitfalls, per-panel contrast.
