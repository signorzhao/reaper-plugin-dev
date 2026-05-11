import datetime
import os
from pathlib import Path
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring


REPO_USER = "signorzhao"
REPO_NAME = "reapack_repo"
RELEASES_DIR = Path("releases")

PLUGIN_BASENAMES = [
    "reaper_enz_ReaperTools.dll",
    "reaper_enz_ReaperTools.dylib",
    "reaper_enz_ReaperTools.so",
]

PLATFORM_MAP = {
    "reaper_enz_ReaperTools.dll": "win64",
    "reaper_enz_ReaperTools.dylib": "darwin",
    "reaper_enz_ReaperTools.so": "linux",
}

UCS_FILES = {
    "enz_UCS_Auto_Rename_Selected_Items.lua": "Scripts/ENZ/UCS/enz_UCS_Auto_Rename_Selected_Items.lua",
    "enz_ucs_service.exe": "Scripts/ENZ/UCS/enz_ucs_service.exe",
    "start_ucs_service_windows.bat": "Scripts/ENZ/UCS/start_ucs_service_windows.bat",
}


def version_key(version):
    return [int(part) for part in version[1:].split(".")]


def find_versions():
    if not RELEASES_DIR.exists():
        return []
    return sorted(
        [
            item.name
            for item in RELEASES_DIR.iterdir()
            if item.is_dir() and item.name.startswith("v")
        ],
        key=version_key,
    )


def raw_url(path):
    return f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/{path}"


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def add_reaper_tools(category, versions):
    reapack = SubElement(
        category,
        "reapack",
        name="reaper_enz_ReaperTools.ext",
        type="extension",
        desc="ENZ ReaperTools",
    )
    metadata = SubElement(reapack, "metadata")
    description = SubElement(metadata, "description")
    description.text = "ENZ ReaperTools - REAPER C++ Extension Plugin"

    for version in versions:
        version_dir = RELEASES_DIR / version
        plugin_files = [
            plugin_name
            for plugin_name in PLUGIN_BASENAMES
            if (version_dir / plugin_name).exists()
        ]
        if not plugin_files:
            continue

        version_elem = SubElement(
            reapack,
            "version",
            name=version[1:],
            author="ENZ",
            time=now_utc(),
        )
        for plugin_name in plugin_files:
            source = SubElement(
                version_elem,
                "source",
                platform=PLATFORM_MAP[plugin_name],
                file=plugin_name,
            )
            source.text = raw_url(f"releases/{version}/{plugin_name}")


def add_ucs_tool(category, versions):
    reapack = SubElement(
        category,
        "reapack",
        name="enz_UCS_Auto_Rename_Selected_Items.lua",
        type="script",
        desc="Rename selected media items from Chinese text using UCS",
    )
    metadata = SubElement(reapack, "metadata")
    description = SubElement(metadata, "description")
    description.text = (
        "Chinese natural-language UCS auto-renamer for selected REAPER media items. "
        "Requires ReaImGui and the bundled local Windows service."
    )

    for version in versions:
        ucs_dir = RELEASES_DIR / version / "ucs"
        if not all((ucs_dir / file_name).exists() for file_name in UCS_FILES):
            continue

        version_elem = SubElement(
            reapack,
            "version",
            name=version[1:],
            author="ENZ",
            time=now_utc(),
        )
        for source_name, install_path in UCS_FILES.items():
            source = SubElement(
                version_elem,
                "source",
                platform="win64",
                file=install_path,
            )
            source.text = raw_url(f"releases/{version}/ucs/{source_name}")


def create_index():
    versions = find_versions()
    root = Element("index", version="1", name="ENZ ReaperTools", commit="main")
    extensions = SubElement(root, "category", name="Extensions")
    scripts = SubElement(root, "category", name="Scripts")
    add_reaper_tools(extensions, versions)
    add_ucs_tool(scripts, versions)
    return minidom.parseString(tostring(root, "utf-8")).toprettyxml(indent="  ")


if __name__ == "__main__":
    Path("index.xml").write_text(create_index(), encoding="utf-8")
    print("index.xml updated.")
