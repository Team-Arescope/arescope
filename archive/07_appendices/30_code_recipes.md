# 30 · Рецепты кода для сборки новой реализации

## Назначение и границы

Этот документ содержит небольшие иллюстративные фрагменты (каждый фрагмент ≤15 строк), алгоритмические схемы и порядок сборки. Они не являются исходными файлами, не копируются из проекта и требуют интеграции с RoomScan SDK, Unity lifecycle и выбранными сервисами. [ПРОВЕРЕНО: политика архива]

Цель — дать инженеру точку привязки для написания нового кода по спецификациям 01–29, а не предоставить готовую компилируемую кодовую базу. [ПРОВЕРЕНО: scope этого документа]

## 0. Рекомендуемый порядок сборки

```text
A. Workspace + pinned dependencies + Android manifest
B. XR rig + RoomScan SDK scene + permissions
C. Scan lifecycle/input state machine
D. GPU counter/buffer reader + mesh validation
E. Live point cache + camera frustum rendering
F. final mesh presentation + mixed view modes
G. minimap (live source, final-mesh source)
H. LAB ingest/schema/mesh/log APIs
I. client networking and Copilot ASR → LLM → TTS
J. evidence logging → build gates → Quest acceptance run
```

[ПРЕДПОЛОЖЕНИЕ: порядок зависимостей; точные API смотрите в файлах указанных ниже]

## 1. Фрагмент package manifest

Место: новые `Packages/manifest.json`; точные versions/pins в приложении 26 и evidence/reference_config. Фрагмент не является полным manifest. [ПРОВЕРЕНО: package contract]

```json
{
  "dependencies": {
    "com.genesis.roomscan": "https://github.com/arghyasur1991/QuestRoomScan.git#4791b24b81015641d4cfb010a93c6283d4eb3dee",
    "com.meta.xr.sdk.core": "205.0.0",
    "com.meta.xr.mrutilitykit": "205.0.0",
    "com.unity.xr.arfoundation": "6.2.0",
    "com.unity.xr.openxr": "1.15.1",
    "com.unity.inputsystem": "1.14.2"
  }
}
```

При создании проекта сохранить lockfile после разрешения зависимостей, не заменять фиксированную Git revision на branch head. [ПРОВЕРЕНО: reproduction contract]

## 2. Фрагмент Android manifest

Место: `Assets/Plugins/Android/AndroidManifest.xml`; это конфигурационный фрагмент, не весь manifest. Значения Horizon SDK сверить с текущими Meta publishing rules до выпуска. [ПРОВЕРЕНО: исследованный manifest]; [ТРЕБУЕТ ПРОВЕРКИ: актуальная policy]

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="com.oculus.permission.USE_SCENE" />
<uses-permission android:name="com.oculus.permission.USE_ANCHOR_API" />
<uses-permission android:name="horizonos.permission.HEADSET_CAMERA" />
<horizonos:uses-horizonos-sdk horizonos:minSdkVersion="60"
    horizonos:targetSdkVersion="85" />
```

Дополнительно определить launcher activity, VR category, exported flag и Unity activity metadata согласно AndroidManifest snapshot в `evidence/reference_config`. [ПРОВЕРЕНО: архивный manifest]

## 3. Фрагмент scan state machine

Место: компонент ввода Unity, обновляется на rising edge кнопок. Это псевдокод; проверить mapping left controller feature values в Meta OpenXR. [ПРЕДПОЛОЖЕНИЕ: псевдокод]; mapping [ТРЕБУЕТ ПРОВЕРКИ]

```csharp
if (xPressed && !busy)
{
    if (!scanning) await StartScanAsync();
    else await FinalizeFromLiveBuffersAsync();
}
if (yHeld) holdSeconds += Time.unscaledDeltaTime;
if (yHeld && holdSeconds >= 1.2f) await ResetScanAsync();
if (yReleased && !resetFired && scanning) TogglePassthrough();
if (yReleased && !resetFired && hasFinalMesh) CycleViewMode();
```

Required post-scan states: ScanOnly, Mixed, Passthrough. On scan start/reset set the cycle state explicitly from the real renderer/passthrough state; do not carry stale enum index. [ПРОВЕРЕНО: scene audit found desynchronization]

## 4. XR startup gate

Место: scene bootstrap. Не читать extension support до активного `XrInstance`/AR subsystem. [ПРОВЕРЕНО: historical failure and Meta depth docs]

```text
wait until XRSettings.isDeviceActive or timeout(15 s)
wait settle(0.6 s)
check AROcclusionManager.subsystem
if null:
    stop ARSession; yield at least one frame; enable ARSession
log provider state and XR runtime/extension support
if still absent: display a non-blocking scan-unavailable state
```

Exact retry count/session restart timing and runtime feature flags must be verified against the pinned OpenXR plugin. [ТРЕБУЕТ ПРОВЕРКИ]

## 5. Bounded GPU readback

Место: adapter compiled inside the RoomScan assembly, because Surface Nets types are internal. Range values from App 23. [ПРОВЕРЕНО: SDK API visibility and package patch architecture]

```csharp
extractor.ExtractForAuthoring();
await Task.Yield();
ReadCounters(surface.CountersBuffer, out var nV, out var nI);
nV = Mathf.Min(nV, surface.VertexBuffer.count, maxVertices);
nI = Mathf.Min(nI, surface.IndexBuffer.count, maxIndices);
var vReq = await AsyncGPUReadback.RequestAsync(surface.VertexBuffer, nV * 48, 0);
if (vReq.hasError) return Fail("vertex readback error");
var iReq = await AsyncGPUReadback.RequestAsync(surface.IndexBuffer, nI * 4, 0);
if (iReq.hasError) return Fail("index readback error");
```

This is an interface recipe, not a complete async error/lifetime implementation. Copy NativeArray results before their validity window ends. [ПРОВЕРЕНО: SDK readback lifetime]; buffer errors require headset profiling.

## 6. Vertex record decoding

Known SDK layout: stride 48 bytes; position offset 0, normal offset 24, packed RGBA-like word offset 36. [ПРОВЕРЕНО: pinned SDK constants]

```text
for each used record i:
  base = i * 48
  x,y,z = read_float32(base + 0, +4, +8)
  nx,ny,nz = read_float32(base + 24, +28, +32)
  packed = read_uint32(base + 36)
  r,g,b,a = decode packed colour per pinned shader packing
```

The packed vertex color is documented as `0xAABBGGRR` in SDK/client code; confirm byte order on target architecture before relying on color channels. [ПРОВЕРЕНО: source comment]; [ТРЕБУЕТ ПРОВЕРКИ: device color test]

## 7. Triangle validation and filtering

Место: CPU validation after positions/index arrays are copied. Detailed risks in App 08. [ПРОВЕРЕНО: architecture]

```text
sample ≤ 20,000 triangles, gather ≤ 60,000 edge lengths
median = sorted_edges[middle] or fallback 0.02 m
limit = clamp(median * 4, 0.06 m, 0.30 m)
for each triangle (a,b,c):
  reject index outside [0, vertexCount)
  reject repeated indices or non-finite XYZ
  reject if any edge length exceeds limit
  otherwise append a,b,c to output index list
log raw/kept/degenerate/stretched/outOfRange/median/limit
```

This filters using one global median threshold; it is not a proof of manifoldness or semantic object correctness. [ПРОВЕРЕНО: algorithm shape]; quality requires reference scans.

## 8. Wireframe build recipe

Место: final mesh presenter. Create unique undirected edges keyed by sorted vertex pair; draw triangle edges, but never use an oversized index array against a shorter uploaded vertex array. [ПРОВЕРЕНО: historical garble cause]

```text
for each retained triangle:
  AddEdge(a,b); AddEdge(b,c); AddEdge(c,a)
  edgeKey = (min(i,j) << 32) | max(i,j)
  if edgeKey not in edgeSet: emit line indices i,j
create MeshTopology.Lines mesh from retained vertices/edge indices
create point billboard mesh from up to 12,000 sampled vertices
apply line/point material with alpha and vertex colour policy
```

Current code has a 200,000 triangle budget, so it usually does not decimate calls capped at 200,000. `HashSet` allocation/performance on Quest remains unmeasured. [ПРОВЕРЕНО: source; performance requires device test]

## 9. Live point accumulation

Место: component `LiveScanPoints`. Current nominal defaults: 6,000 read points, 0.2 s interval, 0.035 m voxel, 60,000-entry cache, 16,000 rendered capacity, 9 m range. [ПРОВЕРЕНО: source]

```text
for each sampled point p:
  key = pack(floor(p.x/0.035), floor(p.y/0.035), floor(p.z/0.035))
  if key unseen and cache not full: store point + colour
on each publish:
  sample accumulated cache up to render capacity
  transform to world and reject outside 9 m/frustum
  upload only surviving vertex/color and index ranges
```

Current frustum rejection runs after GPU readback and cache insertion, so it saves render geometry, not readback work. [ПРОВЕРЕНО: source ordering]

## 10. Minimap projection

Место: `LiveScanMinimap`; point band follows current head height, not gaze pitch. [ПРОВЕРЕНО: current requirement/source]

```text
forward = normalize(project(headset.forward, horizontal plane))
right = cross(worldUp, forward)
delta = point - headset.position
accept if abs(delta.y) <= 0.03 m
mapPoint = (dot(delta,right), dot(delta,forward))
accept if squared distance <= 10² m²
limit map output to 96 points
```

Live input sample buffer 768; finalized mesh sampled with stride from up to 20,000 mesh vertices. [ПРОВЕРЕНО: source defaults]

## 11. Room-frame relocation

Место: `ArescopeFrame`; coordinate convention must match the values returned by GPU/SDK mesh. [ПРОВЕРЕНО: current implementation]; convention compatibility [ТРЕБУЕТ ПРОВЕРКИ]

```text
A_capture = RoomAnchorManager.SpatialAnchorMatrix at scan start
A_now = current anchor matrix
R = A_now * inverse(A_capture)
visualRoot.position = translation(R)
visualRoot.rotation = rotation(R)
visualRoot.scale = (1,1,1)
```

If no active anchor manager exists, present behavior returns identity relocation; decide whether to block scan until anchor is valid or explicitly mark frame as session-local. [ПРОВЕРЕНО: current behavior]; design choice [ТРЕБУЕТСЯ]

## 12. LAB frame ingest recipe

Место: FastAPI LAB service. Producer auth is distinct from viewer auth; live cache updates even when history persistence throttles/fails. [ПРОВЕРЕНО: server source]

```text
POST /api/live/frame
Authorization: Bearer <producer token>
JSON: {room, yawDeg, points:[[x,y,z], ...]}
accept at most 4,096 points; client sends at most 384
persist only if room interval ≥0.25 s and session frameCount <2,000
split session after 60 s gap; gzip compact JSON at level 6
```

Tokens must be supplied out-of-band, never in the archive. [ПРОВЕРЕНО: security policy]

## 13. ARSM mesh packing recipe

Binary layout is fully specified in App 07; v1 and v2 entries are little-endian. [ПРОВЕРЕНО: client/server parser]

```text
write bytes "ARSM"
write u32 version, u32 vertexCount, u32 indexCount
write vertexCount × float32 xyz records
write vertexCount × RGBA uint8 records
write indexCount × uint32 triangle indices
if version=2: append vertexCount × float32 uv pairs
then u32 atlasWidth, u32 atlasHeight, u32 PNG byte count, PNG bytes
```

Before posting, validate exact body length, `indexCount % 3 == 0`, every index in range, body ≤32 MiB. [ПРОВЕРЕНО: server validates some fields]; per-index range validation should be added/verified before relying on it. [ТРЕБУЕТ ПРОВЕРКИ]

## 14. Device log / lifecycle recipe

- `ArescopeLog` file rotates after 512 KiB to `.1`; snapshot concatenates rotated/current content and truncates to 2,000,000 .NET string characters. [ПРОВЕРЕНО: current source]
- Log upload sources: `pause`, `combo`, `crash-recovery`; X+Y hold 2 s; HTTP timeout 25 s; server byte cap 8 MiB. [ПРОВЕРЕНО]
- `OnApplicationQuit` currently only clears marker; do not assume it triggers upload. [ПРОВЕРЕНО: current source]

Illustrative API contract (not complete project file):

```text
POST /api/live/log?source=<source>
Authorization: Bearer <producer>
Content-Type: text/plain; charset=utf-8
success: {ok:true,file,bytes}
```

## 15. Mixed mode recipe

- Passthrough-only: renderer off, passthrough on. [ПРОВЕРЕНО: intended behavior]
- Mixed: renderer on, passthrough on, preserve passthrough-compatible camera clear flags. [ПРОВЕРЕНО: current state handling]; compositor order needs headset validation.
- Scan-only: renderer on, passthrough off, opaque black background. [ПРОВЕРЕНО]
- On scan completion, code currently enters scan-only but its internal view-mode index starts at Passthrough; synchronize the index to rendered state when assembling the new implementation. [ПРОВЕРЕНО: source audit]

## 16. Copilot protocol recipe

- Transcribe: WAV PCM16, 16 kHz client capture, max request 8 MiB, server upstream timeout 60 s. [ПРОВЕРЕНО]
- Chat: JSON text/context, text max 12,000 chars; stream events are `text`, `complete`, `error`; server timeout 90 s (connect 10 s). [ПРОВЕРЕНО]
- Speech: voice `male`/`female`, provider model `minimax/speech-2.8-hd`, MP3, server timeout 90 s, response cap 8 MiB. [ПРОВЕРЕНО]
- Fallback model list/order and prompt behavior are defined in App 19; no SDM stage belongs in the sequence. [ПРОВЕРЕНО: target contract]

## 17. Build recipe and release gates

- Package `in.arescope.beta02.questroom`; ARM64, IL2CPP, min API 29, Linear color space; Unity 6000.2.9f1. [ПРОВЕРЕНО]
- Explicitly build/wire/validate scene before `BuildPlayer`; current helper is not called from build method. [ПРОВЕРЕНО: scene audit]
- Verify result string, aapt2 launcher/ABI/version, xatlas plugin, install, headset smoke test, SHA download equality. [ПРОВЕРЕНО: release gates]
- Full command, cache cleanup and known failures are in App 11; staging secrets are not included. [ПРОВЕРЕНО]

## Assemble-a-project checklist

A code agent or engineer should implement one source file/module at a time from these recipes and acceptance tests; no code snippet here exceeds 15 lines, and none is a complete class or source file. [ПРОВЕРЕНО: code recipe constraints]

1. Create project and import pinned dependencies/config from `evidence/reference_config`. [ПРОВЕРЕНО]
2. Implement XR bootstrap and scene manifest; resolve Appendix 27 null/missing references. [ТРЕБУЕТСЯ]
3. Implement scan state machine + GPU readback and test synthetic buffers. [ПРОВЕРЕНО: interface contracts]; implementation yet to write.
4. Implement filter + render + minimap; run unit and profiler tests. [ПРОВЕРЕНО: target parameters]; performance thresholds require measurement.
5. Implement LAB/Copilot routes against endpoint contracts and temporary local DB. [ПРОВЕРЕНО: API contract]
6. Add resources/assets; restore font files with OFL or accept tested fallback; build native xatlas. [ПРОВЕРЕНО: asset inventory]
7. Run clean-room Android build and headset test matrix; record artifact SHA and evidence. [ТРЕБУЕТСЯ: no clean-room recreation run]

**Готовность:** эти фрагменты и инструкции образуют blueprint реализации, но не готовый набор файлов для сборки. [ПРОВЕРЕНО: замысел документа]
Процедуры сборки/XR/сканирования находятся в `skills/`; это исторические инструкции, которые нужно сверять с актуальными приложениями 27–29. [ПРОВЕРЕНО: skill archive]
Полное соответствие проекту требует закрыть незавершённые вопросы из приложений 16, 22, 27–29. [ПРОВЕРЕНО: cross-reference]
Начало реализации остаётся запрещённым до официального открытия хакатона. [ПРОВЕРЕНО: user instruction]
