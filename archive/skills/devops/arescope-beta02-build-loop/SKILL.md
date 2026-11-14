---
name: arescope-beta02-build-loop
description: Use when rebuilding the Arescope Beta 0.2 Quest APK in InstaBox. Publish every APK to shared hosting and clean the sandbox between builds.
metadata:
  hermes:
    tags: [arescope, unity, quest, instabox, release]
---

# Arescope Beta 0.2 build loop (InstaBox)

## When to Use
Any rebuild of the Arescope Beta 0.2 Quest APK after scene, client or manifest changes.

## Fixed order of operations
1. **Schedule and supervise each build.** After starting every build, create a one-shot cron for estimated completion plus one minute, based on comparable timings. Include machine, PID, start time, exact log and artifact paths. Each cron must diagnose failure from real logs, safely fix verified root causes within project scope and retry, scheduling another one-shot for the new build; if still running, schedule another bounded one-shot. Stop and report after two unsuccessful repair attempts, repeated identical errors, an external dependency, unsafe changes or insufficient evidence. Never delete unrelated data, expose secrets, claim a stale APK, or retry indefinitely. Verify and publish before generated-cache cleanup.
2. **Build.** Unity `6000.2.9f1` at `/data/home/Unity/Hub/Editor/6000.2.9f1/Editor/Unity`, project `/data/home/unity/arescope-beta02`, target Android, `-executeMethod BuildQuestAndroid.Build`, log `/data/home/unity/arescope-beta02/apk-buildN.log`. Free space was ~11 GiB after cleanup; IL2CPP + Gradle needs roughly 8 GiB.
3. **Verify the artifact, not the exit code.** Unity reports `Succeeded` even when the manifest is broken. Check with `aapt dump badging` that `launchable-activity` exists, `native-code: arm64-v8a`, and that `lib/arm64-v8a/libxatlas.so` is packaged. A missing launchable activity means the app cannot start.
4. **Publish every build** to the shared host, then verify by downloading:
   `publish-shared <apk> arescope/<name>.apk --force` and compare SHA-256 with the source.
5. **Clean InstaBox before the next build.** Remove only generated caches: `Library/Bee`, `Library/Artifacts`, `Library/BurstCache`, `Library/ShaderCache`, `/data/home/.gradle/caches`. Keep `Assets`, `Packages`, `ProjectSettings`, the scene, `Build/`, and a copy of the APK outside the project (`/data/home/unity/arescope-beta02-staging.apk`). Do not delete anything else without explicit approval.

## Pitfalls
- **The build log's "Succeeded" is not proof.** The earlier staging APK had a missing `launchable-activity` because the custom `AndroidManifest.xml` had no `<activity>`; Unity still said Succeeded. Always run `aapt`.
- **Grep the result line, not the tail.** Unity ends every log with `SDL leaked ... allocations` and ILPP shutdown noise even after a failure. The verdict is `QuestRoomScan build result: <result>; ... errors=N`. A Gradle failure shows up as `:unityLibrary:compileReleaseJavaWithJavac FAILED` with `IllegalArgumentException: .../transforms/<hash>/transformed/output/jdkImage`; fix it by deleting only the transforms: `rm -rf /data/home/.gradle/caches/*/transforms`, then rebuild (keeps downloaded dependencies).
- **Arescope bridges must be installed, not just present in the repo.** `ArescopeLiveCloud`, `ArescopeMeshExport` and `ArescopeTexturedMesh` compile only inside the package assembly, so they live in `Runtime/Utils/` of the package cache, not in `Assets/`. `patch_roomscan_editor.py` copies all three from `PackagePatches/`; run it after any package re-resolve and confirm the files exist before building.
- **A custom Android manifest replaces Unity's.** It must declare the launcher activity (`com.unity3d.player.UnityPlayerGameActivity`), the `MAIN`/`LAUNCHER`/`com.oculus.intent.category.VR` intent filter, the Quest permissions (`RECORD_AUDIO`, `USE_SCENE`, `USE_ANCHOR_API`, `HEADSET_CAMERA`), and `<horizonos:uses-horizonos-sdk>`. Meta's `OVRManifestPreprocessor` throws on a manifest without an activity node and logs `ovr-manifest-write-failed` — that is the error behind a green build.
- **Meta OpenXR requires Linear colour space** (`PlayerSettings.colorSpace = ColorSpace.Linear`), otherwise the build fails late.
- **IL2CPP or Gradle can be OOM-killed on 8 GiB.** Confirm the killed process from kernel/build logs, stop only verified orphan compiler daemons, and limit Gradle JVM heap and worker concurrency via the isolated project's Unity `gradleTemplate.properties`; verify Unity's generated Gradle invocation also honors the intended heap. Do not change dependencies blindly.
- **Burst stalls `IL2CPP_CodeGen`** on small builders; `com.unity.burst` must be removed from the manifest for the Quest build.
- **The editor package cache needs patches** for Unity 6000.2 (`FindObjectsByType` overloads, `WorldSpaceSizeMode`). The patch script lives in the project and stores originals outside the package; re-apply after every package re-resolve.
- **Missing built-in modules** (`com.unity.modules.animation`, `androidjni`, `assetbundle`, `physics2d`, …) cause hundreds of `CS1069` errors in Meta XR code. Add them to `Packages/manifest.json`.
