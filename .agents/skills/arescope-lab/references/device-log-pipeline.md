# Device log pipeline (Unity / Quest app)

Цель: один grep на прогон вместо 25 тысяч строк, и журнал, который переживает нативный краш.

## 1. В приложении

Один тег `[ARS]`, формат `[ARS] область | ключ=значение`. Области: `boot`, `xr`, `depth`, `scan`, `uplink`, `mesh`, `hud`.

```csharp
[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
static void Boot()
{
    Application.SetStackTraceLogType(LogType.Log, StackTraceLogType.None);
    Application.SetStackTraceLogType(LogType.Warning, StackTraceLogType.None);
    Application.SetStackTraceLogType(LogType.Error, StackTraceLogType.ScriptOnly);
    Info("boot", $"app={Application.version} unity={Application.unityVersion} " +
                 $"device={SystemInfo.deviceModel} os={SystemInfo.operatingSystem}");
}
```

Почему: `Debug.Log` по умолчанию тащит стектрейс, и каждая наша строка превращается в тридцать строк logcat. Снижение до `None` убирает шум, оставляя стек у ошибок.

**Файл-крошка.** Каждую строку дублировать синхронным `File.AppendAllText` в `Path.Combine(Application.persistentDataPath, "arescope-debug.log")`, с ротацией по ~512 КБ. При `SIGABRT` процесс умирает между кадрами, logcat может не успеть сбросить хвост, а файл на диске остаётся. Логирование оборачивать в `try/catch` — оно не имеет права ломать приложение.

**Сердцебиение.** Раз в секунду во время скана: `t`, `phase`, `progress`, `uplink`, наличие рендерера. Плюс одноразовая тревога, если через 8 с прогресс нулевой — со снимком состояния (`occlusion=running|no-subsystem`, `depthMode`, `arSession`, `scanner`, `xr=active`).

Событийные точки: старт приложения, запрос `StartScanAsync` и время ответа, реальный `scanning` после ответа, финализация с числом вершин, исключение с типом, сообщением и первой значимой строкой стека.

## 2. Сбор

```sh
adb logcat -c
adb shell am start -n <pkg>/com.unity3d.player.UnityPlayerGameActivity
# воспроизвести, затем
adb logcat -d -v time > logcat.txt
adb logcat -b crash -d > crash.txt
adb shell dumpsys package <pkg> > package.txt
adb pull /sdcard/Android/data/<pkg>/files/Player.log .
adb pull /sdcard/Android/data/<pkg>/files/arescope-debug.log .
```

Скриншот снимать только через файл на устройстве:

```sh
adb shell screencap -p /sdcard/hud.png && adb pull /sdcard/hud.png hud.png
```

`adb exec-out screencap -p > hud.png` в PowerShell портит PNG: перенаправление работает как текстовая перекодировка.

## 3. Чтение

```sh
# PowerShell пишет UTF-16LE, iconv обязателен до любого grep
iconv -f UTF-16LE -t UTF-8 logcat.txt > log.txt
grep "\[ARS\]" log.txt
grep -E "\[RoomScan\]|Scan failed:|FATAL|SIGABRT|libc\+\+abi" log.txt
```

В PowerShell-скрипте писать логи сразу в UTF-8: `adb logcat -d -v time | Out-File -FilePath $log -Encoding utf8`, а не через `>`.

## 4. Таблица решений

| Что видно | Что это значит |
|---|---|
| нет ни одной `[ARS] boot` | приложение умерло до управляемого кода: нативная инициализация OpenXR или линковка |
| есть `[ARS] boot`, дальше пусто | сцена или XR-лоадер падают до `Start()` скриптов |
| `xr \| occlusion=no-subsystem` | подсистема глубины не создана: нет провайдера (см. `quest-depth-openxr.md`) |
| `scan \| progress=0%` несколько тиков подряд | скан идёт, но интеграция глубины не даёт кадров |
| `scan \| uplink=none` | кадры не уходят на сервер: токен, сеть или эндпоинт |
| сердцебиение оборвалось на полуслове | нативный краш; последняя строка файла-крошки — точка смерти |

## 5. Ловушки

- **Кольцевой буфер logcat.** Прогон длиннее пары минут затирает начало; `adb logcat -c` перед запуском и забирать сразу после.
- **`HEAD` на shared host отвечает 403** — это не недоступность, проверять артефакты ranged `GET`.
- **`pm grant` для `com.oculus.*` часто отвечает `not a changeable permission type`** — такие разрешения выдаются в приложении, а не через ADB.
- **Не грепать по словам вроде `Permission` без привязки к пакету**: в системном буфере десятки чужих отказов, они выглядят как наши.
