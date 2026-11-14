# 28 · Сериализованные параметры RoomScan и сцены

## Назначение и precedence

- Этот документ перечисляет значения, сериализованные непосредственно в `QuestRoomScan-REVIEW-ONLY.unity`; они имеют приоритет над C# field initializer defaults, если объект сцены загружен из этого файла. [ПРОВЕРЕНО: Unity serialization semantics; scene YAML]
- Числа ниже сняты из текущего review scene; они не доказывают, что конкретный опубликованный APK был собран именно из этой неизменённой сцены. [ПРОВЕРЕНО: источник scene]; [ТРЕБУЕТ ПРОВЕРКИ: artifact-to-scene provenance]
- Значения полей, отсутствующих в scene YAML, берутся из pinned SDK component defaults либо property defaults; каждый такой default следует отдельно сверить по соответствующему field. [ПРОВЕРЕНО: Unity serialization rule]; [ТРЕБУЕТ ПРОВЕРКИ: per-field audit]

## Camera/provider/keyframe settings

| Component | Serialized field | Value | Status |
|---|---|---:|---|
| PassthroughCameraProvider | cameraPosition | 0 | [ПРОВЕРЕНО: scene YAML; enum meaning requires enum lookup] |
| PassthroughCameraProvider | requestedResolution | 1280 × 960 | [ПРОВЕРЕНО] |
| PassthroughCameraProvider | maxFramerate | 30 fps | [ПРОВЕРЕНО] |
| KeyframeCollector | moveThreshold | 0.15 m | [ПРОВЕРЕНО] |
| KeyframeCollector | rotateThresholdDeg | 10° | [ПРОВЕРЕНО] |
| KeyframeCollector | bandGapM | 0.5 m | [ПРОВЕРЕНО] |
| KeyframeCollector | standingYawDeg | 8° | [ПРОВЕРЕНО] |
| KeyframeCollector | jpegQuality | 95 | [ПРОВЕРЕНО] |
| KeyframeCollector | maxAngularVelocity | 120 | [ПРОВЕРЕНО: unit in field name/value likely degrees/sec but should confirm] |
| KeyframeCollector | minCaptureInterval | 0.25 s | [ПРОВЕРЕНО] |
| KeyframeCollector | maxHandCoverage | 0.12 | [ПРОВЕРЕНО: unitless fraction per field semantics] |

## RoomScanner and MeshExtractor

| Component | Field | Value | Operational meaning | Status |
|---|---|---:|---|---|
| RoomScanner | integrationHz | 30 Hz | requested volume integration cadence | [ПРОВЕРЕНО: serialized value; effective device cadence unmeasured] |
| RoomScanner | meshExtractionHz | 8 Hz | live mesh extraction cadence | [ПРОВЕРЕНО: serialized value; effective device cadence unmeasured] |
| RoomScanner | renderMode | 0 | SDK rendering mode enum; exact enum mapping must be recovered | [ПРОВЕРЕНО: value]; [ТРЕБУЕТ ПРОВЕРКИ: enum meaning]
| RoomScanner | wireThickness | 1.5 | SDK wireframe rendering parameter | [ПРОВЕРЕНО]
| RoomScanner | showFreezeTint | true | frozen geometry tint | [ПРОВЕРЕНО]
| RoomScanner | logLevel | 1 | SDK log level enum | [ПРОВЕРЕНО: value]; [ТРЕБУЕТ ПРОВЕРКИ: enum meaning]
| RoomScanner | confineScanToContainingRoom | false | scan confinement flag | [ПРОВЕРЕНО]
| RoomScanner | stampScreenPlanes | true | screen-plane stamping feature | [ПРОВЕРЕНО]
| RoomScanner | showSceneObjects | false | SDK scene object visualization | [ПРОВЕРЕНО]
| MeshExtractor | meshSmoothIterations | 1 | smoothing pass count | [ПРОВЕРЕНО]
| MeshExtractor | meshSmoothLambda / meshSmoothBeta | 0.33 / 0.5 | Laplacian/HC smoothing factors | [ПРОВЕРЕНО]
| MeshExtractor | temporalAlphaMax / Min | 0.85 / 0.1 | temporal blend range | [ПРОВЕРЕНО]
| MeshExtractor | temporalDecayRate | 0.15 | temporal alpha decay | [ПРОВЕРЕНО]
| MeshExtractor | convergenceThreshold | 0.005 m | displacement threshold | [ПРОВЕРЕНО]
| MeshExtractor | temporalDeadzone | 0.001 m | suppressed motion threshold | [ПРОВЕРЕНО]
| MeshExtractor | birthFadeSeconds / birthGrowMetres | 1 s / 0.08 m | live-mesh birth animation | [ПРОВЕРЕНО]
| MeshExtractor | meshMorphSeconds | 0.28 s | live mesh morph transition | [ПРОВЕРЕНО]
| MeshExtractor | gpuVertexBudgetPercent | 0.08 | max vertex budget as fraction of voxel count | [ПРОВЕРЕНО]

## VolumeIntegrator serialized values

- Voxel count is not serialized in the inspected scene block; pinned SDK field default is `256×256×256`. [ПРОВЕРЕНО: SDK default; [ТРЕБУЕТ ПРОВЕРКИ] scene runtime value if script-generated]

| Field | Value |
|---|---:|
| voxelSize | 0.05 m |
| voxelDistance | 0.15 m |
| voxelMin | 0.1 |
| depthDisparityThreshold | 0.5 |
| maxUpdateDist | 5 m |
| minUpdateDist | 0.5 m |
| maxFrustumPositions | 1,000,000 |
| blendRate | 0.8 |
| stability | 2.5 |
| weightGrowth | 0.025 |
| maxWeight | 0.5 |
| minMeshWeight | 0.08 |
| cameraExposure | 3.0 |
| warmupIntegrations | 3 |
| torsoRadius / torsoAbove / torsoBelow | 0.35 m / 0.25 m / 1.7 m |
| handRadius / handHalfLength | 0.14 m / 0.08 m |
| forearmRadius / forearmLength | 0.08 m / 0.28 m |
| shoulderDrop / shoulderLateral | 0.2 m / 0.2 m |
| eraseBodyBlobs | false |
| eraseMaxWeight | 0.2 |
| autoFillShellGaps | true |
| fillMaxCells | 6 |
| fillWeight | 0.15 |
| fillNeighborSpreadMax | 0.06 |
| fillMaxPerTick | 8 |
| closeFurnitureHoles | true |
| pruneIntervalSeconds | 3 s |
| analysisIntervalSeconds | 1 s |
| confidentWeight | 0.2 |
| refinementSaturation | 0.85 |
| refinementInfluence | 0.4 |
| holeMinAreaM2 | 0.01 |
| fillLeaks | true |
| fillLeakMaxAreaM2 | 0.25 |
| cutToleranceVoxels | 2 |
| fineFloodDispatchesPerFrame / fineFloodFrames | 2 / 3 |
| closureLinkRounds | 12 |
| freezeConeHalfAngle | 15° |

All values above are scene YAML serialization observations. [ПРОВЕРЕНО: scene file]
Unit/semantics of thresholds not obvious from field name require corresponding SDK source documentation before porting. [ТРЕБУЕТ ПРОВЕРКИ]

## DepthCapture serialized values

| Field | Value | Status |
|---|---:|---|
| enableBilateralFilter | true | [ПРОВЕРЕНО] |
| sigmaSpatial | 3 | [ПРОВЕРЕНО] |
| sigmaColor | 0.1 | [ПРОВЕРЕНО] |
| sigmaDepth | 0.02 | [ПРОВЕРЕНО] |
| filterRadius | 2 | [ПРОВЕРЕНО] |
| dilationSteps | 8 | [ПРОВЕРЕНО] |
| voxelDistance | 0.2 | [ПРОВЕРЕНО: component override differs from VolumeIntegrator 0.15 m]
| voxelSize | 0.05 m | [ПРОВЕРЕНО] |
| removeHandsFromDepth | true | [ПРОВЕРЕНО] |

## HUD/Copilot scene overrides

- `ArescopeHudController.followDistance=1.15 m`, `followSmoothing=14`, `followMode=0`, `canvasSize=1.7×1.0`. [ПРОВЕРЕНО: scene YAML]
- `CopilotHudBridge.controller=5`, press threshold 0.75, release threshold 0.35. [ПРОВЕРЕНО: scene YAML; controller enum mapping requires code enum/source]
- `CopilotClient.baseUrl=https://localhost`, bearer field empty; actual endpoint resource `arescope-endpoint` should override base URL at runtime. [ПРОВЕРЕНО: scene and connection-config source]; [ТРЕБУЕТ ПРОВЕРКИ: actual resource content is secret/config, not archived]
- `CopilotClient` timeout 45 s, settings poll 30 s, max recording 60 s, max response bytes 2,097,152, chat path `/api/copilot/chat`, sample rate 16,000 Hz. [ПРОВЕРЕНО: scene YAML]
- `ViewModeController` scene refs `headsetCamera`, `passthroughLayer`, `scanRenderer` are null. [ПРОВЕРЕНО: scene YAML]
- No complete screenshot or serialized text for the runtime-created HUD canvas hierarchy is archived beyond layout fields from source. [ТРЕБУЕТСЯ: full visual/asset contract]
