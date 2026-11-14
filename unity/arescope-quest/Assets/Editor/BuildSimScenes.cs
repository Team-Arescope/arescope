using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using Arescope.Hud;

namespace Arescope.Editor
{
    public static class BuildSimScenes
    {
        private const string SimRoomScenePath = "Assets/Scenes/SimRoom.unity";
        private const string SimMarsScenePath = "Assets/Scenes/SimMars.unity";
        private const string MarsJsonPath = "Assets/SimData/hirise-gale-2km.json";
        private const string MarsMeshAssetPath = "Assets/SimData/SimMarsTerrain.asset";
        private const int MarsGridSize = 257;
        private const float MarsStepMeters = 8.094f;
        private const float RoomWidth = 6.0f;
        private const float RoomDepth = 5.0f;
        private const float RoomHeight = 2.8f;

        [Serializable]
        private sealed class HiriseGridData
        {
            public int rows;
            public int cols;
            public float step_m;
            public float[] heights;
            public float[] elevation;
        }

        [MenuItem("Arescope/Sim/Build Room")]
        public static void BuildRoom()
        {
            EnsureDir("Assets/Scenes");
            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.32f, 0.31f, 0.30f, 1f);

            GameObject root = new GameObject("SimRoom");
            var createdMats = new List<Material>();

            Material floorMat = CreateLitMaterial("wood_planks", new Color(0.55f, 0.42f, 0.30f), 0.28f, new Vector2(3f, 2.5f), createdMats);
            Material wallMat = CreateLitMaterial("grey_plaster", new Color(0.76f, 0.75f, 0.72f), 0.15f, new Vector2(2f, 1f), createdMats);
            Material ceilMat = CreateLitMaterial("painted_plaster_wall", new Color(0.86f, 0.86f, 0.84f), 0.1f, new Vector2(2f, 2f), createdMats);
            Material trimMat = CreateLitMaterial("dark_paneled_wood", new Color(0.28f, 0.20f, 0.14f), 0.35f, Vector2.one, createdMats);
            Material rugMat = CreateLitMaterial("dirty_carpet", new Color(0.45f, 0.42f, 0.38f), 0.08f, new Vector2(2f, 2f), createdMats);
            Material fabricMat = CreateLitMaterial("fabric_leather_01", new Color(0.30f, 0.26f, 0.24f), 0.25f, Vector2.one, createdMats);
            Material metalMat = CreateLitMaterial("metal_plate", new Color(0.62f, 0.64f, 0.66f), 0.72f, Vector2.one, createdMats);

            // Floor & ceiling
            CreateBox(root.transform, "Floor", new Vector3(0f, -0.05f, 0f), new Vector3(RoomWidth, 0.1f, RoomDepth), floorMat);
            CreateBox(root.transform, "Ceiling", new Vector3(0f, RoomHeight + 0.05f, 0f), new Vector3(RoomWidth, 0.1f, RoomDepth), ceilMat);

            // North wall (+Z) and West wall (-X) solid
            CreateBox(root.transform, "Wall_North", new Vector3(0f, RoomHeight * 0.5f, RoomDepth * 0.5f + 0.06f), new Vector3(RoomWidth, RoomHeight, 0.12f), wallMat);
            CreateBox(root.transform, "Wall_West", new Vector3(-RoomWidth * 0.5f - 0.06f, RoomHeight * 0.5f, 0f), new Vector3(0.12f, RoomHeight, RoomDepth), wallMat);

            // South wall (-Z) with door opening derived strictly from opening edges.
            BuildWallWithOpeningZ(
                root.transform,
                "Wall_South",
                -RoomDepth * 0.5f - 0.06f,
                RoomWidth,
                RoomHeight,
                0.12f,
                openingCenterX: 0.5f,
                openingWidth: 0.96f,
                openingBottomY: 0f,
                openingTopY: 2.12f,
                wallMat,
                trimMat,
                metalMat);

            // East wall (+X) with window opening derived from opening edges.
            BuildWallWithOpeningX(
                root.transform,
                "Wall_East",
                RoomWidth * 0.5f + 0.06f,
                RoomDepth,
                RoomHeight,
                0.12f,
                openingCenterZ: 0.2f,
                openingWidth: 1.6f,
                openingBottomY: 0.9f,
                openingTopY: 2.25f,
                wallMat,
                trimMat,
                fabricMat);

            // Baseboards & rug
            CreateBox(root.transform, "Baseboard_N", new Vector3(0f, 0.05f, RoomDepth * 0.5f - 0.01f), new Vector3(RoomWidth, 0.1f, 0.02f), trimMat);
            CreateBox(root.transform, "Baseboard_W", new Vector3(-RoomWidth * 0.5f + 0.01f, 0.05f, 0f), new Vector3(0.02f, 0.1f, RoomDepth), trimMat);
            CreateBox(root.transform, "Rug", new Vector3(-0.3f, 0.01f, 0.2f), new Vector3(2.8f, 0.02f, 2.0f), rugMat);

            // Framed pictures and wall screen
            CreateBox(root.transform, "WallScreen", new Vector3(0f, 1.55f, RoomDepth * 0.5f - 0.03f), new Vector3(1.4f, 0.8f, 0.04f), trimMat);
            CreateBox(root.transform, "Picture_Left", new Vector3(-RoomWidth * 0.5f + 0.03f, 1.65f, -0.7f), new Vector3(0.04f, 0.65f, 0.85f), trimMat);
            CreateBox(root.transform, "Picture_Right", new Vector3(-RoomWidth * 0.5f + 0.03f, 1.65f, 0.9f), new Vector3(0.04f, 0.65f, 0.85f), trimMat);

            // Furniture (FBX if present under Assets/SimData/Models/<folder>/, else clean fallback)
            PlaceModel(root.transform, "dining_table", new Vector3(-0.2f, 0f, 0.2f), new Vector3(1.6f, 0.76f, 0.95f), 0f, false, 0f, trimMat);
            PlaceModel(root.transform, "dining_chair_02", new Vector3(-0.6f, 0f, -0.55f), new Vector3(0.5f, 0.88f, 0.52f), 15f, false, -90f, fabricMat);
            PlaceModel(root.transform, "dining_chair_02", new Vector3(0.4f, 0f, -0.55f), new Vector3(0.5f, 0.88f, 0.52f), -12f, false, -90f, fabricMat);
            PlaceModel(root.transform, "sofa_02", new Vector3(-2.15f, 0f, 0.6f), new Vector3(1.85f, 0.85f, 0.92f), 90f, false, 0f, fabricMat);
            PlaceModel(root.transform, "wooden_bookshelf_worn", new Vector3(-2.45f, 0f, -1.85f), new Vector3(0.95f, 1.85f, 0.38f), 0f, false, -90f, trimMat);
            PlaceModel(root.transform, "vintage_cabinet_01", new Vector3(2.15f, 0f, 1.85f), new Vector3(1.1f, 0.92f, 0.48f), 180f, false, 0f, trimMat);
            PlaceModel(root.transform, "modern_ceiling_lamp_01", new Vector3(0f, RoomHeight, 0f), new Vector3(0.55f, 0.42f, 0.55f), 0f, true, -90f, metalMat);

            // Table props & procedural plant
            CreateBox(root.transform, "Laptop", new Vector3(-0.35f, 0.79f, 0.2f), new Vector3(0.34f, 0.02f, 0.24f), metalMat);
            CreateCylinder(root.transform, "Mug", new Vector3(0.08f, 0.81f, 0.15f), new Vector3(0.08f, 0.05f, 0.08f), ceilMat);
            CreateBox(root.transform, "Notebook", new Vector3(0.26f, 0.78f, 0.32f), new Vector3(0.21f, 0.015f, 0.28f), wallMat);
            BuildProceduralPlant(root.transform, new Vector3(2.35f, 0f, -1.95f), trimMat);

            // Lighting
            GameObject lampLightGo = new GameObject("CeilingPointLight");
            lampLightGo.transform.SetParent(root.transform, false);
            lampLightGo.transform.position = new Vector3(0f, RoomHeight - 0.55f, 0f);
            Light lampLight = lampLightGo.AddComponent<Light>();
            lampLight.type = LightType.Point;
            lampLight.color = new Color(1.0f, 0.92f, 0.80f);
            lampLight.intensity = 2.6f;
            lampLight.range = 9f;

            GameObject windowSunGo = new GameObject("WindowDirectionalLight");
            windowSunGo.transform.SetParent(root.transform, false);
            windowSunGo.transform.rotation = Quaternion.Euler(36f, -110f, 0f);
            Light sun = windowSunGo.AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.color = new Color(0.95f, 0.97f, 1.0f);
            sun.intensity = 1.15f;

            GameObject camGo = new GameObject("SimCamera");
            camGo.tag = "MainCamera";
            camGo.transform.position = new Vector3(0.9f, 1.6f, -2.1f);
            camGo.transform.LookAt(new Vector3(-0.6f, 1.25f, 0.5f));
            Camera cam = camGo.AddComponent<Camera>();
            cam.nearClipPlane = 0.05f;
            cam.farClipPlane = 100f;

            EditorSceneManager.MarkSceneDirty(scene);
            AssetDatabase.SaveAssets();
            EditorSceneManager.SaveScene(scene, SimRoomScenePath);
            RegisterBuildScene(SimRoomScenePath);
            Debug.Log("[Arescope] BuildSimScenes.BuildRoom saved " + SimRoomScenePath);
        }

        [MenuItem("Arescope/Sim/Build Mars")]
        public static void BuildMars()
        {
            EnsureDir("Assets/Scenes");
            EnsureDir("Assets/SimData");
            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            float[] heights = LoadOrSynthesizeMarsHeights(out int rows, out int cols, out float stepMeters);
            Mesh terrainMesh = BuildMarsTerrainMesh(heights, rows, cols, stepMeters);
            AssetDatabase.CreateAsset(terrainMesh, MarsMeshAssetPath);
            AssetDatabase.SaveAssets();

            var createdMats = new List<Material>();
            Material marsMat = CreateLitMaterial("cracked_red_ground", new Color(0.68f, 0.36f, 0.24f), 0.08f, new Vector2(48f, 48f), createdMats);

            GameObject terrainGo = new GameObject("MarsTerrain");
            MeshFilter mf = terrainGo.AddComponent<MeshFilter>();
            mf.sharedMesh = terrainMesh;
            MeshRenderer mr = terrainGo.AddComponent<MeshRenderer>();
            mr.sharedMaterial = marsMat;

            Shader skyShader = Shader.Find("Skybox/Procedural");
            if (skyShader != null)
            {
                Material skyMat = new Material(skyShader);
                skyMat.SetColor("_SkyTint", new Color(0.62f, 0.42f, 0.30f));
                skyMat.SetColor("_GroundColor", new Color(0.32f, 0.18f, 0.12f));
                skyMat.SetFloat("_AtmosphereThickness", 0.55f);
                skyMat.SetFloat("_Exposure", 1.15f);
                skyMat = PersistMaterialAsset(skyMat, "Mat_MarsSkybox");
                RenderSettings.skybox = skyMat;
            }

            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogColor = new Color(0.58f, 0.38f, 0.28f, 1f);
            RenderSettings.fogStartDistance = 250f;
            RenderSettings.fogEndDistance = 2400f;

            GameObject sunGo = new GameObject("MarsSun");
            sunGo.transform.rotation = Quaternion.Euler(34f, 48f, 0f);
            Light sun = sunGo.AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.color = new Color(1.0f, 0.88f, 0.78f);
            sun.intensity = 1.6f;

            float halfExtent = (cols - 1) * stepMeters * 0.5f;
            float camX = 0f;
            float camZ = -halfExtent * 0.25f;
            float groundY = SampleBilinearHeight(heights, rows, cols, stepMeters, camX, camZ);

            GameObject camGo = new GameObject("SimCamera");
            camGo.tag = "MainCamera";
            camGo.transform.position = new Vector3(camX, groundY + 1.8f, camZ);
            camGo.transform.rotation = Quaternion.Euler(4f, 15f, 0f);
            Camera cam = camGo.AddComponent<Camera>();
            cam.nearClipPlane = 0.05f;
            cam.farClipPlane = 3500f;

            EditorSceneManager.MarkSceneDirty(scene);
            AssetDatabase.SaveAssets();
            EditorSceneManager.SaveScene(scene, SimMarsScenePath);
            RegisterBuildScene(SimMarsScenePath);
            Debug.Log($"[Arescope] BuildSimScenes.BuildMars saved {SimMarsScenePath} ({rows}x{cols}, verts={terrainMesh.vertexCount})");
        }

        [MenuItem("Arescope/Sim/Render Views")]
        public static void RenderViews()
        {
            string scenePath = Environment.GetEnvironmentVariable("SIM_RENDER_SCENE");
            if (string.IsNullOrWhiteSpace(scenePath))
            {
                scenePath = SimRoomScenePath;
            }

            string prefix = Environment.GetEnvironmentVariable("SIM_RENDER_PREFIX");
            if (string.IsNullOrWhiteSpace(prefix))
            {
                prefix = "sim";
            }

            string posesRaw = Environment.GetEnvironmentVariable("SIM_RENDER_POSES");
            if (string.IsNullOrWhiteSpace(posesRaw))
            {
                posesRaw = "0.9,1.6,-2.1,-0.6,1.25,0.5;-0.2,1.5,2.1,2.4,1.1,-1.4";
            }

            bool groundRelative = string.Equals(Environment.GetEnvironmentVariable("SIM_RENDER_GROUND"), "1", StringComparison.Ordinal);

            if (!File.Exists(scenePath))
            {
                if (scenePath.Contains("Mars", StringComparison.OrdinalIgnoreCase)) BuildMars();
                else BuildRoom();
            }

            Scene scene = EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single);
            Camera cam = UnityEngine.Object.FindFirstObjectByType<Camera>();
            if (cam == null)
            {
                GameObject camGo = new GameObject("RenderCamera");
                cam = camGo.AddComponent<Camera>();
                cam.farClipPlane = 3500f;
            }

            float[] marsHeights = null;
            int rows = 0, cols = 0;
            float stepM = MarsStepMeters;
            if (groundRelative)
            {
                marsHeights = LoadOrSynthesizeMarsHeights(out rows, out cols, out stepM);
            }

            string[] poseEntries = posesRaw.Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries);
            for (int i = 0; i < poseEntries.Length; i++)
            {
                string[] nums = poseEntries[i].Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
                if (nums.Length < 6) continue;

                float x = ParseFloat(nums[0]);
                float y = ParseFloat(nums[1]);
                float z = ParseFloat(nums[2]);
                float tx = ParseFloat(nums[3]);
                float ty = ParseFloat(nums[4]);
                float tz = ParseFloat(nums[5]);

                if (groundRelative && marsHeights != null)
                {
                    y += SampleBilinearHeight(marsHeights, rows, cols, stepM, x, z);
                    ty += SampleBilinearHeight(marsHeights, rows, cols, stepM, tx, tz);
                }

                cam.transform.position = new Vector3(x, y, z);
                cam.transform.LookAt(new Vector3(tx, ty, tz));
                string outPng = Path.Combine("Build", $"{prefix}_{i:D2}.png");
                RenderArescopeHudPreview.CaptureCameraToPng(cam, outPng, 1600, 900);
                Debug.Log($"[Arescope] RenderViews wrote {outPng}");
            }
        }

        [MenuItem("Arescope/Sim/Render Mars HUD")]
        public static void RenderMarsHud()
        {
            if (!File.Exists(SimMarsScenePath))
            {
                BuildMars();
            }

            EditorSceneManager.OpenScene(SimMarsScenePath, OpenSceneMode.Single);

            float[] heights = LoadOrSynthesizeMarsHeights(out int rows, out int cols, out float stepM);
            float camX = -120f;
            float camZ = -260f;
            float eyeY = SampleBilinearHeight(heights, rows, cols, stepM, camX, camZ) + 1.8f;

            Camera cam = UnityEngine.Object.FindFirstObjectByType<Camera>();
            if (cam == null)
            {
                GameObject camGo = new GameObject("MarsHudCamera");
                cam = camGo.AddComponent<Camera>();
            }
            cam.nearClipPlane = 0.05f;
            cam.farClipPlane = 3500f;
            cam.fieldOfView = 60f;
            cam.transform.position = new Vector3(camX, eyeY, camZ);
            cam.transform.rotation = Quaternion.Euler(4f, 18f, 0f);

            Light[] lights = UnityEngine.Object.FindObjectsByType<Light>(FindObjectsSortMode.None);
            foreach (Light l in lights)
            {
                if (l.type == LightType.Directional)
                {
                    l.intensity = Mathf.Max(l.intensity, 1.4f);
                }
            }

            // Swap terrain material temporarily to URP/Unlit preserving _BaseMap so facing slope albedo is visible.
            GameObject terrainGo = GameObject.Find("MarsTerrain");
            MeshRenderer terrainRenderer = terrainGo != null ? terrainGo.GetComponent<MeshRenderer>() : null;
            Material originalMat = terrainRenderer != null ? terrainRenderer.sharedMaterial : null;
            Material tempUnlitMat = null;

            GameObject hudGo = new GameObject("MarsPreviewHud");
            try
            {
                if (terrainRenderer != null && originalMat != null)
                {
                    Shader unlitShader = Shader.Find("Universal Render Pipeline/Unlit");
                    if (unlitShader != null)
                    {
                        tempUnlitMat = new Material(unlitShader);
                        Texture baseMap = originalMat.HasProperty("_BaseMap") ? originalMat.GetTexture("_BaseMap") : null;
                        if (baseMap != null)
                        {
                            tempUnlitMat.SetTexture("_BaseMap", baseMap);
                            tempUnlitMat.SetTextureScale("_BaseMap", originalMat.GetTextureScale("_BaseMap"));
                            tempUnlitMat.SetTextureOffset("_BaseMap", originalMat.GetTextureOffset("_BaseMap"));
                        }
                        Color tint = originalMat.HasProperty("_BaseColor") ? originalMat.GetColor("_BaseColor") : new Color(0.75f, 0.42f, 0.28f);
                        tempUnlitMat.SetColor("_BaseColor", tint * 1.15f);
                        terrainRenderer.sharedMaterial = tempUnlitMat;
                    }
                }

                ArescopeHudController hud = hudGo.AddComponent<ArescopeHudController>();
                hud.targetCamera = cam.transform;
                hud.followDistance = 1.15f;
                hud.followMode = 1;
                hud.canvasSize = new Vector2(1.7f, 1.0f);

                MethodInfo awakeMethod = typeof(ArescopeHudController).GetMethod("Awake", BindingFlags.Instance | BindingFlags.NonPublic);
                awakeMethod?.Invoke(hud, null);
                hud.ApplyPreviewFixture();

                MethodInfo lateUpdateMethod = typeof(ArescopeHudController).GetMethod("LateUpdate", BindingFlags.Instance | BindingFlags.NonPublic);
                lateUpdateMethod?.Invoke(hud, null);

                string outPath = Environment.GetEnvironmentVariable("ARESCOPE_MARS_HUD_PATH");
                if (string.IsNullOrWhiteSpace(outPath))
                {
                    outPath = "Build/mars-hud-preview.png";
                }

                RenderArescopeHudPreview.CaptureCameraToPng(cam, outPath, 1600, 900);
                Debug.Log($"[Arescope] RenderMarsHud wrote {outPath} (albedo unlit terrain composition)");
            }
            finally
            {
                if (terrainRenderer != null && originalMat != null)
                {
                    terrainRenderer.sharedMaterial = originalMat;
                }
                if (tempUnlitMat != null)
                {
                    UnityEngine.Object.DestroyImmediate(tempUnlitMat);
                }
                UnityEngine.Object.DestroyImmediate(hudGo);
            }
        }

        private static void BuildWallWithOpeningZ(
            Transform parent,
            string prefix,
            float zPos,
            float wallWidth,
            float wallHeight,
            float thickness,
            float openingCenterX,
            float openingWidth,
            float openingBottomY,
            float openingTopY,
            Material wallMat,
            Material trimMat,
            Material metalMat)
        {
            float leftLen = (openingCenterX - openingWidth * 0.5f) + wallWidth * 0.5f;
            float rightLen = wallWidth * 0.5f - (openingCenterX + openingWidth * 0.5f);

            if (leftLen > 0.01f)
            {
                float leftCenterX = -wallWidth * 0.5f + leftLen * 0.5f;
                CreateBox(parent, prefix + "_Left", new Vector3(leftCenterX, wallHeight * 0.5f, zPos), new Vector3(leftLen, wallHeight, thickness), wallMat);
            }

            if (rightLen > 0.01f)
            {
                float rightCenterX = wallWidth * 0.5f - rightLen * 0.5f;
                CreateBox(parent, prefix + "_Right", new Vector3(rightCenterX, wallHeight * 0.5f, zPos), new Vector3(rightLen, wallHeight, thickness), wallMat);
            }

            float headerH = wallHeight - openingTopY;
            if (headerH > 0.01f)
            {
                CreateBox(parent, prefix + "_Header", new Vector3(openingCenterX, openingTopY + headerH * 0.5f, zPos), new Vector3(openingWidth, headerH, thickness), wallMat);
            }

            // Door frame + open leaf + handle
            CreateBox(parent, "DoorFrame_L", new Vector3(openingCenterX - openingWidth * 0.5f + 0.025f, openingTopY * 0.5f, zPos), new Vector3(0.05f, openingTopY, thickness + 0.03f), trimMat);
            CreateBox(parent, "DoorFrame_R", new Vector3(openingCenterX + openingWidth * 0.5f - 0.025f, openingTopY * 0.5f, zPos), new Vector3(0.05f, openingTopY, thickness + 0.03f), trimMat);
            CreateBox(parent, "DoorFrame_Top", new Vector3(openingCenterX, openingTopY - 0.025f, zPos), new Vector3(openingWidth, 0.05f, thickness + 0.03f), trimMat);

            GameObject doorLeaf = CreateBox(parent, "DoorLeaf", new Vector3(openingCenterX - openingWidth * 0.5f + 0.06f, openingTopY * 0.5f, zPos + 0.42f), new Vector3(0.045f, openingTopY - 0.05f, openingWidth - 0.08f), trimMat);
            doorLeaf.transform.Rotate(0f, 18f, 0f);
            CreateBox(doorLeaf.transform, "DoorHandle", new Vector3(0.04f, -0.05f, (openingWidth - 0.16f) * 0.42f), new Vector3(0.06f, 0.03f, 0.12f), metalMat);
        }

        private static void BuildWallWithOpeningX(
            Transform parent,
            string prefix,
            float xPos,
            float wallWidth,
            float wallHeight,
            float thickness,
            float openingCenterZ,
            float openingWidth,
            float openingBottomY,
            float openingTopY,
            Material wallMat,
            Material trimMat,
            Material fabricMat)
        {
            float leftLen = (openingCenterZ - openingWidth * 0.5f) + wallWidth * 0.5f;
            float rightLen = wallWidth * 0.5f - (openingCenterZ + openingWidth * 0.5f);

            if (leftLen > 0.01f)
            {
                float leftCenterZ = -wallWidth * 0.5f + leftLen * 0.5f;
                CreateBox(parent, prefix + "_Left", new Vector3(xPos, wallHeight * 0.5f, leftCenterZ), new Vector3(thickness, wallHeight, leftLen), wallMat);
            }

            if (rightLen > 0.01f)
            {
                float rightCenterZ = wallWidth * 0.5f - rightLen * 0.5f;
                CreateBox(parent, prefix + "_Right", new Vector3(xPos, wallHeight * 0.5f, rightCenterZ), new Vector3(thickness, wallHeight, rightLen), wallMat);
            }

            if (openingBottomY > 0.01f)
            {
                CreateBox(parent, prefix + "_Sill", new Vector3(xPos, openingBottomY * 0.5f, openingCenterZ), new Vector3(thickness, openingBottomY, openingWidth), wallMat);
            }

            float headerH = wallHeight - openingTopY;
            if (headerH > 0.01f)
            {
                CreateBox(parent, prefix + "_Header", new Vector3(xPos, openingTopY + headerH * 0.5f, openingCenterZ), new Vector3(thickness, headerH, openingWidth), wallMat);
            }

            float winH = openingTopY - openingBottomY;
            float winMidY = openingBottomY + winH * 0.5f;
            CreateBox(parent, "WindowMullion", new Vector3(xPos, winMidY, openingCenterZ), new Vector3(thickness * 0.4f, winH, 0.04f), trimMat);
            CreateBox(parent, "Curtain_L", new Vector3(xPos - 0.10f, winMidY - 0.15f, openingCenterZ - openingWidth * 0.5f - 0.14f), new Vector3(0.08f, winH + 0.5f, 0.28f), fabricMat);
            CreateBox(parent, "Curtain_R", new Vector3(xPos - 0.10f, winMidY - 0.15f, openingCenterZ + openingWidth * 0.5f + 0.14f), new Vector3(0.08f, winH + 0.5f, 0.28f), fabricMat);
        }

        private static GameObject PlaceModel(
            Transform parent,
            string folder,
            Vector3 pos,
            Vector3 targetSize,
            float yaw,
            bool alignTop,
            float rotX,
            Material fallbackMat)
        {
            GameObject prefab = FindFbxPrefab(folder);
            GameObject instance;
            if (prefab != null)
            {
                instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab, parent);
                instance.name = folder;
                Material modelMat = FindModelMaterial(folder) ?? fallbackMat;
                foreach (Renderer r in instance.GetComponentsInChildren<Renderer>(true))
                {
                    r.sharedMaterial = modelMat;
                }
            }
            else
            {
                instance = GameObject.CreatePrimitive(PrimitiveType.Cube);
                instance.name = folder + "_Procedural";
                instance.transform.SetParent(parent, false);
                instance.GetComponent<Renderer>().sharedMaterial = fallbackMat;
                instance.transform.localScale = targetSize;
            }

            instance.transform.rotation = Quaternion.Euler(0f, yaw, 0f) * Quaternion.Euler(rotX, 0f, 0f);
            Bounds b = CalculateWorldBounds(instance);
            Vector3 size = b.size;
            float scale = Mathf.Min(
                size.x > 1e-4f ? targetSize.x / size.x : 1f,
                Mathf.Min(
                    size.y > 1e-4f ? targetSize.y / size.y : 1f,
                    size.z > 1e-4f ? targetSize.z / size.z : 1f));

            instance.transform.localScale *= scale;
            b = CalculateWorldBounds(instance);

            Vector3 delta = pos - b.center;
            delta.y = alignTop ? (pos.y - b.max.y) : (pos.y - b.min.y);
            instance.transform.position += delta;

            b = CalculateWorldBounds(instance);
            Debug.Log($"PLACED {folder}: scale={scale:F3} size={b.size} center={b.center} min={b.min}");
            return instance;
        }

        private static GameObject FindFbxPrefab(string folder)
        {
            string searchDir = $"Assets/SimData/Models/{folder}";
            if (!Directory.Exists(searchDir)) return null;
            string[] guids = AssetDatabase.FindAssets("t:Model", new[] { searchDir });
            foreach (string g in guids)
            {
                string path = AssetDatabase.GUIDToAssetPath(g);
                if (path.EndsWith(".fbx", StringComparison.OrdinalIgnoreCase))
                {
                    return AssetDatabase.LoadAssetAtPath<GameObject>(path);
                }
            }
            return null;
        }

        private static Material FindModelMaterial(string folder)
        {
            string searchDir = $"Assets/SimData/Models/{folder}";
            if (!Directory.Exists(searchDir)) return null;
            string[] guids = AssetDatabase.FindAssets("t:Texture2D", new[] { searchDir });
            Texture2D diff = null;
            foreach (string g in guids)
            {
                string p = AssetDatabase.GUIDToAssetPath(g);
                if (p.IndexOf("diff", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    diff = AssetDatabase.LoadAssetAtPath<Texture2D>(p);
                    break;
                }
            }
            if (diff == null) return null;
            Material mat = CreateUrpLitBase();
            mat.SetTexture("_BaseMap", diff);
            mat.SetColor("_BaseColor", Color.white);
            return mat;
        }

        private static Material CreateLitMaterial(
            string textureKey,
            Color fallbackColor,
            float smoothness,
            Vector2 tiling,
            List<Material> collector)
        {
            Material mat = CreateUrpLitBase();
            mat.name = "Mat_" + textureKey;

            Texture2D diff = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/SimData/Textures/{textureKey}_diff.jpg");
            Texture2D nor = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/SimData/Textures/{textureKey}_nor.jpg");

            if (diff != null)
            {
                mat.SetTexture("_BaseMap", diff);
                mat.SetTextureScale("_BaseMap", tiling);
                mat.SetColor("_BaseColor", Color.white);
            }
            else
            {
                mat.SetColor("_BaseColor", fallbackColor);
            }

            if (nor != null)
            {
                string norPath = AssetDatabase.GetAssetPath(nor);
                if (AssetImporter.GetAtPath(norPath) is TextureImporter importer && importer.textureType != TextureImporterType.NormalMap)
                {
                    importer.textureType = TextureImporterType.NormalMap;
                    importer.SaveAndReimport();
                    nor = AssetDatabase.LoadAssetAtPath<Texture2D>(norPath);
                }
                mat.SetTexture("_BumpMap", nor);
                mat.SetTextureScale("_BumpMap", tiling);
                mat.EnableKeyword("_NORMALMAP");
            }

            mat.SetFloat("_Smoothness", smoothness);
            mat = PersistMaterialAsset(mat, "Mat_" + textureKey);
            collector.Add(mat);
            return mat;
        }

        private static Material PersistMaterialAsset(Material mat, string assetName)
        {
            EnsureDir("Assets/SimData/Materials");
            string path = $"Assets/SimData/Materials/{assetName}.mat";
            Material existing = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (existing != null)
            {
                EditorUtility.CopySerialized(mat, existing);
                UnityEngine.Object.DestroyImmediate(mat);
                EditorUtility.SetDirty(existing);
                return existing;
            }
            AssetDatabase.CreateAsset(mat, path);
            return mat;
        }

        private static Material CreateUrpLitBase()
        {
            Shader s = Shader.Find("Universal Render Pipeline/Lit");
            if (s == null || s.name.Contains("Hidden", StringComparison.OrdinalIgnoreCase))
            {
                Debug.LogWarning("[Arescope] Universal Render Pipeline/Lit shader missing; falling back to Universal Render Pipeline/Unlit.");
                s = Shader.Find("Universal Render Pipeline/Unlit") ?? Shader.Find("Sprites/Default");
            }
            return new Material(s);
        }

        private static float[] LoadOrSynthesizeMarsHeights(out int rows, out int cols, out float stepMeters)
        {
            rows = MarsGridSize;
            cols = MarsGridSize;
            stepMeters = MarsStepMeters;

            if (File.Exists(MarsJsonPath))
            {
                try
                {
                    string json = File.ReadAllText(MarsJsonPath);
                    HiriseGridData data = JsonUtility.FromJson<HiriseGridData>(json);
                    if (data != null && data.rows > 1 && data.cols > 1)
                    {
                        float[] raw = data.heights != null && data.heights.Length >= data.rows * data.cols
                            ? data.heights
                            : data.elevation;
                        if (raw != null && raw.Length >= data.rows * data.cols)
                        {
                            rows = data.rows;
                            cols = data.cols;
                            stepMeters = data.step_m > 0.01f ? data.step_m : MarsStepMeters;
                            return raw;
                        }
                    }
                }
                catch (Exception ex)
                {
                    Debug.LogWarning($"[Arescope] Failed reading {MarsJsonPath}, using synthetic terrain: {ex.Message}");
                }
            }

            float[] h = new float[rows * cols];
            for (int r = 0; r < rows; r++)
            {
                float nz = (r / (float)(rows - 1)) * 2f - 1f;
                for (int c = 0; c < cols; c++)
                {
                    float nx = (c / (float)(cols - 1)) * 2f - 1f;
                    float ridge = Mathf.Sin(nx * 3.1f + nz * 1.7f) * 18f + Mathf.Cos(nz * 4.3f - nx * 2.1f) * 12f;
                    float slope = nz * 26f + nx * 8f;
                    float dist = Mathf.Sqrt(nx * nx + (nz - 0.15f) * (nz - 0.15f));
                    float crater = dist < 0.45f ? -14f * Mathf.Cos((dist / 0.45f) * Mathf.PI * 0.5f) : 0f;
                    h[r * cols + c] = ridge + slope + crater;
                }
            }
            return h;
        }

        private static Mesh BuildMarsTerrainMesh(float[] heights, int rows, int cols, float stepMeters)
        {
            Mesh mesh = new Mesh();
            mesh.name = "MarsTerrainMesh";
            // Set 32-bit indices BEFORE assigning vertices/triangles (>65,535 vertices).
            mesh.indexFormat = IndexFormat.UInt32;

            int vCount = rows * cols;
            var verts = new Vector3[vCount];
            var uvs = new Vector2[vCount];

            float halfW = (cols - 1) * stepMeters * 0.5f;
            float halfD = (rows - 1) * stepMeters * 0.5f;

            for (int r = 0; r < rows; r++)
            {
                float v = r / (float)(rows - 1);
                float z = r * stepMeters - halfD;
                for (int c = 0; c < cols; c++)
                {
                    float u = c / (float)(cols - 1);
                    float x = c * stepMeters - halfW;
                    int idx = r * cols + c;
                    verts[idx] = new Vector3(x, heights[idx], z);
                    uvs[idx] = new Vector2(u, v);
                }
            }

            int quadCount = (rows - 1) * (cols - 1);
            var tris = new int[quadCount * 6];
            int t = 0;
            for (int r = 0; r < rows - 1; r++)
            {
                for (int c = 0; c < cols - 1; c++)
                {
                    int i00 = r * cols + c;
                    int i10 = i00 + 1;
                    int i01 = i00 + cols;
                    int i11 = i01 + 1;

                    tris[t++] = i00;
                    tris[t++] = i01;
                    tris[t++] = i11;

                    tris[t++] = i00;
                    tris[t++] = i11;
                    tris[t++] = i10;
                }
            }

            mesh.vertices = verts;
            mesh.uv = uvs;
            mesh.triangles = tris;
            mesh.RecalculateNormals();
            mesh.RecalculateTangents();
            mesh.RecalculateBounds();
            return mesh;
        }

        public static float SampleBilinearHeight(float[] heights, int rows, int cols, float stepMeters, float worldX, float worldZ)
        {
            float halfW = (cols - 1) * stepMeters * 0.5f;
            float halfD = (rows - 1) * stepMeters * 0.5f;

            float gx = Mathf.Clamp((worldX + halfW) / stepMeters, 0f, cols - 1.001f);
            float gz = Mathf.Clamp((worldZ + halfD) / stepMeters, 0f, rows - 1.001f);

            int c0 = Mathf.FloorToInt(gx);
            int r0 = Mathf.FloorToInt(gz);
            int c1 = Mathf.Min(c0 + 1, cols - 1);
            int r1 = Mathf.Min(r0 + 1, rows - 1);

            float tx = gx - c0;
            float tz = gz - r0;

            float h00 = heights[r0 * cols + c0];
            float h10 = heights[r0 * cols + c1];
            float h01 = heights[r1 * cols + c0];
            float h11 = heights[r1 * cols + c1];

            float hx0 = Mathf.Lerp(h00, h10, tx);
            float hx1 = Mathf.Lerp(h01, h11, tx);
            return Mathf.Lerp(hx0, hx1, tz);
        }

        private static GameObject CreateBox(Transform parent, string name, Vector3 pos, Vector3 scale, Material mat)
        {
            GameObject go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localScale = scale;
            go.GetComponent<Renderer>().sharedMaterial = mat;
            return go;
        }

        private static GameObject CreateCylinder(Transform parent, string name, Vector3 pos, Vector3 scale, Material mat)
        {
            GameObject go = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localScale = scale;
            go.GetComponent<Renderer>().sharedMaterial = mat;
            return go;
        }

        private static void BuildProceduralPlant(Transform parent, Vector3 pos, Material potMat)
        {
            GameObject plant = new GameObject("Plant");
            plant.transform.SetParent(parent, false);
            plant.transform.localPosition = pos;
            CreateCylinder(plant.transform, "Pot", new Vector3(0f, 0.16f, 0f), new Vector3(0.28f, 0.16f, 0.28f), potMat);

            Material leafMat = CreateUrpLitBase();
            leafMat.SetColor("_BaseColor", new Color(0.18f, 0.42f, 0.20f));
            leafMat = PersistMaterialAsset(leafMat, "Mat_PlantLeaf");
            for (int i = 0; i < 6; i++)
            {
                float a = i * 60f * Mathf.Deg2Rad;
                GameObject leaf = CreateBox(
                    plant.transform,
                    $"Leaf_{i}",
                    new Vector3(Mathf.Cos(a) * 0.12f, 0.42f + (i % 2) * 0.08f, Mathf.Sin(a) * 0.12f),
                    new Vector3(0.08f, 0.34f, 0.03f),
                    leafMat);
                leaf.transform.rotation = Quaternion.Euler(22f, i * 60f, 0f);
            }
        }

        private static Bounds CalculateWorldBounds(GameObject go)
        {
            Renderer[] renderers = go.GetComponentsInChildren<Renderer>(true);
            if (renderers.Length == 0)
            {
                return new Bounds(go.transform.position, Vector3.one);
            }

            Bounds b = renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++)
            {
                b.Encapsulate(renderers[i].bounds);
            }
            return b;
        }

        private static void RegisterBuildScene(string scenePath)
        {
            var scenes = new List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);
            if (!scenes.Exists(s => string.Equals(s.path, scenePath, StringComparison.OrdinalIgnoreCase)))
            {
                scenes.Add(new EditorBuildSettingsScene(scenePath, true));
                EditorBuildSettings.scenes = scenes.ToArray();
            }
        }

        private static float ParseFloat(string s)
        {
            return float.TryParse(s.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out float v) ? v : 0f;
        }

        private static void EnsureDir(string path)
        {
            if (!Directory.Exists(path))
            {
                Directory.CreateDirectory(path);
            }
        }
    }
}
