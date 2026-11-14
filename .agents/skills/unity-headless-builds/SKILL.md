---
name: unity-headless-builds
description: "Build Unity Android/Quest APKs headlessly in a sandbox."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [unity, android, quest, build, ci, sandbox, headless]
---

# Unity headless builds (Android / Meta Quest)

Use when an APK must be produced from a Unity project on a remote Linux sandbox, or when a Unity project must be opened or compiled without a human at the keyboard.

## Standing rules

- **Do not stop at the first blocker.** A failed provider, a failed install or a lost licence is a reason to switch path (other sandbox, other editor version, GUI mode), not a reason to hand the task back. Only report partial completion when every available path has actually been tried and named.
- **Never claim a build succeeded without the artifact.** Verify the APK file exists, is non-trivial in size, and unpack it (`unzip -l`) to confirm a real Android package. Report the exact byte size and path.
- **Editor version must equal the project version.** Read `ProjectSettings/ProjectVersion.txt` and install exactly that version plus its changeset. A newer editor triggers a project-upgrade prompt that cannot be answered in batch mode.
- **Prefer the vendor installer over hand-extracting archives.** Manual tar/xar unpacking of Unity editor and module archives produced corrupt built-in package `.tgz` files (`not a valid package tarball`). Install through the vendor CLI so packages stay intact.
- **Work on the persistent disk.** `/tmp` is a small tmpfs and fills mid-download; stage large downloads and editor installs on the persistent volume and delete intermediates as you go.
- **Never delete the vendor editor once the licence is bound to it.** Deleting and reinstalling the editor invalidates the Unity session and forces a fresh interactive sign-in. Fix problems in place instead.
- **Keep the user's credentials out of the app and the repo.** Activation happens on the machine; nothing is committed, and secrets are never printed.

## Procedure

1. **Read the project version and dependencies.** `ProjectSettings/ProjectVersion.txt` (editor + changeset), `Packages/manifest.json` (Unity packages, Meta XR SDK versions), `ProjectSettings/ProjectSettings.asset` (scripting backend, target architecture, package id).
2. **Provision a sandbox with enough disk.** Unity editor + Android module + build cache needs roughly 25-40 GiB free. Check the real free space of each provider before installing; see `references/sandbox-provisioning.md`.
3. **Install the editor and the Android module headlessly** with the vendor CLI, e.g. Unity Hub: `--headless install --version <v> --changeset <c> -m android --cm`, and `--headless install-modules --version <v> -m android --cm` for an existing editor. Verify the module directory and its `modules.asset` exist afterwards.
4. **Bind the licence before building.** A headless editor with no entitlement fails the build with `build target was unsupported` and licensing 404s. Sign in on the machine's desktop (Hub or `unity auth login`) and confirm a licence file exists under `~/.config/unity3d/Unity/licenses/`.
5. **Compile the project once in batch mode** (`-batchmode -nographics -quit -projectPath <p> -logFile <log>`) and read the log for `error CS` and `Failed to resolve packages` before attempting a player build.
6. **Build the player** through a small `-executeMethod` editor script that sets package id, architecture, scripting backend and output path, then reports the build result. Never rely on the GUI for this step.
7. **Verify and deliver.** Locate the APK, check size and contents, and hand over the file.

## Pitfalls

- **Linux editor needs `libembree.so.2`.** Debian ships `libembree4.so.4`; symlink it, or the editor exits with `error while loading shared libraries` before doing anything.
- **Meta XR SDK editor code does not compile on Linux.** `OVRManagerEditor.cs` declares the manager only under `UNITY_EDITOR_WIN/OSX` guards, so the Linux editor reports `The name 'manager' does not exist`; the XR simulator installer has the same gap for `downloadedInstallerPath`. Patch the package cache for the Linux editor and keep the patch in the repo so it survives a cache refresh. See `references/quest-meta-xr.md`.
- **Downgrade the Meta XR SDK rather than upgrading Unity.** When the pinned Meta SDK fails to compile, move to a nearby SDK release that builds; mixing SDK and editor majors reintroduces the same errors.
- **Never delete `Data/Resources/PackageManager/Editor`** to save space. It holds the built-in package manifest; removing it makes every project fail with `manifest.json not found. No packages loaded`. Safe space reclamation targets are Documentation, Tools, DotNetSdk, WebGL/Linux standalone modules and `ProjectTemplates`.
- **Unity 6.x can hide platform settings behind build profiles.** When the profile has no Android settings, the target reads as unsupported even with the module installed. Probe `BuildPipeline.IsBuildTargetSupported` and `EditorUserBuildSettings.SwitchActiveBuildTarget` from a throwaway `-executeMethod` script instead of guessing.
- **A `-batchmode` build cannot show interactive dialogs.** Any dialog (project upgrade, licence, build profile) either times out or fails the build; resolve it beforehand via CLI, or run the editor in GUI mode on a desktop sandbox.
- **Separate import from build.** First run imports and compiles, the second builds. A single run often appears to fail while only compiling.
- **Depth on Quest needs a package, not a setting.** `AROcclusionManager` has no subsystem unless `com.unity.xr.meta-openxr` is installed, its AR Foundation Meta features are enabled, the XR loader is allowed to auto-start, and the package's native bridge actually ships in the APK. Four independent failures produce the same log line (`frames=0, depthAvail=False, sub=null`) and each one hides the next, so fix and verify them one at a time. `sub=null` plus `frames=0` is the tell; a green build proves nothing. Recipe, feature ids, batchmode enabling script and the symptom→cause table: `references/quest-openxr-depth.md`.
- **Package native plugins are not packaged automatically.** A `DllNotFoundException` for `libUnityARFoundationMeta` (or any SDK `.so`) means the build copied the subsystems manifest but skipped the library. Copy the `.so` into `Assets/Plugins/Android/arm64-v8a/` with a minimal `.meta`, then confirm inside the APK with `unzip -l` — the Gradle staging tree and a green build are both misleading.
- **The app can run "flat" with no error.** When `XRGeneralSettingsPerBuildTarget.asset` has `m_AutomaticLoading: 0` / `m_AutomaticRunning: 0` the loader never starts: endless loading screen, `No active XR loader`, `xr=inactive`. Package upgrades reset these flags, so re-check them after every dependency change.
- **A stale Unity process blocks every later headless run.** `Temp/UnityLockfile` left by a previous editor makes `-batchmode -executeMethod` exit after `SDL leaked 2 allocations` with no error and no method execution. Kill leftover `Unity` PIDs and delete the lock before each run.
- **A full disk looks like a random build failure.** At 100 % usage the editor dies while writing its profiler trace and never prints the build-result line. Check `df -h` first; `Library/Bee`, `Library/Artifacts` and `/data/home/.gradle` are the safe ~10 GiB to reclaim.
- **`FinalizeScanAsync` in the RoomScan SDK requires the texture module and waits up to five minutes** for the atlas bake even when the component is disabled. If the app does not show textures, stop the scanner and read the mesh from the GPU buffers instead — seconds instead of minutes.
- **A new dependency can fail the build through OpenXR validation.** `meta-openxr` pulls `com.unity.xr.compositionlayers`, after which the preprocess step aborts with "The Composition Layers Support feature is required". Enable `com.unity.openxr.feature.compositionlayers`; if its class is compiled out and no feature asset appears, flip `m_enabled` to `1` for its block in `Assets/XR/Settings/OpenXR Package Settings.asset`.
- **Set `camera.aspect` before rendering to a RenderTexture.** A world-space HUD rendered with a stale aspect collapses its rows and overlaps its panels; the artifact looks like a layout regression but never appears in the headset.

## Supporting files

- `references/quest-openxr-depth.md` - Quest depth via AR Foundation: the four layers that must be right (loader auto-start, packaged native bridge, lifecycle feature, depth features), the batchmode feature-enabling script, the Composition Layers validation blocker, permission names, finalize bypass, device-log capture, always-on-top HUD and per-panel contrast.
