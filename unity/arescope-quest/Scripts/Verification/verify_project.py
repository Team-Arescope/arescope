"""Offline byte/structure checks and executable patcher/triage regression fixtures."""
import ast
import contextlib
import importlib.util
import io
import json
import re
import shutil
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
ARCHIVE = PROJECT.parents[1] / "archive"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class ProjectTests(unittest.TestCase):
    def test_reference_bytes(self):
        copies = {
            "ProjectSettings__EditorBuildSettings.asset": "ProjectSettings/EditorBuildSettings.asset",
            "Assets__Plugins__Android__AndroidManifest.xml": "Assets/Plugins/Android/AndroidManifest.xml",
        }
        for source, target in copies.items():
            self.assertEqual((ARCHIVE / "evidence/reference_config" / source).read_bytes(), (PROJECT / target).read_bytes(), target)
        manifest = json.loads((PROJECT / "Packages/manifest.json").read_text(encoding="utf-8-sig"))["dependencies"]
        self.assertEqual("https://github.com/arghyasur1991/QuestRoomScan.git#4791b24b81015641d4cfb010a93c6283d4eb3dee", manifest["com.genesis.roomscan"])
        self.assertEqual("2.4.1", manifest["com.unity.xr.meta-openxr"])
        self.assertNotIn("com.unity.burst", manifest)
        for directory in ("ArescopeIcons", "ArescopeFonts"):
            for source in (ARCHIVE / "evidence/reference_assets" / directory).iterdir():
                self.assertEqual(source.read_bytes(), (PROJECT / "Assets/Resources" / directory / source.name).read_bytes())

    def test_icons_and_manifest(self):
        icons = list((PROJECT / "Assets/Resources/ArescopeIcons").glob("*.png"))
        self.assertEqual(6, len(icons))
        for icon in icons:
            data = icon.read_bytes()
            self.assertEqual(b"\x89PNG\r\n\x1a\n", data[:8])
            self.assertEqual((64, 64), struct.unpack(">II", data[16:24]))
        root = ET.parse(PROJECT / "Assets/Plugins/Android/AndroidManifest.xml").getroot()
        ns = "{http://schemas.android.com/apk/res/android}"
        permissions = {item.attrib[ns + "name"] for item in root.findall("uses-permission")}
        self.assertIn("horizonos.permission.HEADSET_CAMERA", permissions)
        self.assertEqual("false", root.find("application").attrib[ns + "usesCleartextTraffic"])

    def test_project_contract(self):
        text = (PROJECT / "ProjectSettings/ProjectSettings.asset").read_text()
        for value in ("in.arescope.beta02.questroom", "bundleVersion: 0.5.13", "AndroidBundleVersionCode: 34",
                      "AndroidTargetArchitectures: 2", "AndroidMinSdkVersion: 29", "m_ActiveColorSpace: 1", "Android: 1"):
            self.assertIn(value, text)
        self.assertIn("6000.2.9f1 (e0c4e791ab71)", (PROJECT / "ProjectSettings/ProjectVersion.txt").read_text())
        core = (PROJECT / "Assets/Arescope/Math/CoreMath.cs").read_text()
        self.assertNotIn("using Unity", core)
        definition = json.loads((PROJECT / "Assets/Arescope/Math/Arescope.Core.asmdef").read_text())
        self.assertTrue(definition["noEngineReferences"])

    def test_xr_serialized_links_and_flags(self):
        general = (PROJECT / "Assets/XR/XRGeneralSettingsPerBuildTarget.asset").read_text()
        self.assertIn("m_AutomaticLoading: 1", general)
        self.assertIn("m_AutomaticRunning: 1", general)
        settings = (PROJECT / "Assets/XR/Settings/OpenXR Package Settings.asset").read_text()
        self.assertIn("priority: 2147483647", settings)  # Native lifecycle bridge initializes first.
        for feature in ("MetaOpenXR-OpenXRLifeCycle", "arfoundation-meta-session", "arfoundation-meta-occlusion",
                        "arfoundation-meta-plane", "arfoundation-meta-mesh", "arfoundation-meta-anchor", "compositionlayers"):
            self.assertRegex(settings, "featureIdInternal: .*" + re.escape(feature) + r"\n")
        for text in (general, settings):
            ids = set(re.findall(r"^--- !u!114 &(\d+)$", text, re.M))
            for local_id in re.findall(r"\{fileID: (114\d+)\}", text):
                self.assertIn(local_id, ids)
        for path, guid in (("Assets/XR/XRGeneralSettingsPerBuildTarget.asset", "b75041287094ca156806da4b56a263ae"),
                           ("Assets/XR/Settings/OpenXR Package Settings.asset", "f6e83c6fb80f53bdd84bc22c39af25d5"),
                           ("Assets/XR/Settings/XRSimulationSettings.asset", "338b3c7ee18eb1879bb3a56c029397c2")):
            self.assertIn("guid: " + guid, (PROJECT / (path + ".meta")).read_text())

    def test_unity_asset_metadata_is_unique(self):
        seen = {}
        for directory in ("Assets/Arescope", "Assets/Tests", "Assets/XR", "Assets/Settings", "Assets/Resources", "PackagePatches"):
            for meta in (PROJECT / directory).rglob("*.meta"):
                guid = re.search(r"^guid: ([0-9a-f]{32})$", meta.read_text(), re.M)
                self.assertIsNotNone(guid, str(meta))
                self.assertNotIn(guid[1], seen, str(meta))
                seen[guid[1]] = meta
        self.assertIn("9e167c771ee24f78b2e60a7e9f746d0c", seen)

    def test_python_syntax_and_json(self):
        for path in (PROJECT / "Scripts").rglob("*.py"):
            if ".verification" not in path.parts:
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for directory in ("Packages", "Assets/Arescope", "Assets/Tests"):
            for path in (PROJECT / directory).rglob("*"):
                if path.suffix in (".json", ".asmdef"):
                    json.loads(path.read_text(encoding="utf-8-sig"))


class ScriptFixtures(unittest.TestCase):
    def setUp(self):
        parent = PROJECT / "Scripts/.verification"
        parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="fixture-", dir=parent)
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self):
        self.assertTrue(self.root.is_relative_to((PROJECT / "Scripts/.verification").resolve()))
        self.temporary.cleanup()

    def test_roomscan_patch_idempotence_and_scope(self):
        patcher = module("roomscan_patch", PROJECT / "Scripts/patch_roomscan_editor.py")
        patcher.PROJECT = self.root
        shutil.copytree(PROJECT / "PackagePatches", self.root / "PackagePatches")
        package = self.root / "Library/PackageCache/com.genesis.roomscan@fixture"
        (package / "Runtime/Core").mkdir(parents=True)
        (package / "Editor").mkdir()
        (package / "package.json").write_text('{"name":"com.genesis.roomscan"}')
        (package / "Runtime/Genesis.RoomScan.asmdef").write_text('{"name":"Genesis.RoomScan","references":[]}')
        (package / "Runtime/Core/GPUSurfaceNets.cs").write_text("VertexStride = 48; VertexPosOffset = 0; VertexNormalOffset = 24; VertexPackedColorOffset = 36;")
        wizard = package / "Editor/RoomScanSetupWizard.BuildingBlocks.cs"
        wizard.write_text("var blocks = Object.FindObjectsByType<BuildingBlock>();")
        setup = package / "Editor/RoomScanSetupWizard.cs"
        setup.write_bytes(b"\xef\xbb\xbf" + (
            "var occlusion = Object.FindObjectsByType<AROcclusionManager>(FindObjectsInactive.Include);\r\n"
            "var cameras = Object.FindObjectsByType<PassthroughCameraAccess>(FindObjectsInactive.Include);\r\n"
            "    uiDoc.worldSpaceSizeMode = WorldSpaceSizeMode.Dynamic;\r\n"
            "    uiDoc.pivot = Pivot.Center;\r\n"
            "    uiDoc.pivotReferenceSize = PivotReferenceSize.Layout;\r\n"
            "    uiDoc.enabled = true;\r\n").encode("utf-8"))
        runtime = package / "Runtime/Core/Unrelated.cs"
        runtime.write_text("var items = FindObjectsByType<Unrelated>();")
        original = {str(p): p.read_bytes() for p in package.rglob("*") if p.is_file()}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(1, patcher.install(package, check=True))
            self.assertEqual(original, {str(p): p.read_bytes() for p in package.rglob("*") if p.is_file()})
            self.assertEqual(0, patcher.install(package))
            before = {str(p): p.read_bytes() for p in package.rglob("*") if p.is_file()}
            self.assertEqual(0, patcher.install(package))
            self.assertEqual(0, patcher.install(package, check=True))
        after = {str(p): p.read_bytes() for p in package.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertIn("UnityEngine.FindObjectsSortMode.None", wizard.read_text())
        for component in ("AROcclusionManager", "PassthroughCameraAccess"):
            self.assertIn("FindObjectsByType<" + component + ">"
                          "(FindObjectsInactive.Include, UnityEngine.FindObjectsSortMode.None)", setup.read_text())
        guard = ("    #if UNITY_6000_3_OR_NEWER\n"
                 "    uiDoc.worldSpaceSizeMode = WorldSpaceSizeMode.Dynamic;\n"
                 "    uiDoc.pivot = Pivot.Center;\n"
                 "    uiDoc.pivotReferenceSize = PivotReferenceSize.Layout;\n"
                 "    #endif\n"
                 "    uiDoc.enabled = true;\n")
        self.assertIn(guard, setup.read_text(encoding="utf-8-sig"))
        self.assertTrue(setup.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", setup.read_bytes().replace(b"\r\n", b""))
        self.assertEqual(original[str(runtime)], runtime.read_bytes())
        self.assertEqual(["Arescope.Core"], json.loads((package / "Runtime/Genesis.RoomScan.asmdef").read_text())["references"])
        self.assertEqual(6, len(list((package / "Runtime/Utils").iterdir())))
        with self.assertRaises(ValueError):
            patcher.install(PROJECT.parent)
        surface = package / "Runtime/Core/GPUSurfaceNets.cs"
        surface.write_text(surface.read_text().replace("VertexNormalOffset = 24", "VertexNormalOffset = 12"))
        with self.assertRaises(ValueError):
            patcher.install(package)

    def test_roomscan_editor_patch_categories_and_existing_guards(self):
        patcher = module("roomscan_editor_patch", PROJECT / "Scripts/patch_roomscan_editor.py")
        block = ("        uiDoc.worldSpaceSizeMode = WorldSpaceSizeMode.Dynamic;\n"
                 "        uiDoc.pivot = Pivot.Center;\n"
                 "        uiDoc.pivotReferenceSize = PivotReferenceSize.Layout;\n")
        guarded = "        #if UNITY_6000_3_OR_NEWER\n" + block + "        #endif\n"
        cases = {
            "parameterless": ("Object.FindObjectsByType<BuildingBlock>( \n );",
                              "Object.FindObjectsByType<BuildingBlock>(UnityEngine.FindObjectsSortMode.None);"),
            "inactive": ("Object.FindObjectsByType<AROcclusionManager>(\n FindObjectsInactive.Include\n);",
                         "Object.FindObjectsByType<AROcclusionManager>(FindObjectsInactive.Include, UnityEngine.FindObjectsSortMode.None);"),
            "qualified inactive": ("Object.FindObjectsByType<PassthroughCameraAccess>(UnityEngine.FindObjectsInactive.Include);",
                                   "Object.FindObjectsByType<PassthroughCameraAccess>(UnityEngine.FindObjectsInactive.Include, UnityEngine.FindObjectsSortMode.None);"),
            "explicit sort": ("FindObjectsByType<BuildingBlock>(FindObjectsInactive.Include, FindObjectsSortMode.InstanceID);",) * 2,
            "sort only": ("FindObjectsByType<BuildingBlock>(UnityEngine.FindObjectsSortMode.None);",) * 2,
            "world space": ("before();\n" + block + "after();\n", "before();\n" + guarded + "after();\n"),
            "already guarded": (guarded,) * 2,
            "nested guard": ("#if UNITY_6000_3_OR_NEWER\n#if UNITY_EDITOR\n" + block + "#endif\n#endif\n",) * 2,
            "else branch": (guarded.rstrip() + "\n#if UNITY_EDITOR\n#else\n" + block + "#endif\n",
                            guarded.rstrip() + "\n#if UNITY_EDITOR\n#else\n" + guarded + "#endif\n"),
            "version else": ("#if UNITY_6000_3_OR_NEWER\n" + block + "#else\n" + block + "#endif\n",
                             "#if UNITY_6000_3_OR_NEWER\n" + block + "#else\n" + guarded + "#endif\n"),
            "version elif": ("#if OTHER_VERSION\n#elif UNITY_6000_3_OR_NEWER\n" + block + "#endif\n",) * 2,
        }
        for name, (source, expected) in cases.items():
            for newline in ("\n", "\r\n"):
                with self.subTest(category=name, newline=repr(newline)):
                    expected_text = expected.replace("\n", newline)
                    patched = patcher.patch_editor_source(source.replace("\n", newline))
                    self.assertEqual(expected_text, patched)
                    self.assertEqual(patched, patcher.patch_editor_source(patched))

    def test_logcat_encodings_and_gate_detection(self):
        triage = module("logcat_triage", PROJECT / "Scripts/triage_logcat.py")
        text = "[ARS] xr-boot | xr=inactive occlusion=no-subsystem\n[RoomScan] depth sub=null\ninstanceProcAddr is null\nFatal signal 6\n"
        for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
            path = self.root / "logcat.txt"
            path.write_bytes(text.encode(encoding))
            self.assertEqual(text, triage.load(path))
        with contextlib.redirect_stdout(io.StringIO()):
            result = triage.triage(text)
        self.assertTrue(result["depth provider missing"])
        self.assertTrue(result["XR inactive"])
        self.assertTrue(result["lifecycle function table missing"])
        self.assertFalse(result["no managed output"])

    def test_linux_patcher_is_idempotent_and_preserves_validation(self):
        patcher = module("meta_patch", PROJECT / "Scripts/patch_meta_sdk_linux.py")
        patcher.PROJECT = self.root
        import sys
        from unittest.mock import patch
        cache = self.root / "Library/PackageCache"
        for pattern, old, new in patcher.PATCHES:
            path = cache / pattern.replace("@*", "@fixture")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(old)
        validation=cache / "com.unity.xr.openxr@fixture/Runtime/OpenXRProjectValidation.cs"
        validation.parent.mkdir(parents=True)
        validation.write_text("checkPredicate = () => ARM64_is_required;")
        with patch.object(sys, "argv", ["patch_meta_sdk_linux.py"]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0,patcher.main())
            before={str(p):p.read_bytes() for p in cache.rglob("*") if p.is_file()}
            self.assertEqual(0,patcher.main())
        self.assertEqual(before,{str(p):p.read_bytes() for p in cache.rglob("*") if p.is_file()})
        self.assertEqual("checkPredicate = () => ARM64_is_required;",validation.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
