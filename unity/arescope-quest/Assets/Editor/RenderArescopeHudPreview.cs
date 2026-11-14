using System;
using System.IO;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Arescope.Hud;

namespace Arescope.Editor
{
    public static class RenderArescopeHudPreview
    {
        private const int Width = 1600;
        private const int Height = 900;

        [MenuItem("Arescope/Render HUD Preview")]
        public static void Run()
        {
            string outPath = Environment.GetEnvironmentVariable("ARESCOPE_HUD_PREVIEW_PATH");
            if (string.IsNullOrWhiteSpace(outPath))
            {
                outPath = "Build/hud-preview.png";
            }

            string bgEnv = Environment.GetEnvironmentVariable("ARESCOPE_PREVIEW_BG");
            bool lightBg = string.Equals(bgEnv, "light", StringComparison.OrdinalIgnoreCase);
            Color bgColor = lightBg
                ? new Color(0.78f, 0.78f, 0.78f, 1f)
                : new Color(0.06f, 0.06f, 0.07f, 1f);

            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            GameObject camGo = new GameObject("PreviewCamera");
            camGo.transform.position = new Vector3(0f, 1.6f, 0f);
            camGo.transform.rotation = Quaternion.identity;
            Camera cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = bgColor;
            cam.fieldOfView = 60f;
            cam.nearClipPlane = 0.05f;
            cam.farClipPlane = 100f;
            cam.cullingMask = ~0;

            GameObject hudGo = new GameObject("PreviewHud");
            ArescopeHudController hud = hudGo.AddComponent<ArescopeHudController>();
            hud.targetCamera = cam.transform;
            hud.followDistance = 1.15f;
            hud.followMode = 1; // Hard snap
            hud.canvasSize = new Vector2(1.7f, 1.0f);

            MethodInfo awakeMethod = typeof(ArescopeHudController).GetMethod(
                "Awake",
                BindingFlags.Instance | BindingFlags.NonPublic);
            awakeMethod?.Invoke(hud, null);

            hud.ApplyPreviewFixture();

            MethodInfo lateUpdateMethod = typeof(ArescopeHudController).GetMethod(
                "LateUpdate",
                BindingFlags.Instance | BindingFlags.NonPublic);
            lateUpdateMethod?.Invoke(hud, null);

            CaptureCameraToPng(cam, outPath, Width, Height);
            Debug.Log($"[Arescope] Rendered HUD preview ({Width}x{Height}, bg={(lightBg ? "light" : "dark")}) -> {outPath}");
        }

        internal static void CaptureCameraToPng(Camera cam, string outPath, int width, int height)
        {
            string dir = Path.GetDirectoryName(outPath);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
            {
                Directory.CreateDirectory(dir);
            }

            cam.aspect = width / (float)height;
            cam.ResetProjectionMatrix();
            cam.projectionMatrix = Matrix4x4.Perspective(
                cam.fieldOfView,
                cam.aspect,
                cam.nearClipPlane,
                cam.farClipPlane);

            Canvas.ForceUpdateCanvases();

            var rt = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            var tex = new Texture2D(width, height, TextureFormat.RGBA32, false);
            RenderTexture prevActive = RenderTexture.active;
            RenderTexture prevTarget = cam.targetTexture;
            try
            {
                cam.targetTexture = rt;
                cam.Render();
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                tex.Apply();
                byte[] png = tex.EncodeToPNG();
                File.WriteAllBytes(outPath, png);
            }
            finally
            {
                cam.targetTexture = prevTarget;
                RenderTexture.active = prevActive;
                rt.Release();
                UnityEngine.Object.DestroyImmediate(rt);
                UnityEngine.Object.DestroyImmediate(tex);
            }
        }
    }
}
