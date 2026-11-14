# 13 · Измерения и метрики

## Фактические значения

| Метрика | Значение | Источник | Статус |
|---|---:|---|---|
| App version | 0.5.12 / code 33 | `BuildQuestAndroid.cs`, APK badging | [ПРОВЕРЕНО] |
| APK bytes | 62,819,774 | downloaded build artifact | [ПРОВЕРЕНО] |
| APK SHA-256 | `bf293ae0d066140d4903797a0a7f5a6dbea355721cf31b401079903c1d1ac307` | source/download checksum | [ПРОВЕРЕНО] |
| Client frame cadence | 3 s | `LiveFrameSender.cs` default | [ПРОВЕРЕНО: configured; actual cadence unmeasured] |
| Client points/frame | max 384 | `LiveFrameSender.cs` default | [ПРОВЕРЕНО: configured] |
| Frame server payload limit | 4096 points | `app.py` | [ПРОВЕРЕНО] |
| History min interval | 0.25 s | `ARESCOPE_MIN_HISTORY_INTERVAL` default | [ПРОВЕРЕНО] |
| Max frames/session | 2000 | `app.py` default | [ПРОВЕРЕНО] |
| Retention | 7 days | `app.py` default | [ПРОВЕРЕНО] |
| DB payload cap | 209,715,200 bytes (200 MiB) | `app.py` default | [ПРОВЕРЕНО] |
| Vertex stride | 48 bytes | pinned `GPUSurfaceNets.cs` | [ПРОВЕРЕНО] |
| Position/normal/packed color offsets | 0 / 24 / 36 bytes | pinned `GPUSurfaceNets.cs` | [ПРОВЕРЕНО] |
| Live buffer read cap | 12,582,912 bytes (12 MiB) | `ArescopeLiveCloud.cs` | [ПРОВЕРЕНО] |
| Live cloud nominal interval | 0.2 s | `LiveScanPoints.cs` default | [ПРОВЕРЕНО: configured] |
| Live cloud sample buffer | 6000 positions | `LiveScanPoints.cs` default | [ПРОВЕРЕНО: configured] |
| Live point voxel size/cache | 0.035 m / 60,000 entries | `LiveScanPoints.cs` | [ПРОВЕРЕНО: configured] |
| Minimap | ±0.03 m, 768 sample capacity, 96 displayed, 1.5 s | `LiveScanMinimap.cs` | [ПРОВЕРЕНО: configured] |
| Historical final mesh on Quest 3S | app `0.5.8`, 62,374 vertices, 118,298 triangles, 2.42 s read; wire diagnostic reported 59,149 triangles kept and 30,900 unique edges | device log `20261113-081211-pause.log`; latest boot marker is `app=0.5.8` at 08:10:35 UTC | [ПРОВЕРЕНО: one run on 0.5.8; do not attribute it to 0.5.10/0.5.12] |
| DB observed snapshot | 19 sessions, 384 frames, 788,147 stored payload bytes; latest session timestamp 2026-11-05 UTC | `/api/live/stats` historical response | [ПРОВЕРЕНО: snapshot only, not current DB state]
| Device log upload | three files for 2026-11-13; 88,035–93,888 bytes | `/var/lib/arescope-lab/logs` historical listing | [ПРОВЕРЕНО: latest concatenated log contains app 0.5.8 boot marker; file may also include older retained segments] |

## Targets with no measurements

| Metric | Target/status |
|---|---|
| Minimum sustained FPS | no project measurement; target must be agreed [ТРЕБУЕТ ПРОВЕРКИ] |
| GPU/CPU frame time | no data [ТРЕБУЕТ ПРОВЕРКИ] |
| Scan completion/finalization time on Quest | One 0.5.8 mesh readback reported 2.42 s; end-to-end scan duration/finalization distribution absent [ТРЕБУЕТ ПРОВЕРКИ] |
| Battery delta per 10-min scan | no data [ТРЕБУЕТ ПРОВЕРКИ] |
| Headset temperature / throttling | no data [ТРЕБУЕТ ПРОВЕРКИ] |
| Relocalization translation/rotation error | no ground-truth measure [ТРЕБУЕТ ПРОВЕРКИ] |
| Mesh quality precision/recall vs ground truth | no reference scan [ТРЕБУЕТ ПРОВЕРКИ] |
| Network throughput/packet loss | no packet capture [ТРЕБУЕТ ПРОВЕРКИ] |
| ARSM upload success rate | no reliable count in current evidence [ТРЕБУЕТ ПРОВЕРКИ] |

## Measurement protocol

- Record each test with APK SHA, headset OS build, OpenXR runtime, room conditions and refresh rate. [ПРЕДПОЛОЖЕНИЕ: proposed reproducibility control]
- Run 3 repeated scans of same room; record scan duration, finalize duration, count metrics, battery %, thermal state and relocalization transform. [ПРЕДПОЛОЖЕНИЕ]
- Do not average across different firmware, scene settings or APK hashes. [ПРЕДПОЛОЖЕНИЕ]
- Distinguish configured values from measured values; source defaults are not runtime observations. [ПРОВЕРЕНО: principle applied in this table]
