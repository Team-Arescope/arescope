# On-device debugging for Quest builds

Use when an APK installs on a Quest headset but crashes, hangs on a loading view, or scans/streams nothing. The goal is evidence that separates "the build is wrong", "XR never started" and "one feature misbehaves" without guessing.

## 1. Capture discipline

```sh
adb logcat -c
adb shell am start -n <package>/com.unity3d.player.UnityPlayerGameActivity
adb logcat -v time > run.txt        # Ctrl+C after reproducing
adb logcat -b crash -d > crash.txt
adb pull /sdcard/Android/data/<package>/files/Player.log
```

Per-process capture is quieter and avoids an unbounded system buffer:

```sh
PID=$(adb shell pidof -s <package>)
adb logcat -d -v time --pid=$PID > run.txt
```

Ask for the app version in the very first log line (see §3). Without it you cannot prove which APK produced the log, and every later conclusion is suspect.

## 2. Encoding traps that make a correct log look empty

- PowerShell `adb logcat > run.txt` writes **UTF-16LE**. `grep` then reports zero matches on text that is present. Convert first: `iconv -f UTF-16LE -t UTF-8 run.txt > run8.txt`, or have the capture script use `| Out-File -Encoding utf8`.
- `adb exec-out screencap -p > shot.png` corrupts the PNG in PowerShell because redirection is text-mode. Take it on the device and pull it: `adb shell screencap -p /sdcard/s.png; adb pull /sdcard/s.png`.
- A log that contains system lines from many PIDs but none from your package usually means the app died before managed logging, not that logging is broken.

## 3. In-app logging that survives a native abort

Default Unity logging is unusable on device: every `Debug.Log` drags a ~30-line stack trace into logcat.

- Silence stacks once at boot:
  `Application.SetStackTraceLogType(LogType.Log, StackTraceLogType.None)` and the same for `Warning`; keep `ScriptOnly` for `Error`.
- Emit one line per event under a single tag with `area | key=value` shape, e.g. `[ARS] scan | t=12s phase=Scanning progress=41% uplink=200/2s/stored`. One grep then reads the whole run.
- Mirror every line to `Application.persistentDataPath/<app>-debug.log`, appending and flushing per write, rotating at a few hundred KB. This file survives `SIGABRT` and is the only evidence when the process dies in native code.
- Log a boot snapshot in `[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]`: app version, Unity version, device model, plus `XRSettings.isDeviceActive`, whether the session/occlusion subsystems exist, and whether the scanner component resolved.
- While a long operation runs, log a one-second heartbeat (elapsed, phase, progress, last uplink status). Add a warning when progress is still zero after ~8 s, with the full XR snapshot in the message.
- Log exceptions with type, message and the **first** managed frame — not the whole chain.

## 4. Horizon OS permissions

Read them from the built APK, never from memory: `aapt2 dump permissions Build/<app>.apk`. The Quest set used by room-scanning apps:

- `android.permission.RECORD_AUDIO`
- `android.permission.CAMERA`
- `horizonos.permission.HEADSET_CAMERA`
- `com.oculus.permission.USE_SCENE`
- `com.oculus.permission.USE_ANCHOR_API`

The `com.oculus.*` entries are frequently **not** grantable with `adb shell pm grant` (`not a changeable permission type`); they are confirmed in-app on first launch. `horizonos.*` is grantable. Write the exact names into runbooks only after checking the APK, because `horizonos.permission.USE_SCENE` is a plausible-looking name that does not exist.

## 5. Symptom → cause

| Symptom in the log | Cause | Check |
|---|---|---|
| `DllNotFoundException: Unable to load DLL '<lib>'` | Native plugin not packaged | `unzip -l app.apk | grep <lib>.so`; if absent, copy into `Assets/Plugins/Android/arm64-v8a/` and rebuild |
| `No active XR loader`, own snapshot shows `xr=inactive`, endless loading view | XR auto-loading disabled | `m_AutomaticLoading` / `m_AutomaticRunning` in `Assets/XR/XRGeneralSettingsPerBuildTarget.asset` |
| `libc++abi: terminating` + `SIGABRT` right after `xrCreateInstance`, no managed lines at all | Native failure during loader/first subsystem creation | Verify required `.so` files are in the APK before touching feature flags |
| `occlusion=no-subsystem`, `frames=0, depthAvail=False`, `sub=null` | Depth provider absent or its plugin missing | Plugin packaged? Environment-depth feature enabled? |
| Scanning starts, `progress` stays 0 %, meshing empty, finalize throws `NullReferenceException` in the occlusion manager | No depth frames ever arrived | Same as above; the NRE is a downstream symptom, not the bug |
| `MRUK LoadSceneFromDevice ... result=NotInitialized` | XR session never came up | Loader state first |

## 6. Bisection etiquette

Bisect feature flags only after §5's first three rows are cleared. One variable per build, keep the previous APK published as a rollback, and name the build by what changed (`only session + occlusion enabled`) so the log-to-build mapping stays obvious. Two consecutive crashes with the same native signature usually mean the variable you toggled is unrelated to the cause.
