from __future__ import annotations

import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLUGIN = ROOT / "plugin.video.telegram.media"
REQ = ROOT / "requirements-build.txt"
BUILD_ROOT = ROOT / ".build"
STAGED = BUILD_ROOT / PLUGIN.name
DIST = ROOT / "dist"


def syntax_check(root: Path) -> None:
    for path in root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")


def main() -> None:
    addon = ET.parse(PLUGIN / "addon.xml").getroot()
    version = addon.attrib["version"]
    out = DIST / f"plugin.video.telegram.media-{version}.zip"

    shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir(parents=True)
    BUILD_ROOT.mkdir(parents=True)
    shutil.copytree(PLUGIN, STAGED)

    vendor = STAGED / "resources" / "lib" / "vendor"
    vendor.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        "--disable-pip-version-check",
        "--no-compile",
        "--target", str(vendor),
        "-r", str(REQ),
    ])

    for path in list(STAGED.rglob("__pycache__")):
        shutil.rmtree(path, ignore_errors=True)
    for path in list(STAGED.rglob("*.pyc")):
        path.unlink(missing_ok=True)

    syntax_check(STAGED)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in STAGED.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            arcname = Path(PLUGIN.name) / path.relative_to(STAGED)
            zf.write(path, arcname.as_posix())

    print(out)


if __name__ == "__main__":
    main()
