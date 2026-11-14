using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.XR.Management;
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
    public static class ValidateArescopeScene
    {
        private const string ScenePath = WireArescopeScene.ScenePath;
        private const string OpenXrSettingsAssetPath = "Assets/XR/Settings/OpenXR Package Settings.asset";
        private const string XrGeneralSettingsAssetPath = "Assets/XR/XRGeneralSettingsPerBuildTarget.asset";

        [MenuItem("Arescope/Validate Scene")]
        public static bool Run()
        {
            var failures = new List<string>();

            if (!File.Exists(ScenePath))
            {
                failures.Add($"Missing scene: {ScenePath}");
                ReportFailures(failures);
                return false;
            }

            bool inBuild = EditorBuildSettings.scenes.Any(
                s => s.enabled && string.Equals(s.path, ScenePath, StringComparison.OrdinalIgnoreCase));
            if (!inBuild)
            {
                failures.Add($"Scene not enabled in EditorBuildSettings: {ScenePath}");
            }

            Scene scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            GameObject[] roots = scene.GetRootGameObjects();

            GameObject roomScan = FindRoot(roots, "RoomScan");
            GameObject cameraRig = FindRoot(roots, "[BuildingBlock] Camera Rig");
            GameObject passthrough = FindRoot(roots, "[BuildingBlock] Passthrough");
            GameObject passthroughCam = FindRoot(roots, "[BuildingBlock] Passthrough Camera Access");
            GameObject arSession = FindRoot(roots, "AR Session");
            GameObject copilot = FindRoot(roots, "ArescopeCopilot");

            RequireObject(roomScan, "RoomScan", failures);
            RequireObject(cameraRig, "[BuildingBlock] Camera Rig", failures);
            RequireObject(passthrough, "[BuildingBlock] Passthrough", failures);
            RequireObject(passthroughCam, "[BuildingBlock] Passthrough Camera Access", failures);
            RequireObject(arSession, "AR Session", failures);
            RequireObject(copilot, "ArescopeCopilot", failures);

            if (cameraRig != null && cameraRig.GetComponent<OVRCameraRig>() == null)
            {
                failures.Add("[BuildingBlock] Camera Rig missing OVRCameraRig");
            }

            if (passthrough != null && passthrough.GetComponent<OVRPassthroughLayer>() == null)
            {
                failures.Add("[BuildingBlock] Passthrough missing OVRPassthroughLayer");
            }

            if (arSession != null)
            {
                if (arSession.GetComponent<ARSession>() == null) failures.Add("AR Session missing ARSession");
                if (arSession.GetComponent<AROcclusionManager>() == null) failures.Add("AR Session missing AROcclusionManager");
            }

            if (copilot != null)
            {
                ValidateCopilotComponents(copilot, failures);
            }

            ValidateXrAutoStart(failures);
            ValidateOpenXrFeatures(failures);

            if (failures.Count > 0)
            {
                ReportFailures(failures);
                return false;
            }

            Debug.Log("[Arescope] ValidateArescopeScene.Run PASSED: all objects, references, XR auto-start, and OpenXR features verified.");
            return true;
        }

        private static void ValidateCopilotComponents(GameObject copilot, List<string> failures)
        {
            if (copilot.GetComponent<AudioSource>() == null) failures.Add("ArescopeCopilot missing AudioSource");
            var client = RequireComp<CopilotClient>(copilot, "CopilotClient", failures);
            var hud = RequireComp<ArescopeHudController>(copilot, "ArescopeHudController", failures);
            var viewModes = RequireComp<ViewModeController>(copilot, "ViewModeController", failures);
            var copilotBridge = RequireComp<CopilotHudBridge>(copilot, "CopilotHudBridge", failures);
            var scanBridge = RequireComp<ScanModeBridge>(copilot, "ScanModeBridge", failures);
            var progressHud = RequireComp<ScanProgressHud>(copilot, "ScanProgressHud", failures);
            var minimap = RequireComp<LiveScanMinimap>(copilot, "LiveScanMinimap", failures);
            var frameSender = RequireComp<LiveFrameSender>(copilot, "LiveFrameSender", failures);
            RequireComp<MeshUploader>(copilot, "MeshUploader", failures);
            RequireComp<ScanDiagnostics>(copilot, "ScanDiagnostics", failures);
            RequireComp<ARSessionBootstrap>(copilot, "ARSessionBootstrap", failures);
            var hudOverlay = RequireComp<HudOverlay>(copilot, "HudOverlay", failures);
            var hudContrast = RequireComp<HudContrast>(copilot, "HudContrast", failures);
            var logUploader = RequireComp<LogUploader>(copilot, "LogUploader", failures);
            RequireComp<CopilotConnectionConfig>(copilot, "CopilotConnectionConfig", failures);

            if (viewModes != null)
            {
                if (viewModes.headsetCamera == null) failures.Add("ViewModeController.headsetCamera is null");
                if (viewModes.passthroughLayer == null) failures.Add("ViewModeController.passthroughLayer is null");
                if (viewModes.scanRenderer == null) failures.Add("ViewModeController.scanRenderer is null");
            }

            if (scanBridge != null)
            {
                if (scanBridge.modes == null) failures.Add("ScanModeBridge.modes is null");
                if (scanBridge.hud == null) failures.Add("ScanModeBridge.hud is null");
                if (scanBridge.headsetCamera == null) failures.Add("ScanModeBridge.headsetCamera is null");
                if (scanBridge.passthroughLayer == null) failures.Add("ScanModeBridge.passthroughLayer is null");
            }

            if (hud != null && hud.targetCamera == null)
            {
                failures.Add("ArescopeHudController.targetCamera is null");
            }

            if (copilotBridge != null)
            {
                var so = new SerializedObject(copilotBridge);
                if (so.FindProperty("client")?.objectReferenceValue == null) failures.Add("CopilotHudBridge.client is null");
                if (so.FindProperty("hud")?.objectReferenceValue == null) failures.Add("CopilotHudBridge.hud is null");
            }

            if (client != null)
            {
                var so = new SerializedObject(client);
                if (so.FindProperty("audioSource")?.objectReferenceValue == null) failures.Add("CopilotClient.audioSource is null");
            }

            if (minimap != null)
            {
                if (minimap.hud == null) failures.Add("LiveScanMinimap.hud is null");
                if (minimap.headsetTransform == null) failures.Add("LiveScanMinimap.headsetTransform is null");
            }

            if (frameSender != null && frameSender.headsetTransform == null)
            {
                failures.Add("LiveFrameSender.headsetTransform is null");
            }

            if (hudOverlay != null)
            {
                if (hudOverlay.headCamera == null) failures.Add("HudOverlay.headCamera is null");
                if (hudOverlay.hud == null) failures.Add("HudOverlay.hud is null");
            }

            if (hudContrast != null && hudContrast.hud == null) failures.Add("HudContrast.hud is null");
            if (logUploader != null && logUploader.hud == null) failures.Add("LogUploader.hud is null");
            if (progressHud != null && progressHud.hud == null) failures.Add("ScanProgressHud.hud is null");
        }

        private static void ValidateXrAutoStart(List<string> failures)
        {
            if (!File.Exists(XrGeneralSettingsAssetPath))
            {
                failures.Add($"Missing XR General Settings asset: {XrGeneralSettingsAssetPath}");
                return;
            }

            var perTarget = AssetDatabase.LoadAssetAtPath<XRGeneralSettingsPerBuildTarget>(XrGeneralSettingsAssetPath);
            if (perTarget == null)
            {
                failures.Add($"Unable to load XRGeneralSettingsPerBuildTarget at {XrGeneralSettingsAssetPath}");
                return;
            }

            XRGeneralSettings android = perTarget.SettingsForBuildTarget(BuildTargetGroup.Android);
            if (android == null)
            {
                failures.Add("Missing Android XRGeneralSettings");
                return;
            }

            if (!android.InitManagerOnStart)
            {
                failures.Add("XRGeneralSettings Android InitManagerOnStart is false");
            }

            if (android.Manager == null || android.Manager.activeLoaders == null || android.Manager.activeLoaders.Count == 0)
            {
                failures.Add("XRGeneralSettings Android has no active XR loaders");
            }
            else
            {
                bool hasOpenXr = android.Manager.activeLoaders.Any(l => l != null && l.GetType().Name.Contains("OpenXR"));
                if (!hasOpenXr)
                {
                    failures.Add("XRGeneralSettings Android activeLoaders missing OpenXRLoader");
                }
            }
        }

        private static void ValidateOpenXrFeatures(List<string> failures)
        {
            if (!File.Exists(OpenXrSettingsAssetPath))
            {
                failures.Add($"Missing OpenXR settings asset: {OpenXrSettingsAssetPath}");
                return;
            }

            bool lifecycleEnabled = false;
            bool occlusionEnabled = false;

            foreach (UnityEngine.Object asset in AssetDatabase.LoadAllAssetsAtPath(OpenXrSettingsAssetPath))
            {
                if (asset is not OpenXRFeature feature || !feature.name.Contains("Android"))
                {
                    continue;
                }

                string id = WireArescopeScene.GetFeatureId(feature);
                if (string.IsNullOrEmpty(id))
                {
                    continue;
                }

                if (id == "MetaOpenXR-OpenXRLifeCycle" && feature.enabled)
                {
                    lifecycleEnabled = true;
                }
                else if (id == "com.unity.openxr.feature.arfoundation-meta-occlusion" && feature.enabled)
                {
                    occlusionEnabled = true;
                }
            }

            if (!lifecycleEnabled)
            {
                failures.Add("OpenXR Android feature MetaOpenXR-OpenXRLifeCycle is disabled or missing");
            }

            if (!occlusionEnabled)
            {
                failures.Add("OpenXR Android feature com.unity.openxr.feature.arfoundation-meta-occlusion is disabled or missing");
            }
        }

        private static GameObject FindRoot(GameObject[] roots, string name)
        {
            return roots.FirstOrDefault(r => r != null && r.name == name);
        }

        private static void RequireObject(GameObject go, string name, List<string> failures)
        {
            if (go == null) failures.Add($"Missing scene GameObject: {name}");
        }

        private static T RequireComp<T>(GameObject go, string label, List<string> failures) where T : Component
        {
            T comp = go.GetComponent<T>();
            if (comp == null) failures.Add($"{go.name} missing component {label}");
            return comp;
        }

        private static void ReportFailures(List<string> failures)
        {
            foreach (string f in failures)
            {
                Debug.LogError("[Arescope Validate] " + f);
            }
        }
    }
}
