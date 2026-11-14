#!/usr/bin/env python3
"""Apply narrow Linux editor compatibility fixes; preserve ARM64 validation."""
import argparse
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
PATCHES = [
    ("com.meta.xr.sdk.core@*/Scripts/Editor/OVRManagerEditor.cs",
     "#if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN || UNITY_EDITOR_OSX || UNITY_STANDALONE_OSX || UNITY_ANDROID\n        OVRManager manager = (OVRManager)target;",
     "#if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN || UNITY_EDITOR_OSX || UNITY_STANDALONE_OSX || UNITY_ANDROID || UNITY_EDITOR_LINUX || UNITY_STANDALONE_LINUX\n        OVRManager manager = (OVRManager)target;"),
    ("com.meta.xr.sdk.core@*/Editor/MetaXRSimulator/Installer.cs",
     '#elif UNITY_EDITOR_OSX\n            var downloadedInstallerPath =\n                            Path.Combine(XRSimConstants.DownloadFolderPath, $"meta_xr_simulator.dmg");\n#endif',
     '#elif UNITY_EDITOR_OSX\n            var downloadedInstallerPath =\n                            Path.Combine(XRSimConstants.DownloadFolderPath, $"meta_xr_simulator.dmg");\n#else\n            var downloadedInstallerPath =\n                            Path.Combine(XRSimConstants.DownloadFolderPath, "meta_xr_simulator_installer");\n#endif'),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", type=Path, default=PROJECT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.project.resolve() != PROJECT:
        parser.error("Only this Unity project may be patched")
    cache = PROJECT / "Library/PackageCache"
    pending, missing = [], []
    for pattern, old, new in PATCHES:
        matches = sorted(cache.glob(pattern))
        if not matches:
            missing.append(pattern)
        for path in matches:
            if not path.resolve().is_relative_to(cache.resolve()):
                parser.error("Package symlink escapes the project")
            text = path.read_text(encoding="utf-8-sig")
            if new in text:
                print("already patched", path.name)
            elif old in text:
                pending.append(path.name)
                if not args.check:
                    path.write_text(text.replace(old, new), encoding="utf-8")
            else:
                missing.append(str(path.relative_to(cache)))
    print(f"pending={len(pending)} missing_or_newer_layout={len(missing)}")
    for item in missing:
        print("REVIEW", item)
    # A newer vendor version can already have a different Linux fix. Report
    # unknown layouts explicitly; never disable project validation to hide them.
    return 1 if args.check and pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
