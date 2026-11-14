"""Read official Unity package tarballs in memory; print serialized type GUIDs."""
import io
import tarfile
import urllib.request
import sys

PACKAGES = [
    ("com.unity.xr.management", "4.5.2"),
    ("com.unity.xr.arfoundation", "6.2.0"),
    ("com.unity.xr.openxr", "1.15.1"),
    ("com.unity.xr.meta-openxr", "2.4.1"),
    ("com.unity.xr.compositionlayers", "2.2.0"),
]

if __name__ == "__main__":
    for name, version in PACKAGES:
        if "--meta-only" in sys.argv and name != "com.unity.xr.meta-openxr":
            continue
        print(name, flush=True)
        try:
            url = f"https://packages.unity.com/{name}/-/{name}-{version}.tgz"
            raw = urllib.request.urlopen(url, timeout=20).read()
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
                for member in archive.getmembers():
                    if member.name.endswith(".cs.meta") and any(term in member.name for term in (
                        "XRGeneralSettings", "XRManagerSettings", "OpenXRLoader", "OpenXRSettings", "OpenXRPackageSettings",
                        "Feature", "LifeCycle", "SimulationSettings")):
                        print(member.name, archive.extractfile(member).read().decode().splitlines()[:2], flush=True)
                    if member.name.endswith(".cs") and any(term in member.name for term in ("OpenXRPackageSettings", "Feature")):
                        source = archive.extractfile(member).read().decode()
                        if "meta-openxr" in name or "compositionlayers" in name or "PackageSettings" in member.name:
                            print(member.name, "\n".join(line for line in source.splitlines() if any(term in line for term in (
                                "featureId", "FeatureId", "SerializeField", "List<BuildTargetGroup>", "List<OpenXRSettings>", "m_Settings"))), flush=True)
                            if "--attributes" in sys.argv:
                                start=source.find("[OpenXRFeature(")
                                end=source.find(")]",start)
                                if start>=0 and end>=0:
                                    print(source[start:end+2],flush=True)
        except Exception as error:
            print(type(error).__name__, error, flush=True)
