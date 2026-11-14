# 29 · Каталог ресурсов и лицензий

## Назначение

Файл описывает ресурсы, которые должны существовать в функционально эквивалентном проекте. Он перечисляет наблюдаемые каталоги/размеры, но не содержит бинарные исходники самого Unity-проекта. [ПРОВЕРЕНО: archive contains specs/evidence only]

## Scene files

| Scene | Размер | Функция/статус |
|---|---:|---|
| `Assets/Scenes/QuestRoomScan-REVIEW-ONLY.unity` | 50,171 bytes | единственная включённая Android scene согласно `EditorBuildSettings.asset` [ПРОВЕРЕНО] |
| `Assets/Scenes/SimRoom.unity` | 280,665 bytes | simulator/testing scene; не входит в Android build selection по `BuildQuestAndroid` path filter [ПРОВЕРЕНО: scene list + build method]
| `Assets/Scenes/SimMars.unity` | 9,506,034 bytes | simulator/testing scene; не входит в Android build selection по тому же фильтру [ПРОВЕРЕНО]

## Explicit project resources

| Resource | Path/presence | Observed properties | Status |
|---|---|---|---|
| Wire shader | `Assets/Resources/ArescopeWire.shader` and duplicate `Assets/Arescope/Shaders/ArescopeWire.shader` | Unity shader name `Arescope/Wire`; transparent URP | [ПРОВЕРЕНО]
| Scan/depth/link/power/voice/dot icons | `Assets/Resources/ArescopeIcons/*.png`; copies preserved at `evidence/reference_assets/ArescopeIcons/` | each 64×64 RGBA PNG; copied byte-identically | [ПРОВЕРЕНО: `file` output + SHA256SUMS] |
| Icon license | `Assets/Resources/ArescopeIcons/LICENSE-Tabler-MIT.txt`; copy preserved alongside icons | Tabler MIT license file present | [ПРОВЕРЕНО: file content/existence] |
| Manrope-SemiBold font | `.meta` exists, `.ttf` missing; `Manrope-OFL.txt` license copy preserved in evidence/reference_assets/ArescopeFonts | HUD resource loader falls back to built-in font if resource missing | [ПРОВЕРЕНО: filesystem + HUD source + copied license]
| DMMono-Medium font | `.meta` exists, `.ttf` missing; `DMMono-OFL.txt` license copy preserved in evidence/reference_assets/ArescopeFonts | HUD resource loader falls back to Manrope, then Unity built-in if unavailable | [ПРОВЕРЕНО: filesystem + HUD source + copied license]
| Небинарные файлы конфигурации | `evidence/reference_config/` | копии `Packages/manifest.json`, `Packages/packages-lock.json`, `AndroidManifest.xml`, `EditorBuildSettings.asset`; SHA в корневом манифесте | [ПРОВЕРЕНО: побайтное совпадение и scan secrets] |
| Endpoint resource | `Assets/Resources/arescope-endpoint.txt` | file size 172 bytes at inspection; content intentionally not copied because deployment-specific | [ПРОВЕРЕНО: file metadata]; exact endpoint mapping [ТРЕБУЕТ ПРОВЕРКИ]
| Producer token resource | `Assets/Resources/arescope-live-token.txt` | file size 43 bytes at inspection; secret content excluded | [ПРОВЕРЕНО: metadata]; token value not archived
- RoomScan Setup Wizard checks for Android plugin at `Packages/com.genesis.roomscan/Runtime/Plugins/Android/libxatlas.so` and can build it from package `Native/xatlas` sources using the Unity Android NDK. [ПРОВЕРЕНО: pinned `RoomScanSetupWizard.cs`]
- Recorded Android plugin compiler flags: `-shared -O2 -fPIC -std=c++11 -fvisibility=hidden`; exact NDK clang executable selected through Unity `AndroidExternalToolsSettings.ndkRootPath`. [ПРОВЕРЕНО: pinned SDK source]
- `Assets/Plugins/Android/arm64-v8a/libxatlas.so.meta` exists but the matching native binary was not found under Assets. This does not prove it is absent from package cache or APK. [ПРОВЕРЕНО: filesystem search]; [ТРЕБУЕТ ПРОВЕРКИ: APK contents]

## Resources delivered by Unity package cache

- RoomScan shader/compute/material assets are provided through package `com.genesis.roomscan` at the pinned Git revision; they are not all stored under `Assets/`. [ПРОВЕРЕНО: manifest and package source tree]
- Exact set of package `.compute`, shader, material and internal resource dependencies needed by the Android player has not been exported into a standalone dependency manifest. [ТРЕБУЕТСЯ]
- Meta XR package assets and native binaries are resolved from package lock and Meta package cache; complete binary redistribution/licensing is not established by this document. [ПРОВЕРЕНО: package dependency]; [ТРЕБУЕТ ПРОВЕРКИ: license/export terms]

## Clean-room asset recreation rules

1. Recreate icon/UI assets from specifications or obtain source assets under documented licenses; preserve dimensions and alpha channel for the six observed 64×64 icons. [ПРЕДПОЛОЖЕНИЕ: reimplementation instruction]
2. Either restore Manrope SemiBold and DM Mono Medium font files with license notices or document and test the built-in fallback; do not leave only `.meta` references. [ПРОВЕРЕНО: current missing-file state]; [ПРЕДПОЛОЖЕНИЕ: recovery choice]
3. Generate endpoint config at build/deployment time and inject revocable producer credentials via secure process; do not copy values from the original resource file. [ПРОВЕРЕНО: secret policy]
4. Confirm native plugin `libxatlas.so` inside APK using `unzip -l` or equivalent; a `.meta` file alone is not the library. [ПРОВЕРЕНО: build gate requirement]
5. Create an asset inventory with path, Unity GUID, content SHA-256, source/license, import settings and runtime role. [ПРЕДПОЛОЖЕНИЕ: required reproducibility artifact]

## Known asset blockers

- Font `.ttf` payloads are missing from the inspected local source tree while `.meta` files exist. [ПРОВЕРЕНО]
- `libxatlas.so` отсутствовал в локальном Assets tree, но inspected APK 0.5.12 содержит `lib/arm64-v8a/libxatlas.so` размером 279,288 bytes. [ПРОВЕРЕНО: `unzip -l` по APK; SHA-256 `bf293ae0d066140d4903797a0a7f5a6dbea355721cf31b401079903c1d1ac307`]
- Это подтверждает упаковку native plugin только для APK 0.5.12; следующую сборку нужно проверить повторно. [ПРОВЕРЕНО/ТРЕБУЕТ ПРОВЕРКИ]
- No material/prefab/compute files were found under the searched Assets root during the inventory pass; package cache assets are therefore a necessary source dependency. [ПРОВЕРЕНО: search result]; package cache inventory is incomplete.
