# Arescope

Clean-room recreation of the **Arescope** system for Mars surface exploration (Meta Quest 3S MR spatial scanner, Arescope LAB Mission Control, and Voice Copilot), reconstructed from the specifications and evidence in [archive/](archive/).

V2 focuses on rovers: a shared terrain view, synthetic rover fault replay, and
Guardian risk warnings with an operator-reviewed learning loop. Quest 3S is the
sensor-mast testbed. [Production LAB](https://arescope.mrfenek.eu.cc) and
[deployment evidence and rollback](docs/V2_DEPLOYMENT.md).

The fleet demo coordinates 1–6 simulated rovers surveying an approximately 40 km²
HiRISE tile. Guardian risk can trigger a safety halt and an available rover's
inspection approach. Coverage and trails share the terrain's freely rotating
camera. [Demo runbook](docs/FLEET_DEMO_RUNBOOK.md).

## Repository Structure

- [services/arescope-lab/](services/arescope-lab/README.md) — FastAPI Mission Control server (`127.0.0.1:18965`), SQLite history with gzipped frames and retention pruning, ARSM v1/v2 binary mesh parser/storage, ASCII PLY exporter, WebSocket `/api/live/stream`, device log endpoint, and static 3D Mission Control web dashboard (`NASA MGS MOLA` + `NASA MRO HiRISE` Gale Crater terrain + live WebSocket stream).
- [services/arescope-copilot/](services/arescope-copilot/README.md) — FastAPI Voice Copilot relay (`127.0.0.1:18975`) implementing ASR (`POST /api/copilot/transcribe`), streaming SSE LLM chat (`POST /api/copilot/chat`) with pre-delta fallback, TTS (`POST /api/copilot/speech`), and SQLite settings/acknowledgement sync (`GET/PUT /api/copilot/settings`, `POST /api/copilot/settings/ack`). No SDM / `/api/copilot/decision` route is present.
- [unity/arescope-quest/](unity/arescope-quest/README.md) — Unity `6000.2.9f1` (`e0c4e791ab71`) Android ARM64 IL2CPP Quest 3S client project, OpenXR/Meta XR configuration, `Arescope/Wire` URP shader, byte-preserved Tabler icons and font licenses, `PackagePatches/` for `Genesis.RoomScan` (`4791b24b81015641d4cfb010a93c6283d4eb3dee`), `Assets/Arescope/`, `Assets/ArescopeClient/`, `Assets/ArescopeHud/`, `Assets/Editor/` (`WireArescopeScene`, `ValidateArescopeScene`, `BuildQuestAndroid`, `RenderArescopeHudPreview`, `BuildSimScenes`), and unit tests.
- [docs/HEADSET_RUNBOOK.md](docs/HEADSET_RUNBOOK.md) — Quest 3S installation, controller bindings, H-01..H-10 test procedure, and `adb logcat` triage runbook.
- [archive/](archive/README.md) — Preliminary clean-room technical research archive (108 entries verified against `archive/SHA256SUMS.txt`, preserved byte-for-byte).

## Verification Scope

- **Arescope LAB (`services/arescope-lab`):** 224 Python tests passed on the deployment host and 19 Node tests passed for terrain geometry, the camera, fleet UI and existing contracts. Production checks cover authenticated streaming, persistent history and both terrain views. The expanded display contains 11,062 source-verified heights; the original Guardian benchmark is frozen separately.
- **Arescope Copilot (`services/arescope-copilot`):** 260 Python tests passed on the deployment host, including legacy SQLite migration, provider fallback, role isolation and POSIX `0600` permissions.
- **Unity Quest Client (`unity/arescope-quest`):** project verification (10 passed) and standalone C# core kernel tests (22 passed). Unity scene wiring, HUD preview, cloud APK build and package inspection completed in prior V2 QA; these do not establish headset runtime behavior.
- **Remaining hardware gate:** Meta Quest 3S device QA (`H-01..H-10`). Do not run Unity/Android builds on the local Windows workstation; execute them on the InstaBox cloud build host. Guardian benchmark results are synthetic hold-out validation, not flight or field validation.
