"""Write a complete addon directory: .toc + .lua + CHANGELOG.md + README.md +
LICENSE, and bundle every addon directory into one CurseForge-ready archive."""
from .changelog import read_changelog
from .curseforge import (
    build_bundle_readme,
    build_curseforge_description,
    write_curseforge_description,
)
from .names import addon_name_for_faction, guide_title_for_faction
from .writer import write_addon
from .zipper import bundle_zip_path, zip_addon_bundle

__all__ = [
    'addon_name_for_faction', 'build_bundle_readme',
    'build_curseforge_description', 'bundle_zip_path',
    'guide_title_for_faction', 'read_changelog', 'write_addon',
    'write_curseforge_description', 'zip_addon_bundle',
]
