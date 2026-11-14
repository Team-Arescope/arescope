# Simulator test scenes (SimRoom / SimMars)

Editor-only scene generators for checking the Arescope app in Meta XR Simulator
without a headset trip. Source: `Assets/Editor/BuildSimScenes.cs` in
`/root/Developer/arescope-beta02-questroom` (mirrored to InstaBox at
`/data/home/unity/arescope-beta02`). Scenes are written to `Assets/Scenes/` and
registered in Build Settings, so they ship inside `Build/SimPC/`.

Entry points:

| Method | Effect |
|---|---|
| `BuildSimScenes.BuildRoom` | Regenerate `SimRoom.unity` |
| `BuildSimScenes.BuildMars` | Regenerate `SimMars.unity` |
| `BuildSimScenes.RenderViews` | Render N camera poses of an existing scene to PNG |

## Textures (CC0, Poly Haven)

Asset list: `https://api.polyhaven.com/assets?t=textures` (JSON keyed by name).
Direct 1k file URL pattern:

```
https://dl.polyhaven.org/file/ph-assets/Textures/jpg/1k/<name>/<name>_diff_1k.jpg
https://dl.polyhaven.org/file/ph-assets/Textures/jpg/1k/<name>/<name>_nor_gl_1k.jpg
```

Land them in `Assets/SimData/Textures/<name>_diff.jpg` and `_nor.jpg`; the
generator resolves `<name>_diff` / `<name>_nor` by that convention. Normal maps
must be reimported with `TextureImporter.textureType = TextureImporterType.NormalMap`
(`SaveAndReimport`) or they behave as albedo.

Set used: `wood_planks` (floor), `grey_plaster` (walls), `painted_plaster_wall`
(ceiling), `dark_paneled_wood` (door/trim), `fabric_leather_01` (upholstery),
`metal_plate` (hardware), `dirty_carpet` (rug), `cracked_red_ground` (Mars).

## Furniture models (CC0, Poly Haven)

`GET https://api.polyhaven.com/files/<asset>` → `fbx.1k.fbx.url` plus
`fbx.1k.fbx.include` (textures under `textures/<name>_*_1k.jpg`; skip `.exr`).
Download the FBX and flatten the jpg includes into
`Assets/SimData/Models/<asset>/` so `ModelMat` can find the one whose path
contains `diff`.

Used: `dining_table`, `dining_chair_02`, `sofa_02`, `wooden_bookshelf_worn`,
`vintage_cabinet_01`, `modern_ceiling_lamp_01`. `periwinkle_plant` ships extra
geometry in FBX — keep the procedural plant instead.

`PlaceModel(parent, folder, pos, targetSize, yaw, alignTop, rotX)` instantiates
the FBX as a prefab, applies `yaw * rotX`, overrides every renderer material,
scales by `min(target.x/size.x, target.y/size.y, target.z/size.z)` and rests the
bounds on `pos` (or hangs them with `alignTop: true`). It logs
`PLACED <folder>: scale=… size=… center=… min=…` — read those numbers first; they
catch wrong orientation and wrong footprint far faster than a render.

Known rotations: chairs, bookshelf and ceiling lamp need `rotX` (±90) because
their FBX is Z-up; table, sofa and cabinet import upright. Wrong sign = the
model is upside down while every dimension still looks plausible.

## Room layout

6 × 5 m, 2.8 m ceiling. Door opening on −Z (frame + open leaf + handle), window
with frame, mullion, glass and curtains on +X, baseboards, rug, framed pictures,
wall screen, ceiling lamp hung with `alignTop`, procedural plant, and table
props (laptop, mug, notebook). Lights: one warm point light under the lamp plus
a soft directional "window" light; `RenderSettings.ambientMode = Flat`.

## Mars terrain (2 km square)

The full HiRISE product is 6736 × 13375 px at 1.0117468 m/px (~6.8 × 13.5 km),
so a 2 km crop is a bounded read, never a downsample of the 1 km asset:

- header 26944 B, `linebytes = 6736 * 4`; crop rows `5663…7711`,
  cols `2343…4391` (2049 native px → 257 lattice points, stride 8,
  step 8.094 m, extent 2072.1 m, 66 049 vertices, 0 NULLs).
- Fetch one `Range` header from the PDS IMG, assert `206` and a matching
  `Content-Range`, then sample `struct.unpack_from('<I'/... '<f')` per point.
- Write a NEW asset (`Assets/SimData/hirise-gale-2km.json`); never overwrite the
  1 km `hirise-gale.json` the LAB site serves.

Scene dressing: `cracked_red_ground` tiled 48×, `Skybox/Procedural` with a dusty
`_SkyTint`/`_GroundColor`, and linear fog (`fogStartDistance` 250,
`fogEndDistance` 2400) — without the fog distant ridges read as flat shapes and
the sky looks terrestrial.

## Rendering and verifying

```bash
cd /data/home/unity/arescope-beta02
DISPLAY=:1 SIM_RENDER_SCENE=Assets/Scenes/SimRoom.unity SIM_RENDER_PREFIX=room \
  SIM_RENDER_POSES="0.9,1.6,-2.1,-0.6,1.25,0.5;-0.2,1.5,2.1,2.4,1.1,-1.4;..." \
  /data/home/Unity/Hub/Editor/6000.2.9f1/Editor/Unity -batchmode -quit -projectPath $PWD \
  -executeMethod BuildSimScenes.RenderViews -logFile $PWD/render-room.log
```

`SIM_RENDER_POSES` is `x,y,z,targetx,targety,targetz` separated by `;`. For the
Mars scene add `SIM_RENDER_GROUND=1` so each pose's Y is a height above the
sampled terrain instead of an absolute altitude. Pull the PNGs over the InstaBox
`/files/content` API, look at them with vision, and send them to the user as
documents — the user expects the renders themselves, not a description.

Renderer sanity signals: a plausible PNG is a few hundred KB to ~1.5 MB; a
20–60 KB frame usually means the camera is inside geometry or the material
failed (black silhouette / flat fill).

## Generated geometry pitfalls

**Index format.** `Mesh.indexFormat` is 16-bit by default. The 257×257 Mars
lattice is 66 049 vertices, so indices above 65 535 wrap: the frame shows a
black slab over the sky, holes near the horizon and long diagonal seams. Set
`mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32` immediately after
`new Mesh()` and before assigning vertices/triangles. File size of the saved
scene grows sharply (SimMars is ~9.5 MB) because UVs and tangents are
serialised per vertex — that is expected, not corruption.

**Wall openings.** Build a wall with an opening from segments derived from the
opening edges, not from the opening width:
`leftLen = (openingCenter - openingWidth/2) + wallWidth/2` and
`rightLen = wallWidth/2 - (openingCenter + openingWidth/2)`. Computing the left
segment from the *right* edge shifts the hole by one opening width, leaving the
door frame standing on solid wall and a matching gap of raw skybox beside it.
Always render one interior pose looking at the opening: a bright uniform
rectangle behind a door frame is a hole, not lighting.

**Defect sweep after every render.** Look for, in this order: sky visible where
a wall should be, a flat black mass in the upper frame (index or camera issue),
torn triangles along the horizon, objects floating above the floor (a real
missing-contact-shadow artefact, not a render bug), and textures that read as
flat colour because a material lost its `_BaseMap`.

## Rendering the HUD over the Mars scene (astronaut POV)

`BuildSimScenes.RenderMarsHud` composes the real HUD over the Mars terrain so the
interface can be judged against something other than flat grey. Three traps, all
of which produce a plausible-looking but wrong frame:

- **URP keeps the terrain unlit when the camera faces away from the sun.** Any
eye-level pose that looks at a slope the sun is not hitting renders as a pure
black silhouette, and adjusting `RenderSettings.ambientLight`, moving the sun, or
re-aiming the camera does not reliably fix it in edit mode. For a review shot,
swap the terrain material for `Universal Render Pipeline/Unlit` with the same
`_BaseMap` and its texture scale, tint it slightly warm, render, then restore the
original material and destroy the temporary one. Say in the hand-off that the
surface is shown by albedo, not by a lighting study, so missing shadows are not
read as a bug.
- **`Camera.Render()` is fine, but a runtime spot light is not.** Adding a
`Light` (a "scanner headlamp") to the camera before the manual render crashed the
batchmode editor with a native stack and no `error CS`. Light the shot by
material swap instead of adding lights at render time.
- **`FindFirstObjectByType<Light>()` returns whichever light comes first.** After
adding a spot, it is that spot, so an `if (light.type == Directional)` guard
silently skips the sun override. Enumerate with
`FindObjectsByType<Light>(FindObjectsSortMode.None)` and pick the directional one.

**Eye height needs a bilinear sample, not the nearest vertex.** The lattice is
~8 m; on a slope the nearest vertex sits below the interpolated surface, the
camera ends up inside the mesh and the frame reads as a black wedge. Interpolate
the four surrounding vertices of the heightmap, then add 1.8 m.

Composition that reads as "astronaut": stand on a gentle rise, aim at a slope
that rises ahead (terrain fills the frame instead of sky), pitch down ~4°, and
keep the top HUD row against terrain rather than blown-out sky where possible.
Verify with vision and expect it to criticise sky colour and missing rocks —
those are scene-dressing gaps, not HUD defects.

## Commit hygiene

Keep raw PDS byte caches (tens of MB of `.bin`) outside the project: they live
under `Assets/SimData/` by default when the crop script caches locally, and the
editor then imports them. Move them to a scratch path, gitignore them, and keep
the resulting JSON in `Assets/SimData/`. Commit the generated scenes too — they
exist only on the sandbox until pulled back, and regenerating them requires the
whole texture/model set to be present.
