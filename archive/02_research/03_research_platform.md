# 03 · Исследование аппаратной и программной платформы

## Устройство

| Параметр | Значение | Статус |
|---|---|---|
| Устройство целевого испытания | Meta Quest 3S | [ПРОВЕРЕНО: пользователь сообщил устройство; `BuildQuestAndroid.cs` target Android]
| SoC | Snapdragon XR2 Gen 2 | [ПРОВЕРЕНО: Meta Store product technical specs; см. references]
| DRAM | 8 GB | [ПРОВЕРЕНО: Meta Store product technical specs]
| Display | 1832×1920 pixels per eye; 72/90/120 Hz | [ПРОВЕРЕНО: Meta Store specs; active runtime refresh rate не установлен]
| Passthrough sensors | 2 color RGB cameras; device product page describes full-colour passthrough | [ПРОВЕРЕНО: Meta product page; API pixel access availability is separate]
| Device OS/Horizon OS build | Boot log records Android OS 14 / API-34, build `UP1A.231005.007.A1/4069240023000610` during app 0.5.8 on 2026-11-13 | [ПРОВЕРЕНО: device boot log; Horizon OS label/runtime build not separately captured] |
| Runtime graphics device | `Adreno (TM) 740`; Unity reported `SystemInfo.systemMemorySize=7757 MB` | [ПРОВЕРЕНО: boot log for app 0.5.8; not a live memory measurement] |
| Active OpenXR runtime version | данных нет | [ТРЕБУЕТ ПРОВЕРКИ] |
| Thermal/GPU power budget for this app | данных нет | [ТРЕБУЕТ ПРОВЕРКИ]

Официальная карточка устройства даёт аппаратные характеристики; она не доказывает доступность конкретного API в установленном firmware. [ПРОВЕРЕНО: Meta Quest 3S specs page]

## Программный стек проекта

- Unity Editor `6000.2.9f1`, Unity release ID `e0c4e791ab71`. [ПРОВЕРЕНО: Unity release archive и `BuildQuestAndroid.cs`]
- Meta XR Core SDK `205.0.0`, MR Utility Kit `205.0.0`; AR Foundation `6.2.0`, OpenXR `1.15.1`, Input System `1.14.2`. [ПРОВЕРЕНО: `Packages/manifest.json` and `Packages/packages-lock.json`]
- RoomScan dependency: Git `https://github.com/arghyasur1991/QuestRoomScan.git`, revision `4791b24b81015641d4cfb010a93c6283d4eb3dee`. [ПРОВЕРЕНО: `Packages/manifest.json`]
- Android package `in.arescope.beta02.questroom`, min API 29, ARM64, IL2CPP, Linear color space. [ПРОВЕРЕНО: `Assets/Editor/BuildQuestAndroid.cs`]
- APK snapshot 0.5.12, versionCode 33, size 62,819,774 bytes. [ПРОВЕРЕНО: aapt2/hash command output]

## OpenXR и расширения

- Проект использует Meta OpenXR/Quest packages и Android headset app manifest. [ПРОВЕРЕНО: package lock + Android manifest]
- Environment Depth — OpenXR extension `XR_META_environment_depth`, требует проверки расширения/свойств runtime перед использованием; официальная документация описывает provider, swapchain и acquire depth image. [ПРОВЕРЕНО: Meta OpenXR Depth API documentation]
- Ранее диагностировался сбой раннего запроса `xrGetSystemProperties` до корректного `XrInstance`; в релизной конфигурации включение `MetaOpenXR-OpenXRLifeCycle` считалось обязательным. [ПРОВЕРЕНО: исторический проектный отчёт; включён ли он в архивном текущем Unity asset — повторно проверить]
- Presence of `XR_META_environment_depth` in runtime and exact extension version on the target headset firmware: данных нет. [ТРЕБУЕТ ПРОВЕРКИ]
- Passthrough composition layer and environment depth are separate capabilities; simultaneous use/occlusion behaviour depends on configuration and requires headset testing. [ПРЕДПОЛОЖЕНИЕ: архитектурное разделение по API]; [ТРЕБУЕТ ПРОВЕРКИ: конкретная сцена]

## Память и графические ограничения

- RoomScan SDK source allocates GPU Surface Nets buffers lazily. Source comment estimates ~480 MB for default 256³ voxel grid. [ПРОВЕРЕНО: `Runtime/Core/MeshExtractor.cs` comment, pinned revision]
- Surface Nets capacity formula is `max(1024, floor(totalVoxels * vertexBudgetPercent))`; pinned SDK method fallback default is 0.05, `MeshExtractor` serialized field default is 0.08, and inspected release scene explicitly serializes 0.08. [ПРОВЕРЕНО: SDK source + scene YAML]
- Index capacity is `maxVertices * 18` 32-bit indices. [ПРОВЕРЕНО: `GPUSurfaceNets.EnsureBuffers`]
- Vertex record stride = 48 bytes; position offset 0 bytes, normal offset 24 bytes, packed colour offset 36 bytes; counter buffer = 4 uint32 values. [ПРОВЕРЕНО: pinned `GPUSurfaceNets.cs`]
- Live point readback max full vertex buffer can exceed safe driver transfer size; cloud reader caps a request at 12 MiB. [ПРОВЕРЕНО: `ArescopeLiveCloud.cs`]; actual driver maximum unmeasured [ТРЕБУЕТ ПРОВЕРКИ].
- Pinned SDK `VolumeIntegrator` defaults: voxel grid `256×256×256`, voxel size `0.05 m`, voxel distance `0.15 m`; mesh confidence default is `0.08`. [ПРОВЕРЕНО: `/root/QuestRoomScan-audit/Runtime/Core/VolumeIntegrator.cs`]
- Therefore default volume spans 12.8 m along each axis before room-specific cropping/translation (`256×0.05 m`). [ПРОВЕРЕНО: arithmetic from source defaults; effective scene overrides unknown]
- SDK buffer estimate from pinned `GPUSurfaceNets` formula: at vertex budget 0.05, 16,777,216 voxels, 838,860 max vertices, 15,099,480 max indices, estimated allocations 456,340,208 bytes (435.2 MiB); at component default 0.08, 1,342,177 max vertices, 24,159,186 max indices, estimated allocations 528,817,856 bytes (504.32 MiB). [ПРОВЕРЕНО: source formula + arithmetic; scene's effective 0.05/0.08 setting is unknown]
- These are estimated GraphicsBuffer/temporal allocation totals, not measured process RSS or GPU memory after other textures, camera buffers and runtime allocations. [ПРЕДПОЛОЖЕНИЕ: measurement boundary]
- Live cloud read uses a 12 MiB cap per request every nominal 0.2 s; 12 MiB / 48-byte stride = 262,144 consecutive records from offset 0, then CPU decimation returns at most 6,000 points. [ПРОВЕРЕНО: `ArescopeLiveCloud.cs`, `LiveScanPoints.cs`, arithmetic]
- At full cap, nominal maximum readback request rate is 60 MiB/s before driver/copy overhead; this is a configured worst-case estimate, not a measured sustained throughput. [ПРОВЕРЕНО: arithmetic]; [ТРЕБУЕТ ПРОВЕРКИ: actual bytes/timing]
- Since the cap reads a contiguous prefix, active vertices beyond the prefix are excluded from live-cloud sampling when the buffer is larger than 12 MiB; spatial bias depends on vertex ordering. [ПРОВЕРЕНО: code offset/count]; [ТРЕБУЕТ ПРОВЕРКИ: spatial distribution]
- Quest 3S app thermal throttling curve, available heap at runtime, maximum safe upload size and sustained GPU frequency: данных нет. [ТРЕБУЕТ ПРОВЕРКИ]

## Tracking, sleep and boundary

- The implementation reads `RoomAnchorManager.SpatialAnchorMatrix` to form a relocation transform. [ПРОВЕРЕНО: `ArescopeFrame.cs` and pinned RoomAnchorManager API]
- Whether a spatial anchor is active, survives sleep, and is localized after guardian boundary exit is not shown by current device logs. [ТРЕБУЕТ ПРОВЕРКИ]
- Required runtime log values: OS/runtime build, anchor matrix before scan, after resume, after boundary exit/re-entry, controller mapping, refresh rate and thermal state. [ПРЕДПОЛОЖЕНИЕ: proposed diagnostic record]

## Platform research gates

1. Capture headset firmware and OpenXR runtime version on the test device. [ТРЕБУЕТ ПРОВЕРКИ]
2. Query and record whether `XR_META_environment_depth` is advertised, and whether provider acquisition succeeds. [ТРЕБУЕТ ПРОВЕРКИ]
3. Measure 10-minute scan battery/temperature/FPS at 72/90/120 Hz or actual selected rate. [ТРЕБУЕТ ПРОВЕРКИ]
4. Repeat mixed passthrough + mesh, suspend/resume, and boundary relocalization at least 3 times. [ТРЕБУЕТ ПРОВЕРКИ]
