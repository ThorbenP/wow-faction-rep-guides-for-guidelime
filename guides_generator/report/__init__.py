"""Quality report generation: aggregate pathing stats and render Markdown.

`write_quality_report` is the public entry point — called from the bulk
runner once every faction has been generated.
"""
from .writer import write_quality_report

__all__ = ['write_quality_report']
