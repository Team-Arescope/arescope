# Архив технического исследования Arescope

**Название системы:** Arescope Quest Room Scanner + Arescope LAB. [ПРОВЕРЕНО: имена каталогов, APK и deployment]
**Предметная область:** сканирование помещения на автономном VR/MR-шлеме, построение и визуализация геометрии, передача облака точек и меша в веб-LAB, голосовой Copilot. [ПРОВЕРЕНО: проектные файлы и API]
**Целевая платформа:** Meta Quest 3S; приложение Android ARM64 на Unity 6000.2.9f1, Meta XR Core/MRUK 205.0.0, AR Foundation 6.2.0, OpenXR 1.15.1, Input System 1.14.2 и RoomScan SDK из pinned Git revision `4791b24b81015641d4cfb010a93c6283d4eb3dee`. [ПРОВЕРЕНО: BuildQuestAndroid.cs, Packages/packages-lock.json, Packages/manifest.json]
**Объём:** 18 обязательных разделов плюс 14 инженерных приложений, архивированные project skills и evidence-пакет; размер фиксируется в контрольной сумме перед выпуском. [ПРОВЕРЕНО: структура перечислена ниже]
**Язык:** русский; английские строки оставлены только для API, имён компонентов, моделей, файлов и точных значений конфигурации. [ПРОВЕРЕНО: документация редактируется по-русски]
**Исходные материалы:** `/root/Developer/arescope-beta02-questroom`, `/root/Developer/arescope-lab`, `/root/Developer/arescope-beta02-core`, SDK-клон `/root/QuestRoomScan-audit`, device logs `/var/lib/arescope-lab/logs/`, APK/релизные сведения в истории сборок и shared hosting. Секретные значения не копируются. [ПРОВЕРЕНО: источники доступны/перечислены; секретные значения исключены]

> Архив представляет исследование и спецификацию для независимого воссоздания. Он не является утверждением, что описанные версии прошли полный аппаратный QA. Каждый технический факт маркируется статусом достоверности.

## План подготовки архива

1. Зафиксировать границы системы, версии, доступные источники, артефакты и неизвестные; не переносить секреты. [ПРОВЕРЕНО: источники перечислены в этом документе; секреты исключены]
2. Записать план архива и вопросы, которым документы должны дать ответ. [ПРОВЕРЕНО: список ниже]
3. Подготовить разделы контекста, требований и исследования платформы; отдельно пометить неустановленные параметры устройства. [ТРЕБУЕТ ПРОВЕРКИ: firmware/runtime Quest]
4. Описать алгоритмы по текущим исходникам, включая известные дефекты и несовпадения между намерением и фактическим поведением. [ПРОВЕРЕНО: исходники проверены; аппаратный результат отдельно]
5. Зафиксировать API, SQLite, форматы файлов, systemd/nginx и резервное копирование без токенов и паролей. [ПРОВЕРЕНО: код/конфиги; точное внешнее устройство инфраструктуры частично]
6. Составить воспроизводимую сборку, проверки артефакта, тест-матрицу, риски, ADR и формальный прогон чек-листа. [ПРОВЕРЕНО: build logs 0.5.11/0.5.12; повторная сборка отдельным инженером не выполнена]
7. Провести редакторскую самопроверку: ссылки, статусы, точность чисел, пропуски; незакрытое обозначить явно. [ТРЕБУЕТ ПРОВЕРКИ: окончательный независимый инженерный прогон]

## Вопросы, на которые должен ответить архив

1. Какую задачу решает система, кто её использует и что входит/не входит в границы? → `01_scope/01_context.md`.
2. Какие проверяемые требования и критерии приёмки нужны? → `01_scope/02_requirements.md`.
3. Каковы точные аппаратные и программные предпосылки, разрешения, OpenXR-функции и неизвестные ограничения? → `02_research/03_research_platform.md`.
4. Почему выбран TSDF + GPU Surface Nets и где применяются refinement, текстурирование и vertex colors? → `02_research/04_research_scanning.md`.
5. Какие данные передаются, как часто, в каком формате, что происходит при потере сети? → `02_research/05_research_networking.md`.
6. Из каких компонентов состоит система и где проходят границы доверия? → `03_design/06_architecture.md`.
7. Каковы HTTP-контракты, схемы хранения, лимиты и форматы? → `03_design/07_data_contracts.md`.
8. Как повторить извлечение, фильтрацию, каркас, мини-карту, HUD и релокацию; где фильтр способен выкинуть корректные грани? → `03_design/08_algorithms.md`.
9. Какие экраны, состояния, кнопки и деградации предусмотрены? → `03_design/09_client_design.md`.
10. Как развернуть LAB/Copilot, какие порты, env-переменные, БД и backup? → `03_design/10_server_design.md`.
11. Как собрать, проверить и опубликовать APK без ложноположительного «Succeeded»? → `04_operations/11_build_and_release.md`.
12. Какие тесты нужны и каков измеримый pass/fail? → `04_operations/12_testing.md`.
13. Какие метрики реально измерены, какие цели заданы, а где данных нет? → `04_operations/13_measurements.md`.
14. Какие риски, ранние признаки и меры снижения? → `05_assurance/14_risks.md`.
15. Какие решения приняты и какие альтернативы отклонены? → `00_governance/15_decision_log.md`.
16. Можно ли повторить систему по чек-листу без репозитория и устных объяснений; где чек-лист блокируется? → `04_operations/16_reproduction_checklist.md`.
17. Какие термины, источники и внешняя документация используются? → `06_reference/17_glossary_and_refs.md`.
18. Какие версии исходников, lockfiles и build artifacts составляют точную базу документа? → `07_appendices/26_source_snapshot.md`.
19. Какие build/device observations принадлежат конкретной версии, а какие — нет? → `07_appendices/25_evidence_ledger.md`.
20. Какие компоненты фактически serialised в release scene, какие добавляются вручную, и вызывает ли build process wiring helper? → `07_appendices/27_scene_build_audit.md`.
21. Какие exact per-component parameters сериализованы в исходной release scene и какие defaults overridden? → `07_appendices/28_serialized_scene_parameters.md`.
22. Какие assets/plugins реально лежат в проекте, какие только `.meta`, и каких бинарных ресурсов не хватает? → `07_appendices/29_asset_manifest_spec.md`.
23. Какие project-related Hermes skills содержат исторические процедуры по Quest/Unity/Arescope? → `skills/README.md` и `07_appendices/31_project_skills_catalog.md`.
24. Как из коротких, неполных code recipes и инструкций собрать новую реализацию, не импортируя проектный source code? → `07_appendices/30_code_recipes.md`; как соблюсти hackathon start gate? → `README.md`/`skills/README.md`.

## Карта файлов

- `00_governance/00_index.md` — назначение, статусы, план, вопросы и карта архива.
- `01_scope/01_context.md`, `01_scope/02_requirements.md` — контекст и требования.
- `02_research/03_research_platform.md`, `02_research/04_research_scanning.md`, `02_research/05_research_networking.md` — предметное и платформенное исследование.
- `03_design/06_architecture.md` … `03_design/10_server_design.md` — архитектура и контракты.
- `04_operations/11_build_and_release.md` … `04_operations/13_measurements.md`, `04_operations/16_reproduction_checklist.md` — эксплуатация и воспроизведение.
- `05_assurance/14_risks.md` — реестр рисков.
- `00_governance/15_decision_log.md` — ADR-журнал.
- `06_reference/17_glossary_and_refs.md` — словарь и ссылки.
- `07_appendices/18_scene_and_asset_spec.md` — scene graph, serialized objects, permissions and asset/resource contract.
- `07_appendices/19_voice_copilot_spec.md` — exact ASR/LLM/TTS flow, settings, limits, timeouts and failure semantics.
- `07_appendices/20_runtime_component_spec.md` — component inputs/outputs, defaults, events, state and logging requirements.
- `07_appendices/21_server_configuration_spec.md` — complete environment-variable inventory and deployment parameter table.
- `07_appendices/22_reconstruction_gaps.md` — explicit unknowns, required source inputs and completion gate for source-free recreation.
- `07_appendices/23_tsdf_surface_nets_spec.md` — exact volume, fusion and GPU meshing parameters plus memory estimates.
- `07_appendices/24_hud_interaction_spec.md` — panel geometry, colors, typography, controls, minimap and contrast details.
- `07_appendices/25_evidence_ledger.md` — versioned build and headset evidence ledger, separating current facts from unverified claims.
- `07_appendices/26_source_snapshot.md` — source revisions, package locks and source-to-artifact traceability.
- `07_appendices/27_scene_build_audit.md` — serialized scene inventory vs. editor helper/build invocation; critical wiring discrepancy.
- `07_appendices/28_serialized_scene_parameters.md` — exact RoomScan, depth, mesh, keyframe, HUD and Copilot scene values.
- `07_appendices/29_asset_manifest_spec.md` — scene/assets, fonts, icons, plugin payload and missing-resource inventory.
- `07_appendices/30_code_recipes.md` — короткие фрагменты и пошаговый порядок сборки новой реализации; фрагменты не являются полными файлами.
- `07_appendices/31_project_skills_catalog.md` — перечень архивированных навыков и правило приоритета актуальных спецификаций.
- `AGENTS.md` — master agent instructions, evidence rules and hackathon gate. [ПРОВЕРЕНО]
- `SKILL.md` — master-инструкция для агента, включая обязательную паузу до открытия хакатона. [ПРОВЕРЕНО]
- `skills/` — project-related skill Markdown and references; шесть helper scripts/templates сохранены фрагментами в `skills/_supporting_tools_in_markdown.md`, без исполняемых файлов. [ПРОВЕРЕНО: inventory]
- `evidence/` — оригинальные пользовательские JPG, три исходных headset log, UI icon PNG, font licenses и non-secret Unity package/build configs; копии побайтно идентичны источнику. [ПРОВЕРЕНО: hash manifest]

## Статусы достоверности

- `[ПРОВЕРЕНО]` — подтверждено текущим исходником, конфигурацией, фактическим выводом команды, HTTP-ответом или конкретным device log; источник указан рядом.
- `[ПРЕДПОЛОЖЕНИЕ]` — инженерная интерпретация, расчётная оценка или проектное предложение, которое ещё не подтверждено устройством.
- `[ТРЕБУЕТ ПРОВЕРКИ]` — неизвестный факт, аппаратный критерий, функциональность без прогона или требование без тестового результата.

Статус относится к конкретному утверждению, а не ко всему документу. Значения из исходников не следует автоматически считать подтверждёнными на Quest.

## Область достоверности и открытые входные данные

- APK 0.5.12 / versionCode 33 был успешно собран, проверен через `aapt2`, скачан обратно и SHA-256 совпал с опубликованным файлом. Это подтверждает артефакт, но не аппаратное поведение. [ПРОВЕРЕНО: build log 0.5.12; checksum `bf293ae0d066140d4903797a0a7f5a6dbea355721cf31b401079903c1d1ac307`]
- Последний фактически разобранный headset log содержит latest boot marker `app=0.5.8` от 2026-11-13; внутри него также сохранены более ранние сессии. [ПРОВЕРЕНО: `20261113-081211-pause.log`]
- APK 0.5.11/0.5.12 не подтверждены device log в текущем evidence snapshot. [ТРЕБУЕТ ПРОВЕРКИ]
- Точная версия Horizon OS/firmware, OpenXR runtime build, температура/частота GPU, длительность непрерывного скана и реальный FPS отсутствуют. [ТРЕБУЕТ ПРОВЕРКИ]
- Границы хакатонного MVP и дата последнего freeze не заданы в машинно-читаемом проектном документе. [ТРЕБУЕТ ПРОВЕРКИ]
- Продукционные токены, пароли, ключи и приватные env-значения намеренно не входят в архив. [ПРОВЕРЕНО: политика архива]
