using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace Arescope.Editor
{
    public static class BuildQuestAndroid
    {
        private const string PackageId = "in.arescope.beta02.questroom";
        private const string DefaultOutputPath = "Build/QuestRoomScan.apk";

        [MenuItem("Arescope/Build Quest Android APK")]
        public static void Build()
        {
            WireArescopeScene.Run();
            if (!ValidateArescopeScene.Run())
            {
                throw new InvalidOperationException("ValidateArescopeScene.Run() failed; aborting Android APK build.");
            }

            string[] scenes = EditorBuildSettings.scenes
                .Where(s => s.enabled && !string.IsNullOrEmpty(s.path) && s.path.Contains("QuestRoomScan", StringComparison.OrdinalIgnoreCase))
                .Select(s => s.path)
                .ToArray();

            if (scenes.Length == 0)
            {
                throw new InvalidOperationException("No enabled EditorBuildSettings scene path contains 'QuestRoomScan'.");
            }

            if (!BuildPipeline.IsBuildTargetSupported(BuildTargetGroup.Android, BuildTarget.Android))
            {
                throw new InvalidOperationException("Android BuildTarget is not supported by this Unity Editor installation.");
            }

            if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android)
            {
                EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);
            }
            EditorUserBuildSettings.selectedBuildTargetGroup = BuildTargetGroup.Android;

            PlayerSettings.colorSpace = ColorSpace.Linear;
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, PackageId);
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.SetIl2CppCompilerConfiguration(NamedBuildTarget.Android, Il2CppCompilerConfiguration.Master);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel29;

            StageMetaArFoundationNativePlugin();

            string outputPath = Environment.GetEnvironmentVariable("ARESCOPE_APK_PATH");
            if (string.IsNullOrWhiteSpace(outputPath))
            {
                outputPath = DefaultOutputPath;
            }

            string outputDir = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(outputDir) && !Directory.Exists(outputDir))
            {
                Directory.CreateDirectory(outputDir);
            }

            var options = new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = outputPath,
                target = BuildTarget.Android,
                options = BuildOptions.None
            };

            BuildReport report = BuildPipeline.BuildPlayer(options);
            BuildSummary summary = report.summary;
            Debug.Log($"QuestRoomScan build result: {summary.result}; output={summary.outputPath}; size={summary.totalSize}; errors={summary.totalErrors}; warnings={summary.totalWarnings}");

            if (summary.result != BuildResult.Succeeded || summary.totalErrors > 0)
            {
                throw new InvalidOperationException($"QuestRoomScan build failed: result={summary.result}, errors={summary.totalErrors}");
            }
        }

        private static void StageMetaArFoundationNativePlugin()
        {
            string cacheDir = Path.GetFullPath("Library/PackageCache");
            if (!Directory.Exists(cacheDir)) return;
            string[] matches = Directory.GetFiles(cacheDir, "libUnityARFoundationMeta.so", SearchOption.AllDirectories);
            string source = matches.FirstOrDefault(p => p.Replace('\\', '/').Contains("/arm64"));
            if (string.IsNullOrEmpty(source))
            {
                Debug.LogWarning("[Arescope] libUnityARFoundationMeta.so not found under Library/PackageCache.");
                return;
            }
            string destDir = Path.GetFullPath("Assets/Plugins/Android/arm64-v8a");
            Directory.CreateDirectory(destDir);
            string dest = Path.Combine(destDir, "libUnityARFoundationMeta.so");
            if (!File.Exists(dest) || new FileInfo(dest).Length != new FileInfo(source).Length)
            {
                File.Copy(source, dest, overwrite: true);
                Debug.Log("[Arescope] Staged native plugin -> Assets/Plugins/Android/arm64-v8a/libUnityARFoundationMeta.so");
            }
        }
    }
}
