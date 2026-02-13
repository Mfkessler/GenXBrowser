"""
Species registry for managing multiple H5AD datasets.

The registry provides a unified interface for:
- Loading and caching AnnData objects
- Managing species metadata and configurations
- Column name mappings and transformations
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from h5ad_lib.core.loader import H5ADCache, load_h5ad
from h5ad_lib.core.discovery import auto_discover_species, discover_layers

logger = logging.getLogger(__name__)


class SpeciesRegistry:
    """
    Registry for managing multiple species/datasets.
    
    The registry maintains:
    - Species metadata (names, tags, available layers)
    - Layer preferences per species
    - Name mappings (code <-> full name)
    - Cached AnnData objects
    
    Example:
        registry = SpeciesRegistry(data_dir="/data/prepared")
        
        # Auto-discover species
        registry.discover()
        
        # Load AnnData
        adata = registry.load("AC")
        
        # Get species info
        species_list = registry.get_species_list()
    """
    
    def __init__(
        self,
        data_dir: str,
        max_cache_size_mb: int = 2048,
        file_pattern: str = "{code}/{code}_full.h5ad",
        transform_fn: Optional[Callable[[Any, str], Any]] = None,
    ):
        """
        Initialize species registry.
        
        Args:
            data_dir: Base directory containing H5AD files
            max_cache_size_mb: Maximum cache size in MB
            file_pattern: Pattern for file paths, with {code} placeholder
            transform_fn: Optional transformation function applied on load
        """
        self.data_dir = Path(data_dir)
        self.file_pattern = file_pattern
        self.transform_fn = transform_fn
        
        # Cache
        self._cache = H5ADCache(max_size_mb=max_cache_size_mb)
        
        # Species metadata
        self._species: Dict[str, Dict[str, Any]] = {}
        
        # Name mappings
        self._code_to_name: Dict[str, str] = {}
        self._name_to_code: Dict[str, str] = {}
        
        # Layer preferences per species
        self._layer_preferences: Dict[str, str] = {}
    
    def discover(self) -> int:
        """
        Auto-discover species from H5AD files.
        
        Returns:
            Number of species discovered
        """
        # Convert file pattern to glob pattern
        glob_pattern = self.file_pattern.replace("{code}", "*")
        
        discovered = auto_discover_species(str(self.data_dir), glob_pattern)
        
        for code, metadata in discovered.items():
            self.register_species(
                code=code,
                full_name=metadata["full_name"],
                display_name=metadata.get("display_name", metadata["full_name"]),
                file_path=metadata["file_path"],
                available_layers=metadata["available_layers"],
                tags=metadata.get("tags", []),
                enabled=True,
            )
        
        return len(self._species)
    
    def register_species(
        self,
        code: str,
        full_name: str,
        display_name: Optional[str] = None,
        file_path: Optional[str] = None,
        available_layers: Optional[List[str]] = None,
        layer_preference: str = "X",
        tags: Optional[List[str]] = None,
        enabled: bool = True,
    ) -> None:
        """
        Manually register a species.
        
        Args:
            code: Species code (e.g., 'AC')
            full_name: Full species name (e.g., 'Aquilegia caerulea')
            display_name: Display name (defaults to full_name)
            file_path: Path to H5AD file (defaults to pattern-based)
            available_layers: List of available layers
            layer_preference: Default layer preference
            tags: Searchable tags
            enabled: Whether species is enabled
        """
        if file_path is None:
            file_path = str(self.data_dir / self.file_pattern.format(code=code))
        
        self._species[code] = {
            "code": code,
            "full_name": full_name,
            "display_name": display_name or full_name,
            "file_path": file_path,
            "available_layers": available_layers or ["X"],
            "tags": tags or [],
            "enabled": enabled,
        }
        
        # Build name mappings
        name_key = full_name.lower().replace(" ", "_")
        self._code_to_name[code] = name_key
        self._name_to_code[name_key] = code
        
        # Set layer preference
        self._layer_preferences[code] = layer_preference
        
        logger.debug(f"Registered species: {code} = {full_name}")
    
    def load(self, species_code: str, force_reload: bool = False, ignore_enabled: bool = False) -> Optional[Any]:
        """
        Load AnnData for a species (thread-safe).
        
        This method prevents multiple threads from loading the same species simultaneously.
        If another thread is already loading the requested species, this thread will wait
        for the load to complete and then return the cached result.
        
        Args:
            species_code: Species code or full name
            force_reload: If True, bypass cache
            ignore_enabled: If True, load even if species is disabled (for admin purposes)
            
        Returns:
            AnnData object or None if not found
        """
        # Normalize species identifier
        code = self.normalize_code(species_code)
        if code is None:
            logger.warning(f"Unknown species: {species_code}")
            return None
        
        # Check cache first
        if not force_reload:
            cached = self._cache.get(code)
            if cached is not None:
                return cached
            
            # Check if another thread is loading - if so, wait for it
            cached = self._cache.get_or_wait(code)
            if cached is not None:
                return cached
        
        # Get species info
        species_info = self._species.get(code)
        if not species_info:
            return None
        
        if not ignore_enabled and not species_info.get("enabled", True):
            logger.warning(f"Species {code} is disabled")
            return None
        
        # Try to acquire loading lock - if another thread is loading, wait for it
        if not self._cache.start_loading(code):
            # Another thread is loading, wait and return cached result
            cached = self._cache.get_or_wait(code)
            if cached is not None:
                return cached
            # If still not in cache after waiting, fall through to load
            if not self._cache.start_loading(code):
                return self._cache.get(code)
        
        # This thread is responsible for loading
        try:
            file_path = species_info["file_path"]
            layer_pref = self._layer_preferences.get(code, "X")
            
            adata = load_h5ad(
                file_path,
                layer_preference=layer_pref,
                transform_fn=self.transform_fn,
                species_code=code,
            )
            
            self._cache.put(code, adata)
            return adata
            
        except Exception as e:
            logger.error(f"Failed to load {code}: {e}")
            return None
        finally:
            # Always signal that loading is complete
            self._cache.finish_loading(code)
    
    def normalize_code(self, identifier: str) -> Optional[str]:
        """
        Normalize a species identifier to a code.
        
        Handles:
        - Already a code: "AC" -> "AC"
        - Full name: "aquilegia_caerulea" -> "AC"
        - With _meta suffix: "AC_meta" -> "AC"
        
        Args:
            identifier: Species code or name
            
        Returns:
            Species code or None if not found
        """
        if not identifier:
            return None
        
        # Strip _meta suffix
        if identifier.endswith("_meta"):
            identifier = identifier[:-5]
        
        # Already a code?
        if identifier in self._species:
            return identifier
        
        # Full name to code
        name_key = identifier.lower().replace(" ", "_")
        if name_key in self._name_to_code:
            return self._name_to_code[name_key]
        
        return None
    
    def get_species_list(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get list of species with metadata.
        
        Args:
            enabled_only: If True, only return enabled species
            
        Returns:
            List of species metadata dicts
        """
        result = []
        for code, info in self._species.items():
            if enabled_only and not info.get("enabled", True):
                continue
            result.append({
                "code": code,
                "full_name": info["full_name"],
                "display_name": info["display_name"],
                "table_name": self._code_to_name.get(code, code.lower()),
                "available_layers": info["available_layers"],
                "layer_preference": self._layer_preferences.get(code, "X"),
                "tags": info.get("tags", []),
                "enabled": info.get("enabled", True),
            })
        return result
    
    def get_available_codes(self, enabled_only: bool = True) -> List[str]:
        """
        Get list of available species codes.
        
        Args:
            enabled_only: If True, only return enabled species
            
        Returns:
            List of species codes
        """
        if enabled_only:
            return [
                code for code, info in self._species.items()
                if info.get("enabled", True)
            ]
        return list(self._species.keys())
    
    def get_layer_preference(self, species_code: str) -> str:
        """Get layer preference for a species."""
        code = self.normalize_code(species_code)
        return self._layer_preferences.get(code, "X") if code else "X"
    
    def set_layer_preference(self, species_code: str, layer: str) -> bool:
        """
        Set layer preference for a species.
        
        Args:
            species_code: Species code
            layer: Layer name
            
        Returns:
            True if successful
        """
        code = self.normalize_code(species_code)
        if code is None:
            return False
        
        species_info = self._species.get(code)
        if not species_info:
            return False
        
        available = species_info.get("available_layers", ["X"])
        if layer not in available:
            logger.error(f"Layer '{layer}' not available for {code}. Available: {available}")
            return False
        
        self._layer_preferences[code] = layer
        # Invalidate cache so next load uses new preference
        self._cache.remove(code)
        logger.info(f"Set layer preference for {code}: {layer}")
        return True
    
    def get_available_layers(self, species_code: str) -> List[str]:
        """Get available layers for a species."""
        code = self.normalize_code(species_code)
        if code is None:
            return ["X"]
        
        species_info = self._species.get(code)
        if species_info:
            return species_info.get("available_layers", ["X"])
        
        return ["X"]
    
    def enable_species(self, species_code: str, enabled: bool = True) -> bool:
        """Enable or disable a species."""
        code = self.normalize_code(species_code)
        if code is None or code not in self._species:
            return False
        
        self._species[code]["enabled"] = enabled
        return True
    
    def invalidate_cache(self, species_code: Optional[str] = None) -> None:
        """
        Invalidate cache for a species or all species.
        
        Args:
            species_code: If provided, only invalidate this species.
                         If None, clear entire cache.
        """
        if species_code:
            code = self.normalize_code(species_code)
            if code:
                self._cache.remove(code)
        else:
            self._cache.clear()
    
    def get_table_name(self, species_code: str) -> str:
        """Get table name (snake_case full name) for a species code."""
        code = self.normalize_code(species_code)
        return self._code_to_name.get(code, species_code.lower()) if code else species_code.lower()
    
    def get_code_for_table(self, table_name: str) -> Optional[str]:
        """Get species code for a table name."""
        return self.normalize_code(table_name)
    
    @property
    def cache(self) -> H5ADCache:
        """Access the underlying cache."""
        return self._cache
    
    def __contains__(self, species_code: str) -> bool:
        return self.normalize_code(species_code) is not None
    
    def __len__(self) -> int:
        return len(self._species)
