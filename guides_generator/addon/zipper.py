"""Zip the per-expansion addon directories into ONE ready-to-upload bundle.

Produces a single archive at
`<DIST_DIR>/<expansion>/Guidelime_<AUTHOR>_RepGuides-<expansion>-v<version>.zip`,
containing every generated addon directory at the top level — and
nothing else. CurseForge's upload validator rejects archives that have
loose files at the zip root ("WoW addons must be packaged so that all
files are inside a root folder"), so this builder writes folders only.
Install instructions for the bundle live on the CurseForge project
page (`build_curseforge_description`), not inside the zip.

CurseForge moderation also rejects multiple similar projects from the
same author under the "Fair Play" rule — see
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
) -> str:
    """Bundle every directory in `addon_dirs` into a single archive at
    `bundle_zip_path(expansion, version)` and return its absolute path.

    Each addon directory becomes a top-level folder inside the zip and
    nothing else lives at the zip root — that is the layout CurseForge's
    upload validator requires for multi-folder addons. `QUALITY_REPORT.md`
    is excluded from every folder.
    """
    zip_path = bundle_zip_path(expansion, version)
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
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
