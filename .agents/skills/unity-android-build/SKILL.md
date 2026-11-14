---
name: unity-android-build
description: "Build a Quest APK from Unity on a cloud sandbox."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [unity, android, quest, build, sandbox, apk]
    related_skills: [instabox, daytona-sandboxes, background-job-supervision]
---

# Unity Android build on a cloud Linux sandbox

## When to Use

A Unity project must be compiled into an Android/Quest APK and the machine doing it is a remote Linux sandbox (InstaBox, Daytona, E2B) rather than the local workstation.

## Always-on rules

- Authenticate Unity Personal through the supported Unity Hub sign-in; ask the user to enter credentials in the remote UI. On Linux, if OAuth reaches `unityhub://` but the OS cannot open it, register the Hub executable as the XDG scheme handler, then initiate a fresh Hub login. Never capture or replay the OAuth authorization code. Check entitlement/target support again after authentication: Hub sign-in alone does not prove Android build entitlement.
- Compile the requested modified source revision, not an upstream APK; use an independent Android package ID if the user wants the original app preserved.
- Verify `Build Finished, Result: Success`, the APK's actual existence and byte size, package ID, ARM64 ABI, signing via `apksigner verify`, and source/destination SHA-256 after transfer. Treat compiler success, valid signature, and a working Quest app as separate claims; only a real headset run establishes device functionality.
- Diagnose apparent hangs with recent log and artifact timestamps, process CPU time, and OOM logs, not process existence or the last logged task number alone. Never claim active progress from an unchanged log.
- Preserve and disclose all non-upstream package versions and build patches. Do not disable OpenXR validation merely to obtain an APK; correct configuration and verify required runtime features on the device.

- **The editor version must equal the version pinned in the project.** `ProjectSettings/ProjectVersion.txt` holds version + changeset. A different editor prompts a GUI upgrade dialog on first open, which blocks a batch run and can silently change package resolution. Fetch the exact editor tarball from Unity's public release API instead of guessing a URL:

```python
requests.get("https://services.api.unity.com/unity/editor/release/v1/releases?version=<v>&limit=1")
```

The `downloads` list carries the Linux editor tarball plus Android module, OpenJDK and SDK/NDK URLs with byte sizes. Prefer Unity Hub's Linux installation for Android modules. Unity release metadata can offer a Mac `.pkg` for the Linux editor; its xar/gzip payload can be extracted with 7z and bsdtar, but extraction alone does not validate SDK layout or build compatibility.

- **Budget disk before installing.** Include temporary downloads, extraction, package cache, IL2CPP/Gradle intermediates and the APK, not just installed editor size. Inspect each filesystem with `df -h` and actual directories with `du -sh`; place build intermediates on a volume with enough headroom. Do not remove editor Tools, SDKs, package-manager components or user-installed modules as an unverified space-saving shortcut: imports and builds may depend on them. Before deleting any existing component, inspect ownership and ask when its scope is not clearly authorized.

- **Stage the project on a path the build user can write.** `Library/`, `Temp/` and `Logs/` are created next to the project; a root-owned directory fails mid-import. Create the target with `sudo -n mkdir -p` and `chown` it to the guest user. Exclude `Library/`, `Temp/`, `Logs/`, `obj/` from the upload tarball — they are regenerated and large. Verify the upload by comparing the SHA-256 the file API returns against the local tarball.

- **Personal licenses still need activation.** Unity Personal is free but is activated through a Hub sign-in flow; manual `.alf` activation is no longer supported for Personal. Success marker: `~/.config/unity3d/Unity/licenses/UnityEntitlementLicense.xml` exists.

- **Never claim an APK before the file exists.** A finished import step is not a build. Confirm the artifact on disk (size, manifest read) and an install attempt before reporting success.

- **A library shipped inside a package is not automatically packaged into the APK.** Plugins under `Library/PackageCache/<pkg>/Runtime/Plugins/android/arm64/` can be ignored by the player build even with Android enabled in their `.meta`; they never reach `jniLibs/` or `merged_native_libs/`. The device then fails at runtime with `DllNotFoundException: Unable to load DLL '<name>'`. Fix: copy the `.so` into `Assets/Plugins/Android/arm64-v8a/` beside a minimal `.meta` (`fileFormatVersion: 2` plus a fresh `guid:`), rebuild, and confirm the file is inside the APK: `unzip -l Build/<app>.apk | grep "lib/arm64-v8a/"`.

- **Check the shipped binary before bisecting behaviour.** XR apps hide two defects behind each other: a loader that never initializes masks a missing native library, and the missing library looks exactly like whichever feature flag you just toggled. Always clear these three in order — XR loader actually initialized, every `DllImport` library present in the APK, feature flags last. Never report "feature X crashes the app" while an earlier check is unverified.

- **XR Plug-in Management can silently ship with automatic loading off.** In `Assets/XR/XRGeneralSettingsPerBuildTarget.asset` the target block needs `m_AutomaticLoading: 1`, `m_AutomaticRunning: 1`, `m_InitManagerOnStart: 1` and the loader asset listed in `m_Loaders`. With `0/0` the title launches flat: the app logs `No active XR loader`, `XRGeneralSettings:InitXRSDK()` creates no session, and the headset shows an endless loading view. Package upgrades to XR Management / AR Foundation can flip these flags.

## Procedure

1. **Provision the desktop.** Use the sandbox's XFCE display (`DISPLAY=:1`) and enlarge it with `xrandr --output VNC-0 --mode 1280x800`; the default 800x600 hides dialog buttons.
2. **Install the Hub** as a portable AppImage and launch with `--appimage-extract-and-run --no-sandbox` (needed when FUSE is absent). Headless Hub subcommands run from the same AppImage and still require a DISPLAY, because it is an Electron app:

```bash
DISPLAY=:1 ./UnityHub.AppImage --appimage-extract-and-run --no-sandbox -- --headless editors -r
```

3. **Register the OAuth callback scheme BEFORE signing in.** The sign-in redirect returns to the desktop app via `unityhub://`; with no handler the browser shows "Failed to open URI. Operation not supported" and the sign-in never completes. Write a `.desktop` file with `MimeType=x-scheme-handler/unityhub;` and `xdg-mime default` it.
4. **Complete sign-in with the user present** and accept the Personal license consent — its Agree button stays disabled until the license text is scrolled to the bottom.
5. **Install the editor and modules.** `install --version <v> --changeset <hash>`; then `install-modules --version <v> -m android --cm` — the `--version` flag is mandatory and `--cm` is what pulls the OpenJDK and SDK/NDK tools alongside the module.
6. **Import the project**, then run the build entry point (an editor script under `Assets/Editor/`) that sets the application id, ARM64 and IL2CPP, and calls `BuildPipeline.BuildPlayer`.
7. **Verify the artifact** before handing it over.

## Pitfalls

- **Headless import can crash in GUI-only editor tools.** `-batchmode -nographics` import died inside the built-in UV unwrapper (`Data/Tools/UnwrapCL`) with a segfault after assets had imported. Fall back to running the editor against the existing virtual display instead of `-nographics`, or drive the GUI over the shared desktop with the user present.
- **Editor binaries may need extra system libraries.** `ldd` on the editor can show a missing `libembree.so.2` while the distro ships only `libembree4.so.4`; install the runtime package and symlink the soname rather than assuming the toolchain is complete.
- **Do not install the wrong module set.** WebGL support alone is several GB and useless for Quest; the first editor install defaults to the web template's modules.
- **Do not leave a GUI dialog unhandled in a batch run.** A pending modal (license consent, project upgrade) hangs the editor with no log output; check the desktop state, not only the log tail.
- **Remote GUI work needs the remote user for secrets.** Credentials, license consent and account sign-in belong to the user; the agent can prepare everything else and hand over control through the sandbox's shared desktop.
- **A blocker is not a stopping point for the rest of the chain.** Report it precisely and keep executing the independent steps (disk cleanup, staging the project, preparing the matching editor version), then hand over only the piece that genuinely needs the user.
- **Distinguish "verified", "attempted" and "planned" in every report.** Installed, launched, imported and built are four different claims; only one of them produces an APK. Say which one was reached and name the exact remaining step.

## Supporting files

- `references/instabox-desktop-unity.md` — verified InstaBox-specific commands: AppImage install, `xdotool`/`scrot` desktop driving, upload via the files API, disk cleanup, and the exact failure modes observed.
- `references/quest-device-debugging.md` — on-device log capture and triage for Quest builds: ADB workflow, encoding fixes, compact `[ARS]` logging, permission names, and the symptom→cause table.
- `references/unity-offline-renders.md` — producing review PNGs from a scene without play mode: camera aspect for RenderTexture + world-space Canvas, edit-mode lifecycle, lighting choices, and how to tell a projection bug from a layout bug.
