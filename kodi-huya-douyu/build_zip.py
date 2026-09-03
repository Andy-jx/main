from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLUGIN = ROOT / "plugin.video.huya_douyu"
DIST = ROOT / "dist"


def main():
    addon = ET.parse(PLUGIN / "addon.xml").getroot()
    version = addon.attrib["version"]
    out = DIST / f"plugin.video.huya_douyu-{version}.zip"
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in PLUGIN.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            arcname = Path(PLUGIN.name) / path.relative_to(PLUGIN)
            zf.write(path, arcname.as_posix())
    print(out)


if __name__ == "__main__":
    main()
