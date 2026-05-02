"""Quality report generation: aggregate pathing stats and render Markdown.

Two report flavours are produced from the same per-faction stats:
- `write_addon_report(stats, addon_dir, ...)` writes a self-contained
  `QUALITY_REPORT.md` inside the addon's directory.
- `write_global_report(results, ...)` writes the slim global
  `_quality_report.md` at the repo root.

Bulk runs emit both. Single-faction runs emit only the per-addon file
(the global summary would be a one-row table — not useful).
"""
from .writer import write_addon_report, write_global_report

__all__ = ['write_addon_report', 'write_global_report']
