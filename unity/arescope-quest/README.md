# Arescope Quest Client (Unity 6000.2.9f1)

Unity Quest 3S MR client for room scanning, world-space HUD telemetry, live point/mesh/log ingestion to Arescope LAB, and Voice Copilot interaction.

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
