# Meta XR SDK на Linux-редакторе Unity

Проверено на Unity 6000.2.9f1 (Linux x86_64) и Meta XR SDK 81.0.0 / 83.0.4.
Цель: проект с `com.meta.xr.*` должен импортироваться в headless-редакторе.

## Симптомы и причины

| Сообщение в логе | Причина |
|---|---|
| `OVRManagerEditor.cs(403): error CS0103: The name 'manager' does not exist` | `OVRManager manager` объявлен внутри `#if UNITY_EDITOR_WIN \|\| UNITY_STANDALONE_WIN \|\| UNITY_EDITOR_OSX \|\| UNITY_STANDALONE_OSX \|\| UNITY_ANDROID`. На Linux ветка вырезается, а обращения ниже остаются. |
| `Installer.cs(88): error CS0103: The name 'downloadedInstallerPath' does not exist` | В `DownloadXRSimInstaller` путь объявлен только для `UNITY_EDITOR_WIN` и `UNITY_EDITOR_OSX`; на Linux переменной нет. |
| `Failed to resolve packages: ... manifest.json cannot be found` | Повреждён `Editor/Data/Resources/PackageManager` — ручная распаковка редактора или удаление каталога. Восстанавливать только из свежего архива. |
| `not a valid package tarball` | Встроенные пакеты редактора повреждены (оборванная загрузка или частичная распаковка). |
| `error while loading shared libraries: libembree.so.2` | В Debian 13 пакет называется `libembree4-4` и даёт `libembree4.so.4`; редактор ждёт `libembree.so.2`. |

## Порядок исправления

1. Убедиться, что версия редактора совпадает с `ProjectSettings/ProjectVersion.txt`.
2. Если версия Meta XR не собирается — понизить все `com.meta.xr.*` в
   `Packages/manifest.json` до версии с Linux-поддержкой (проверяются на
   `https://packages.unity.com/<package-name>`), удалить `Packages/packages-lock.json`.
3. Удалить кэш пакетов: `Library/PackageCache/com.meta.xr.*`.
4. Пропатчить кэш (после импорта пакетов он лежит в `Library/PackageCache/<pkg>@<hash>/`):
   - `OVRManagerEditor.cs`: добавить `|| UNITY_EDITOR_LINUX || UNITY_STANDALONE_LINUX`
     в условие объявления `OVRManager manager`;
   - `MetaXRSimulator/Installer.cs`: добавить `#else`-ветку, задающую
     `downloadedInstallerPath`.
5. Пересобрать ассеты: удалить `Library/ScriptAssemblies` и `Library/Bee`, повторить
   импорт `-batchmode -nographics -quit`.
6. **Закоммитить эти правки в репозитории проекта** (например, как скрипт, который
   применяет их к кэшу после резолва пакетов). Кэш пакетов пересоздаётся при каждом
   обновлении `packages-lock.json`, и незакоммиченный патч исчезает без предупреждения.

## Проверка

```bash
grep -c "error CS" <log>          # 0 — компиляция чистая
grep -c "Failed to resolve packages" <log>
ldd <Editor>/Unity | grep "not found"   # нативные библиотеки
```
