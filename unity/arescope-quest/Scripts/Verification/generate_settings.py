"""Regenerate only Arescope-owned XR/URP settings using verified package GUIDs.

Meta feature GUIDs: official com.unity.xr.meta-openxr 2.4.1 tarball.
OpenXR/Management GUIDs: official 1.15.1 / 4.5.2 tarballs.
URP GUIDs: Unity-Technologies/Graphics 6000.2/staging.
Does not resolve packages or alter the archived manifest/lock.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n"


def asset(file_id, name, script, body):
    return (f"--- !u!114 &{file_id}\nMonoBehaviour:\n"
            "  m_ObjectHideFlags: 0\n  m_CorrespondingSourceObject: {fileID: 0}\n"
            "  m_PrefabInstance: {fileID: 0}\n  m_PrefabAsset: {fileID: 0}\n"
            "  m_GameObject: {fileID: 0}\n  m_Enabled: 1\n  m_EditorHideFlags: 0\n"
            f"  m_Script: {{fileID: 11500000, guid: {script}, type: 3}}\n"
            f"  m_Name: {name}\n  m_EditorClassIdentifier: \n{body}")


def write(path, guid, text):
    dest = ROOT / path
    if not (path.startswith("Assets/XR/") or path.startswith("Assets/Settings/")):
        raise ValueError("Settings generator scope violation")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")
    dest.with_name(dest.name + ".meta").write_text(
        f"fileFormatVersion: 2\nguid: {guid}\nNativeFormatImporter:\n"
        "  externalObjects: {}\n  mainObjectFileID: 11400000\n  userData: \n"
        "  assetBundleName: \n  assetBundleVariant: \n", encoding="utf-8")


def generate():
    text = PREFIX + asset(11400000, "XRGeneralSettingsPerBuildTarget", "d2dc886499c26824283350fa532d087d",
        "  Keys: 07000000\n  Values:\n  - {fileID: 11400001}\n")
    text += asset(11400001, "Android Settings", "d236b7d11115f2143951f1e14045df39",
        "  m_LoaderManagerInstance: {fileID: 11400002}\n  m_InitManagerOnStart: 1\n")
    text += asset(11400002, "Android Providers", "f4c3631f5e58749a59194e0cf6baf6d5",
        "  m_RequiresSettingsUpdate: 0\n  m_AutomaticLoading: 1\n  m_AutomaticRunning: 1\n"
        "  m_Loaders:\n  - {fileID: 11400003}\n")
    text += asset(11400003, "OpenXR Loader", "d3552e428dc7646a88de3ed3650f87da", "")
    write("Assets/XR/XRGeneralSettingsPerBuildTarget.asset", "b75041287094ca156806da4b56a263ae", text)

    features = [
        ("OpenXRLifeCycleFeature", "MetaOpenXR-OpenXRLifeCycle", "323d71788dcf5ca4b9cb3c4a90e38335", ""),
        ("ARSessionFeature", "com.unity.openxr.feature.arfoundation-meta-session", "076937beb8763d94790d2e9cc1248ac8", "XR_FB_scene_capture"),
        ("AROcclusionFeature", "com.unity.openxr.feature.arfoundation-meta-occlusion", "8b9b8cd1fcf8499eb57f194da9698fcd", "XR_META_environment_depth"),
        ("ARPlaneFeature", "com.unity.openxr.feature.arfoundation-meta-plane", "d00bb9c182ae8406ca03773119fa07ea", "XR_FB_scene XR_FB_spatial_entity XR_FB_spatial_entity_container XR_META_spatial_entity_discovery XR_META_spatial_entity_semantic_label XR_META_spatial_entity_room_mesh"),
        ("ARMeshFeature", "com.unity.openxr.feature.arfoundation-meta-mesh", "f2a13300a9e14cacbb01ed5d6ae84e69", "XR_FB_scene XR_FB_spatial_entity XR_META_spatial_entity_discovery XR_META_spatial_entity_mesh"),
        ("ARAnchorFeature", "com.unity.openxr.feature.arfoundation-meta-anchor", "85fd4a84074c74cb183c18e803dabb9e", "XR_FB_spatial_entity XR_META_spatial_entity_discovery XR_META_spatial_entity_persistence XR_META_spatial_entity_sharing XR_META_spatial_entity_group_sharing XR_FB_spatial_entity_query"),
        ("OpenXRCompositionLayersFeature", "com.unity.openxr.feature.compositionlayers", "6096094d69d82cc40947df806f66ab34", "XR_KHR_composition_layer_cylinder XR_KHR_composition_layer_equirect XR_KHR_composition_layer_equirect2 XR_KHR_composition_layer_cube XR_KHR_composition_layer_color_scale_bias XR_KHR_android_surface_swapchain"),
        ("MetaQuestFeature", "com.unity.openxr.feature.metaquest", "f647cc0545697264a9878224faada6d5", "XR_OCULUS_android_initialize_loader"),
        ("OculusTouchControllerProfile", "com.unity.openxr.feature.input.oculustouch", "feeef8d85de8db242bdda70cc7ff5acd", ""),
    ]
    text = PREFIX + asset(11400000, "OpenXR Package Settings", "9f0ebc320a151d3408ea1e9fce54d40e",
        "  Keys: 07000000\n  Values:\n  - {fileID: 11400001}\n")
    text += asset(11400001, "Android", "b5a1f07dc5afe854f9f12a4194aca3fb",
        "  features:\n" + "".join(f"  - {{fileID: {11400100+i}}}\n" for i in range(len(features))) +
        "  m_renderMode: 1\n  m_depthSubmissionMode: 0\n  m_spaceWarpMotionVectorTextureFormat: 0\n"
        "  m_optimizeBufferDiscards: 1\n  m_symmetricProjection: 1\n")
    for i, (name, feature_id, guid, extensions) in enumerate(features):
        text += asset(11400100+i, name + " Android", guid,
            "  m_enabled: 1\n  nameUi: " + name + "\n  version: " + ("0.1.0" if i<6 else "1.0.0") + "\n"
            "  featureIdInternal: " + feature_id + "\n  openxrExtensionStrings: " + extensions + "\n"
            "  company: Unity\n  priority: " + ("2147483647" if i==0 else "0") + "\n  required: 0\n")
    write("Assets/XR/Settings/OpenXR Package Settings.asset", "f6e83c6fb80f53bdd84bc22c39af25d5", text)

    # Keep the editor-only simulation config reference in the exact build-settings
    # snapshot resolvable using AR Foundation 6.2's actual script GUID.
    text = PREFIX + asset(11400000, "XR Simulation Settings", "e0688bbae6cedcd4a871944e38c19ec0", "")
    write("Assets/XR/Settings/XRSimulationSettings.asset", "338b3c7ee18eb1879bb3a56c029397c2", text)
    text = PREFIX + asset(11400000, "Arescope Quest URP", "bf2edee5c58d82540a51f03df9d42094",
        "  k_AssetVersion: 12\n  k_AssetPreviousVersion: 12\n  m_RendererType: 1\n"
        "  m_RendererData: {fileID: 0}\n  m_RendererDataList:\n"
        "  - {fileID: 11400000, guid: 4375d31a74d64feeb0babd47478f428b, type: 2}\n"
        "  m_DefaultRendererIndex: 0\n  m_RequireDepthTexture: 0\n  m_RequireOpaqueTexture: 0\n"
        "  m_SupportsTerrainHoles: 0\n  m_SupportsHDR: 0\n  m_MSAA: 4\n  m_RenderScale: 1\n"
        "  m_MainLightRenderingMode: 0\n  m_MainLightShadowsSupported: 0\n  m_AdditionalLightsRenderingMode: 0\n"
        "  m_AdditionalLightShadowsSupported: 0\n  m_ShadowDistance: 0\n  m_ShadowCascadeCount: 1\n"
        "  m_SoftShadowsSupported: 0\n  m_UseSRPBatcher: 1\n  m_SupportsDynamicBatching: 0\n"
        "  m_SupportsMixedLighting: 0\n  m_StoreActionsOptimization: 0\n  m_UseAdaptivePerformance: 0\n")
    write("Assets/Settings/ArescopeQuestURP.asset", "a4c4fcbcf6c6473fbf73907828e678fb", text)
    text = PREFIX + asset(11400000, "Arescope Quest Renderer", "de640fe3d0db1804a85f9fc8f5cadab6",
        "  m_RendererFeatures: []\n  m_RendererFeatureMap: \n  m_UseNativeRenderPass: 0\n"
        "  m_AssetVersion: 2\n  m_OpaqueLayerMask:\n    serializedVersion: 2\n    m_Bits: 4294967295\n"
        "  m_TransparentLayerMask:\n    serializedVersion: 2\n    m_Bits: 4294967295\n"
        "  m_DefaultStencilState:\n    overrideStencilState: 0\n    stencilReference: 0\n"
        "    stencilCompareFunction: 8\n    passOperation: 0\n    failOperation: 0\n    zFailOperation: 0\n"
        "  m_ShadowTransparentReceive: 0\n  m_RenderingMode: 0\n  m_DepthPrimingMode: 0\n"
        "  m_CopyDepthMode: 0\n  m_DepthAttachmentFormat: 0\n  m_DepthTextureFormat: 0\n"
        "  m_AccurateGbufferNormals: 0\n  m_IntermediateTextureMode: 1\n")
    write("Assets/Settings/ArescopeQuestRenderer.asset", "4375d31a74d64feeb0babd47478f428b", text)
    print("Generated XR settings, nine Android features and URP asset/renderer")


if __name__ == "__main__":
    generate()
