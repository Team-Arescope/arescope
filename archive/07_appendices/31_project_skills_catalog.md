# 31 · Каталог архивированных навыков проекта

## Назначение

В `skills/` сохранены Markdown-документы локальных навыков Hermes, связанных с Arescope, Quest, VR, Unity, OpenXR, mesh/point rendering, headset build и LAB. Они фиксируют процедуры и опыт, но не заменяют спецификации настоящего архива. [ПРОВЕРЕНО: каталог навыков собран из локального profile]

## Состав

- Включены 14 project-relevant skill roots и 43 исходных Markdown-документа; `skills/README.md` описывает их состав и приоритет. [ПРОВЕРЕНО: inventory]
- Шесть поддерживающих `.py/.cs/.sh` скриптов/шаблонов сохранены как Markdown-фрагменты в `skills/_supporting_tools_in_markdown.md` (450 строк, блоки до 15 строк); они не сохранены как исполняемые source files. [ПРОВЕРЕНО: inventory/fence audit]
- Бинарные артефакты, caches и credentials намеренно исключены. [ПРОВЕРЕНО: inclusion filter]
- При поиске явных bearer/API-key шаблонов в скопированных skill Markdown совпадений не обнаружено; это не доказывает отсутствие всех возможных секретов. [ПРОВЕРЕНО: regex scan with stated scope]

## Скиллы

1. `skills/devops/arescope-beta02-build-loop/` — процедура сборки Arescope APK в InstaBox, проверки артефакта и очистки кэша.
2. `skills/devops/arescope-lab/` — процедуры LAB, device log, live scan feed, HUD, scene testing, stale-content audit и Quest integration.
3. `skills/devops/quest-xr-diagnostics/` — диагностика Quest XR/OpenXR/depth, renderer и finalization.
4. `skills/devops/unity-quest-xr-diagnostics/` — Unity Quest XR wiring and settings diagnostics.
5. `skills/quest-openxr-diagnostics/` — Quest OpenXR logs and failure triage.
6. `skills/quest-openxr-runtime-debugging/` — OpenXR runtime issues.
7. `skills/software-development/quest-scan-visualization/` — GPU mesh readback, point cloud and wireframe rendering guidance.
8. `skills/software-development/unity-quest-xr-wiring/` — Unity/Quest lifecycle and Meta XR wiring.
9. `skills/software-development/quest-world-space-hud/` — world-space HUD setup, following and preview.
10. `skills/devops/unity-android-headless-builds/` — headless Unity Android/Quest build procedures and Quest references.
11. `skills/devops/unity-android-build/` — Unity Android build and Quest debugging.
12. `skills/devops/unity-android-headless-build/` — separate headless build procedure.
13. `skills/software-development/unity-android-builds/` — Unity Android release/Quest references.
14. `skills/unity-headless-builds/` — Unity headless workflow and Quest depth references.

[ПРОВЕРЕНО: skill root inventory]

## Source precedence / safety

- Skill contents may contain historical values or claims predating the final source audit. [ПРОВЕРЕНО: skill/source comparison]
- For current parameters and discrepancies, prefer core docs, especially Apps 27–29; use skill docs for procedure, not as proof of runtime behavior. [ПРЕДПОЛОЖЕНИЕ: precedence rule]
- Implementation freeze: project implementation may begin only after the hackathon officially opens. [ПРОВЕРЕНО: explicit user instruction]; opening confirmation [ТРЕБУЕТ ПРОВЕРКИ]
