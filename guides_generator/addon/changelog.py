"""Read versioned changelog files and produce the addon's CHANGELOG.md.

Each release lives in `changelog/vX.Y.Z[_<slug>].md`. On generation, all
entries are concatenated in reverse-chronological order (newest on top,
separated by `---`) and the highest version is returned as the addon's
current version.
"""
from __future__ import annotations

import os
import re

from ..constants import FALLBACK_VERSION

VERSION_FILENAME_RE = re.compile(r'^v(\d+)\.(\d+)\.(\d+)(?:_.*)?\.md$', re.IGNORECASE)


def read_changelog(changelog_dir: str) -> tuple[str, str]:
    """Return `(latest_version, concatenated_text)`. If the directory is
    empty or missing, returns the fallback version with a placeholder text.
    """
    if not os.path.isdir(changelog_dir):
        return FALLBACK_VERSION, '# Changelog\n\nNo entries yet.\n'

    entries: list[tuple[tuple[int, int, int], str]] = []
    for fname in sorted(os.listdir(changelog_dir)):
        m = VERSION_FILENAME_RE.match(fname)
        if not m:
            continue
        vt = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        with open(os.path.join(changelog_dir, fname), 'r', encoding='utf-8') as f:
            entries.append((vt, f.read().strip()))

    if not entries:
        return FALLBACK_VERSION, '# Changelog\n\nNo entries yet.\n'

    entries.sort(key=lambda e: e[0], reverse=True)
    latest_version = '.'.join(str(n) for n in entries[0][0])

    body_parts: list[str] = []
    for i, (_, content) in enumerate(entries):
        body_parts.append(content)
        if i < len(entries) - 1:
            body_parts.append('---')
    body = '\n\n'.join(body_parts)
    return latest_version, f'# Changelog\n\n{body}\n'
