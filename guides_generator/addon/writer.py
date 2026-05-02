"""Write the files that make up an addon directory."""
from __future__ import annotations

import os
import shutil

from ..constants import LICENSE_PATH
from .readme import build_readme
from .toc import build_toc


def write_addon(
    addon_dir: str,
    addon_name: str,
    guide_title: str,
    expansion: str,
    faction_name: str,
    guide_text: str,
    version: str,
    changelog_text: str,
) -> tuple[str, str, str, str, str]:
    """Create `addon_dir` and write:
        <addon_name>.toc — addon metadata
        <addon_name>.lua — the generated guide source
        CHANGELOG.md     — concatenated history
        README.md        — faction- and expansion-specific player-facing readme
        LICENSE          — GPL-3.0 text, copied from repo root so each addon
                           ships standalone-compliant under §4 of the GPL

    Returns the (toc_path, lua_path, changelog_path, readme_path,
    license_path) of the written files.
    """
    os.makedirs(addon_dir, exist_ok=True)

    lua_path = os.path.join(addon_dir, f'{addon_name}.lua')
    with open(lua_path, 'w', encoding='utf-8') as f:
        f.write(guide_text)

    toc_path = os.path.join(addon_dir, f'{addon_name}.toc')
    with open(toc_path, 'w', encoding='utf-8') as f:
        f.write(build_toc(addon_name, guide_title, expansion, faction_name, version))

    changelog_path = os.path.join(addon_dir, 'CHANGELOG.md')
    with open(changelog_path, 'w', encoding='utf-8') as f:
        f.write(changelog_text)

    readme_path = os.path.join(addon_dir, 'README.md')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(build_readme(addon_name, faction_name, expansion, version))

    license_path = os.path.join(addon_dir, 'LICENSE')
    shutil.copyfile(LICENSE_PATH, license_path)

    return toc_path, lua_path, changelog_path, readme_path, license_path
