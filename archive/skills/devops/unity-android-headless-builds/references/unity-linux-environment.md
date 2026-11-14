# Unity Linux environment: versions, modules, patches, sizing

## Editor and module sources

Query the release API for the exact version and changeset of the project:

```
GET https://services.api.unity.com/unity/editor/release/v1/releases?version=<v>&limit=1
```

The response carries, per platform:

- Linux editor tarball: `.../LinuxEditorInstaller/Unity-<v>.tar.xz`
  (about 4.2 GiB compressed, 8.5 GiB installed).
- Android Build Support: published as a **macOS `.pkg`** even for the Linux
  editor. It is a XAR archive containing `TargetSupport.pkg.tmp/Payload`,
  itself a gzip-compressed cpio stream. Extract with:

```
7z x -opkgx android.pkg                     # XAR -> TargetSupport.pkg.tmp/Payload
bsdtar -xf pkgx/TargetSupport.pkg.tmp/Payload -C <editor>/Editor/Data/PlaybackEngines/
```

- `OpenJDK` (17.0.9), `android-sdk-ndk-tools`, NDK r27c, CMake 3.22.1,
  build-tools 36.0.0, platform-tools 36.0.0 and platforms 34/35/36 come as
  separate ZIPs with a documented `destination` per module. The Hub CLI
  (`--headless install-modules -m android --cm`) installs all of them.

Prefer the Hub CLI over manual extraction: it writes `modules.json` and
`modules.asset`, which the editor consults for the platform settings.

## Host libraries

The Linux editor links against `libembree.so.2`. On Debian 13 the package is
`libembree4-4` and provides `libembree4.so.4`; symlink it:

```
sudo ln -sf /usr/lib/x86_64-linux-gnu/libembree4.so.4 \
         /usr/lib/x86_64-linux-gnu/libembree.so.2
```

Also install `libarchive-tools` (bsdtar), `p7zip-full`, `cpio`, `xz-utils`,
`libtbb12`.

## Meta XR on a headless Linux editor

Meta XR 81 does not compile for the Linux editor; 83.0.4 compiles after two
source patches, applied to the **package cache**
(`Library/PackageCache/com.meta.xr.sdk.core@<hash>/`):

1. `Scripts/Editor/OVRManagerEditor.cs` — the `OVRManager manager` declaration
   sits inside `#if UNITY_EDITOR_WIN || ... || UNITY_ANDROID`. Add
   `|| UNITY_EDITOR_LINUX || UNITY_STANDALONE_LINUX`.
2. `Editor/MetaXRSimulator/Installer.cs` — `DownloadXRSimInstaller` declares
   `downloadedInstallerPath` only for Windows and macOS. Add an `#else` branch
   with a generic file name.

A third patch is needed for the build itself:
`Editor/OVRGradleGeneration.cs` throws when
`PlayerSettings.Android.targetArchitectures != AndroidArchitecture.ARM64`,
which Unity 6.2 reports as ARMv7 because the value lives in a build profile.

The OpenXR package carries its own checks in
`Library/PackageCache/com.unity.xr.openxr@<hash>/Runtime/OpenXRProjectValidation.cs`:

- rule "Only arm64 or x86_x64 is supported on Android with OpenXR" fires when the
  reported architectures miss ARM64/x86_64;
- rule "The **Composition Layers Support** feature is required to use the
  Composition Layers package" fires when the project depends on that package
  while the OpenXR feature is disabled.

Both are satisfied by rewriting the `checkPredicate` to a constant.

**The package cache is recreated whenever packages re-resolve**, so the
patches must live in a script that runs after every resolve, not as a one-off
edit. `scripts/patch_meta_sdk_linux.py` in this skill does exactly that and is
idempotent.

## Burst is what stalls IL2CPP on small builders

With the Meta XR sample stack present, the build hangs in `IL2CPP_CodeGen`
for tens of minutes. The symptom: the log stops at one `[BUSY] IL2CPP_CodeGen`
line, the parent `Unity` process still holds ~2.3 GiB RSS, and two `mono
.../com.unity.burst@<hash>/.Runtime/bcl.exe +burstc` children sit at 0% CPU
with only a few seconds of total CPU time. Compare CPU time over time — the
parent being alive proves nothing.

Fix: drop the package from the project and re-import.

```python
import json, pathlib
p = pathlib.Path("Packages/manifest.json")
d = json.loads(p.read_text())
d["dependencies"].pop("com.unity.burst", None)
p.write_text(json.dumps(d, indent=2))
```

Then delete `Packages/packages-lock.json`, `Library/PackageCache/com.unity.burst*`,
`Library/BurstCache` and `Temp/Burst`, and re-run the import. The Meta XR
sample code does not need Burst for this prototype.

## Keeping the editor module off the persistent volume

The persistent volume on a free plan is too small for editor + Android module
+ project + build output. The module can be moved to the root volume and
symlinked back, because the editor resolves it through
`Editor/Data/PlaybackEngines/<Module>`:

```bash
sudo cp -a $E/PlaybackEngines/AndroidPlayer/. /opt/unity-android/
sudo rm -rf $E/PlaybackEngines/AndroidPlayer
sudo ln -s /opt/unity-android $E/PlaybackEngines/AndroidPlayer
```

Run the build with the project on the *other* volume from the editor, so
neither the IL2CPP scratch nor the Gradle output competes for the same space.

## Sizing reality

| Item | Size |
|---|---|
| Unity Editor 6000.2.x, installed | ~8.5 GiB |
| Android Build Support module | ~5.5 GiB (SDK+NDK+JDK dominate) |
| Optional modules not needed for Android (WebGL ~7 GiB, Linux Standalone ~0.3 GiB, Documentation ~1.3 GiB) | deletable |
| Project `Library/` after import | 2–7 GiB, growing during IL2CPP |

A 20 GiB persistent volume is too small for editor + module + project + build
output. Keep the editor on the persistent volume and the project on the root
volume, and expect the IL2CPP step to need several GiB of scratch space.

## Memory limits

On an 8 GiB builder, IL2CPP with the *Release* configuration gets its
`clang++` processes OOM-killed; the log shows only `Killed`. Use the *Master*
configuration and stop any GUI processes (Hub, browser) before building.

Check the kernel log to confirm an OOM rather than guessing from the build
message: `sudo dmesg | grep -i 'out of memory\|oom-kill'` names the killed
process (often `clang++`, sometimes an unrelated browser that grabbed the
memory first).

## Reading the build failure

`Build Finished, Result: Failure` is printed before the reason. The useful
lines come from the build report, not the console stream:

- `Error building Player: N errors` is only a count.
- The concrete reason follows as a stack trace pointing at the rule that
  failed, e.g. `OVRGradleGeneration.cs` (Meta XR architecture check) or
  `OpenXRProjectValidationRulesSetup.cs` (OpenXR validation).
- Warnings about moving `XRSimulation*Settings.asset` during a build are
  harmless noise, not the failure.

Capture them in the build script by walking `report.steps` and logging every
`LogType.Error`, `LogType.Exception` and `LogType.Assert` message; otherwise
the cause is buried in a multi-thousand-line log.
