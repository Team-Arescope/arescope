---
name: unity-android-headless-builds
description: "Build Unity Android APKs headlessly on Linux."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [unity, android, quest, xr, build, ci, headless]
---

# Unity Android APK builds in headless Linux

## When to Use

Use when a Unity project must be compiled into an Android APK on a Linux machine
without a human at the keyboard: CI runners, cloud sandboxes, a remote desktop
box. Quest/XR projects need extra care (Meta XR packages, OpenXR validation).

Read `references/unity-linux-environment.md` for exact URLs, module extraction
and the Meta XR patch recipe. `scripts/patch_meta_sdk_linux.py` applies the
package-cache patches automatically.

## Procedure

1. **Fix the version first.** The editor version comes from the project's
   `ProjectSettings/ProjectVersion.txt`; the Unity release API lists the exact
   Linux tarball and the matching module set. Never install "latest" — a
   different editor version opens an upgrade dialog that blocks headless runs.

2. **Install the editor with the Android module in one shot.**
   Unity Hub's headless CLI installs editor + modules from signed archives and
   writes the module manifest that the editor later reads:
   `unityhub --headless install --version <v> --changeset <hash> -m android --cm`.
   Verify with `--headless editors -i` and confirm the AndroidPlayer folder
   plus `modules.json`.

3. **Install the Linux shared libraries the editor links against.** Unity's
   Linux editor expects `libembree.so.2`; Debian 13 ships `libembree4-4`.
   Without it the editor dies instantly with a loader error, not a Unity error.

4. **Activate the license through the Hub GUI, once.** Unity Personal is free
   but must be activated by a signed-in Hub session; the browser OAuth
   redirect returns via a `unityhub://` deep link, so register a scheme handler
   before signing in, or the redirect fails with "Failed to open URI" and no
   license lands.

5. **Keep the project tree on the largest writable volume.** Editor +
   Android module ≈ 15 GiB, and the project `Library/` grows to several GiB
   during import and IL2CPP. Put the editor on the persistent volume and the
   project on the root/system volume when the persistent one is small.

6. **Import once, headless, before building.**
   `Unity -batchmode -nographics -quit -projectPath <dir> -logFile <log>`.
   Read the log for `error CS` — a clean exit line alone does not mean the
   import succeeded. For a minimal hand-built project manifest, add the Unity
   built-in `com.unity.modules.*` dependencies named by forwarded-type errors
   (for example animation, androidjni, assetbundle, physics2d and audio); the
   editor being installed does not automatically enable those project modules.

7. **Build via a small editor script** with `-executeMethod`, not by clicking:
   the script switches the active build target, sets the application id,
   architecture and scripting backend, then calls `BuildPipeline.BuildPlayer`.
   Always log `report.summary.result`, the output path, and every error/warning
   message from `report.steps` — the build log alone hides the real reason.

8. **Re-read the build log for the actual failure.** Unity prints the
   summary line first and the cause afterwards; grep for the step messages
   rather than stopping at "Result: Failure".

9. **Verify the artifact, not the exit code.** Check that the APK file exists,
   is non-trivial in size, and inspect it (`unzip -l`, `aapt dump badging`)
   for the package id, min/target SDK and ABIs. Only then report success.
   Move it OFF the machine before publishing: a cloud sandbox does not share
   the host filesystem. InstaBox serves raw bytes at
   `GET https://api.instabox.sh/v1/machines/<id>/files/content?path=<url-encoded path>`
   with the `X-API-Key` header; download it to the host, publish with
   `publish-shared`, then re-download the public URL and compare SHA-256 with
   the file you pulled.

10. **Verify the APK can actually start.** `aapt dump badging` must report a
    `launchable-activity`. A build can report `Succeeded` with zero errors and
    still ship a package that no launcher can open — usually because a custom
    `Assets/Plugins/Android/AndroidManifest.xml` replaced Unity's generated
    manifest and omitted the activity, its MAIN/LAUNCHER intent filter, the
    Oculus VR category, or the theme. A custom manifest is a full
    replacement, so it must declare all of those itself. For
    `UnityPlayerGameActivity`, inspect the final merged manifest's resolved
    activity theme and confirm it derives from AppCompat: a launcher entry
    alone can pass `aapt` while Android crashes in `onCreate` for a non-AppCompat
    theme. Verify startup on the device before claiming the app launches.

11. **Confirm packaging-side errors separately from compile errors.** The
    `BuildReport` summary counts errors and warnings even when the result is
    `Succeeded`; read them and grep the log for the offending postprocessor
    (for example a manifest patcher that failed). For a device crash, inspect
    the supplied logcat's encoding first (Windows redirection may produce
    UTF-16), identify the app's process/PID, and read its full fatal exception
    and caused-by chain; do not mistake OpenXR logs from the system shell for
    evidence that the app's own XR session started.

## Pitfalls

- **A stale editor silently swallows the next batch run.** When `-executeMethod`
  returns within seconds, the log ends at `SDL leaked 2 allocations`, and the
  method's own output never appears, an orphaned editor still holds the project
  lock. Kill the `[U]nity` processes, delete `Temp/UnityLockfile`, then re-run.
  Diagnose this before touching the method, the code or the build script.
- **Every hand-written `.meta` needs a real 32-hex GUID.** A GUID containing
  non-hex characters makes the editor drop the import and exit before reaching
  `-executeMethod`, with no `error CS` in the log — the failure looks like a
  silent no-op rather than an asset problem.
- **Enable OpenXR features in small groups and launch the APK after each.**
  A feature set the runtime rejects aborts inside `xrCreateInstance` about a
  second into launch (`libc++abi: terminating`, SIGABRT in `UnityMain`) before
  any managed line runs, so app-side logging cannot see it and the crash reads
  as a mysterious startup death. Bisect the feature list instead of adding
  diagnostics to the game.
- **Meta XR packages do not compile on a headless Linux editor.** `OVRManagerEditor.cs`
  excludes Linux from a platform `#if` block, so `manager` is undefined;
  `MetaXRSimulator/Installer.cs` has no Linux branch for the download path.
  Patch the package cache after every package re-resolve (the cache is wiped
  on version change). A patch that is not scripted silently disappears on the
  next resolve.
- **Unity 6.2 stores Android platform settings in a build profile.** Writing
  `PlayerSettings.Android.targetArchitectures` or `ProjectSettings.asset` can
  have no effect: the OpenXR validation rule then rejects the build with
  "Only arm64 or x86_x64 is supported on Android with OpenXR". Write through
  `EditorUserBuildSettings.SetPlatformSettings` as well, and inspect the
  profile asset that actually holds the settings.
- **Run the build without a desktop session alive.** A running Unity Hub plus
  a browser plus the Unity build share 8 GiB, and the kernel OOM-kills
  `clang++` mid-IL2CPP with the unhelpful "Killed" message. Stop the GUI
  processes before the build and prefer the IL2CPP *Master* configuration;
  *Release* optimisation is the memory hog.
- **Do not hand-extract the editor from a raw tarball and expect it to work.**
  The embedded package tarballs get truncated, and the editor then fails with
  "not a valid package tarball". Use the Hub installer, or verify the archive
  checksum before extracting.
- **Deleting editor payloads to free disk is a trap.** Removing parts of
  `Editor/Data/Resources` (project templates, package manager assets) breaks
  the next import. Delete only whole optional modules (WebGL, Linux
  standalone, documentation) and re-verify with an import run.
- **A green Unity exit code is not a green build.** "Exiting batchmode
  successfully" only means the editor quit; the build result lives in the
  `BuildReport` and in the step messages.
- **The `unityhub://` deep link needs a registered handler** before any
  browser sign-in, otherwise the OAuth handoff dies and the next build fails
  with entitlement errors that look like a licensing problem.
- **A stalled IL2CPP stage is usually Burst, not the linker.** When the build
  sits in `IL2CPP_CodeGen` for tens of minutes with the log frozen at one
  `[BUSY]` line, look for `bcl.exe` (Burst compiler) children at ~0% CPU.
  Removing `com.unity.burst` from `Packages/manifest.json` and re-importing
  unblocks the stage on an 8 GiB builder. Confirm a stall by comparing CPU
  time of the *worker* processes, not the parent editor.
- **Set linear color space for Meta OpenXR** (`PlayerSettings.colorSpace = ColorSpace.Linear`) before building; the Oculus utilities build validator rejects gamma color space.
- **Review third-party Unity setup wizards before invoking them.** Split scene, XR, manifest and native-build steps where possible; an all-in-one preset can enable cleartext HTTP or start native code compilation as a side effect. Pin package versions and use scripted, reversible compatibility edits when an editor minor version lacks APIs used by an upstream package.
- **OpenXR validates more than architecture.** Besides the ARM64 rule, the
  "Composition Layers Support feature is required" rule fires when the
  project uses the Composition Layers package with the feature disabled.
  Both rules live in `OpenXRProjectValidation.cs` and must be patched
  together with the Meta XR ones.
- **The editor's Android module can live on the root volume.** When the
  persistent volume is too small, move `Editor/Data/PlaybackEngines/AndroidPlayer`
  to the root volume and leave a symlink in its place; the editor resolves
  the module through that path.
- **Budget RAM across Unity and Gradle, not per process.** If kernel logs confirm the Gradle daemon was OOM-killed, reduce the isolated project's Gradle JVM heap and worker concurrency using its `gradleTemplate.properties`, then verify the effective generated invocation: Unity may also pass JVM settings on the command line. Inspect and stop only confirmed orphan compiler daemons before retrying; do not delete project data to compensate.
- **Native helper libraries can be cross-compiled from the package's own
  sources.** When a package needs an ARM64 `.so` it does not ship prebuilt,
  build it with the NDK clang inside the Android module against the package's
  C++ sources, then confirm the library is inside the APK under
  `lib/arm64-v8a/` and that it loads on the device.
- **Preserve each requested APK before cleanup or another build.** Copy it to a distinct versioned server/shared-host path, verify its downloaded SHA-256 against the source, then remove only identified regenerable build caches; never overwrite an existing publication without checking it or explicit authorization. `Library/Bee`, `Library/Artifacts`, Burst and shader caches and Gradle caches are regenerable, but package-cache compatibility patches may need reapplication. Keep source, scene, project settings and the verified APK; re-verify imports after cleanup. Explain that clearing caches slows the next build, and measure cold and warm timings separately rather than presenting a single cold observation as an average.
 - **Clean caches BEFORE launching the next build, not only after the last one.**
 One IL2CPP run refills `Library/Bee` to several gigabytes: on a fixed 20 GiB
 volume the space freed after one build is gone again after the next, and the
 following build dies mid-IL2CPP with a disk or Gradle failure rather than a
 compile error. Check `df -h` immediately before every launch and delete
 `Library/Bee`, `Artifacts`, `BurstCache`, `ShaderCache`, `Temp` and `obj`.
 - **Check for `error CS` at the script-compilation stage, not at the end.**
 Managed compile errors surface in the first few minutes; the remaining 20–30
 are IL2CPP and Gradle. Grepping the log early turns a doomed half-hour wait
 into a one-line fix plus a fresh run.

## Choosing the build machine (sandbox capacity limits)

Unity's footprint makes ordinary cloud sandboxes marginal. Verify capacity
before starting, not after an hour of downloads:

- **E2B** — the sandbox API caps `min_free_disk_mb` at **25 600 MiB**, so a
  template cannot promise 40–50 GiB. Resources are set only through the
  template; `POST /sandboxes` silently ignores `cpuCount`/`memoryMB`, and a
  default sandbox comes back with 2 vCPU / 512 MiB. Template names must be
  valid IDs (no dots, no version strings).
- **Daytona** — pick `daytona-large` (4 vCPU / 8 GiB) and set `disk` explicitly
  in `Resources(disk=N)`; the disk is sized independently of the snapshot.
- **InstaBox free plan** — the persistent `/data` volume is fixed at 20 GiB and
  cannot be grown, so the editor must live there and the project tree on the
  root volume.

Rule of thumb: editor + Android module ≈ 15 GiB, project `Library/` 2–7 GiB,
IL2CPP output several GiB. Anything under ~40 GiB total needs the two-volume
layout.

## Memory limits

On an 8 GiB builder, IL2CPP with the *Release* configuration gets its
`clang++` processes OOM-killed; the log shows only `Killed`. Use the *Master*
configuration and stop any GUI processes (Hub, browser) before building.

## Supporting files

- `references/unity-linux-environment.md` — editor/module URLs, extraction
  steps, Meta XR patch details, sizing numbers.
- `references/quest-openxr-features.md` — where OpenXR feature toggles live,
  how to enable them scripted or in the asset YAML, feature ids, and the depth
  provider requirements for AR Foundation scanners.
- `references/quest-device-diagnostics.md` — adb/logcat capture, the UTF-16
  trap, permission truth from the APK, crash classes, and in-app logging that
  survives a native abort.
- `references/quest-gpu-mesh-readback.md` — reading an SDK's GPU vertex/index
  buffers on Quest: bounded readbacks, counter clamping, triangle sanitation,
  index slicing, and placing baked geometry after a relocalisation.
- `scripts/patch_meta_sdk_linux.py` — idempotent package-cache patcher.
