"""Zip the per-expansion addon directories into ONE ready-to-upload bundle.

Produces a single archive at
`<DIST_DIR>/<expansion>/Guidelime_<AUTHOR>_RepGuides-<expansion>-v<version>.zip`,
containing every generated addon directory at the top level (so a
player can drag-extract straight into `Interface/AddOns/` and every
folder becomes its own standalone addon).

CurseForge moderation rejects multiple similar projects from the same
author under the "Fair Play" rule — see
https://support.curseforge.com/en/support/solutions/articles/9000197279
— so the project ships as one umbrella zip rather than 30 separate
downloads. Inside the zip the umbrella structure follows the same
convention as WeakAuras, Bagnon, Bartender: each top-level folder is a
self-contained addon.

The maintainer-only `QUALITY_REPORT.md` is excluded from each addon
directory — per the project readme it is not part of the distributed
addons.
"""
from __future__ import annotations

import os
import zipfile
from collections.abc import Sequence

from ..constants import AUTHOR, DIST_DIR

# Files written into an addon directory but not meant for the player zip.
ADDON_ZIP_EXCLUDE = frozenset({'QUALITY_REPORT.md'})

BUNDLE_PREFIX = f'Guidelime_{AUTHOR}_RepGuides'


def bundle_zip_path(expansion: str, version: str) -> str:
    """Absolute path of the bundle archive for `expansion` at `version`.
    Useful for callers that want to refer to the artefact without
    rebuilding it."""
    dist_root = os.path.join(os.path.abspath(DIST_DIR), expansion)
    return os.path.join(
        dist_root, f'{BUNDLE_PREFIX}-{expansion}-v{version}.zip',
    )


def zip_addon_bundle(
    addon_dirs: Sequence[str],
    expansion: str,
    version: str,
    bundle_readme: str | None = None,
) -> str:
    """Bundle every directory in `addon_dirs` into a single archive at
    `bundle_zip_path(expansion, version)` and return its absolute path.

    Each addon directory becomes a top-level folder inside the zip — the
    layout a CurseForge multi-folder umbrella project expects.
    `QUALITY_REPORT.md` is excluded from every folder.

    `bundle_readme`, when provided, is written into the zip root as
    `README.md` so the archive is self-describing on download.
    """
    zip_path = bundle_zip_path(expansion, version)
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        if bundle_readme is not None:
            zf.writestr('README.md', bundle_readme)
        for addon_dir in addon_dirs:
            addon_name = os.path.basename(os.path.normpath(addon_dir))
            for entry in sorted(os.listdir(addon_dir)):
                if entry in ADDON_ZIP_EXCLUDE:
                    continue
                src = os.path.join(addon_dir, entry)
                if not os.path.isfile(src):
                    continue
                zf.write(src, f'{addon_name}/{entry}')

    return zip_path
