"""Core module for h5ad file loading, caching, and species registry."""

from h5ad_lib.core.loader import H5ADCache, load_h5ad
from h5ad_lib.core.discovery import auto_discover_species, discover_layers
from h5ad_lib.core.registry import SpeciesRegistry

__all__ = [
    "H5ADCache",
    "load_h5ad",
    "auto_discover_species",
    "discover_layers",
    "SpeciesRegistry",
]
