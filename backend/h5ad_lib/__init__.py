"""
h5ad-lib: Inlined library for H5AD-based bioinformatics web applications.

Provides core functionality for loading, caching, and serving AnnData (.h5ad)
files including configuration management, filter storage, and GO services.

Originally from: https://github.com/Mfkessler/h5ad-lib
Inlined to remove external private dependency.
"""

__version__ = "0.1.0"

from h5ad_lib.core.loader import H5ADCache, load_h5ad
from h5ad_lib.core.discovery import auto_discover_species, discover_layers
from h5ad_lib.core.registry import SpeciesRegistry
from h5ad_lib.filters.storage import FilterStore
from h5ad_lib.search.go_service import GOService
from h5ad_lib.config.manager import ConfigManager
from h5ad_lib.config.schema import ColumnTypeInference

__all__ = [
    "__version__",
    "H5ADCache",
    "load_h5ad",
    "auto_discover_species",
    "discover_layers",
    "SpeciesRegistry",
    "FilterStore",
    "GOService",
    "ConfigManager",
    "ColumnTypeInference",
]
