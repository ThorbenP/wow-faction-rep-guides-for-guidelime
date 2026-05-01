"""Single-run and bulk-run pipelines plus their shared loaders."""
from .bulk import run_all
from .single import run_single

__all__ = ['run_all', 'run_single']
