# Arescope V2 Rover Sensor-Mast Testbed Runbook

Field test runbook for validating `in.arescope.beta02.questroom` on Meta Quest 3S as the **Rover Sensor-Mast Testbed**, connected to Mission Control (Arescope LAB). The Quest supplies real local geometry and tracking/appearance proxies; Guardian risk and recovery advice come back from LAB. Voice Copilot supports the Mission Control operator and field engineer. The HiRISE rover simulator is a separate, explicitly simulated carrier.

## Pre-Flight Checks

1. Verify APK artifact metadata before installation:
   - Package ID: `in.arescope.beta02.questroom`
   - ABI: `arm64-v8a`, minSdk API 29, Linear color space
   - Confirm SHA-256 of the local APK matches the published staging build.
   - Confirm `lib/arm64-v8a/libxatlas.so` is present inside the APK.
   - Confirm the RoomScan patcher and its `--check` passed after package resolution: explicit sort mode for parameterless and inactive-inclusive object lookups, plus a `UNITY_6000_3_OR_NEWER` guard around the three UIDocument world-space assignments. Unity `6000.2.9f1` must compile with zero errors before APK build; see the [client README](../unity/arescope-quest/README.md).
2. Confirm backend services are reachable and healthy:
   - LAB ingest service responding on `https://<host>/api/live/latest`
   - Copilot service responding on `https://<host>/api/copilot/status`
   - Verify the device token packaged in the APK matches the active server token.
   - Use the producer token for frame ingestion and the viewer token for Mission Control/API observation. A V2 frame acknowledgement must contain a `guardian` object; an older server can accept geometry while the headset shows `GUARDIAN --`.
   - Identify the physical carrier as `carrierType=mast-testbed`, normally `carrierId=quest-mast-01`. Use distinct room/carrier IDs if also running `rover-sim-01`. Confirm the selected Mission Control carrier and frame timestamps before inducing faults.
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
- **Expected HUD:** Status row shows `UPLINK 200`; Mission Control live panel updates every ~3 s for the mast-testbed carrier. The acknowledgement contains `ok=true`, storage/throttle flags, a session ID when storage succeeds, and V2 Guardian data.
- **Fail Criteria:** HTTP `401`, repeated status `0`/failed uplinks, or no fresh frames in LAB. Use device logs for timeouts/authentication detail; the status row itself shows only the HTTP code. A `200` alone does not prove that history was stored or that Guardian is available.

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

## Guardian Fault-Induction Demo (G-00 to G-04)

Introduce the device as a portable rover sensor-mast testbed. These trials exercise real headset telemetry and LAB-returned warnings; they do not validate autonomous rover control, wheel-slip sensing, or offline/on-device Guardian inference. Keep a stationary operator and an observer in a clear test area. Simulate dust with a clean translucent card held in front of the camera area; never put dust, adhesive, or liquid on the lenses. Stop the trial if headset tracking becomes uncomfortable or unsafe.

### G-00 · Establish the Baseline

1. Start a new scan with **X**, facing textured objects in even lighting. Move slowly until real points appear and at least five successful uplinks have arrived (allow about 30 s). Initial empty samples are suppressed until the first non-empty frame attempt.
2. In Mission Control, select the mast-testbed carrier. Confirm fresh frames with `carrierId`, `carrierType`, and `telemetry.pointCount`, `fps`, `poseJumpM`, `lumaContrast`, `linkOk`, and `position`.
3. Record baseline values and the returned `guardian.riskScore`, `riskLevel`, `predictedCause`, `recoveryAction`, and `lowConfidence`. Expect a stable nominal baseline; if already warning/critical, resolve or record that condition before proceeding. `GUARDIAN --` means no Guardian result has been received, not nominal health.

### G-01 · Lens Occlusion / Simulated Dust

1. Remain stationary and note the trial start time. Have the observer partially obscure the front camera area for two to three uplinks with the clean card. Keep tracking cameras unobstructed where possible.
2. Observe sampled point count and vertex-color contrast against baseline. Record the actual Guardian level, cause, recovery advice, and Mission Control low-confidence flag. A dust/occlusion or sensor-degradation warning is the intended response; do not relabel a different observed cause to fit the demo.
3. Remove the card, face textured landmarks, and follow the returned recovery advice. Capture both the fault and recovery frames, then wait for at least five fresh baseline uplinks before the next trial.

### G-02 · Blank Low-Texture Wall

1. From the recovered baseline, face a plain matte wall with few visible features, at a normal tracking distance. Slowly pan along it for two to three uplinks without covering the cameras.
2. Compare point count, contrast, and pose steps with baseline. The intended Guardian response is `warning`/`critical` with a low-texture explanation and advice to reacquire landmarks. Confirm the persistent `GUARDIAN` status row, the five-second event for a changed warning/cause/action, and the corresponding `[ARS] guardian` log.
3. Turn back toward a textured corner or doorway, move slowly, and record recovery to nominal or the remaining warning. Wait for five baseline uplinks before continuing.

### G-03 · Sudden Mast Motion

1. Use a carried test rig for one brief, controlled lateral displacement in the clear area, then stop. Do not jerk a wearer's head or throw/shake the device. When worn, keep movement within comfortable limits and record the resulting measured stimulus.
2. Check that `poseJumpM` rises relative to baseline and record the actual Guardian response. The intended response is a pose/tracking or `sensor_drop` warning with advice to stop, slow down, or reacquire a reliable landmark. Pure rotation may leave positional `poseJumpM` near zero.
3. Hold still facing textured landmarks and follow the returned advice. Record the return to baseline; use **Y** hold to reset if alignment remains wrong. Reset must clear Guardian state to `--` and clear the old session ID; previous in-flight replies must not restore old warnings.

### G-04 · Evidence & Honest Pass/Fail Reporting

For each trial, save the APK SHA-256, Unity/build version, room/carrier/session IDs, UTC fault start/removal times, the pre-fault/fault/recovery telemetry and Guardian responses, headset HUD capture, Mission Control capture, and device log. Record warning latency from the observed timestamps, unexpected causes, missed detections, and baseline false alarms. If replay is used for presentation, label it as a recording with its capture time.

The request `points` array is capped at 384 and head-relative; `telemetry.pointCount` counts up to 6000 GPU samples before spatial filtering. `fps` measures Unity update/render rate, `poseJumpM` measures the largest consecutive positional step between uploads, and `lumaContrast` is derived from accumulated reconstruction vertex colors. Stored geometry can survive camera occlusion or a blank wall, so these faults may leave the proxies unchanged. Record that limitation or a missed detection; a simulated rover fault is not evidence of a successful physical Quest trial.

Treat valid finite telemetry, fresh server Guardian responses, matching HUD/log warnings, and cleared state on reset as integration checks. Treat actual fault detection and recovery as separate measured outcomes. With ~3 s uploads, a multi-frame Guardian window adds observation delay; do not claim model lead time or detection latency without measured results. A failed uplink leaves the last advice visible and cannot deliver a fresh LAB prediction.

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
