# 18 · Спецификация сцены, объектов и ресурсов

## Цель

Этот документ фиксирует минимальный набор Unity scene objects, зависимостей и ссылок для реконструкции клиентской сцены без копирования исходных файлов. [ПРОВЕРЕНО: состав зависит от review scene и wiring helper]

## Сцена и build inclusion

- Обзорная/релизная сцена указана как `Assets/Scenes/QuestRoomScan-REVIEW-ONLY.unity`. [ПРОВЕРЕНО: `WireArescopeScene.cs`, `ValidateArescopeScene.cs`]
- Build method включает все включённые `EditorBuildSettings.scenes`, путь которых содержит `QuestRoomScan`; валидация staging сцены выбирает `QuestRoomScan-REVIEW-ONLY.unity`. [ПРОВЕРЕНО: `BuildQuestAndroid.cs`, `ValidateArescopeScene.cs`]
- Exact scene YAML is intentionally not copied into archive; the following is a logical object inventory, not a Unity source dump. [ПРОВЕРЕНО: archive contains specification only]

## Scene graph

```text
QuestRoomScan-REVIEW-ONLY
├── RoomScan                         [RoomScanSession, RoomScanner, MeshExtractor, integration modules]
├── [BuildingBlock] Camera Rig       [OVRCameraRig]
│   ├── TrackingSpace
│   │   ├── CenterEyeAnchor           [Camera, MainCamera]
│   │   ├── LeftEyeAnchor             [stereo eye transform]
│   │   ├── RightEyeAnchor            [stereo eye transform]
│   │   ├── LeftControllerAnchor
│   │   └── RightControllerAnchor
├── [BuildingBlock] Passthrough       [OVRPassthroughLayer]
├── [BuildingBlock] Passthrough Camera Access [PassthroughCameraProvider]
├── AR Session                        [ARSession, AROcclusionManager]
└── ArescopeCopilot                    [AudioSource + Arescope components]
    ├── CopilotClient
    ├── ArescopeHudController
    ├── ViewModeController
    ├── CopilotHudBridge
    ├── ScanModeBridge
    ├── ScanProgressHud
    ├── LiveScanMinimap
    ├── LiveFrameSender
    ├── MeshUploader
    ├── ScanDiagnostics
    ├── ARSessionBootstrap
    ├── HudOverlay
    ├── HudContrast
    ├── LogUploader
    └── CopilotConnectionConfig
```

- `RoomScan`, `ArescopeCopilot`, camera rig, CenterEyeAnchor, passthrough camera access, passthrough layer, AR Session and controller anchors appear in serialized scene scan. [ПРОВЕРЕНО: scene text inspection]
- Exact hierarchy parenting, all component GUIDs and serialized field overrides should be recovered from Unity scene importer; the diagram is normalized logical hierarchy and may omit implementation-only GameObjects. [ПРЕДПОЛОЖЕНИЕ]
- `WireArescopeScene.Run()` — separate editor utility that adds and wires the listed components when invoked. [ПРОВЕРЕНО: helper source]
- `BuildQuestAndroid.Build()` does not invoke this utility; the current serialized scene contains only a subset of the helper-added components. [ПРОВЕРЕНО: build method and scene inspection; details in appendix 27]
- `ValidateArescopeScene.Run()` validates some required objects and selects the scene, but `BuildQuestAndroid.Build()` does not invoke it directly. [ПРОВЕРЕНО: source inspection]
- `ScanWireframe` и `LiveScanPoints` добавляются динамически в `ScanModeBridge.Awake()`; `ArescopeFrame` — static helper, отдельный scene component не нужен. [ПРОВЕРЕНО: source]
- `LiveScanMinimap` должен быть serialized component или явно добавляться; текущий `ScanModeBridge` только ищет его через `GetComponent`, а editor helper добавляет при запуске. Build entry point helper не вызывает, поэтому наличие в APK не доказано. [ПРОВЕРЕНО: source/static scene audit]; [ТРЕБУЕТ ПРОВЕРКИ: APK extraction]


## Required serialized references

| Component | Reference/setting | Required value or rule | Status |
|---|---|---|---|
| `ScanModeBridge` | headset camera | `OVRCameraRig.centerEyeAnchor` Camera | [ПРОВЕРЕНО: scene wiring helper] |
| `ScanModeBridge` | passthrough layer | scene `OVRPassthroughLayer` | [ПРОВЕРЕНО] |
| `ScanModeBridge` | HUD | `ArescopeHudController` | [ПРОВЕРЕНО] |
| `ScanModeBridge` | mode controller | `ViewModeController` | [ПРОВЕРЕНО] |
| `ViewModeController` | camera/passthrough/scan renderer | runtime scan geometry renderer or custom visual root; exact scene assignment unconfirmed | [ТРЕБУЕТ ПРОВЕРКИ] |
| `LiveScanMinimap` | HUD/headset transform | HUD and CenterEyeAnchor | [ПРОВЕРЕНО: scene wiring helper] |
| `LiveFrameSender` | headset transform | CenterEyeAnchor | [ПРОВЕРЕНО] |
| `ArescopeHudController` | target camera | center eye camera transform | [ПРОВЕРЕНО: scene wiring helper] |
| `CopilotClient` | AudioSource | same GameObject AudioSource | [ПРОВЕРЕНО] |
| `HudOverlay` | head camera | center eye camera | [ПРОВЕРЕНО] |
| `HudContrast` | HUD | ArescopeHudController | [ПРОВЕРЕНО] |
| `LogUploader` | HUD | ArescopeHudController | [ПРОВЕРЕНО] |

## Android manifest contract

- Required Android permissions: `INTERNET`, `RECORD_AUDIO`, `com.oculus.permission.USE_SCENE`, `com.oculus.permission.USE_ANCHOR_API`, `horizonos.permission.HEADSET_CAMERA`. [ПРОВЕРЕНО: `Assets/Plugins/Android/AndroidManifest.xml`]
- Launcher activity: `com.unity3d.player.UnityPlayerGameActivity`; intent filters include `MAIN`, `LAUNCHER`, `com.oculus.intent.category.VR`. [ПРОВЕРЕНО: manifest]
- Horizon OS manifest attributes: `horizonos:minSdkVersion=60`, `horizonos:targetSdkVersion=85`. [ПРОВЕРЕНО: manifest; platform policy compatibility must be checked at future rebuild]
- Build script separately sets Android minSdk API 29; this is not the same field as Horizon OS SDK min/target in manifest. [ПРОВЕРЕНО]

## Shader/material behaviour

- `Arescope/Wire` is an unlit transparent URP shader; Blend `SrcAlpha OneMinusSrcAlpha`, `ZWrite Off`, `Cull Off`. [ПРОВЕРЕНО: `Assets/Resources/ArescopeWire.shader`]
- `_UseVertexColor=1` causes incoming vertex color to modulate point tint; lines with no color data use material tint. [ПРОВЕРЕНО]
- Wire material defaults: line color `(0.93,0.54,0.36,0.25)`, point tint `(0.97,0.91,0.87,0.55)`; final point size input 0.006 m in `ScanWireframe`, live point component uses 0.0045 m. [ПРОВЕРЕНО: source defaults]
- Shader behavior in single-pass stereo/HDR is compile-tested by the build but not visually verified on Quest 3S. [ТРЕБУЕТ ПРОВЕРКИ]

## Resource files and identifiers

- Runtime token resource names: `arescope-live-token` and endpoint/config resource; exact file contents are secret-bearing and excluded. [ПРОВЕРЕНО: source references]
- Shader resource name `ArescopeWire`; resource path `Assets/Resources/ArescopeWire.shader`. [ПРОВЕРЕНО]
- A full asset manifest with GUIDs, package cache patch copies, textures, fonts, prefabs and scene references is absent. [ТРЕБУЕТСЯ: source-free recreation blocker]
