# 26 · Снимок исходных источников и связка версий

## Снимок репозиториев

| Источник | Revision / состояние | Что содержит | Статус |
|---|---|---|---|
| Unity Quest project `/root/Developer/arescope-beta02-questroom` | HEAD `eb66ec7aece61003e9bd11657a1f8178993b0160`; рабочее дерево было чистым при проверке | сцена клиента, Unity assets, build settings, patch scripts | [ПРОВЕРЕНО: вывод git]
| Arescope LAB `/root/Developer/arescope-lab` | HEAD `4b357af19c89d6268a7fd62069b1d2ecca569fdb` | FastAPI ingest/history/export/log API и static LAB | [ПРОВЕРЕНО: вывод git]
| Copilot source `/root/Developer/arescope-beta02-core` | git metadata отсутствует в проверенной директории | reference ASR/LLM/TTS protocol и auth | [ПРОВЕРЕНО: `git rev-parse` не нашёл git repo; копия не версионирована]
| RoomScan SDK | `4791b24b81015641d4cfb010a93c6283d4eb3dee` | depth integration, TSDF, Surface Nets, texture refinement | [ПРОВЕРЕНО: manifest + clone checkout]

## Пакетный контракт Unity

- Unity `6000.2.9f1`, release id `e0c4e791ab71`. [ПРОВЕРЕНО]
- `com.genesis.roomscan`: Git URL + pinned revision выше. [ПРОВЕРЕНО]
- `com.meta.xr.sdk.core=205.0.0`; `com.meta.xr.mrutilitykit=205.0.0`; `com.unity.xr.arfoundation=6.2.0`; `com.unity.xr.openxr=1.15.1`; `com.unity.inputsystem=1.14.2`. [ПРОВЕРЕНО: manifests]
- Модули Unity и дерево транзитивных зависимостей требуется зафиксировать по `packages-lock.json`; переустановка с более новым registry dependency не гарантирует воспроизводимость. [ПРЕДПОЛОЖЕНИЕ: правило package pinning]

## Карта релевантных файлов (только имена)

```text
Assets/Editor/BuildQuestAndroid.cs
Assets/Editor/WireArescopeScene.cs
Assets/Editor/ValidateArescopeScene.cs
Assets/Arescope/ScanModeBridge.cs
Assets/Arescope/ArescopeFrame.cs
Assets/Arescope/LiveScanPoints.cs
Assets/Arescope/LiveScanMinimap.cs
Assets/Arescope/ScanWireframe.cs
Assets/Arescope/LiveFrameSender.cs
Assets/Arescope/MeshUploader.cs
Assets/Arescope/LogUploader.cs
Assets/Arescope/ArescopeLog.cs
Assets/Arescope/HudContrast.cs
Assets/ArescopeClient/CopilotClient.cs
Assets/ArescopeHud/ArescopeHudController.cs
PackagePatches/ArescopeLiveCloud.cs
PackagePatches/ArescopeMeshExport.cs
PackagePatches/ArescopeTexturedMesh.cs
patch_roomscan_editor.py
```

[ПРОВЕРЕНО: имена файлов наблюдались в репозитории; это карта, не исходный код]

## LAB source и deployment

- API source: `/root/Developer/arescope-lab/app.py`; static frontend: `/root/Developer/arescope-lab/static/`. [ПРОВЕРЕНО]
- Deployed service: `/etc/systemd/system/arescope-lab.service`, systemd user `root`, cwd `/root/Developer/arescope-lab`, Uvicorn bind `127.0.0.1:18965`. [ПРОВЕРЕНО: systemctl unit]
- Последний проверенный DB путь `/var/lib/arescope-lab/live.sqlite3`; device logs `/var/lib/arescope-lab/logs/`; mesh dir default `/var/lib/arescope-lab/meshes`. [ПРОВЕРЕНО: source/default и исторические файлы]
- Copilot deployment path `/opt/arescope-copilot` inspected; точные unit/hash не вошли в snapshot. Нельзя считать local source равным production без хэш-сверки. [ПРОВЕРЕНО: git metadata и deployment hash отсутствуют]

## Release baseline

- Последний архивный client artifact: 0.5.12, versionCode 33, SHA-256 `bf293ae0d066140d4903797a0a7f5a6dbea355721cf31b401079903c1d1ac307`. [ПРОВЕРЕНО: aapt2 и public download hash]
- APK URL: https://shared.mrfenek.eu.cc/arescope/Arescope-Beta-0.5.12.apk. [ПРОВЕРЕНО: public HTTP 200 и byte/hash check]
- APK — только бинарный результат; он не заменяет assets, Unity project settings или лицензируемый package cache. [ПРОВЕРЕНО]
