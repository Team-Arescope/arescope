# 22 · Разрывы спецификации и gate самодостаточности

Этот документ фиксирует информацию, без которой инженер не сможет однозначно воспроизвести оригинальное поведение только по текстовому архиву. Это не дефекты реализации, а пробелы в доступной спецификации. [ПРОВЕРЕНО: сравнение архива с требованием source-free recreation]

## Blocker A · Не определён полный Unity scene contract

- Требуются полный список GameObjects/Components и их parent/local transforms, active state, layer/culling masks, camera clear flags/target textures, passthrough composition order, shader/material refs and GUID mapping. [ТРЕБУЕТСЯ]
- Нужны значения serialized overrides для всех `[SerializeField]` полей; текущие поля defaults могут быть переопределены в scene/prefab. [ТРЕБУЕТСЯ]
- Нужны точные prefabs/URP asset/renderer feature/shader variants, icon/font assets, texture assets, Android gradle templates and plugin manifests. [ТРЕБУЕТСЯ]
- Решение: добавить нормализованный scene manifest (не Unity YAML; сущность, родитель, компоненты, поля/значения, refs) плюс список ассетов с лицензиями и SHA-256. [ПРЕДПОЛОЖЕНИЕ: required documentation artifact]

## Blocker B · XR capabilities and runtime reproducibility

- Не записаны Quest 3S Horizon OS build, OpenXR runtime version, environment-depth extension availability, refresh mode, guardian settings, room-permission state or tracking-origin settings. [ТРЕБУЕТСЯ]
- Не зафиксированы Unity XR Plug-in Management provider order, Meta OpenXR feature flags (включая lifecycle), manifest/build target SDK reconciliation, application permissions prompt history. [ТРЕБУЕТСЯ]
- Решение: device fingerprint record from ArescopeLog boot + Meta Quest Developer Hub device details, before any functional test. [ПРЕДПОЛОЖЕНИЕ]

## Blocker C · RoomScan internal parameters

- Не сведены все effective scene overrides: voxel dimensions/voxel size, volume bounds, min mesh weight, integration frequency, depth confidence threshold, color volume format, mesh smoothing values, temporal settings, compute shader references, GPU buffer budget. [ТРЕБУЕТСЯ]
- SDK code has component defaults, including `MinMeshWeight=0.08`, `gpuVertexBudgetPercent` component default 0.08, method default 0.05 and 256³ volume referenced in comments; effective prefab overrides are unknown. [ПРОВЕРЕНО: source defaults]; [ТРЕБУЕТ ПРОВЕРКИ: effective values]
- Решение: extract an implementation-neutral parameter table by inspecting serialized RoomScan components and matching pinned SDK fields. [ПРЕДПОЛОЖЕНИЕ]

## Blocker D · Geometry validation data

- Current median-edge filter parameters are documented; ground-truth reference mesh and measured false-positive/false-negative rates are absent. [ПРОВЕРЕНО/ТРЕБУЕТСЯ]
- No canonical test scene set exists in this archive for: plain walls, thin door frames, glass, dark furniture, reflective surfaces, occluded corners, moving people, large gap edges. [ТРЕБУЕТСЯ]
- No triangle quality metric threshold, edge-length histogram, connected components or normal discontinuity acceptance thresholds are fixed. [ТРЕБУЕТСЯ]
- Решение: acquire room-level references, log raw/filtered mesh and comparison metrics, agree quality gate before declaring scan fit for use. [ПРЕДПОЛОЖЕНИЕ]

## Blocker E · Coordinate frame derivation

- Current implementation captures `RoomAnchorManager.SpatialAnchorMatrix` at scan start and applies `A_now * inverse(A_capture)` to a visual root. [ПРОВЕРЕНО]
- Missing specification: whether sampled GPU positions are MeshExtractor-local, room-anchor-local or world coordinates; whether MeshExtractor transform is identity; whether SDK refinement changes coordinate frame; whether `SpatialAnchorMatrix` is valid at capture time. [ТРЕБУЕТСЯ]
- Missing durable spatial anchor creation/load lifecycle contract and persistence key/UUID details. [ТРЕБУЕТСЯ]
- Решение: declare one canonical frame per data type (live positions, final GPU mesh, refined SDK mesh, HUD points, server points) and write explicit transform equations for all conversions. [ПРЕДПОЛОЖЕНИЕ]

## Blocker F · API lifecycle and migrations

- Exact public nginx host/path mapping, websocket upgrade/heartbeat settings, CDN/Access behavior, CORS and request body buffering are incomplete. [ТРЕБУЕТСЯ]
- `sessions` and `frames` schema documented, but SQLite migration versioning, transaction strategy, WAL mode, lock policy and restore procedure not fully documented. [ТРЕБУЕТСЯ]
- `MeshUploader` binds upload to last point-ingest session ID; if no frame was accepted it aborts. Exact race/order with server `sessionId` and `RoomReady` callbacks needs integration test. [ПРОВЕРЕНО: code path]; [ТРЕБУЕТ ПРОВЕРКИ: timing]

## Blocker G · Complete reproducible artifacts

- Unity Editor package and module installation list with hashes is incomplete. [ТРЕБУЕТСЯ]
- Android signing keystore, alias, certificate fingerprint, Play/side-load signing policy and update key custody are excluded. [ТРЕБУЕТСЯ: do not place secret in this archive]
- Exact Copilot deployment unit, Python interpreter, pinned dependencies, service working directory, restart policy and model router config are not part of archive. [ТРЕБУЕТСЯ]
- System-level backup/snapshot/restore runbook, retention for meshes/logs, disk alert thresholds and disaster recovery target are missing. [ТРЕБУЕТСЯ]

## Definition of archive complete

Archive becomes sufficient for a clean-room functional recreation when all gates below pass:

- [ ] A new engineer can generate the scene and references from scene manifest without opening original Unity scene file. [ТРЕБУЕТСЯ]
- [ ] Every prefab/resource/material/shader/plugin dependency has name, version/GUID substitute, source/license and hash. [ТРЕБУЕТСЯ]
- [ ] Runtime effective parameters are distinguished from component defaults. [ТРЕБУЕТСЯ]
- [ ] Each coordinate frame and transformation has test fixture and expected numeric output. [ТРЕБУЕТСЯ]
- [ ] All network/API routes include auth role, request/response schema, limits, error body and versioning policy. [ТРЕБУЕТСЯ]
- [ ] Build instructions include exact toolchain dependencies and a verified clean-room build by a separate engineer. [ТРЕБУЕТСЯ]
- [ ] Headset test report records OS/runtime, setup, steps, results, logs and artifact SHA. [ТРЕБУЕТСЯ]
- [ ] Backup restore tested and checksum/restore evidence filed. [ТРЕБУЕТСЯ]

**Текущий статус:** архитектурная и API спецификация содержательна, но source-free reconstruction gate не пройден. [ПРОВЕРЕНО: checklist above has open required inputs]
