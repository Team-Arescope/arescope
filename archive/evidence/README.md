# Evidence directory

This folder contains copied evidence artifacts used by the archive. [ПРОВЕРЕНО]

## Screenshots

- `screenshots/` contains 11 unique user-submitted JPG files copied byte-for-byte from the session image cache; one duplicate image was excluded by SHA-256 comparison. No recompression, resizing, or enhancement was applied. [ПРОВЕРЕНО]
- Names use `<sha256-prefix>-<original-name>.jpg`; exact full hashes are in the archive-root `SHA256SUMS.txt`. [ПРОВЕРЕНО]
- Images document point/line mesh appearance and HUD values; they are qualitative visual evidence, not geometry ground truth. [ПРОВЕРЕНО: evidence type]

## Device logs

- `device_logs/` contains three original uploads from 2026-11-13: pause, combo and pause. They were copied without editing; hashes are recorded in `SHA256SUMS.txt`. [ПРОВЕРЕНО]
- Logs contain multiple concatenated app sessions; latest boot marker reports app `0.5.8`. Do not treat earlier entries in the same file as belonging to the latest app version. [ПРОВЕРЕНО: archived log boot lines]
- Logs include `token=yes` as a boolean credential-presence indicator; no token value was found in the inspected files. [ПРОВЕРЕНО: grep scan]

## Project reference assets

- `reference_assets/ArescopeIcons/` contains the six original 64×64 PNG icons from the project plus their Tabler MIT license file. They were copied byte-for-byte and are checksummed in archive-root `SHA256SUMS.txt`. [ПРОВЕРЕНО]
- Font license texts for Manrope and DM Mono are copied under `reference_assets/ArescopeFonts/`; font binaries themselves were absent from the inspected project and are not included. [ПРОВЕРЕНО: byte-identical license copies; font binary absence]
- No project source code or shader source is stored in `evidence/`. [ПРОВЕРЕНО: inventory]

- `reference_config/` contains byte-identical non-secret `Packages/manifest.json`, `Packages/packages-lock.json`, AndroidManifest and EditorBuildSettings snapshots. They are project configuration, not implementation source. SHA-256 values are in root `SHA256SUMS.txt`. [ПРОВЕРЕНО: hash/secret scan]

## Handling rules

- Keep evidence immutable; create annotations in a separate Markdown file. [ПРЕДПОЛОЖЕНИЕ: archive maintenance policy]
- Do not add bearer tokens, API keys, raw voice recordings, or personal identifiers. [ПРОВЕРЕНО: archive security policy]
- For new artifacts record date, APK SHA-256, device OS/runtime, capture conditions and source. [ПРЕДПОЛОЖЕНИЕ: evidence procedure]
