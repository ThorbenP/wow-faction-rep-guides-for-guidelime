#!/usr/bin/env python3
"""Entry point: generates GuideLime reputation-farm addons.

Run `python3 create.py` for an interactive prompt, or use `--all` /
`--faction <id|name>` for non-interactive runs.
"""
from guides_generator.cli import main

if __name__ == '__main__':
    main()
