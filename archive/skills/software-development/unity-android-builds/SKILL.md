---
name: unity-android-builds
description: "Build a Unity Android/Quest APK in a cloud sandbox."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [unity, android, quest, apk, openxr, meta-xr, sandbox, ci]
    related_skills: [instabox, daytona-sandboxes, agent-task-briefs, background-job-supervision]
---

# Сборка Unity APK для Android/Quest в облачной песочнице

## When to Use

Use when a Unity project must become an installable Android APK (Quest, standalone
VR, mobile) and the build has to run on a cloud Linux sandbox rather than on a
workstation with a GUI.

## Порядок работы

1. **Снять точные требования проекта.** Версия редактора — `ProjectSettings/ProjectVersion.txt`
   (`m_EditorVersion` + `m_EditorVersionWithRevision`). Версии Meta XR SDK — в
   `Packages/manifest.json`. Целевая платформа и идентификатор приложения — в
   `ProjectSettings/ProjectSettings.asset` (`AndroidTargetArchitectures`,
   `AndroidMinSdkVersion`, `applicationIdentifier`). Ставить **ровно ту версию
   редактора, что указана в проекте**: иначе Unity показывает диалог апгрейда,
   который в headless-сборке не пройти.

2. **Получить официальные URL, а не угадывать их.** Метаданные релиза:
   `https://services.api.unity.com/unity/editor/release/v1/releases?version=<VERSION>&limit=1`
   → `downloads[]` для `platform: LINUX, architecture: X86_64` и его `modules[]`
   (`android`, `android-open-jdk`, `android-sdk-ndk-tools`). Linux-Android-модуль
   часто отдаётся только как `.pkg` (xar) для macOS — его распаковывают вручную:
   `7z x` → `TargetSupport.pkg.tmp/Payload` → `bsdtar -xf Payload` → содержимое
   кладётся в `Editor/Data/PlaybackEngines/AndroidPlayer`.

3. **Учитывать место заранее.** Редактор с Android-модулем — около 15 ГБ, плюс
   распаковка и копирование модуля требуют временного запаса вдвое больше итогового.
   Скачивать в постоянный диск песочницы с докачкой (`curl -fL -C - --retry 8`), не в `/tmp`.

4. **Лицензия — отдельный человеческий шаг.** Unity Personal активируется входом в
   Unity Hub. Проверять результат по файлу
   `~/.config/unity3d/Unity/licenses/UnityEntitlementLicense.xml` и логу
   `Unity.Licensing.Client.log`. Пока файла нет, сборка невозможна — это блокер,
   а не повод перескакивать.

5. **Собирать скриптом, а не руками.** Положить в `Assets/Editor/` статический метод
   `Build()`: `BuildPipeline.BuildPlayer` со включёнными сценами из
   `EditorBuildSettings.asset`, `BuildTarget.Android`, `BuildOptions.Development`.
   Запуск: `Unity -batchmode -nographics -quit -projectPath <proj> -executeMethod <Class>.Build`.
   Для первого прогона — debug-подпись, `PlayerSettings.Android.targetArchitectures = ARM64`,
   `ScriptingImplementation.IL2CPP`, и **свой package id**, чтобы APK ставился рядом
   с оригиналом, а не заменял его.

6. **Проверять результат артефактом.** Успех — это файл APK нужного размера,
   открытый и пересобранный; сообщение сборки без файла успехом не считается.
   Дальше: установка на устройство, разрешения, фактический запуск, замер FPS и памяти.

## Pitfalls

- **Не вырезать каталоги редактора «на всякий случай».** Удаление
  `Editor/Data/Resources/PackageManager/Editor` ломает разрешение пакетов:
  `Failed to resolve packages: ... manifest.json cannot be found. No packages loaded.`
  Редактор перестаёт открывать проект. Если место поджимает, сначала убрать модули
  (WebGL Build Support ~7 ГБ, Documentation ~1.3 ГБ, Tools ~1.4 ГБ), а не системные
  ресурсы редактора.
- **Headless-импорт может падать в segfault** на встроенных инструментах, требующих
  GUI-библиотек (например, UV-распаковщик). Это падение окружения, а не ошибка
  проекта: включать графический режим через удалённый рабочий стол вместо того,
  чтобы чинить проект.
- **Недостающая системная библиотека** даёт `error while loading shared libraries`
  до запуска. Проверять `ldd <Unity> | grep "not found"` и доустанавливать пакет;
  если имя soname отличается от пакета (`libembree.so.2` против `libembree4-4`),
  делать symlink на актуальную версию.
- **Не считать, что установка в GUI-окне = работающая сборка.** Скриншот «установлено»
  говорит только о состоянии UI; проверять наличие каталога редактора, нужного модуля
  и файла лицензии.
- **Не смешивать версии.** Редактор, поставленный Unity Hub, и ручная распаковка
  официального архива — два разных пути; выбрать один и не оставлять вторую копию:
  иначе пути модулей, лицензии и `Library` расходятся.
- **Проверять целостность архива до распаковки** (`xz -t`, `unzip -t`): оборванная
  загрузка даёт «битый» архив, который распакуется частично и ломает сборку
  непонятной ошибкой.
- **Качать в постоянный диск, а не в `/tmp`.** На InstaBox `/tmp` — tmpfs всего 3.9 ГБ:
  переполнение обрывает-transfer, и файл выглядит «скачанным», но не проходит `xz -t`.
  Скачивать в `/data/...` с `curl -fL -C - --retry 8`, чтобы докачка продолжалась,
  а не начиналась заново.
- **Meta XR SDK не собирается на Linux-редакторе без вмешательства.** На проверенной
  версии 81.0.0 `OVRManagerEditor.cs` падает с `CS0103: The name 'manager' does not
  exist` — переменная объявлена под `UNITY_EDITOR_WIN/OSX/ANDROID`, а на Linux
  ветка вырезается. Более свежие версии падают иначе (`Installer.cs`:
  `downloadedInstallerPath` не объявлен вне `UNITY_EDITOR_WIN/OSX`). Рабочий путь:
  понизить версии `com.meta.xr.*` в `Packages/manifest.json`, удалить
  `packages-lock.json` и кэш пакетов, и пропатчить кэш (добавить
  `UNITY_EDITOR_LINUX` в условие объявления `OVRManager manager` и `#else`-ветку в
  `Installer.cs`). Патч должен лежать в репозитории проекта, иначе он исчезает при
  каждом пере-резолве пакета. Подробности — в
  `references/meta-xr-linux-editor.md`.
- **Ставить редактор и модуль одной командой Hub.** `--headless install-modules`
  требует `--version/-v`; без него выдаёт `Missing [-v|--version] argument`.
  Надёжнее `--headless install --version <ver> --changeset <hash> -m android --cm`:
  это кладёт редактор, Android-модуль и SDK/NDK/JDK туда, где их ждёт редактор.
  Ручная распаковка `.pkg` (см. пункт 2) даёт редактор без корректных встроенных
  пакетов — `not a valid package tarball` при разрешении пакетов.
- **Учитывать потолок диска провайдера до обещания сборки.** На бесплатном InstaBox
  `/data` жёстко 20 ГБ и не расширяется (`PATCH ... persistentDiskGiB` отвечает
  `400 spec_not_allowed` для free-машины); E2B Hobby даёт 10 ГБ диска и 1 час
  непрерывного запуска. 15–16 ГБ под редактор с Android-модулем — уже впритык,
  импорт проекта (`Library` ~2 ГБ) и сборка требуют запаса сверху.
- **Публичный API InstaBox ограничивает параллельные exec-вызовы** (не больше 32 на
  пользователя): при частых опросах получаешь `429 quota_exceeded` — это не поломка
  среды, а повод сократить частоту проверок.
- **Headless-сборка не видна в окнах.** Работа идёт через API, поэтому в удалённом
  рабочем столе нет ни одного окна Unity — пользователь не может отличить зависшую
  задачу от работающей. Каждый раз сообщать: что запущено, какой файл лога читать,
  и есть ли что-то видимое на экране.

## Supporting files

- `references/quest-live-stream.md` — протокол передачи point cloud и позы с Quest
  в веб-панель: формат кадра, роли отправителя и просмотра, отказоустойчивость.
