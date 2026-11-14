# Quest XR / depth log signals

Read top-down: the first failing layer masks every later symptom.

| Log line | Root cause | Fix |
|---|---|---|
| `E/libc++abi: terminating` then `SIGABRT` in `UnityMain`, 1–2 s after `Start proc` | Native abort during `xrCreateInstance`; no managed code ran | Check the native plugin set and the OpenXR feature list first; do not bisect app logic |
| `DllNotFoundException: Unable to load DLL 'libUnityARFoundationMeta'` | The bridge native library is not in the APK | Copy the `.so` from the package to `Assets/Plugins/Android/arm64-v8a/`, verify with `unzip -l` |
| `No active XR loader`, `isDeviceActive == false`, endless loading | XR Plug-in Management does not auto-start | In `Assets/XR/XRGeneralSettingsPerBuildTarget.asset` set `m_AutomaticLoading: 1`, `m_AutomaticRunning: 1` for Android |
| `[OpenXR Meta] [XrFuncTable] … instanceProcAddr is null`; `runtime doesn't support XR_META_environment_depth` while the runtime advertises it | The feature that initialises the native function table is disabled | Enable `MetaOpenXR-OpenXRLifeCycle` for Android |
| `DepthCapture: frames=0, depthAvail=False, sub=null` | Occlusion subsystem never created because an earlier layer failed | Fix the layer above first; it will not appear while the func table is null |
| `DepthCapture: frames=NNN, depthAvail=True, sub=MetaOpenXROcclusionSubsystem` | Depth is flowing | Move on to scan/mesh logic |
| `mesh readback empty` | Buffers read after the producer released them | Prepare the extractor, read, then stop |
| `Texture refinement failed: Mesh readback returned no vertices` | Finalize ran on an empty mesh | Same as above; also ensure finalize is not pressed twice |
| `NullReferenceException at AROcclusionManager.DestroyTextures()` on disable | Occlusion textures were never created | Symptom of the depth failures above |
| `Render mode: Vertex` during scan | The SDK draws its own vertex-coloured mesh | Switch the scanner to `ScanRenderMode.None` and present your own visualisation |

## Packaging verification

```sh
/opt/unity-android/SDK/build-tools/36.0.0/aapt2 dump badging Build/QuestRoomScan.apk | grep -E "^package:|launchable-activity|native-code"
unzip -l Build/QuestRoomScan.apk | grep 'lib/arm64-v8a/'
```

Expected for a Meta-OpenXR build: `libUnityARFoundationMeta.so`, `libOVRPlugin.so`, `libopenxr_loader.so`, `libxatlas.so`, `libil2cpp.so`, `libunity.so`.

## Feature list sanity check

Enabled OpenXR features for Android must include the lifecycle feature plus the AR Foundation Meta features actually used (session, occlusion, and plane/mesh/anchor when needed), and `com.unity.openxr.feature.compositionlayers` whenever the Composition Layers package is present — otherwise project validation fails the build with `Composition Layers Support feature is required`.

A feature can be force-enabled by editing `Assets/XR/Settings/OpenXR Package Settings.asset` (`m_enabled: 0` → `1`) when its class is compiled out and unreachable from an editor script; build-time validation still runs, so re-verify the APK afterwards.
