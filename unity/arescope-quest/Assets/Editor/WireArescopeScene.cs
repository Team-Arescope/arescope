using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.XR.Management;
using UnityEditor.XR.OpenXR.Features;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.Management;
using UnityEngine.XR.OpenXR.Features;
using Arescope;
using Arescope.Client;
using Arescope.Hud;

namespace Arescope.Editor
{
    public static class WireArescopeScene
    {
        public const string ScenePath = "Assets/Scenes/QuestRoomScan-REVIEW-ONLY.unity";
        private const string OpenXrSettingsAssetPath = "Assets/XR/Settings/OpenXR Package Settings.asset";
        private const string XrGeneralSettingsAssetPath = "Assets/XR/XRGeneralSettingsPerBuildTarget.asset";

        private static readonly string[] RequiredOpenXrFeatureIds =
        {
            "MetaOpenXR-OpenXRLifeCycle",
            "com.unity.openxr.feature.arfoundation-meta-session",
            "com.unity.openxr.feature.arfoundation-meta-occlusion",
            "com.unity.openxr.feature.compositionlayers",
            "com.meta.openxr.feature.metaxr"
        };

        private static readonly string[] RoomScanComponentNames =
        {
            "RoomScanSession",
            "RoomUnderstanding",
            "TextureRefinement",
            "KeyframeCollector",
            "PassthroughCameraProvider",
            "RoomScanner",
            "RoomAnchorManager",
            "RoomScanPersistence",
            "MeshExtractor",
            "VolumeIntegrator",
            "DepthCapture"
        };

        [MenuItem("Arescope/Wire Scene")]
        public static void Run()
        {
            EnsureDirectory("Assets/Scenes");
            Scene scene = File.Exists(ScenePath)
                ? EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single)
                : EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            GameObject roomScanGo = FindOrCreateRoot(scene, "RoomScan");
            GameObject cameraRigGo = FindOrCreateRoot(scene, "[BuildingBlock] Camera Rig");
            GameObject passthroughGo = FindOrCreateRoot(scene, "[BuildingBlock] Passthrough");
            GameObject pcaGo = FindOrCreateRoot(scene, "[BuildingBlock] Passthrough Camera Access");
            GameObject arSessionGo = FindOrCreateRoot(scene, "AR Session");
            GameObject copilotGo = FindOrCreateRoot(scene, "ArescopeCopilot");

            // 1. Camera Rig + TrackingSpace + Anchors
            EnsureComponent<OVRCameraRig>(cameraRigGo);
            Transform trackingSpace = EnsureChild(cameraRigGo.transform, "TrackingSpace");
            Transform centerEye = EnsureChild(trackingSpace, "CenterEyeAnchor");
            EnsureChild(trackingSpace, "LeftEyeAnchor");
            EnsureChild(trackingSpace, "RightEyeAnchor");
            EnsureChild(trackingSpace, "LeftControllerAnchor");
            EnsureChild(trackingSpace, "RightControllerAnchor");

            centerEye.tag = "MainCamera";
            Camera centerEyeCam = EnsureComponent<Camera>(centerEye.gameObject);
            centerEyeCam.clearFlags = CameraClearFlags.SolidColor;
            centerEyeCam.backgroundColor = new Color(0f, 0f, 0f, 0f);
            centerEyeCam.nearClipPlane = 0.05f;
            centerEyeCam.farClipPlane = 100f;
            centerEyeCam.cullingMask &= ~(1 << ArescopeHudController.HudLayer);
            EnsureComponent<AudioListener>(centerEye.gameObject);

            // 2. Passthrough & Passthrough Camera Access
            OVRPassthroughLayer passthroughLayer = EnsureComponent<OVRPassthroughLayer>(passthroughGo);
            passthroughLayer.overlayType = OVROverlay.OverlayType.Underlay;
            passthroughLayer.compositionDepth = 0;

            Type pcaType = ResolveType("Genesis.RoomScan.PassthroughCameraProvider", "PassthroughCameraProvider");
            if (pcaType != null)
            {
                Component pcaComp = EnsureComponentByType(pcaGo, pcaType);
                ConfigurePassthroughCameraProvider(pcaComp);
            }

            // 3. AR Session + AROcclusionManager
            EnsureComponent<ARSession>(arSessionGo);
            EnsureComponent<AROcclusionManager>(arSessionGo);

            // 4. RoomScan object + App 28 serialized parameters + scanRenderer
            foreach (string compName in RoomScanComponentNames)
            {
                Type t = ResolveType("Genesis.RoomScan." + compName, compName);
                if (t != null)
                {
                    Component comp = EnsureComponentByType(roomScanGo, t);
                    ApplyRoomScanParameters(compName, comp);
                }
            }

            Renderer scanRenderer = ResolveOrCreateScanRenderer(roomScanGo);

            // 5. ArescopeCopilot + AudioSource + all 15 required components
            AudioSource audioSource = EnsureComponent<AudioSource>(copilotGo);
            audioSource.playOnAwake = false;
            audioSource.spatialBlend = 0f;

            CopilotClient copilotClient = EnsureComponent<CopilotClient>(copilotGo);
            ArescopeHudController hudController = EnsureComponent<ArescopeHudController>(copilotGo);
            ViewModeController viewModeController = EnsureComponent<ViewModeController>(copilotGo);
            CopilotHudBridge copilotHudBridge = EnsureComponent<CopilotHudBridge>(copilotGo);
            ScanModeBridge scanModeBridge = EnsureComponent<ScanModeBridge>(copilotGo);
            ScanProgressHud scanProgressHud = EnsureComponent<ScanProgressHud>(copilotGo);
            LiveScanMinimap liveScanMinimap = EnsureComponent<LiveScanMinimap>(copilotGo);
            LiveFrameSender liveFrameSender = EnsureComponent<LiveFrameSender>(copilotGo);
            EnsureComponent<MeshUploader>(copilotGo);
            EnsureComponent<ScanDiagnostics>(copilotGo);
            EnsureComponent<ARSessionBootstrap>(copilotGo);
            HudOverlay hudOverlay = EnsureComponent<HudOverlay>(copilotGo);
            HudContrast hudContrast = EnsureComponent<HudContrast>(copilotGo);
            LogUploader logUploader = EnsureComponent<LogUploader>(copilotGo);
            CopilotConnectionConfig connectionConfig = EnsureComponent<CopilotConnectionConfig>(copilotGo);

            // Wire serialized fields matching App 18 / 27 / 28
            SetSerializedFields(copilotClient, so =>
            {
                SetStringIfEmpty(so, "baseUrl", "https://localhost");
                SetFloat(so, "requestTimeoutSeconds", 45f);
                SetFloat(so, "settingsPollIntervalSeconds", 30f);
                SetFloat(so, "maxRecordingSeconds", 60f);
                SetInt(so, "maxResponseBytes", 2097152);
                SetString(so, "chatPath", "/api/copilot/chat");
                SetInt(so, "sampleRate", 16000);
                SetObjectRef(so, "audioSource", audioSource);
            });

            SetSerializedFields(connectionConfig, so =>
            {
                SetString(so, "endpointResourceName", "arescope-endpoint");
            });

            hudController.targetCamera = centerEye;
            hudController.followDistance = 1.15f;
            hudController.followSmoothing = 14f;
            hudController.followMode = 0;
            hudController.canvasSize = new Vector2(1.7f, 1.0f);
            EditorUtility.SetDirty(hudController);

            SetSerializedFields(copilotHudBridge, so =>
            {
                SetInt(so, "controller", 5);
                SetFloat(so, "pressThreshold", 0.75f);
                SetFloat(so, "releaseThreshold", 0.35f);
                SetObjectRef(so, "client", copilotClient);
                SetObjectRef(so, "hud", hudController);
            });

            // Fix App 27 null ViewModeController references explicitly.
            viewModeController.headsetCamera = centerEyeCam;
            viewModeController.passthroughLayer = passthroughLayer;
            viewModeController.scanRenderer = scanRenderer;
            viewModeController.Configure(centerEyeCam, passthroughLayer, scanRenderer, scanRenderer != null ? scanRenderer.gameObject : roomScanGo);
            EditorUtility.SetDirty(viewModeController);

            scanModeBridge.modes = viewModeController;
            scanModeBridge.hud = hudController;
            scanModeBridge.headsetCamera = centerEyeCam;
            scanModeBridge.passthroughLayer = passthroughLayer;
            scanModeBridge.resetHoldSeconds = 1.2f;
            EditorUtility.SetDirty(scanModeBridge);

            liveScanMinimap.hud = hudController;
            liveScanMinimap.headsetTransform = centerEye;
            EditorUtility.SetDirty(liveScanMinimap);

            liveFrameSender.headsetTransform = centerEye;
            EditorUtility.SetDirty(liveFrameSender);

            scanProgressHud.hud = hudController;
            EditorUtility.SetDirty(scanProgressHud);

            hudOverlay.headCamera = centerEyeCam;
            hudOverlay.hud = hudController;
            EditorUtility.SetDirty(hudOverlay);

            hudContrast.hud = hudController;
            EditorUtility.SetDirty(hudContrast);

            logUploader.hud = hudController;
            EditorUtility.SetDirty(logUploader);

            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene, ScenePath);
            EnsureSceneInBuildSettings(ScenePath);
            ConfigureAndroidXrSettings();
            AssetDatabase.SaveAssets();

            Debug.Log("[Arescope] WireArescopeScene.Run completed: " + ScenePath);
        }

        private static Renderer ResolveOrCreateScanRenderer(GameObject roomScanGo)
        {
            Renderer existing = roomScanGo.GetComponentInChildren<MeshRenderer>(true);
            if (existing != null)
            {
                return existing;
            }

            Transform child = EnsureChild(roomScanGo.transform, "ScanVisualRoot");
            EnsureComponent<MeshFilter>(child.gameObject);
            MeshRenderer mr = EnsureComponent<MeshRenderer>(child.gameObject);
            Shader wireShader = Shader.Find("Arescope/Wire") ?? Resources.Load<Shader>("ArescopeWire");
            if (wireShader != null && mr.sharedMaterial == null)
            {
                Material mat = new Material(wireShader);
                mr.sharedMaterial = mat;
            }
            return mr;
        }

        private static void ConfigurePassthroughCameraProvider(Component comp)
        {
            if (comp == null) return;
            SetSerializedFields(comp, so =>
            {
                SetInt(so, "cameraPosition", 0);
                SetVector2Int(so, "requestedResolution", new Vector2Int(1280, 960));
                SetInt(so, "maxFramerate", 30);
            });
        }

        private static void ApplyRoomScanParameters(string compName, Component comp)
        {
            if (comp == null) return;
            SetSerializedFields(comp, so =>
            {
                switch (compName)
                {
                    case "PassthroughCameraProvider":
                        SetInt(so, "cameraPosition", 0);
                        SetVector2Int(so, "requestedResolution", new Vector2Int(1280, 960));
                        SetInt(so, "maxFramerate", 30);
                        break;
                    case "KeyframeCollector":
                        SetFloat(so, "moveThreshold", 0.15f);
                        SetFloat(so, "rotateThresholdDeg", 10f);
                        SetFloat(so, "bandGapM", 0.5f);
                        SetFloat(so, "standingYawDeg", 8f);
                        SetInt(so, "jpegQuality", 95);
                        SetFloat(so, "maxAngularVelocity", 120f);
                        SetFloat(so, "minCaptureInterval", 0.25f);
                        SetFloat(so, "maxHandCoverage", 0.12f);
                        break;
                    case "RoomScanner":
                        SetFloat(so, "integrationHz", 30f);
                        SetFloat(so, "meshExtractionHz", 8f);
                        SetInt(so, "renderMode", 0);
                        SetFloat(so, "wireThickness", 1.5f);
                        SetBool(so, "showFreezeTint", true);
                        SetInt(so, "logLevel", 1);
                        SetBool(so, "confineScanToContainingRoom", false);
                        SetBool(so, "stampScreenPlanes", true);
                        SetBool(so, "showSceneObjects", false);
                        break;
                    case "MeshExtractor":
                        SetInt(so, "meshSmoothIterations", 1);
                        SetFloat(so, "meshSmoothLambda", 0.33f);
                        SetFloat(so, "meshSmoothBeta", 0.5f);
                        SetFloat(so, "temporalAlphaMax", 0.85f);
                        SetFloat(so, "temporalAlphaMin", 0.1f);
                        SetFloat(so, "temporalDecayRate", 0.15f);
                        SetFloat(so, "convergenceThreshold", 0.005f);
                        SetFloat(so, "temporalDeadzone", 0.001f);
                        SetFloat(so, "birthFadeSeconds", 1f);
                        SetFloat(so, "birthGrowMetres", 0.08f);
                        SetFloat(so, "meshMorphSeconds", 0.28f);
                        SetFloat(so, "gpuVertexBudgetPercent", 0.08f);
                        break;
                    case "VolumeIntegrator":
                        SetFloat(so, "voxelSize", 0.05f);
                        SetFloat(so, "voxelDistance", 0.15f);
                        SetFloat(so, "voxelMin", 0.1f);
                        SetFloat(so, "depthDisparityThreshold", 0.5f);
                        SetFloat(so, "maxUpdateDist", 5f);
                        SetFloat(so, "minUpdateDist", 0.5f);
                        SetInt(so, "maxFrustumPositions", 1000000);
                        SetFloat(so, "blendRate", 0.8f);
                        SetFloat(so, "stability", 2.5f);
                        SetFloat(so, "weightGrowth", 0.025f);
                        SetFloat(so, "maxWeight", 0.5f);
                        SetFloat(so, "minMeshWeight", 0.08f);
                        SetFloat(so, "cameraExposure", 3.0f);
                        SetInt(so, "warmupIntegrations", 3);
                        SetBool(so, "eraseBodyBlobs", false);
                        SetBool(so, "autoFillShellGaps", true);
                        SetBool(so, "closeFurnitureHoles", true);
                        SetBool(so, "fillLeaks", true);
                        break;
                    case "DepthCapture":
                        SetBool(so, "enableBilateralFilter", true);
                        SetFloat(so, "sigmaSpatial", 3f);
                        SetFloat(so, "sigmaColor", 0.1f);
                        SetFloat(so, "sigmaDepth", 0.02f);
                        SetInt(so, "filterRadius", 2);
                        SetInt(so, "dilationSteps", 8);
                        SetFloat(so, "voxelDistance", 0.2f);
                        SetFloat(so, "voxelSize", 0.05f);
                        SetBool(so, "removeHandsFromDepth", true);
                        break;
                }
            });
        }

        private static void ConfigureAndroidXrSettings()
        {
            if (File.Exists(XrGeneralSettingsAssetPath))
            {
                var perTarget = AssetDatabase.LoadAssetAtPath<XRGeneralSettingsPerBuildTarget>(XrGeneralSettingsAssetPath);
                if (perTarget != null)
                {
                    XRGeneralSettings androidSettings = perTarget.SettingsForBuildTarget(BuildTargetGroup.Android);
                    if (androidSettings != null)
                    {
                        androidSettings.InitManagerOnStart = true;
                        var so = new SerializedObject(androidSettings);
                        SetBool(so, "m_InitManagerOnStart", true);
                        if (androidSettings.Manager != null)
                        {
                            var mso = new SerializedObject(androidSettings.Manager);
                            SetBool(mso, "m_AutomaticLoading", true);
                            SetBool(mso, "m_AutomaticRunning", true);
                            mso.ApplyModifiedPropertiesWithoutUndo();
                        }
                        so.ApplyModifiedPropertiesWithoutUndo();
                        EditorUtility.SetDirty(androidSettings);
                    }
                }
            }

            try
            {
                FeatureHelpers.RefreshFeatures(BuildTargetGroup.Android);
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[Arescope] FeatureHelpers.RefreshFeatures warning: {ex.Message}");
            }

            if (File.Exists(OpenXrSettingsAssetPath))
            {
                foreach (UnityEngine.Object asset in AssetDatabase.LoadAllAssetsAtPath(OpenXrSettingsAssetPath))
                {
                    if (asset is not OpenXRFeature feature)
                    {
                        continue;
                    }

                    if (!feature.name.Contains("Android"))
                    {
                        continue;
                    }

                    string id = GetFeatureId(feature);
                    if (string.IsNullOrEmpty(id) || !RequiredOpenXrFeatureIds.Contains(id))
                    {
                        continue;
                    }

                    var so = new SerializedObject(feature);
                    SerializedProperty enabledProp = so.FindProperty("m_enabled");
                    if (enabledProp != null && !enabledProp.boolValue)
                    {
                        enabledProp.boolValue = true;
                        so.ApplyModifiedPropertiesWithoutUndo();
                        EditorUtility.SetDirty(feature);
                    }
                }
            }
        }

        internal static string GetFeatureId(OpenXRFeature feature)
        {
            if (feature == null) return null;
            FieldInfo fi = feature.GetType().GetField(
                "featureId",
                BindingFlags.Public | BindingFlags.Static | BindingFlags.FlattenHierarchy);
            return fi?.GetValue(null) as string;
        }

        private static void EnsureSceneInBuildSettings(string scenePath)
        {
            var scenes = new List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);
            int idx = scenes.FindIndex(s => string.Equals(s.path, scenePath, StringComparison.OrdinalIgnoreCase));
            if (idx >= 0)
            {
                if (!scenes[idx].enabled)
                {
                    scenes[idx] = new EditorBuildSettingsScene(scenePath, true);
                    EditorBuildSettings.scenes = scenes.ToArray();
                }
                return;
            }

            scenes.Insert(0, new EditorBuildSettingsScene(scenePath, true));
            EditorBuildSettings.scenes = scenes.ToArray();
        }

        private static GameObject FindOrCreateRoot(Scene scene, string name)
        {
            foreach (GameObject root in scene.GetRootGameObjects())
            {
                if (root.name == name)
                {
                    return root;
                }
            }

            return new GameObject(name);
        }

        private static Transform EnsureChild(Transform parent, string name)
        {
            Transform existing = parent.Find(name);
            if (existing != null)
            {
                return existing;
            }

            GameObject go = new GameObject(name);
            go.transform.SetParent(parent, false);
            return go.transform;
        }

        private static T EnsureComponent<T>(GameObject go) where T : Component
        {
            T existing = go.GetComponent<T>();
            return existing != null ? existing : go.AddComponent<T>();
        }

        private static Component EnsureComponentByType(GameObject go, Type type)
        {
            Component existing = go.GetComponent(type);
            return existing != null ? existing : go.AddComponent(type);
        }

        internal static Type ResolveType(params string[] candidateNames)
        {
            foreach (Assembly asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                foreach (string name in candidateNames)
                {
                    Type exact = asm.GetType(name, false);
                    if (exact != null)
                    {
                        return exact;
                    }
                }
            }

            foreach (Assembly asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                Type[] types;
                try
                {
                    types = asm.GetTypes();
                }
                catch (ReflectionTypeLoadException ex)
                {
                    types = ex.Types;
                }

                if (types == null) continue;
                foreach (Type t in types)
                {
                    if (t == null) continue;
                    if (candidateNames.Contains(t.Name, StringComparer.Ordinal))
                    {
                        return t;
                    }
                }
            }

            return null;
        }

        private static void SetSerializedFields(UnityEngine.Object target, Action<SerializedObject> apply)
        {
            if (target == null) return;
            var so = new SerializedObject(target);
            apply(so);
            so.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(target);
        }

        private static void SetString(SerializedObject so, string propName, string value)
        {
            SerializedProperty p = so.FindProperty(propName);
            if (p != null && p.propertyType == SerializedPropertyType.String)
            {
                p.stringValue = value;
            }
        }

        private static void SetStringIfEmpty(SerializedObject so, string propName, string value)
        {
            SerializedProperty p = so.FindProperty(propName);
            if (p != null && p.propertyType == SerializedPropertyType.String && string.IsNullOrEmpty(p.stringValue))
            {
                p.stringValue = value;
            }
        }

        private static void SetFloat(SerializedObject so, string propName, float value)
        {
            SerializedProperty p = so.FindProperty(propName);
            if (p != null && p.propertyType == SerializedPropertyType.Float)
            {
                p.floatValue = value;
            }
        }

        private static void SetInt(SerializedObject so, string propName, int value)
        {
            SerializedProperty p = so.FindProperty(propName);
            if (p != null && (p.propertyType == SerializedPropertyType.Integer || p.propertyType == SerializedPropertyType.Enum))
            {
                p.intValue = value;
            }
        }

        private static void SetBool(SerializedObject so, string propName, bool value)
        {
            SerializedProperty p = so.FindProperty(propName);
            if (p != null && p.propertyType == SerializedPropertyType.Boolean)
            {
                p.boolValue = value;
            }
        }

        private static void SetVector2Int(SerializedObject so, string propName, Vector2Int value)
        {
            SerializedProperty p = so.FindProperty(propName);
            if (p != null && p.propertyType == SerializedPropertyType.Vector2Int)
            {
                p.vector2IntValue = value;
            }
        }

        private static void SetObjectRef(SerializedObject so, string propName, UnityEngine.Object value)
        {
            SerializedProperty p = so.FindProperty(propName);
            if (p != null && p.propertyType == SerializedPropertyType.ObjectReference)
            {
                p.objectReferenceValue = value;
            }
        }

        private static void EnsureDirectory(string path)
        {
            if (!Directory.Exists(path))
            {
                Directory.CreateDirectory(path);
            }
        }
    }
}
