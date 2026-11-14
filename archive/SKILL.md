---
name: arescope-clean-room-archive
description: Use when continuing the Arescope Quest/LAB preliminary research archive. Check evidence first and do not start implementation until the hackathon officially opens.
---

# Arescope project archive skill

## Current standing

This archive is preliminary research and a clean-room reconstruction specification; it is not a guarantee that the current APK is complete or verified on device. [ПРОВЕРЕНО: QA/evidence status]

**Implementation gate:** do not create or modify the product implementation until the official hackathon opening is confirmed. Before then, restrict work to research, documentation, evidence checks, and explicitly approved planning. The opening announcement/date has not been verified in this archive. [ПРОВЕРЕНО: user instruction]; [ТРЕБУЕТ ПРОВЕРКИ: organizer announcement]

## Start here

1. Read `00_governance/00_index.md`.
2. Read `04_operations/16_reproduction_checklist.md` and `07_appendices/22_reconstruction_gaps.md`.
3. Before believing build behavior, inspect `07_appendices/27_scene_build_audit.md`; the Unity build entry point does not call the separate scene wiring helper, and the scene contains null/missing component references. [ПРОВЕРЕНО: static source audit]
4. Read `07_appendices/28_serialized_scene_parameters.md` for scene overrides; source defaults alone are insufficient. [ПРОВЕРЕНО]
5. Read the correct version row in `07_appendices/25_evidence_ledger.md`; latest uploaded boot marker identifies app 0.5.8, while 0.5.11/0.5.12 lack confirmed headset QA. [ПРОВЕРЕНО]
6. Use `07_appendices/30_code_recipes.md` only as short illustrative fragments; the archive intentionally has no complete project source files. [ПРОВЕРЕНО]
7. Project-specific procedural skill notes are under `skills/`; treat them as historical references and follow current architecture/evidence docs first. [ПРОВЕРЕНО]

## Evidence and claims

- Mark each technical statement `[ПРОВЕРЕНО]`, `[ПРЕДПОЛОЖЕНИЕ]`, or `[ТРЕБУЕТ ПРОВЕРКИ]`.
- Distinguish build success, package inspection and actual Quest runtime QA.
- Do not invent OS/runtime, FPS, thermal, battery, mesh-quality, upload-success or relocalization measurements.
- Keep tokens/keys out of documentation and artifacts.
- Preserve user screenshots, logs and licensed assets byte-for-byte; update `SHA256SUMS.txt` and verify before repackaging.

## Completion criterion

Do not report the recreation archive as fully self-sufficient until scene wiring, asset inventory, XR runtime settings, API/service setup and a clean-room build/headset test have been independently reproduced. [ПРОВЕРЕНО: open gates are listed in Appendices 22, 27–29]
