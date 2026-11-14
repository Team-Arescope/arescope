# Arescope

Clean-room recreation of the **Arescope** system for Mars surface exploration (Meta Quest 3S MR spatial scanner, Arescope LAB Mission Control, and Voice Copilot), reconstructed from the specifications and evidence in [archive/](archive/).

## Repository Structure

- [services/arescope-lab/](services/arescope-lab/README.md) — FastAPI Mission Control server (`127.0.0.1:18965`), SQLite history with gzipped frames and retention pruning, ARSM v1/v2 binary mesh parser/storage, ASCII PLY exporter, WebSocket `/api/live/stream`, device log endpoint, and static 3D Mission Control web dashboard (`NASA MGS MOLA` + `NASA MRO HiRISE` Gale Crater terrain + live WebSocket stream).
- [services/arescope-copilot/](services/arescope-copilot/README.md) — FastAPI Voice Copilot relay (`127.0.0.1:18975`) implementing ASR (`POST /api/copilot/transcribe`), streaming SSE LLM chat (`POST /api/copilot/chat`) with pre-delta fallback, TTS (`POST /api/copilot/speech`), and SQLite settings/acknowledgement sync (`GET/PUT /api/copilot/settings`, `POST /api/copilot/settings/ack`). No SDM / `/api/copilot/decision` route is present.
- [unity/arescope-quest/](unity/arescope-quest/README.md) — Unity `6000.2.9f1` (`e0c4e791ab71`) Android ARM64 IL2CPP Quest 3S client project, OpenXR/Meta XR configuration, `Arescope/Wire` URP shader, byte-preserved Tabler icons and font licenses, `PackagePatches/` for `Genesis.RoomScan` (`4791b24b81015641d4cfb010a93c6283d4eb3dee`), `Assets/Arescope/`, `Assets/ArescopeClient/`, `Assets/ArescopeHud/`, `Assets/Editor/` (`WireArescopeScene`, `ValidateArescopeScene`, `BuildQuestAndroid`, `RenderArescopeHudPreview`, `BuildSimScenes`), and unit tests.
- [docs/HEADSET_RUNBOOK.md](docs/HEADSET_RUNBOOK.md) — Quest 3S installation, controller bindings, H-01..H-10 test procedure, and `adb logcat` triage runbook.
- [archive/](archive/README.md) — Preliminary clean-room technical research archive (108 entries verified against `archive/SHA256SUMS.txt`, preserved byte-for-byte).

## Verification Scope

- **Arescope LAB (`services/arescope-lab`):** `pytest` (65 passed), `node --test tests/mission_control.test.cjs` (8 passed), headless browser QA (WebSocket push/4401 close, auth-header Blob downloads, zero drawer horizontal overflow), and NASA PDS terrain verification (20,866 heights).
- **Arescope Copilot (`services/arescope-copilot`):** `pytest` (175 passed on Windows with mocked upstream router transport; POSIX `0600` permission check verified on Linux).
- **Unity Quest Client (`unity/arescope-quest`):** `Scripts/Verification/verify_project.py` (9 passed: reference bytes, Android manifest, project settings, XR serialized links, unique asset GUIDs, idempotent patchers, logcat triage) and standalone `csc.exe` C# core kernel tests (`Scripts/run-core-tests.ps1`, 22 passed).
- **Remaining External / Cloud Gates:** Unity `6000.2.9f1` + Android NDK/SDK compilation and APK build (`BuildQuestAndroid.Build`), HUD preview PNG capture (`RenderArescopeHudPreview.Run`), `aapt2` / `libxatlas.so` / `libUnityARFoundationMeta.so` APK inspection, live OmniRoute upstream checks, and Meta Quest 3S device QA (`H-01..H-10`). Do not run Unity/Android builds on the local Windows workstation; execute them on the InstaBox cloud build host.
