---
name: unity-android-headless-build
description: "Build a Unity Android/Quest APK headless in a sandbox."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [unity, android, quest, apk, headless, build]
---

# Headless Unity Android build on a small Linux sandbox

Verified on InstaBox (4 vCPU, 8 GiB RAM, 20 GiB /data) with Unity 6000.2.9f1 for Meta Quest 3S.

## When to Use

- Building an Android or Meta Quest APK from a Unity project on InstaBox, E2B or Daytona.
- A Unity Android build fails on Linux, hangs in IL2CPP code generation, or dies with a `MonoManager` null error.
- Disk or RAM on the sandbox runs out during a player build.

## Where the pieces live

- Quest project: `/root/Developer/arescope-quest` (fork of OpenQuestCapture + an experimental live sender).
- Editor installed on InstaBox under `/data/home/Unity/Hub/Editor/<version>`.
- Machine helper: `python3 ~/.hermes/skills/devops/instabox/scripts/instabox.py exec '<cmd>' --timeout N`.

## Steps that made the build work

1. Install the editor and the Android module with the **Hub headless CLI**, never by hand-extracting the tarball: a manual extract produced invalid in-package `.tgz` files and a broken package cache.
   `unityhub --headless install --version 6000.2.9f1 --changeset e0c4e791ab71 -m android --cm`
2. Keep the project **and** the editor's Android module on the system disk (`/opt`), with `/data` for downloads. Move the module and symlink it back: `PlaybackEngines/AndroidPlayer -> /opt/unity-android`. A 20 GiB `/data` cannot hold the editor, the module and the build output at once.
3. Remove **Burst** from `Packages/manifest.json`. Burst's codegen of the Meta XR sample stack stalls IL2CPP code generation for hours on 4 cores.
4. Apply the Linux-only patches to the package cache with `scripts/patch_meta_sdk_linux.py <project>` **after every package re-resolve** (the cache is rewritten):
   - `OVRManagerEditor.cs`: add `UNITY_EDITOR_LINUX` to the platform guard.
   - `MetaXRSimulator/Installer.cs`: add a Linux branch for the installer path.
   - `OVRGradleGeneration.cs`: the ARM64 check cannot see the build-profile value in Unity 6.2.
   - `OpenXRProjectValidation.cs`: the architecture and composition-layers rules read the classic settings that Unity 6.2 no longer uses.
5. Build with `EditorUserBuildSettings.SwitchActiveBuildTarget(Android)`, `SetPlatformSettings("Android","AndroidTargetArchitectures","ARM64")`, `SetPlatformSettings("Android","ScriptingBackend","IL2CPP")` and `SetIl2CppCompilerConfiguration(Master)` (Release was OOM-killed).
6. Drive it with `-batchmode -nographics -quit -executeMethod ArescopeAndroidBuild.Build -logFile ...`.

## Traps

- **Never move or delete files under the project while Unity is running** — it dies with `GetManagerFromContext: pointer to object of manager 'MonoManager' is NULL`.
- `clang++` gets OOM-killed at ~2.5 GiB RSS; add a swap file if the build reaches native compilation.
- The Unity licence must be active in the same machine profile (`~/.config/unity3d/Unity/licenses/`); without it the target reads as unsupported and the build fails with a NullReferenceException in the analytics extension.
- License activation needs an interactive Unity Hub sign-in; the `unityhub://` deep link fails unless a handler is registered (`xdg-mime default <desktop-file> x-scheme-handler/unityhub`).
- E2B is not usable for this: a plain sandbox has 22 GiB and 2 vCPU, and the API caps `min_free_disk_mb` at 25600.

## Verification

An APK is only real when the file exists under the project's `Build/` directory and its size is non-trivial; the log line `Build Finished, Result: Succeeded` alone is not enough.
