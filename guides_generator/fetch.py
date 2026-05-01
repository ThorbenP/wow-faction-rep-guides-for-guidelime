"""Download and cache the Questie database files."""
from __future__ import annotations

import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .constants import DB_FILES, QUESTIE_RAW

USER_AGENT = 'guides_generator/1.0'
DOWNLOAD_TIMEOUT = 60
MIN_VALID_SIZE_BYTES = 1000  # below this, treat the cached file as truncated


def fetch_or_load(name: str, expansion: str, cache_dir: str) -> str:
    """Return the local path to a DB file. Cache hit if present and large
    enough, otherwise downloaded from the configured source. Aborts the
    program on network failure — no point continuing without the DB.

    Files are cached under `<cache_dir>/<expansion>/...` so different game
    versions never collide on the same filename.
    """
    source, rel_path = DB_FILES[expansion][name]
    base_url = QUESTIE_RAW  # currently the only configured source

    expansion_cache_dir = os.path.join(cache_dir, expansion)
    os.makedirs(expansion_cache_dir, exist_ok=True)
    cache_file = os.path.join(expansion_cache_dir, f'{source}_' + rel_path.replace('/', '_'))

    if os.path.exists(cache_file) and os.path.getsize(cache_file) > MIN_VALID_SIZE_BYTES:
        print(f'  ✓ cache: {cache_file}')
        return cache_file

    url = f'{base_url}/{rel_path}'
    print(f'  ↓ download: {url}')
    try:
        req = Request(url, headers={'User-Agent': USER_AGENT})
        with urlopen(req, timeout=DOWNLOAD_TIMEOUT) as response:
            content = response.read()
        with open(cache_file, 'wb') as f:
            f.write(content)
        return cache_file
    except (HTTPError, URLError) as e:
        print(f'\n  ✗ download failed: {e}')
        print(f'  URL: {url}')
        sys.exit(1)
