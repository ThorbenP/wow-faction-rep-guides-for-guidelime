"""Write a complete addon directory: .toc + .lua + CHANGELOG.md + README.md +
LICENSE, and optionally zip it into a CurseForge-ready archive."""
from .changelog import read_changelog
from .names import addon_name_for_faction, guide_title_for_faction
from .writer import write_addon
from .zipper import zip_addon

__all__ = [
    'addon_name_for_faction', 'guide_title_for_faction',
    'read_changelog', 'write_addon', 'zip_addon',
]
