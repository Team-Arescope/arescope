# Arescope Quest Client (Unity 6000.2.9f1)

The Arescope V2 **Rover Sensor-Mast Testbed** uses Quest 3S as a portable sensor mast: RGB/depth sensing, tracking, GPU reconstruction, and a local HUD. It streams real local geometry and compact telemetry to Mission Control (Arescope LAB), then displays Guardian risk and recovery advice returned by LAB. Voice Copilot supports the Mission Control operator and field engineer.

This prototype validates rover perception and fault recovery workflows. Quest does not measure wheel slip or chassis speed, and Guardian inference in this integration runs in LAB; an uplink outage prevents fresh Guardian advice. Rover simulation on HiRISE terrain is a separate carrier, not a measurement from the Quest testbed.

## Toolchain & Package Contract

- **Unity Editor:** `6000.2.9f1` (release ID `e0c4e791ab71`, Android Build Support + IL2CPP)
- **Target:** Android ARM64, IL2CPP, Linear color space, minSdk API 29, package `in.arescope.beta02.questroom`
- **Packages:** `com.genesis.roomscan` (pinned commit `4791b24b81015641d4cfb010a93c6283d4eb3dee`), Meta XR SDK / MRUK `205.0.0`, AR Foundation `6.2.0`, OpenXR `1.15.1`, Input System `1.14.2`

## Directory Layout (Client, HUD & Editor Tooling)

- `Assets/ArescopeClient/` (`Arescope.Client`):
  - `CopilotConnectionConfig.cs`: loads `Resources/arescope-endpoint` and optional `Resources/arescope-copilot-token`
  - `CopilotClient.cs`: 16 kHz mic capture, PCM16 WAV encoding, `POST /api/copilot/transcribe`, UTF-8 chunk-safe SSE parser for `POST /api/copilot/chat`, TTS gating on `complete` -> `POST /api/copilot/speech` MP3 playback, and 30 s settings poll/ack
  - `CopilotHudBridge.cs`: analog right-grip push-to-talk (`controller=5`, press `0.75`, release `0.35`) bridging `CopilotClient` events to `ArescopeHudController`
- `Assets/ArescopeHud/` (`Arescope.Hud`):
  - `ArescopeHudGraphics.cs`: custom `MaskableGraphic` meshes (`ArescopeChamferCardGraphic`, `ArescopeCircleCardGraphic`, `ArescopeCompassTicksGraphic`, `ArescopeChevronGraphic`, `ArescopeMapPointsGraphic`, `ArescopeVoiceMeterGraphic`) avoiding UI `Outline` opacity bugs
  - `ArescopeHudController.cs`: 6-panel world-space HUD (`status`, `event`, `map`, `assistant`, `compass`, `voice`) at `followDistance=1.15f` with 112-unit side inset, `0.25` fill alpha, glyph `Shadow`, circular 56-segment `Mask` minimap, and single-mesh 5°/15°/45° compass strip
- `Assets/Editor/` (`Arescope.Editor`):
  - `WireArescopeScene.cs`: builds/wires `Assets/Scenes/QuestRoomScan-REVIEW-ONLY.unity`, populates all 15 `ArescopeCopilot` components, applies Appendix 28 RoomScan parameters, fixes null `ViewModeController` references, and enables Android XR auto-start + OpenXR Lifecycle/Occlusion features
  - `ValidateArescopeScene.cs`: validates required scene GameObjects, non-null component references, XR auto-start, and OpenXR features
  - `BuildQuestAndroid.cs`: invokes `WireArescopeScene.Run()` and `ValidateArescopeScene.Run()` before `BuildPipeline.BuildPlayer`, filters scenes to `QuestRoomScan`, enforces Linear/ARM64/IL2CPP/API 29, and logs `QuestRoomScan build result: Succeeded; ... errors=0`
  - `RenderArescopeHudPreview.cs`: offline 1600 × 900 PNG preview renderer (see [HUD-PREVIEW.md](HUD-PREVIEW.md))
  - `BuildSimScenes.cs`: `SimRoom.unity` and `SimMars.unity` scene generators plus `RenderViews` and `RenderMarsHud`

## Configuration & Credentials

- Place deployment base URL in `Assets/Resources/arescope-endpoint.txt` (loaded by `CopilotConnectionConfig`).
- Place revocable device token in `Assets/Resources/arescope-live-token.txt` (and optional Copilot token in `Assets/Resources/arescope-copilot-token.txt`).
- Never commit real tokens or keystores to Git. Packaged APK `Resources/` assets are extractable from the APK; issue scoped, revocable device tokens only.

## Editor & Batchmode Commands

After package resolution, apply the pinned RoomScan compatibility patch **before** running the editor entry points below. From this Unity project directory in PowerShell (use the actual resolved cache directory if its suffix differs):

```powershell
py -B Scripts/patch_roomscan_editor.py Library/PackageCache/com.genesis.roomscan@4791b24b8101
py -B Scripts/patch_roomscan_editor.py Library/PackageCache/com.genesis.roomscan@4791b24b8101 --check
py -B Scripts/Verification/verify_project.py
./Scripts/run-core-tests.ps1
```

`patch_roomscan_editor.py` installs the Arescope bridges and assembly reference, then applies three Unity `6000.2.9f1` compatibility fixes to SDK editor sources:

- Parameterless `FindObjectsByType<BuildingBlock>()` receives `UnityEngine.FindObjectsSortMode.None`.
- Inactive-inclusive lookups of `AROcclusionManager` and `PassthroughCameraAccess` receive the second argument: `FindObjectsInactive.Include, UnityEngine.FindObjectsSortMode.None`.
- The three `uiDoc.worldSpaceSizeMode`, `uiDoc.pivot`, and `uiDoc.pivotReferenceSize` assignments are enclosed by `#if UNITY_6000_3_OR_NEWER` / `#endif`, preserving their behavior on newer editors.

The explicit overload is documented in [Unity's Object API](https://docs.unity.com/en-us/engine/6000.0/script-reference/unityengine/object/findobjectsbytype); the world-space property is documented for [Unity 6000.3](https://docs.unity.com/en-us/engine/6000.3/script-reference/unityengine/uielements/uidocument/worldspacesizemode-1). Repeating the patch is a no-op, and `--check` reports pending changes without writing. Fixture checks cover all three categories, pre-existing guards, LF/CRLF, BOM preservation, and repeated installs. Reapply after a package cache refresh. Offline checks do not replace a Unity batchmode compile or headset run.

```bash
# 1. Wire and validate the Quest scene
Unity -batchmode -quit -projectPath . -executeMethod Arescope.Editor.WireArescopeScene.Run -logFile wire.log
Unity -batchmode -quit -projectPath . -executeMethod Arescope.Editor.ValidateArescopeScene.Run -logFile validate.log

# 2. Render offline HUD preview
ARESCOPE_HUD_PREVIEW_PATH=Build/hud-preview.png Unity -batchmode -quit -projectPath . -executeMethod Arescope.Editor.RenderArescopeHudPreview.Run -logFile preview.log

# 3. Build Quest Android APK (automatically runs Wire + Validate first)
Unity -batchmode -quit -projectPath . -executeMethod Arescope.Editor.BuildQuestAndroid.Build -logFile apk-build.log

# 4. Generate simulator test scenes (excluded from Quest APK scene filter)
Unity -batchmode -quit -projectPath . -executeMethod Arescope.Editor.BuildSimScenes.BuildRoom -logFile sim-room.log
Unity -batchmode -quit -projectPath . -executeMethod Arescope.Editor.BuildSimScenes.BuildMars -logFile sim-mars.log
```

## V2 Live Frame & Guardian Contract

`LiveFrameSender` posts JSON to `POST /api/live/frame` using the producer bearer token. Existing `room`, `yawDeg`, and `points` remain compatible with V1. V2 adds camelCase `carrierId`, `carrierType`, and `telemetry`, matching Track 1's ingest, simulator, and Guardian field names. Defaults are `quest-mast-01` and `mast-testbed`; a non-default room supplies the carrier ID when `carrierId` is blank. Room/carrier IDs are trimmed and capped at 64 characters. Carrier type is normalized to `rover`, `mast-testbed`, or legacy `helmet`; an unsupported value falls back to `mast-testbed`. Give simultaneous physical carriers distinct room and carrier IDs.

Illustrative request:

```json
{
  "room": "mast-demo",
  "carrierId": "quest-mast-01",
  "carrierType": "mast-testbed",
  "yawDeg": 90.0,
  "points": [[0.5, 0.1, 2.0]],
  "telemetry": {
    "pointCount": 1200,
    "fps": 72.0,
    "poseJumpM": 0.01,
    "lumaContrast": 0.45,
    "linkOk": true,
    "position": [0.0, 1.6, 0.0]
  }
}
```

- Default uplink interval is 3 s. `points` contains at most 384 finite, head-relative `[right, vertical, ahead]` points in metres, filtered to a 10 m radius and ±1.4 m height band. `position` is the current Unity world-space headset position in metres.
- `telemetry.pointCount` is the unfiltered GPU sample count (up to 6000), not the transmitted array length. `fps` is smoothed Unity render/update FPS, not measured camera or depth integration FPS. `poseJumpM` is the largest consecutive headset-position step observed between uplinks.
- `lumaContrast` is twice the luminance standard deviation of sampled reconstruction vertex colors, clamped to `[0,1]`. It is a proxy from accumulated geometry, not current camera exposure or a dust sensor. `linkOk` combines network reachability with the previous request result, not an independent connectivity probe. Chassis telemetry is omitted.

The success response retains `ok`, `stored`, `throttled`, and numeric/nullable `sessionId`. Track 1 adds `guardian: {riskScore, riskLevel, predictedCause, recoveryAction, lowConfidence, ...}`. The client reads those fields (and legacy snake_case Guardian aliases), shows `GUARDIAN NOMINAL/WARNING/CRITICAL` with a shortened recovery action, and emits a five-second event/log when warning level, cause, or advice changes. Missing Guardian data displays `GUARDIAN --`; transport failures leave the last received advice visible, so check `UPLINK` and Mission Control freshness. Starting/resetting a scan clears session telemetry and ignores late replies from the previous session.

For the V2 demonstration, establish a textured-room baseline, then test simulated lens occlusion/dust, a blank low-texture wall, and a controlled sudden mast movement separately, restoring the baseline between trials. See [the headset runbook](../../docs/HEADSET_RUNBOOK.md) for steps, evidence, recovery, and limitations. Accumulated map colors and geometry may mask an optical fault; record observed responses and missed detections without claiming a guaranteed classifier result.

## Post-Build Verification Gates

1. Confirm `apk-build.log` contains `QuestRoomScan build result: Succeeded; ... errors=0`.
2. Inspect APK manifest and ABI:
   ```bash
   aapt2 dump badging Build/QuestRoomScan.apk | grep -E "^package:|sdkVersion|launchable-activity|native-code"
   ```
   Verify package `in.arescope.beta02.questroom`, `launchable-activity` `com.unity3d.player.UnityPlayerGameActivity`, and `arm64-v8a`.
3. Verify native plugin packaging:
   ```bash
   unzip -l Build/QuestRoomScan.apk | grep "lib/arm64-v8a/"
   ```
   Confirm `lib/arm64-v8a/libxatlas.so` and AR Foundation Meta native libraries are present.
