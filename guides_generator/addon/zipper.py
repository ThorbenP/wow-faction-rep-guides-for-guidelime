"""Zip a written addon directory into a ready-to-upload archive.

Produces `<DIST_DIR>/<expansion>/<addon_name>.zip` containing the addon
directory at the top level (so a player can drag-extract straight into
`Interface/AddOns/`). Intended to run *after* `write_addon` and
`write_addon_report`, so the source directory is fully populated.

The maintainer-only `QUALITY_REPORT.md` is excluded — per the project
readme it is not part of the distributed addons.
"""
from __future__ import annotations

import os
import zipfile

from ..constants import DIST_DIR

# Files written into the addon directory but not meant for the player zip.
ADDON_ZIP_EXCLUDE = frozenset({'QUALITY_REPORT.md'})


def zip_addon(addon_dir: str, expansion: str) -> str:
    """Zip `addon_dir` into `<DIST_DIR>/<expansion>/<basename>.zip` and
    return the absolute path of the written archive."""
    addon_name = os.path.basename(os.path.normpath(addon_dir))
    dist_root = os.path.join(os.path.abspath(DIST_DIR), expansion)
    os.makedirs(dist_root, exist_ok=True)
    zip_path = os.path.join(dist_root, f'{addon_name}.zip')

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for entry in sorted(os.listdir(addon_dir)):
            if entry in ADDON_ZIP_EXCLUDE:
                continue
            src = os.path.join(addon_dir, entry)
            if not os.path.isfile(src):
                continue
            zf.write(src, f'{addon_name}/{entry}')

    return zip_path
