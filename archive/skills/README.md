# Project skill archive

## Purpose

Этот каталог хранит Markdown-документацию локальных навыков Hermes, которые использовались или создавались для Arescope/Quest/Unity/VR сборки, диагностики, HUD, mesh readback, LAB и OpenXR. Это справочные материалы, не кодовая база приложения. [ПРОВЕРЕНО: происхождение указано для каждого корня навыка]

## Inclusion rule

- Включены `SKILL.md` и связанные Markdown-файлы `references/` из 14 project-relevant skill roots; всего 43 исходных skill Markdown-файла. [ПРОВЕРЕНО: inventory source]
- Шесть вспомогательных `.py`, `.cs`, `.sh` инструментов/шаблонов сохранены как исходный текст внутри `skills/_supporting_tools_in_markdown.md`; каждый fenced code block не длиннее 15 строк, материал не является исполняемым файлом. [ПРОВЕРЕНО: fragment audit]
- Бинарники, credentials и caches из skill-каталогов не включены. [ПРОВЕРЕНО: inclusion filter]
- Четыре длинных fenced snippets в skill документации разделены на последовательные части, каждая часть не длиннее 15 строк; исходные смысловые строки сохранены, но фрагменты не гарантируются к копированию напрямую. [ПРОВЕРЕНО: split procedure]
- Skill-материалы исторические: в них могут быть старые значения, старый build flow или несовпадающие заявления о проверке. Текущим источником фактов являются core docs в `../00_governance/00_index.md`, `../07_appendices/27_scene_build_audit.md`, `../07_appendices/28_serialized_scene_parameters.md` и `../07_appendices/29_asset_manifest_spec.md`. [ПРОВЕРЕНО: archive precedence policy]
- Скилл не означает, что функция реализована, работает в release APK или прошла headset QA. Проверяй статус [ПРОВЕРЕНО]/[ТРЕБУЕТ ПРОВЕРКИ]. [ПРОВЕРЕНО: archive evidence rules]

## Included skill roots

1. `devops/arescope-beta02-build-loop/` — повторная сборка APK в InstaBox, artifact gates, cache cleanup.
2. `devops/arescope-lab/` — Arescope LAB, client/LAB integration, HUD, live ingest, testing; includes its Markdown references, excludes helper scripts/templates.
3. `devops/quest-xr-diagnostics/` — Quest crash/depth diagnostics and related references.
4. `devops/unity-quest-xr-diagnostics/` — Unity XR/OpenXR fault localization.
5. `quest-openxr-diagnostics/` — Quest XR runtime/log diagnostics.
6. `quest-openxr-runtime-debugging/` — broader OpenXR runtime troubleshooting.
7. `software-development/quest-scan-visualization/` — point-cloud and Surface Nets rendering guidance.
8. `software-development/unity-quest-xr-wiring/` — Unity/Quest XR setup constraints.
9. `software-development/quest-world-space-hud/` — world-space HUD implementation guidance.
10. `devops/unity-android-headless-builds/` — cloud/Unity Android build flow and Quest references.
11. `devops/unity-android-build/` — Android/Quest cloud build guidance.
12. `devops/unity-android-headless-build/` — headless Unity Android build guidance.
13. `software-development/unity-android-builds/` — Unity Android build and Quest streaming references.
14. `unity-headless-builds/` — headless Unity build and OpenXR depth guidance.

## How to use

1. Start with `../00_governance/00_index.md` for system scope and current evidence.
2. Read `../07_appendices/27_scene_build_audit.md` and `../07_appendices/28_serialized_scene_parameters.md` before following historical skill wiring claims.
3. Use the build-loop skill for artifact workflow only after resolving the documented scene-wiring gap.
4. Do not copy credential-bearing values from any source; no actual keys are intentionally archived.
5. Start new project implementation only after the hackathon has officially opened. The current archive is preliminary research and preparation, not authorization to begin implementation. [ПРОВЕРЕНО: user instruction]
