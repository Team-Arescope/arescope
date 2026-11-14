# 16 · Чек-лист воссоздания системы с нуля

## Назначение

Чек-лист ведёт инженера от пустого workspace до нового функционального Android-приложения и совместимого Arescope LAB deployment. [ПРЕДПОЛОЖЕНИЕ: процедура независимого воссоздания]

> Архив намеренно не содержит исходный код проекта. Инженер должен написать новую реализацию по API, алгоритмам и сценовой спецификации; копирование файлов старого репозитория не является шагом. [ПРОВЕРЕНО: требование архива]

## Итог формального прогона

- Версии Unity/SDK, параметры mesh, API, форматы, лимиты, controller flow и большая часть scene parameters описаны в архиве. [ПРОВЕРЕНО: наличие разделов и приложений]
- Точный исходный APK воспроизвести невозможно и это не является целью; целевой результат — новый функционально совместимый проект с новым signing identity. [ПРОВЕРЕНО: требование пользователя]
- Полная функциональная реконструкция пока блокируется: build helper не подключён к build entry point, scene references неполны, отсутствуют font payloads и APK-подтверждение native plugin; точные XR runtime settings также не зафиксированы. [ПРОВЕРЕНО: static audit]; [ТРЕБУЕТ ПРОВЕРКИ]

## A. Workspace и исходные зависимости

- [ ] Создать чистый Unity project; реализовать модульную структуру по `06_architecture.md`, `09_client_design.md`, `18_scene_and_asset_spec.md`, `20_runtime_component_spec.md`, `27_scene_build_audit.md`, `28_serialized_scene_parameters.md`. [ПРЕДПОЛОЖЕНИЕ: стартовая процедура]
- [ ] Установить Unity Editor `6000.2.9f1` и Android Build Support с IL2CPP; release ID `e0c4e791ab71`. [ПРОВЕРЕНО: Unity release page]
- [ ] Разрешить Unity packages согласно `evidence/reference_config/Packages__manifest.json` и `Packages__packages-lock.json`; проверить их SHA из root `SHA256SUMS.txt`. [ПРОВЕРЕНО: архив содержит побайтные копии конфигурации]
- [ ] Получить публичную зависимость QuestRoomScan revision `4791b24b81015641d4cfb010a93c6283d4eb3dee`; сверить commit. [ПРОВЕРЕНО: manifest pin]
- [ ] Установить Meta XR Core/MRUK `205.0.0`, AR Foundation `6.2.0`, OpenXR `1.15.1`, Input System `1.14.2`. [ПРОВЕРЕНО: package locks]
- [ ] Подключить Meta Quest Developer Hub/USB install workflow и проверить, что Quest 3S виден как development device. [ПРЕДПОЛОЖЕНИЕ: execution prerequisite]
- [ ] Создать локальный config для endpoint и новые ограниченные credentials; значения не переносить из production ресурсов. [ПРЕДПОЛОЖЕНИЕ: безопасная установка]

## B. Реализовать клиентские подсистемы

1. **XR bootstrap:** OpenXR/Meta lifecycle, camera rig, permissions, passthrough, ARSession/occlusion. [ПРОВЕРЕНО: требуемые типы компонентов]; runtime feature availability [ТРЕБУЕТ ПРОВЕРКИ]
2. **Room scan:** TSDF volume integration и Surface Nets по параметрам Appendix 23 и scene overrides Appendix 28. [ПРОВЕРЕНО: SDK/source spec]
3. **Input state machine:** X начинает/завершает scan; Y во время scan переключает passthrough; удержание Y 1.2 s сбрасывает; после финализации доступны Passthrough/Mixed/Scan. Устранить null ViewModeController refs и рассинхронизацию cycle state из Appendix 27. [ПРОВЕРЕНО: static audit]
4. **GPU mesh export:** active counters → clamp к capacity → bounded readback → проверка треугольников → диагностические counters; размеры/смещения в Appendix 23. [ПРОВЕРЕНО: контракт формата]
5. **Live cloud:** цветная выборка, накопление voxel cache 3.5 cm и render culling; текущий contiguous-buffer bias описан в Appendix 23. Добавить frame-time instrumentation. [ПРОВЕРЕНО: параметры]; стратегия равномерной выборки [ТРЕБУЕТ ПРОВЕРКИ]
6. **Room frame:** capture anchor matrix; определить каноническую координатную систему live vertices/final mesh/HUD/server payload; применять relocation только после теста на известных точках. [ПРОВЕРЕНО: текущая формула]; корректность frame [ТРЕБУЕТ ПРОВЕРКИ]
7. **Мини-карта:** текущая высота глаз ±0.03 m, range 10 m, sample buffer 768, max display 96; после завершения использовать финальный mesh. [ПРОВЕРЕНО: specification]
8. **LAB и логи:** point POST каждые 3 s, ARSM mesh upload, log trigger X+Y/pause/crash marker; `OnApplicationQuit` в inspected source только удаляет marker и не инициирует upload, поэтому новый проект должен определить lifecycle явно. [ПРОВЕРЕНО: source audit]
9. **Copilot:** ASR → LLM SSE → TTS; SDM route не входит в target; ограничения и модели — Appendix 19. [ПРОВЕРЕНО: target spec]
10. **HUD:** панели, шрифты и цвета из Appendix 24; восстановить отсутствующие font binaries под OFL либо проверить fallback. [ПРОВЕРЕНО: спецификация/лицензии]; font payloads отсутствуют в source snapshot. [ПРОВЕРЕНО]

## C. Генерация сцены и build graph

- [ ] Создать scene manifest по Appendix 18, 27 и 28: object tree, components, serialized properties, object references, cameras, render layers, build scene list. [ТРЕБУЕТСЯ: полный manifest]
- [ ] Build entry point должен явно запускать scene wiring/validation либо использовать scene manifest как единственный источник. Исследованный `BuildQuestAndroid.Build()` выбирает сцену и вызывает BuildPlayer, но не вызывает отдельный `WireArescopeScene.Run()`. [ПРОВЕРЕНО: static audit]
- [ ] Заполнить `ViewModeController` references на camera, passthrough и scan renderer; не воспроизводить их сериализованное null состояние. [ПРОВЕРЕНО: текущая сцена содержит null refs]
- [ ] Обеспечить наличие `LiveScanMinimap`, `LiveFrameSender`, `MeshUploader`, `ScanProgressHud`, `HudContrast`, `LogUploader`, `ARSessionBootstrap` либо обосновать замены; текущая сцена не подтверждает эти компоненты. [ТРЕБУЕТ ПРОВЕРКИ: итоговая сцена]
- [ ] Зафиксировать effective HUD distance осознанно: inspected scene override 1.15 m отличается от class default 0.62 m. [ПРОВЕРЕНО: scene/source]
- [ ] Создать native `libxatlas.so` из pinned RoomScan package/NDK и проверить включение в APK. [ПРОВЕРЕНО: Setup Wizard]; бинарник в APK [ТРЕБУЕТ ПРОВЕРКИ]

## D. Чистое развертывание сервера

- [ ] Установить Python/runtime зависимости и создать новый pinned dependency lock; исторический точный Python/package lock отсутствует. [ТРЕБУЕТ ПРОВЕРКИ]
- [ ] Настроить LAB по Appendix 21: отдельные producer/viewer credentials, Uvicorn на loopback `127.0.0.1:18965`, systemd, SQLite/mesh/log directories. [ПРОВЕРЕНО: API contract/current unit]
- [ ] Создать новый env file с нужными переменными и ограничить доступ; значения не публиковать. [ПРЕДПОЛОЖЕНИЕ: secure deployment]
- [ ] Настроить HTTPS reverse proxy для REST и WebSocket `/api/live/stream`; query token необходимо исключить из access logs. [ПРОВЕРЕНО: source uses query token]; nginx config [ТРЕБУЕТ ПРОВЕРКИ]
- [ ] Отдельно развернуть Copilot и router по Appendix 19/21; проверить тестовыми credentials и несекретным sample audio. [ТРЕБУЕТ ПРОВЕРКИ]

## E. Build и артефакт

- [ ] Установить package `in.arescope.beta02.questroom`, ARM64, IL2CPP, min API 29, Linear color space. [ПРОВЕРЕНО: build spec]
- [ ] Увеличить `versionCode`; создать новый signing key для новой установки. Для обновления уже опубликованной app с тем же package name потребуется исходный signing identity, которого в архиве нет. [ПРЕДПОЛОЖЕНИЕ: Android package signing rule]; [ТРЕБУЕТСЯ: legacy key only if update continuity needed]
- [ ] Выполнить Unity batch build; требовать явную строку `QuestRoomScan build result: Succeeded; ... errors=0`. [ПРОВЕРЕНО]
- [ ] Запустить aapt2 и проверить launcher, package, version, ARM64, permissions и native xatlas binary. [ПРОВЕРЕНО: проверки описаны]; результат xatlas для 0.5.12 [ТРЕБУЕТ ПРОВЕРКИ]
- [ ] Вычислить SHA-256, перенести APK, пересчитать hash, загрузить в staging, скачать и снова пересчитать. [ПРОВЕРЕНО: workflow]

## F. Сквозная проверка

- [ ] Выполнить headset tests H-01..H-10 из `12_testing.md`, минимум 3 повторения для relocalization. [ТРЕБУЕТ ПРОВЕРКИ]
- [ ] Проверить качество меша по сохранённым снимкам и triangle counters; build success не считать приёмкой. [ПРОВЕРЕНО: тестовый gate]
- [ ] Проверить LAB ingest/history с test credentials; убедиться, что `live-quest` и `archived-quest` не смешиваются. [ПРОВЕРЕНО: API contract]
- [ ] Проверить mesh upload, переключение minimap source и log-upload lifecycle. [ТРЕБУЕТ ПРОВЕРКИ]
- [ ] Для каждого прогона записать OS/runtime fingerprint, APK hash, scan settings, log, session id, mesh hash, FPS/thermal/battery. [ПРЕДПОЛОЖЕНИЕ: evidence form]

## G. Оставшиеся разрывы спецификации

1. Исходный код проекта намеренно не включён; его нужно написать заново по документированным контрактам. [ПРОВЕРЕНО: требование пользователя]
2. Полный scene manifest и корректное build-time wiring отсутствуют; audit нашёл mismatch между helper и BuildPlayer. [ТРЕБУЕТСЯ]
3. `.ttf` файлы отсутствуют; сохранены только OFL licenses и UI icons. [ПРОВЕРЕНО]
4. Native xatlas binary отсутствует в Assets; требуется генерация из pinned package и проверка APK. [ПРОВЕРЕНО: local Assets]; [ТРЕБУЕТ ПРОВЕРКИ: artifact]
5. Точные NDK/JDK/Android SDK subcomponent versions, Python dependency lock, Copilot systemd unit, nginx/TLS/CDN settings и backup/restore процедура не завершены. [ТРЕБУЕТСЯ]
6. Device QA после app 0.5.8, OpenXR runtime build, frame-time, battery, temperature и relocation accuracy отсутствуют. [ТРЕБУЕТСЯ]

## Формальный результат

- По архиву можно спроектировать и реализовать новый функциональный эквивалент с нуля, используя внешние pinned SDK dependencies. [ПРЕДПОЛОЖЕНИЕ: оценка полноты спецификации]
- Гарантировать полный feature parity или original APK reproduction сейчас нельзя: scene wiring, native plugin packaging, некоторые assets и runtime behavior остаются открытыми. [ПРОВЕРЕНО: reconstruction gaps]
