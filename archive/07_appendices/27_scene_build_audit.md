# 27 · Scene/build inclusion audit (static inspection)

## Scope

Это документальный аудит того, какие компоненты реально находятся в единственной включённой Unity scene и какие указаны только в editor helper. Он основан на статическом чтении текущей версии 0.5.12 source tree; фактический APK scene package отдельно не распаковывался для component enumeration. [ПРОВЕРЕНО: source inspection]; [ТРЕБУЕТ ПРОВЕРКИ: APK scene runtime]

## Build entry point

- `BuildQuestAndroid.Build()` фильтрует включённые `EditorBuildSettings.scenes` по пути, содержащему `QuestRoomScan`, затем передаёт их в `BuildPipeline.BuildPlayer`. [ПРОВЕРЕНО: `Assets/Editor/BuildQuestAndroid.cs`]
- `BuildQuestAndroid.Build()` не вызывает `WireArescopeScene.Run()` или `ValidateArescopeScene.Run()` явно. [ПРОВЕРЕНО: method body inspection]
- Поиск вызовов этих editor methods в `Assets/` на момент audit не нашёл вызывающего call site. [ПРОВЕРЕНО: source search]
- `EditorBuildSettings.asset` включает `Assets/Scenes/QuestRoomScan-REVIEW-ONLY.unity`. [ПРОВЕРЕНО]
- `WireArescopeScene.Run()` — отдельная editor utility; наличие utility-файла не доказывает, что она была запущена перед APK build. [ПРОВЕРЕНО]

## Serialized scene component inventory

### `RoomScan` GameObject

- `RoomScanSession`. [ПРОВЕРЕНО: scene YAML]
- `RoomUnderstanding`. [ПРОВЕРЕНО]
- `TextureRefinement`. [ПРОВЕРЕНО]
- `KeyframeCollector`. [ПРОВЕРЕНО]
- `PassthroughCameraProvider`. [ПРОВЕРЕНО]
- `RoomScanner`. [ПРОВЕРЕНО]
- `RoomAnchorManager`. [ПРОВЕРЕНО]
- `RoomScanPersistence`. [ПРОВЕРЕНО]
- `MeshExtractor`. [ПРОВЕРЕНО]
- `VolumeIntegrator`. [ПРОВЕРЕНО]
- `DepthCapture`. [ПРОВЕРЕНО]

### XR objects

- `[BuildingBlock] Camera Rig` with `OVRCameraRig`, CenterEyeAnchor tagged MainCamera and eye/controller transforms. [ПРОВЕРЕНО]
- `[BuildingBlock] Passthrough` with `OVRPassthroughLayer`. [ПРОВЕРЕНО]
- `[BuildingBlock] Passthrough Camera Access`. [ПРОВЕРЕНО]
- `AR Session` object. Presence of `ARSession`/`AROcclusionManager` must be confirmed by serialized component IDs; editor validation helper checks only ARSession-related integration at runtime. [ПРОВЕРЕНО: object name]; [ТРЕБУЕТ ПРОВЕРКИ: exact serialized component set]

### `ArescopeCopilot` object

Serialized components found: `AudioSource`, `CopilotClient`, `ArescopeHudController`, `ViewModeController`, `CopilotHudBridge`, `ScanModeBridge`, `CopilotConnectionConfig`, `Transform`. [ПРОВЕРЕНО: scene YAML component references]

Serialized overrides and references:

- `ScanModeBridge`: `modes` references ViewModeController; `hud` references HUD; camera reference targets scene camera; passthrough reference targets passthrough layer. [ПРОВЕРЕНО]
- `CopilotHudBridge`: controller value `5`, press threshold `0.75`, release threshold `0.35`; exact meaning of numeric controller value depends on enum/input mapping and should be verified against corresponding client source. [ПРОВЕРЕНО: serialized values]; [ТРЕБУЕТ ПРОВЕРКИ: semantic mapping]
- `ArescopeCopilot` scene `ViewModeController` fields `headsetCamera`, `passthroughLayer`, `scanRenderer` are serialized null. [ПРОВЕРЕНО: scene YAML]
- `WireArescopeScene.Run()` also does not call `ViewModeController.Configure(...)` or assign those three refs. [ПРОВЕРЕНО: helper body]
- `ScanModeBridge.ResetScan()` calls `modes.Switch(Passthrough)`; with those null refs the controller guard returns false and does not switch the layer. Unless another uninspected runtime path assigns them, reset may unload the scan without activating passthrough. [ПРОВЕРЕНО: source control flow]; [ТРЕБУЕТ ПРОВЕРКИ: actual APK execution]
- `ArescopeHudController`: target camera assigned; `worldCanvas` and `panel` references null; `followDistance=1.15 m`, smoothing `14`, mode `0`, canvas size `1.7×1.0`. [ПРОВЕРЕНО: scene YAML]
- Scene override `followDistance=1.15 m` differs from class default `0.62 m`; the scene value takes precedence unless a later build-time step modifies it. [ПРОВЕРЕНО: scene YAML/default]; [ТРЕБУЕТ ПРОВЕРКИ: build preprocessing]
- `CopilotClient`: serialized base URL `https://localhost`, bearer field empty; timeout 45 s, settings poll 30 s, max recording 60 s, max response 2,097,152 bytes, chat path `/api/copilot/chat`, sample rate 16,000 Hz; `AudioSource` assigned. [ПРОВЕРЕНО: scene YAML]
- `CopilotConnectionConfig` uses resource name `arescope-endpoint`; the resource content is not included because it may contain deployment configuration. [ПРОВЕРЕНО: scene YAML]; [ТРЕБУЕТ ПРОВЕРКИ: resource source]


## Components named in editor helper but absent from serialized scene

`WireArescopeScene.Run()` may add/wire `ScanProgressHud`, `LiveFrameSender`, `MeshUploader`, `ScanDiagnostics`, `ARSessionBootstrap`, `HudOverlay`, `HudContrast`, `LogUploader`, and `LiveScanMinimap`. The serialized scene component inventory does not show these on `ArescopeCopilot`. [ПРОВЕРЕНО: source helper vs scene YAML]

- Since BuildPlayer does not call the helper, current source alone does not prove those helper-added components are present in the APK scene. [ПРОВЕРЕНО: method call graph inspection]
- `ScanModeBridge.Awake()` dynamically adds `ScanWireframe` and `LiveScanPoints`, so those two components do not require serialized scene entries to exist after Awake. [ПРОВЕРЕНО: client source]
- `LiveScanMinimap`, `LiveFrameSender`, `MeshUploader`, `HudContrast`, `LogUploader`, and `ARSessionBootstrap` are not dynamically added in the scanned `ScanModeBridge`. If the utility has not run and the component is not in scene through another mechanism, the behavior is absent. [ПРОВЕРЕНО: source inspection]; [ТРЕБУЕТ ПРОВЕРКИ: built APK]

## Required clean-room correction before claiming reproducibility

1. Make build orchestration explicitly ensure/wire/validate the scene before `BuildPlayer`, or treat a committed scene manifest as the sole source of truth. [ПРЕДПОЛОЖЕНИЕ: recommended design]
2. Fill `ViewModeController` refs and align view-cycle enum with actual initial view after finalization/reset. [ТРЕБУЕТ ПРОВЕРКИ: implementation/test]
3. Enumerate scene component inventory from the actual 0.5.12 APK by manifest/asset extraction or Unity build report, not only from the editor source scene. [ТРЕБУЕТ ПРОВЕРКИ]
4. Record the effective HUD follow distance as 1.15 m unless the editor helper or another build-time step changes it. [ПРОВЕРЕНО: serialized scene; build-time rewrite search needed]
5. Run a headset smoke test proving LiveFrameSender, minimap, log uploader and HUD contrast are active. [ТРЕБУЕТ ПРОВЕРКИ]

**Impact on source-free recreation:** this audit is a blocking discovery. A future engineer needs the component list and exact scene wiring behavior, but the current archive identifies an unresolved integration gap instead of assuming every helper component is in the shipped APK. [ПРОВЕРЕНО: static audit result]
