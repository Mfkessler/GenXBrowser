"""
H5AD file loader with LRU caching.

Provides efficient loading and caching of AnnData (.h5ad) files with:
- Memory-aware LRU eviction
- Per-species layer preference support
- Optional data transformation on load
- Thread-safe caching for multi-threaded servers
"""

import logging
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import anndata as ad

logger = logging.getLogger(__name__)


class H5ADCache:
    """
    Thread-safe LRU cache for AnnData objects with memory limit.
    
    The cache automatically evicts least-recently-used entries when
    the memory limit is exceeded. All operations are protected by
    a lock for thread safety in multi-threaded environments (e.g., gunicorn gthread).
    
    Example:
        cache = H5ADCache(max_size_mb=2048)
        cache.put("AC", adata)
        adata = cache.get("AC")
    """
    
    def __init__(self, max_size_mb: int = 2048):
        """
        Initialize H5AD cache.
        
        Args:
            max_size_mb: Maximum cache size in megabytes
        """
        self._cache: Dict[str, Any] = {}
        self._access_order: List[str] = []
        self._max_size_mb = max_size_mb
        self._current_size_mb = 0.0
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        # Track keys currently being loaded to prevent duplicate loading
        self._loading: Dict[str, threading.Event] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get AnnData from cache (thread-safe).
        
        Args:
            key: Cache key (typically species code)
            
        Returns:
            Cached AnnData or None if not found
        """
        with self._lock:
            if key in self._cache:
                # Move to end of access order (most recently used)
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key]
            return None
    
    def get_or_wait(self, key: str) -> Optional[Any]:
        """
        Get AnnData from cache, or wait if another thread is loading it.
        
        This prevents multiple threads from loading the same data simultaneously.
        
        Args:
            key: Cache key (typically species code)
            
        Returns:
            Cached AnnData or None if not found/not being loaded
        """
        with self._lock:
            # Check if already in cache
            if key in self._cache:
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key]
            
            # Check if another thread is loading this key
            if key in self._loading:
                event = self._loading[key]
            else:
                return None
        
        # Wait outside the lock for the other thread to finish loading
        event.wait(timeout=300)  # 5 minute timeout
        
        # Check cache again after waiting
        with self._lock:
            if key in self._cache:
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key]
        return None
    
    def start_loading(self, key: str) -> bool:
        """
        Mark a key as being loaded. Returns True if this thread should load it.
        
        Args:
            key: Cache key to mark as loading
            
        Returns:
            True if this thread should load the data, False if another thread is already loading
        """
        with self._lock:
            if key in self._cache:
                return False  # Already cached
            if key in self._loading:
                return False  # Another thread is loading
            self._loading[key] = threading.Event()
            return True
    
    def finish_loading(self, key: str) -> None:
        """
        Mark loading as complete and notify waiting threads.
        
        Args:
            key: Cache key that finished loading
        """
        with self._lock:
            if key in self._loading:
                event = self._loading.pop(key)
                event.set()  # Wake up waiting threads
    
    def put(self, key: str, adata: Any) -> None:
        """
        Store AnnData in cache with LRU eviction (thread-safe).
        
        Args:
            key: Cache key (typically species code)
            adata: AnnData object to cache
        """
        with self._lock:
            # If already in cache, just update access order
            if key in self._cache:
                if key in self._access_order:
                    self._access_order.remove(key)
                self._access_order.append(key)
                return
            
            size_mb = self._estimate_size(adata)
            
            # Evict old entries if necessary
            while self._current_size_mb + size_mb > self._max_size_mb and self._access_order:
                oldest = self._access_order.pop(0)
                if oldest in self._cache:
                    old_size = self._estimate_size(self._cache.pop(oldest))
                    self._current_size_mb -= old_size
                    logger.debug(f"Evicted {oldest} from cache ({old_size:.1f}MB)")
            
            # Add new entry
            self._cache[key] = adata
            self._access_order.append(key)
            self._current_size_mb += size_mb
            logger.info(f"Cached {key} ({size_mb:.1f}MB, total: {self._current_size_mb:.1f}MB)")
    
    def remove(self, key: str) -> bool:
        """
        Remove entry from cache (thread-safe).
        
        Args:
            key: Cache key to remove
            
        Returns:
            True if entry was removed, False if not found
        """
        with self._lock:
            if key in self._cache:
                size_mb = self._estimate_size(self._cache.pop(key))
                if key in self._access_order:
                    self._access_order.remove(key)
                self._current_size_mb -= size_mb
                logger.debug(f"Removed {key} from cache ({size_mb:.1f}MB)")
                return True
            return False
    
    def clear(self) -> None:
        """Clear all entries from cache (thread-safe)."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._current_size_mb = 0.0
            self._loading.clear()
            logger.info("Cache cleared")
    
    def _estimate_size(self, adata: Any) -> float:
        """
        Estimate memory size of AnnData object in MB.
        
        Args:
            adata: AnnData object
            
        Returns:
            Estimated size in megabytes
        """
        try:
            x_size = adata.X.nbytes if hasattr(adata.X, 'nbytes') else 0
            obs_size = sum(adata.obs.memory_usage(deep=True))
            var_size = sum(adata.var.memory_usage(deep=True))
            
            # Add layer sizes
            layers_size = sum(
                layer.nbytes if hasattr(layer, 'nbytes') else 0
                for layer in adata.layers.values()
            )
            
            return (x_size + obs_size + var_size + layers_size) / (1024 * 1024)
        except Exception:
            return 100.0  # Default fallback
    
    @property
    def size_mb(self) -> float:
        """Current cache size in MB."""
        return self._current_size_mb
    
    @property
    def max_size_mb(self) -> int:
        """Maximum cache size in MB."""
        return self._max_size_mb
    
    @property
    def keys(self) -> List[str]:
        """List of cached keys in access order (oldest first)."""
        return self._access_order.copy()
    
    def __contains__(self, key: str) -> bool:
        return key in self._cache
    
    def __len__(self) -> int:
        return len(self._cache)


def load_h5ad(
    file_path: str,
    layer_preference: str = "X",
    transform_fn: Optional[Callable[[Any, str], Any]] = None,
    species_code: Optional[str] = None,
) -> Any:
    """
    Load an H5AD file with optional layer preference and transformation.
    
    Args:
        file_path: Path to the .h5ad file
        layer_preference: Which layer to use as X ('X', 'tpm', 'tmm')
        transform_fn: Optional function to transform the AnnData after loading
        species_code: Species code (passed to transform_fn if provided)
        
    Returns:
        Loaded (and optionally transformed) AnnData object
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If specified layer doesn't exist
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"H5AD file not found: {file_path}")
    
    logger.info(f"Loading H5AD: {file_path}")
    adata = ad.read_h5ad(file_path)
    
    # Apply layer preference
    if layer_preference != "X" and layer_preference in adata.layers:
        logger.info(f"Applying layer preference: {layer_preference}")
        original_X = adata.X.copy()
        adata.X = adata.layers[layer_preference].copy()
        
        # Store original X in a layer if not already stored
        if "raw" not in adata.layers:
            adata.layers["raw"] = original_X
        
        logger.info(f"Loaded {layer_preference} as primary expression matrix (X)")
    elif layer_preference != "X":
        logger.warning(
            f"Layer '{layer_preference}' not found, using X. "
            f"Available layers: {list(adata.layers.keys())}"
        )
    
    # Apply transformation if provided
    if transform_fn and species_code:
        adata = transform_fn(adata, species_code)
    
    logger.info(
        f"Loaded: {adata.n_vars} genes × {adata.n_obs} samples, "
        f"layers: {list(adata.layers.keys())}"
    )
    
    return adata


class H5ADLoader:
    """
    Convenient loader class combining cache and loading logic.
    
    Example:
        loader = H5ADLoader(
            data_dir="/data/prepared",
            max_cache_size_mb=2048,
            layer_preferences={"AC": "tmm", "CS": "tpm"}
        )
        adata = loader.load("AC")
    """
    
    def __init__(
        self,
        data_dir: str,
        max_cache_size_mb: int = 2048,
        layer_preferences: Optional[Dict[str, str]] = None,
        file_pattern: str = "{code}/{code}_full.h5ad",
        transform_fn: Optional[Callable[[Any, str], Any]] = None,
    ):
        """
        Initialize H5AD loader.
        
        Args:
            data_dir: Base directory containing H5AD files
            max_cache_size_mb: Maximum cache size in MB
            layer_preferences: Dict mapping species codes to preferred layers
            file_pattern: Pattern for file paths, with {code} placeholder
            transform_fn: Optional transformation function
        """
        self.data_dir = Path(data_dir)
        self.cache = H5ADCache(max_size_mb=max_cache_size_mb)
        self.layer_preferences = layer_preferences or {}
        self.file_pattern = file_pattern
        self.transform_fn = transform_fn
    
    def load(self, species_code: str, force_reload: bool = False) -> Optional[Any]:
        """
        Load AnnData for a species, using cache if available.
        
        Args:
            species_code: Species code (e.g., 'AC', 'CS')
            force_reload: If True, bypass cache and reload from disk
            
        Returns:
            AnnData object or None if file not found
        """
        # Check cache first
        if not force_reload:
            cached = self.cache.get(species_code)
            if cached is not None:
                return cached
        
        # Build file path
        file_path = self.data_dir / self.file_pattern.format(code=species_code)
        
        if not file_path.exists():
            logger.warning(f"H5AD file not found: {file_path}")
            return None
        
        # Get layer preference
        layer_pref = self.layer_preferences.get(species_code, "X")
        
        # Load and cache
        adata = load_h5ad(
            str(file_path),
            layer_preference=layer_pref,
            transform_fn=self.transform_fn,
            species_code=species_code,
        )
        
        self.cache.put(species_code, adata)
        return adata
    
    def set_layer_preference(self, species_code: str, layer: str) -> None:
        """
        Set layer preference for a species.
        
        Note: Changes take effect on next load (after cache invalidation).
        
        Args:
            species_code: Species code
            layer: Layer name ('X', 'tpm', 'tmm')
        """
        self.layer_preferences[species_code] = layer
        # Invalidate cache for this species so next load uses new preference
        self.cache.remove(species_code)
    
    def get_available_layers(self, species_code: str) -> List[str]:
        """
        Get available layers for a species.
        
        Args:
            species_code: Species code
            
        Returns:
            List of available layer names (always includes 'X')
        """
        adata = self.load(species_code)
        if adata is None:
            return ["X"]
        
        return ["X"] + list(adata.layers.keys())
    
    def reload_all(self) -> None:
        """Clear cache, forcing all species to reload on next access."""
        self.cache.clear()
