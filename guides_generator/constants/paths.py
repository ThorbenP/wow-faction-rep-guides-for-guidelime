"""Filesystem paths and addon-identity strings."""

CACHE_DIR = './cache'          # downloaded DBs live in `<CACHE_DIR>/<expansion>/`
ADDONS_DIR = './addons'        # generated addons live in `<ADDONS_DIR>/<expansion>/`
CHANGELOG_DIR = './changelog'  # version files in the form `vX.Y.Z[_<slug>].md`
LICENSE_PATH = './LICENSE'     # GPL-3.0 license text, copied into every addon
DIST_DIR = './dist'            # zipped, ready-to-upload addons live in `<DIST_DIR>/<expansion>/`

DEFAULT_EXPANSION_FOR_ALL = 'tbc'
FALLBACK_VERSION = '0.0.0'     # used when the changelog directory is empty

# Author tag — embedded in addon folder names, .toc Title, and Author field.
AUTHOR = 'ThPi'

# Public link shown in the per-addon README.md and the CurseForge project page.
REPO_URL = 'https://github.com/ThorbenP/wow-faction-rep-guides-for-guidelime'
