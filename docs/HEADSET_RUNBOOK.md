# Arescope Quest 3S Headset Runbook

Field test runbook for validating `in.arescope.beta02.questroom` on Meta Quest 3S against Arescope LAB and Voice Copilot.

## Pre-Flight Checks

1. Verify APK artifact metadata before installation:
   - Package ID: `in.arescope.beta02.questroom`
   - ABI: `arm64-v8a`, minSdk API 29, Linear color space
   - Confirm SHA-256 of the local APK matches the published staging build.
   - Confirm `lib/arm64-v8a/libxatlas.so` is present inside the APK.
2. Confirm backend services are reachable and healthy:
   - LAB ingest service responding on `https://<host>/api/live/latest`
   - Copilot service responding on `https://<host>/api/copilot/status`
   - Verify the device token packaged in the APK matches the active server token.
3. Install APK via ADB:
   ```bash
   adb devices
   adb install -r Build/QuestRoomScan.apk
   ```
4. Grant runtime permissions when prompted on launch: microphone (`RECORD_AUDIO`), spatial/scene data (`USE_SCENE`, `USE_ANCHOR_API`), and headset camera (`HEADSET_CAMERA`).

## Controller Bindings

| Input | Action | Notes |
|---|---|---|
| Left **X** (`primaryButton`) tap | Start scan / Finalize active scan | Ignored while finalize readback is busy |
| Left **Y** (`secondaryButton`) tap (during scan) | Toggle passthrough on/off | Scanning continues while toggled |
| Left **Y** (`secondaryButton`) tap (after finalize) | Cycle view mode: `Passthrough` → `Mixed` → `Scan` | Synchronized with active renderer state |
| Left **Y** (`secondaryButton`) hold ≥ 1.2 s | Reset / unload active scan | Returns to `Passthrough` ready state |
| Right **Grip** (`PrimaryHandTrigger` / `XRNode.RightHand` grip) hold & release | Voice Copilot push-to-talk (press ≥ 0.75, release ≤ 0.35) | Hold to speak, release to transcribe → chat → speak |
| Left **X + Y** hold ≥ 2.0 s | Upload diagnostic device log | Sends rolling `ArescopeLog` snapshot to LAB |
| Triggers, thumbsticks, right A/B buttons | Unused | No bindings assigned |

## Headset Test Protocol (H-01 to H-10)

### H-01 · Launch & XR Bootstrap
- **Steps:** Launch app from Quest Library / Unknown Sources.
- **Expected HUD:** Passthrough background active, 6-panel HUD visible (`status` top-left, `compass` top-center, `map` top-right, `voice` bottom-left, `assistant` bottom-right), `VOICE -`.
- **Fail Criteria:** Black screen, crash to home, missing HUD, or `occlusion=no-subsystem` stall without recovery.

### H-02 · Active Room Scan
- **Steps:** Press **X** to start scanning; walk slowly and turn around the room for 60 s.
- **Expected HUD:** `SCAN` status updates phase/progress (`0%` → rising %), live point cloud renders, minimap shows `POINTS n` updating around the center chevron.
- **Fail Criteria:** Progress stays `0%`, tracking freezes, or HUD locks up.

### H-03 · Minimap Eye-Height Band
- **Steps:** Face a doorway or furniture wall, then crouch and stand back up while looking at the floor and ceiling.
- **Expected HUD:** Minimap displays points within ±0.03 m of current head height (within 10 m radius) without floor/ceiling clutter.
- **Fail Criteria:** Floor plane fills minimap regardless of head height, or eye-level walls are missing.

### H-04 · Mixed View Mode
- **Steps:** Press **X** to finalize scan, then tap **Y** to cycle `Scan` → `Passthrough` → `Mixed`.
- **Expected HUD & View:** `Mixed` shows both live passthrough and the finalized copper/paper wireframe mesh simultaneously.
- **Fail Criteria:** Black background in `Mixed`, invisible wireframe, or `Reset` leaves passthrough off.

### H-05 · Final Wireframe Quality
- **Steps:** Inspect finalized wireframe walls, corners, and doorways.
- **Expected HUD & View:** Clean polygon edges with vertex points, no cross-room spike triangles; log records raw vs kept triangle counts.
- **Fail Criteria:** Long spikes crossing the room, empty mesh, or multi-second hang on finalize.

### H-06 · Relocalization (Boundary & Sleep/Wake)
- **Steps:** Exit Guardian boundary for 10 s and re-enter (3×); press Quest power button to sleep and wake (3×).
- **Expected View:** Wireframe stays aligned with physical door/cabinet landmarks (target RMS ≤ 5 cm, yaw error ≤ 3°).
- **Fail Criteria:** Room geometry rotates arbitrarily or swaps axes.

### H-07 · Live Point Uplink to Mission Control
- **Steps:** During active scan, monitor `UPLINK` status row and check Mission Control web UI.
- **Expected HUD:** Status row shows `UPLINK 200 <N>s` (or `200 cap` when rate-limited); Mission Control live panel updates every ~3 s.
- **Fail Criteria:** `UPLINK 401 AUTH`, `UPLINK TIMEOUT`, or no frames appearing in LAB.

### H-08 · Final Mesh Upload (ARSM)
- **Steps:** Finalize scan and inspect session in Mission Control (`GET /api/live/sessions`).
- **Expected Result:** Active session reports `hasMesh=true` and `meshBytes > 0`; mesh downloads and renders in LAB.
- **Fail Criteria:** Missing mesh upload or 422/413 error in log.

### H-09 · Diagnostic Log Upload
- **Steps:** Hold **X + Y** for 2 s (and separately pause/resume headset to test `pause` trigger).
- **Expected Result:** `GET /api/live/logs` lists a fresh UTC `.log` file containing `app=` boot line and session telemetry.
- **Fail Criteria:** No new log file created or empty file.

### H-10 · Voice Copilot End-to-End & 10-Minute Thermal Run
- **Steps:** Hold Right **Grip**, ask a short spatial/mission question, release Grip; continue scanning/using app for 10 min.
- **Expected HUD:** `VOICE LISTENING` (bars animate) → `TRANSCRIBING` → `THINKING` (assistant text streams into `COPILOT` card) → `SPEAKING` (MP3 audio plays) → `VOICE -`.
- **Fail Criteria:** Stream cuts off before `complete` yet speaks partial audio, microphone fails, or thermal throttle / crash within 10 min.

## Post-Run Checks & ADB Triage

When any step fails, capture logs and a headset screenshot immediately before closing the app:

```bash
# Dump Unity + OpenXR + RoomScan logcat
adb logcat -d -v threadtime > build-triage-logcat.txt

# Filter Arescope & XR diagnostic lines
adb logcat -d | grep -E "\[ARS\]|\[Arescope\]|OpenXR|AROcclusion|DepthCapture|Copilot"

# Capture current headset eye buffer screenshot
adb shell screencap -p /sdcard/arescope-fail.png
adb pull /sdcard/arescope-fail.png .
```

Also check `/storage/emulated/0/Android/data/in.arescope.beta02.questroom/files/arescope-debug.log` if ADB logcat wrapped:

```bash
adb pull /storage/emulated/0/Android/data/in.arescope.beta02.questroom/files/arescope-debug.log .
```

## Known Risks & Unverified Hardware Items

- **AROcclusionManager subsystem initialization:** On Quest 3S, if `MetaOpenXR-OpenXRLifeCycle` or `com.unity.openxr.feature.arfoundation-meta-occlusion` is disabled in `OpenXR Package Settings.asset`, `AROcclusionManager.subsystem` stays null permanently for the process. Always confirm `ValidateArescopeScene.Run()` passed on the build.
- **Single-pass stereo & passthrough contrast:** `HudContrast` viewport projection and `Arescope/Wire` alpha blending under real Quest 3S HDR/stereo passthrough require on-device visual verification.
- **Thermal & battery budget:** Sustained 30 Hz TSDF integration + 8 Hz Surface Nets extraction on Quest 3S XR2 Gen 2 has not yet completed a full 10-minute thermal/FPS benchmark.
