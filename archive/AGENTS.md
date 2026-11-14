# Agent instructions for the Arescope archive

## Mission and status

- Treat this directory as a preliminary research/specification archive for rebuilding Arescope from a clean Unity project without importing original implementation source. [ПРОВЕРЕНО: archive scope]
- Do not interpret historical skills, APKs, screenshots or build-success messages as proof of current functionality; use the status labels and evidence ledger. [ПРОВЕРЕНО: evidence policy]
- The archive includes short illustrative code fragments only; it does not contain complete application source files. [ПРОВЕРЕНО: archive content]
- **Implementation gate:** do not begin creating or modifying the product project until the hackathon has officially opened. Until then, work is limited to research, archive documentation, evidence checks, and approved planning. The opening date/state has not been verified in this archive. [ПРОВЕРЕНО: explicit user instruction]; [ТРЕБУЕТ ПРОВЕРКИ: organizer announcement]

## Read order

1. `00_governance/00_index.md` — scope, evidence rules and map.
2. `01_scope/01_context.md`, `01_scope/02_requirements.md` — problem and acceptance criteria.
3. `02_research/03_research_platform.md` through `05_research_networking.md` — platform, reconstruction and network.
4. `03_design/06_architecture.md` through `10_server_design.md` — components, data, algorithms, client and server.
5. `04_operations/11_build_and_release.md` through `16_reproduction_checklist.md` — build, tests, metrics and gates.
6. `05_assurance/14_risks.md`, `00_governance/15_decision_log.md`, `06_reference/17_glossary_and_refs.md`.
7. `07_appendices/` and `skills/` — audits, source-derived parameters, code recipes and historical procedures.

## Hard rules

- Do not add complete Arescope application code files to this archive. Keep project implementation examples inside Markdown as short fragments (≤15 code lines per fenced block), signatures, pseudocode, schemas, and explicit assembly instructions.
- Tag each new technical assertion `[ПРОВЕРЕНО]`, `[ПРЕДПОЛОЖЕНИЕ]`, or `[ТРЕБУЕТ ПРОВЕРКИ]`; cite its source/evidence where possible.
- Do not invent firmware, runtime, performance or test results. If unobserved, write `данных нет` and give a verification condition.
- Distinguish source defaults, serialized scene overrides, server defaults, observed device values, targets and estimates.
- Do not copy tokens, signing keys, API credentials or private data into the archive. Re-scan any future additions for secrets.
- Preserve original screenshots, logs and licensed assets byte-for-byte; add hashes.
- After edits, regenerate `SHA256SUMS.txt`, verify all entries, package the ZIP, run the ZIP integrity check and compare public-download SHA-256 before reporting publication.
- Do not call this archive a completed implementation or fully reproducible release until the blockers below are closed.

## Current known blockers

- The inspected build method does not invoke `WireArescopeScene.Run()`, and the serialized scene has missing component references/components. Resolve intended scene-generation/build wiring before claiming feature parity. [ПРОВЕРЕНО: `07_appendices/27_scene_build_audit.md`]
- Scene `ViewModeController` camera/passthrough/renderer references are null; reset routes through this controller. [ПРОВЕРЕНО: scene audit]
- The latest uploaded device boot marker reports app `0.5.8`; 0.5.9–0.5.12 have no confirmed headset run in captured evidence. [ПРОВЕРЕНО: `07_appendices/25_evidence_ledger.md`]
- OpenXR runtime behavior, FPS/thermal/battery metrics and relocalization accuracy remain unmeasured. [ТРЕБУЕТ ПРОВЕРКИ]

## Output expectations

Only continue with documentation, research and evidence work until the official hackathon opening is confirmed. After opening, use the reproduction checklist, preserve the archive’s evidence/status rules, and verify each acceptance criterion before claiming completion.
