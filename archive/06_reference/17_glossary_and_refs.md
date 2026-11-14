# 17 · Глоссарий и ссылки

## Глоссарий

| Термин | Определение |
|---|---|
| Arescope LAB | Веб-сервис для live point frames, session history, mesh/log files, exports and Mission Control. [ПРОВЕРЕНО: app routes]
| ARSM | Arescope binary mesh format; magic `ARSM`, version and vertex/index counts followed by data. [ПРОВЕРЕНО: MeshUploader/server parser]
| ASR (Automatic Speech Recognition) | Audio-to-text recognition endpoint `/api/copilot/transcribe`. [ПРОВЕРЕНО]
| Bearer token | HTTP authorization credential in `Authorization: Bearer …`. [ПРОВЕРЕНО]
| Depth API / environment depth | Runtime-produced environmental depth maps; Meta OpenXR extension `XR_META_environment_depth`. [ПРОВЕРЕНО: Meta docs]
| GPU | Graphics processing unit, used by Surface Nets compute extraction and readback. [ПРОВЕРЕНО]
| HUD | Head-up display overlay with scan/status/map/voice panels. [ПРОВЕРЕНО: project assets]
| IL2CPP | Unity scripting backend compiling managed code to native code for target. [ПРОВЕРЕНО: build setting; explanatory detail official Unity docs required for deeper spec]
| LLM (Large Language Model) | Text generation endpoint streamed through `/api/copilot/chat`. [ПРОВЕРЕНО]
| Mesh | Vertices plus triangle indices representing reconstructed surface. [ПРОВЕРЕНО: data format]
| MRUK (Mixed Reality Utility Kit) | Meta Unity package for room/scene understanding. [ПРОВЕРЕНО: package lock and Meta docs]
| OpenXR | XR runtime/API standard used by the headset client. [ПРОВЕРЕНО: project dependencies; exact runtime version unknown]
| PLY | Polygon File Format; here ASCII point-only export with x/y/z properties. [ПРОВЕРЕНО: exporter]
| Producer | Device-side identity authorized to ingest frames/mesh/logs and delete sessions. [ПРОВЕРЕНО: API auth]
| Relocalization | Runtime correction of tracked coordinate frame after tracking interruption or room re-entry. [ПРЕДПОЛОЖЕНИЕ: term usage; system behaviour requires test]
| SDM | Structured decision model/system used by earlier Copilot path; removed from current intended voice pipeline. [ПРОВЕРЕНО: project change record]
| Surface Nets | Isosurface extraction method used by pinned RoomScan GPU extractor. [ПРОВЕРЕНО: source code]
| TSDF (Truncated Signed Distance Function) | Voxel representation integrating signed distance estimates from depth observations. [ПРОВЕРЕНО: RoomScan module terminology; exact fusion parameters not all inventoried]
| TTS (Text-to-Speech) | Text-to-audio synthesis endpoint `/api/copilot/speech`. [ПРОВЕРЕНО]
| Viewer | Read-only identity for live frames, history, stats, PLY, mesh and logs. [ПРОВЕРЕНО: API role use]
| Voxel cache | Dictionary keyed by quantized 3D coordinates, used to suppress repeat live points. [ПРОВЕРЕНО]

## Local primary sources

- Unity project: `/root/Developer/arescope-beta02-questroom`. [ПРОВЕРЕНО: local filesystem]
- LAB server project: `/root/Developer/arescope-lab`. [ПРОВЕРЕНО]
- Copilot project: `/root/Developer/arescope-beta02-core`; production path historically `/opt/arescope-copilot`. [ПРОВЕРЕНО: context; verify live hashes]
- RoomScan source clone: `/root/QuestRoomScan-audit`, pinned revision `4791b24b81015641d4cfb010a93c6283d4eb3dee`. [ПРОВЕРЕНО]
- Production SQLite historical path: `/var/lib/arescope-lab/live.sqlite3`; device logs `/var/lib/arescope-lab/logs/`. [ПРОВЕРЕНО: prior filesystem inspection]
- Current APK link: https://shared.mrfenek.eu.cc/arescope/Arescope-Beta-0.5.12.apk ; SHA-256 `bf293ae0d066140d4903797a0a7f5a6dbea355721cf31b401079903c1d1ac307`. [ПРОВЕРЕНО: public download checksum]

## External references

1. Unity Editor 6000.2.9f1 release page, release ID and supported installers: https://unity.com/releases/editor/whats-new/6000.2.9f1. [ПРОВЕРЕНО: fetched official page]
2. Unity release archive: https://unity.com/releases/editor/archive. [ПРОВЕРЕНО: official page indexed]
3. Meta Quest 3S technical specifications: https://www.meta.com/quest/quest-3s/. [ПРОВЕРЕНО: official product page extraction]
4. Meta OpenXR Depth API overview: https://developers.meta.com/vr/documentation/native/android/mobile-depth/. [ПРОВЕРЕНО: official documentation extraction]
5. Meta MRUK samples: https://developers.meta.com/horizon/documentation/unity/unity-mr-utility-kit-samples/. [ПРОВЕРЕНО: official documentation extraction]
6. Kerbl et al., “3D Gaussian Splatting for Real-Time Radiance Field Rendering”: https://arxiv.org/abs/2308.04079. [ПРОВЕРЕНО: publication link; project performance comparisons are not inferred]
7. RoomScan repository at pinned revision: https://github.com/arghyasur1991/QuestRoomScan/tree/4791b24b81015641d4cfb010a93c6283d4eb3dee. [ПРОВЕРЕНО: package manifest]

## Source precedence

1. Exact current source/config at recorded commit/hash. [ПРЕДПОЛОЖЕНИЕ: archive rule]
2. Reproducible command output or captured device/server log with timestamp and APK SHA. [ПРЕДПОЛОЖЕНИЕ]
3. Official platform documentation for platform capability/constraints. [ПРЕДПОЛОЖЕНИЕ]
4. User screenshot/observation for reported visual symptoms, not for root-cause proof. [ПРОВЕРЕНО: epistemic distinction]
5. Previous chat claims without source artifact are not proof; label as historical report. [ПРЕДПОЛОЖЕНИЕ]
