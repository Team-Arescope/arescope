# Архив Arescope

Входная точка: `00_governance/00_index.md`. [ПРОВЕРЕНО: файл создан]

Архив содержит 18 основных разделов, 14 инженерных спецификаций, 43 архивированные Markdown skills и evidence. [ПРОВЕРЕНО: manifest/inventory]

- `00_governance/` — индекс и ADR.
- `01_scope/` — контекст и требования.
- `02_research/` — платформа, сканирование, networking.
- `03_design/` — архитектура, контракты, алгоритмы, клиент, сервер.
- `04_operations/` — сборка, тесты, измерения, воспроизведение.
- `05_assurance/` — риски.
- `06_reference/` — глоссарий и источники.
- `07_appendices/` — scene/assets, voice, runtime components, server config, reconstruction gaps, TSDF/Surface Nets, HUD, evidence ledger, source snapshot, serialized scene parameters, build-scene audit, asset manifest, code recipes and skill catalog.
- `AGENTS.md` — master agent instructions: preliminary research status, read order, evidence rules and implementation gate. [ПРОВЕРЕНО]
- `SKILL.md` — master skill guide for the archive and the hackathon implementation gate. [ПРОВЕРЕНО]
- `skills/` — 43 project-relevant skill/reference Markdown files; six supporting scripts/templates are preserved as ≤15-line Markdown code fragments in `skills/_supporting_tools_in_markdown.md`, not as executable files. [ПРОВЕРЕНО]
- `evidence/` — оригинальные скриншоты, headset logs, UI icons, лицензии и non-secret package/build configs; бинарные файлы сохранены побайтно, implementation source не включён. [ПРОВЕРЕНО]
- `SHA256SUMS.txt` — хэши Markdown и evidence-файлов. [ПРОВЕРЕНО: sha256 verification]

Полное воспроизведение исходного APK по одним документам пока невозможно: недостающие входные материалы перечислены в `04_operations/16_reproduction_checklist.md`. Функциональный эквивалент можно проектировать по спецификациям, но часть платформенных параметров и аппаратных результатов должна быть измерена заново. [ПРОВЕРЕНО: исходный Unity project и keystore не включены; см. reconstruction gaps]

## Статус и ограничение старта

Это **предварительный технический ресерч и проектная спецификация**, а не подтверждённый релиз или готовый продукт. [ПРОВЕРЕНО: аппаратная матрица QA не закрыта]

Создание/изменение проектной реализации разрешено начинать **только после официального открытия хакатона**. До подтверждения открытия допустимы только анализ, уточнение архива и подготовка документации. Дата/подтверждение открытия в архиве не зафиксированы. [ПРОВЕРЕНО: прямое требование пользователя]; [ТРЕБУЕТ ПРОВЕРКИ: объявление организаторов]

