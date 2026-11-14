# 02 · Требования и критерии приёмки

## Функциональные требования

| ID | Требование | Критерий приёмки | Статус/источник |
|---|---|---|---|
| FR-01 | Запускать room scan через левый контроллер X | Нажатие запускает SDK scan; `IsScanning=true`; HUD показывает scanning state | [ПРОВЕРЕНО: предусмотрено в `ScanModeBridge.cs`; [ТРЕБУЕТ ПРОВЕРКИ] на устройстве |
| FR-02 | Переключать passthrough во время активного скана | Y tap меняет `OVRPassthroughLayer.enabled`, scan продолжает интеграцию | [ПРОВЕРЕНО: код]; [ТРЕБУЕТ ПРОВЕРКИ] hardware |
| FR-03 | Сбрасывать активный scan удержанием Y | 1.2 s hold вызывает `UnloadActiveScanAsync`, переводит в passthrough | [ПРОВЕРЕНО: сериализованный порог]; [ТРЕБУЕТ ПРОВЕРКИ] UX |
| FR-04 | Показывать живые точки | Точки обновляются из GPU Surface Nets sample; целевой параметр клиента: 6000 sampled vertices/read every 0.2 s; cloud cache max 60000 voxels | [ПРОВЕРЕНО: сериализованные значения 0.5.11+]; GPU readback/цвет и точность требуют проверки |
| FR-05 | Мини-карта по высоте глаз | Band ±0.03 m относительно текущей headset position.y; до 96 точек, sampling budget 768, interval 1.5 s | [ПРОВЕРЕНО: `LiveScanMinimap.cs`; плотность и coordinate frame требуют проверки]
| FR-06 | Показывать финализированный scan | Положительный тест: корректный меш, нет непреднамеренных длинных рёбер; лог содержит vertex/triangle counts | [ТРЕБУЕТ ПРОВЕРКИ: последняя подтверждённая картинка показывала артефакты до 0.5.11; 0.5.12 не подтверждена]
| FR-07 | Переключать post-scan views | Цикл passthrough → mixed → scan-only; mixed одновременно показывает реальную камеру и scan mesh | [ПРОВЕРЕНО: предусмотрено кодом 0.5.11+]; [ТРЕБУЕТ ПРОВЕРКИ] на шлеме |
| FR-08 | Отправлять live point frame в LAB | POST `/api/live/frame`, producer Bearer, максимум 4096 points на сервере; клиент сериализует до 384 points/frame, каждые 3 s | [ПРОВЕРЕНО: клиент/сервер исходники; фактические кадры ранее наблюдались в базе, текущая версия не проверена]
| FR-09 | Загружать mesh в LAB | POST `/api/live/mesh?session=<id>`, ARSM v1/v2, максимальный body 32 MiB | [ПРОВЕРЕНО: client/server code; успешная загрузка в последнем device run не подтверждена]
| FR-10 | Отправлять diagnostic log без adb | При `OnApplicationPause(true)`, X+Y hold и crash marker recovery; body ≤8 MiB server-side | [ПРОВЕРЕНО: `LogUploader.cs`/server; `OnApplicationQuit` only clears marker and does not start upload] |
| FR-11 | Voice assistant only LLM/ASR/TTS | Sequence ASR → LLM SSE → TTS; `/api/copilot/decision` отсутствует | [ПРОВЕРЕНО: серверный live test в предыдущем контексте; код в `/opt` нужно hash-verify для reproduction]

## Нефункциональные требования (проектные цели)

| Категория | Целевое значение | Статус |
|---|---|---|
| Build target | Android ARM64, IL2CPP, minSdk API 29, Unity color space Linear | [ПРОВЕРЕНО: build script]
| Frame ingest cadence | 3 s/client frame, max 384 sampled points/client payload | [ПРОВЕРЕНО: `LiveFrameSender.cs`]
| Live history rate cap | Persist no faster than 0.25 s/room | [ПРОВЕРЕНО: server config default]
| Session split | New persisted session after 60 s without frame | [ПРОВЕРЕНО: server config default]
| Session frame cap | 2000 frames | [ПРОВЕРЕНО: server config default]
| DB payload cap | 200 MiB | [ПРОВЕРЕНО: server config default; applies payload-sum logic]
| Retention | 7 days | [ПРОВЕРЕНО: server config default]
| Mesh/log body cap | Mesh 32 MiB; log 8 MiB | [ПРОВЕРЕНО: server constants]
| Battery/FPS/thermal | No numeric target captured | [ТРЕБУЕТ ПРОВЕРКИ: target must be agreed and measured]
| Minimap accuracy | Must follow current eye height within ±3 cm in vertical coordinate | [ПРОВЕРЕНО: configured threshold]; [ТРЕБУЕТ ПРОВЕРКИ: sensor sample density/physical accuracy]

## Platform constraints

- Android app is ARM64 IL2CPP; package identifier `in.arescope.beta02.questroom`; version at archive snapshot 0.5.12, versionCode 33. [ПРОВЕРЕНО: `BuildQuestAndroid.cs`, APK badging]
- Meta XR SDK and RoomScan package provide platform-specific scanner, passthrough, controllers and spatial anchor interfaces. [ПРОВЕРЕНО: dependency manifests/source]
- Async GPU readback returns finite-time GPU buffer data and may fail on unsupported/oversized requests; current client caps one live cloud read to 12 MiB and mesh read to used ranges. [ПРОВЕРЕНО: code; driver-specific max is not measured]
- Android backgrounding, suspend/resume, tracking-origin changes and guardian boundary transitions require on-device validation. [ТРЕБУЕТ ПРОВЕРКИ]

## Acceptance gates

1. **Build gate:** `aapt2 dump badging` confirms package, versionCode, launchable activity and `arm64-v8a`; APK public download SHA equals source SHA. [ПРОВЕРЕНО: performed for 0.5.12]
2. **Scan gate:** 60 s room scan with no crash, points update, headset pose remains responsive. FPS threshold not specified; record measured fps/device HUD. [ТРЕБУЕТ ПРОВЕРКИ]
3. **Mesh gate:** final mesh visible; no lines across empty space; log records raw/kept/degenerate/stretched/out-of-range counts. [ТРЕБУЕТ ПРОВЕРКИ]
4. **Mixed view gate:** passthrough and scan mesh visible simultaneously for 30 s, no black background and no scan-position jump. [ТРЕБУЕТ ПРОВЕРКИ]
5. **Minimap gate:** looking down does not include floor if its vertical points fall outside ±0.03 m; looking at an eye-level door includes points; crouching updates the band. [ТРЕБУЕТ ПРОВЕРКИ]
6. **Relocalization gate:** exit tracked play area, sleep/resume, return; scan features stay aligned within a measured tolerance. No tolerance established. [ТРЕБУЕТ ПРОВЕРКИ]
7. **Network gate:** live frame accepted with producer token, viewer can read it; 401 without/with wrong token; no token value in artifacts. [ПРОВЕРЕНО: server auth pattern; end-to-end against current APK requires check]
8. **Log gate:** X+Y upload appears in log list and downloaded log contains current run. [ПРОВЕРЕНО: previous uploads from headset exist; current release needs check]

## Out of scope / not accepted as delivered

- Semantic object labels/classification: отсутствует требование/реализация подтверждённая в проекте. [ТРЕБУЕТ ПРОВЕРКИ]
- Gaussian Splat training on-device: deliberately excluded from current release scope. [ПРОВЕРЕНО: project decision history]
- Numeric guarantees for FPS, mesh completeness, latency, battery use or environmental lighting: данных нет. [ТРЕБУЕТ ПРОВЕРКИ]
