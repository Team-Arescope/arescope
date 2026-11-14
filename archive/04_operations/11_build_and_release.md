# 11 · Сборка и выпуск

## Зафиксированный toolchain и артефакт

- Unity `6000.2.9f1`; официальный release page указывает дату 2025-10-22 и release ID `e0c4e791ab71`. [ПРОВЕРЕНО: страница Unity]
- RoomScan SDK: Git revision `4791b24b81015641d4cfb010a93c6283d4eb3dee`. [ПРОВЕРЕНО: `Packages/manifest.json`]
- Meta XR Core/MRUK `205.0.0`, AR Foundation `6.2.0`, OpenXR `1.15.1`, Input System `1.14.2`. [ПРОВЕРЕНО: `Packages/manifest.json` и `packages-lock.json`]
- Цель: Android ARM64, IL2CPP, minSdk API 29, Linear color space, package `in.arescope.beta02.questroom`. [ПРОВЕРЕНО: `BuildQuestAndroid.cs`]
- Последний записанный артефакт: `Arescope-Beta-0.5.12.apk`, versionName `0.5.12`, versionCode `33`, 62,819,774 bytes, SHA-256 `bf293ae0d066140d4903797a0a7f5a6dbea355721cf31b401079903c1d1ac307`. [ПРОВЕРЕНО: aapt2 + скачивание/hash]

## Сборочная машина и свободное место

- Сборки выполнялись в InstaBox `m_agqya3hdghwfljpea3rx6midke`, image `agent-browser`, 4 vCPU, 8 GiB RAM, persistent `/data` 20 GiB. [ПРОВЕРЕНО: конфигурация sandbox]
- Project path `/data/home/unity/arescope-beta02`; Unity path `/data/home/Unity/Hub/Editor/6000.2.9f1/Editor/Unity`. [ПРОВЕРЕНО: build recipe]
- Для чистой сборки требовалось около 8 GiB свободно; после прежних очисток фиксировалось около 10–11 GiB. Это плановое значение, а не гарантированный максимум. [ПРОВЕРЕНО: исторический вывод df]
- Android/Quest APK собирается в облачной sandbox; сборка на хосте запрещена проектным правилом. [ПРОВЕРЕНО: build constraint]

## Порядок сборки

Пример вызова (команда для повторного проекта; не исходный файл):

```bash
python3 ~/.hermes/skills/devops/instabox/scripts/instabox.py exec \
  'cd /data/home/unity/arescope-beta02 && /data/home/Unity/Hub/Editor/6000.2.9f1/Editor/Unity \
   -batchmode -quit -projectPath /data/home/unity/arescope-beta02 \
   -executeMethod BuildQuestAndroid.Build -logFile apk-build.log'
```

- После package cache re-resolve требуется повторно применить Unity 6000.2 compatibility edits и Arescope package bridges через `patch_roomscan_editor.py`; точное содержимое helper не включено, его поведение описано в разделе 16 и приложении 26. [ПРОВЕРЕНО: helper exists]; [ТРЕБУЕТСЯ: переносимый алгоритм helper ещё не полностью описан]
- Перед сборкой очищать только generated caches: `Library/Bee`, `Library/Artifacts`, `Library/BurstCache`, `Library/ShaderCache`, `Temp`, `obj`; Gradle transform/cache удалять только при подтверждённой ошибке. Сохранять Assets, Packages, ProjectSettings, сцены, Build artifact и staging copy вне project. [ПРОВЕРЕНО: build procedure]
- Не считать build успешным по exit code или последним строкам с SDL/ILPP. Обязательная строка: `QuestRoomScan build result: Succeeded; ... errors=0`. [ПРОВЕРЕНО: build history]
- При Gradle `IllegalArgumentException ... transforms/.../jdkImage` удаляется только Gradle transform cache; downloaded dependencies сохраняются. [ПРОВЕРЕНО: исторический сбой и успешное исправление]

## Проверки артефакта

1. `aapt2 dump badging` должен подтвердить package, ожидаемые version/versionCode, launcher `com.unity3d.player.UnityPlayerGameActivity` и ABI `arm64-v8a`. [ПРОВЕРЕНО: 0.5.12]
2. RoomScan Setup Wizard и texture refinement используют native xatlas; проверить наличие `lib/arm64-v8a/libxatlas.so` внутри APK. [ПРОВЕРЕНО: APK 0.5.12 содержит файл, 279,288 bytes; SHA APK подтверждён]; после следующей сборки повторить эту проверку.
3. SHA-256 APK, скачанного из sandbox, обязан совпасть с SHA-256 исходной сборки. [ПРОВЕРЕНО: 0.5.12]
4. Публикация: `publish-shared <apk> arescope/Arescope-Beta-<version>.apk --force`; затем скачать публичный URL и сверить SHA-256. [ПРОВЕРЕНО: повторённая процедура]
5. В релизной записи фиксировать source commit, Unity log, размер APK, вывод aapt2, source hash и hash публичной копии. [ПРЕДПОЛОЖЕНИЕ: архивная процедура]
6. Целостность APK не равна runtime-приёмке: успешная сборка не доказывает работу на Quest. [ПРОВЕРЕНО: build history]

## Известные ловушки

- Custom Android manifest заменяет Unity-generated manifest; он обязан сохранять launcher activity, MAIN/LAUNCHER/VR intent filter и нужные разрешения. [ПРОВЕРЕНО: manifest/build record]
- `com.unity.burst` ранее вызывал зависание IL2CPP на малой сборочной машине; наличие/отсутствие в текущем lockfile нужно сверить. [ПРОВЕРЕНО: исторический инцидент]; [ТРЕБУЕТ ПРОВЕРКИ: current lock]
- Meta OpenXR lifecycle feature должна быть включена; исторический ранний crash был вызван выключенным lifecycle feature. [ПРОВЕРЕНО: расследование]; текущую serialized feature проверить повторно. [ТРЕБУЕТ ПРОВЕРКИ]
- Unity может вывести Success при сломанном launcher manifest; `aapt2` gate обязателен. [ПРОВЕРЕНО: incident]
- Для RoomScan compatibility edits/patch bridges должны лежать в нужной package assembly; наличие patch-файла в проекте само по себе не означает, что он применён к build cache. [ПРОВЕРЕНО: сборочные ошибки]

## История релизов и headset evidence

| Версия | Code | SHA-256 | Headset evidence |
|---|---:|---|---|
| 0.5.6 | 27 | `3edb0094a0f68f1b2b643ed0ad37c609adf49e0fca6abc867431f00b88d11cb0` | [ТРЕБУЕТ ПРОВЕРКИ: точная привязка uploaded logs к APK hash отсутствует] |
| 0.5.7 | 28 | `8cb879e16927f843c5088c27d7ddf4a64d7923979df63573b350a53153a39760` | [ТРЕБУЕТ ПРОВЕРКИ] |
| 0.5.8 | 29 | `bb17a99d8021367a81c1ab89d7fb880c4299737d3c5bba7a2e2039965f7d1083` | [ПРОВЕРЕНО: boot marker app=0.5.8 в загруженном log от 2026-11-13; release hash device log не содержит] |
| 0.5.9 | 30 | `250fe25954436bfdd28034850d3581f8f820513057c13a35a23a3650893e6bc1` | [ТРЕБУЕТ ПРОВЕРКИ] |
| 0.5.10 | 31 | `c1f3ec58d8c61776422a5a83ca83477e94c67c5e04337882a237e32f2f9ff4c1` | [ТРЕБУЕТ ПРОВЕРКИ: нет boot marker 0.5.10 в uploaded log set] |
| 0.5.11 | 32 | `b91c2013ba2f5db3bbdb177746f0921237a5a886a9752289d269730bc5b12d99` | [ТРЕБУЕТ ПРОВЕРКИ] |
| 0.5.12 | 33 | `bf293ae0d066140d4903797a0a7f5a6dbea355721cf31b401079903c1d1ac307` | [ТРЕБУЕТ ПРОВЕРКИ: no later headset log in captured state] |
