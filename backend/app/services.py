"""
GenXBrowser H5AD Service - Thin wrapper over h5ad-lib
======================================================
Uses h5ad-lib for core functionality, adds GenXBrowser-specific features:
- SequenceStore: FASTA protein/RNA sequences
- GeneTreeStore: Newick gene trees by orthogroup
- Virtual columns: newick_str, protein_seq, rna_seq
- _meta table support for Metadata dialog
"""

import os
import logging
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Set
import re

import numpy as np
import pandas as pd

# h5ad-lib imports
from h5ad_lib.core.registry import SpeciesRegistry
from h5ad_lib.config.manager import ConfigManager
from h5ad_lib.filters.storage import FilterStore

logger = logging.getLogger(__name__)


# ============================================================================
# Species Photo Utilities
# ============================================================================

def fuzzy_match_photo(species_name: str, photo_files: List[str]) -> Optional[str]:
    """
    Match species name to photo filename using fuzzy matching.
    
    Algorithm:
    1. Normalize both species name and filenames (lowercase, remove spaces/underscores)
    2. Calculate character overlap
    3. Return best match if overlap is significant (>70% of shorter string)
    
    Args:
        species_name: Species table name (e.g., 'capnoides_sempervirens')
        photo_files: List of photo filenames (e.g., ['capnoides_sempervirens.jpg'])
    
    Returns:
        Matching filename or None
    """
    def normalize(s: str) -> str:
        """Remove extension, lowercase, remove non-alphanumeric."""
        s = s.lower()
        # Remove file extension
        s = re.sub(r'\.[^.]+$', '', s)
        # Keep only alphanumeric characters
        s = re.sub(r'[^a-z0-9]', '', s)
        return s
    
    normalized_species = normalize(species_name)
    
    best_match = None
    best_score = 0
    
    for photo_file in photo_files:
        normalized_photo = normalize(photo_file)
        
        # Calculate character overlap
        common_chars = sum(1 for c in normalized_species if c in normalized_photo)
        shorter_len = min(len(normalized_species), len(normalized_photo))
        
        if shorter_len == 0:
            continue
        
        score = common_chars / shorter_len
        
        # Bonus for exact prefix match
        if normalized_photo.startswith(normalized_species) or normalized_species.startswith(normalized_photo):
            score += 0.2
        
        if score > best_score:
            best_score = score
            best_match = photo_file
    
    # Return match only if score is high enough (70% overlap)
    if best_score >= 0.7:
        return best_match
    
    return None


def detect_species_photos(photos_dir: str) -> Dict[str, str]:
    """
    Scan photos directory and return dict of available photos.
    
    Args:
        photos_dir: Path to species photos directory
    
    Returns:
        Dict mapping normalized names to filenames
    """
    if not os.path.exists(photos_dir):
        logger.info(f"Species photos directory not found: {photos_dir}")
        return {}
    
    supported_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    photo_files = []
    
    try:
        for filename in os.listdir(photos_dir):
            ext = os.path.splitext(filename)[1].lower()
            if ext in supported_extensions:
                photo_files.append(filename)
        
        logger.info(f"Found {len(photo_files)} photos in {photos_dir}: {photo_files}")
        return photo_files
    
    except Exception as e:
        logger.error(f"Error scanning photos directory: {e}")
        return []


# ============================================================================
# Expression Layer Metadata & Transform Logic (CoNExUS-inspired)
# ============================================================================

LAYER_DESCRIPTIONS = {
    "X": {
        "name": "Raw Counts",
        "short": "RAW",
        "description": "Main expression matrix - unprocessed read counts",
        "use_case": "Direct count data from sequencing",
        "is_log": False
    },
    "tpm": {
        "name": "TPM",
        "short": "TPM",
        "description": "Transcripts Per Million. Within-sample normalization that accounts for gene length and sequencing depth.",
        "use_case": "Compare gene expression levels WITHIN a single sample",
        "is_log": False
    },
    "tmm": {
        "name": "TMM",
        "short": "TMM",
        "description": "Trimmed Mean of M-values (edgeR). Between-sample normalization for comparing expression across samples.",
        "use_case": "Compare expression levels BETWEEN different samples/conditions",
        "is_log": False
    },
    "log-cpm": {
        "name": "log-CPM",
        "short": "logCPM",
        "description": "Log2 Counts Per Million - already log-transformed normalized counts",
        "use_case": "Pre-transformed data for downstream analysis",
        "is_log": True
    },
    "getmm": {
        "name": "GeTMM",
        "short": "GeTMM",
        "description": "Gene-length corrected TMM. Combines between-sample TMM normalization with gene-length correction (similar to TPM).",
        "use_case": "Accounts for gene length AND provides between-sample normalization.",
        "is_log": False
    },
    "vst": {
        "name": "VST",
        "short": "VST",
        "description": "Variance Stabilizing Transformation (DESeq2). Stabilizes variance across expression range.",
        "use_case": "Already stabilized; use directly or with z-score. Avoid additional log2.",
        "is_log": True
    }
}

TRANSFORM_LAYER_RECOMMENDATIONS = {
    "log2": {
        "preferred": "tpm",
        "fallbacks": ["tmm", "X"],
        "reasoning": "Log2(x+1) on TPM provides comparable log-expression values",
        "avoid": ["log-cpm", "vst"]  # Already log-transformed
    },
    "zscore": {
        "preferred": "getmm",  # GeTMM is gene-length corrected AND between-sample normalized
        "fallbacks": ["tmm", "tpm", "log-cpm", "X"],
        "reasoning": "Z-score on log2(GeTMM+1) standardizes per gene across samples. GeTMM combines gene-length correction with between-sample normalization."
    },
    "raw": {
        "preferred": None,  # User chooses
        "fallbacks": [],
        "reasoning": "Display values directly from selected layer without transformation"
    }
}


def select_optimal_layer(adata, transform: str, requested_layer: Optional[str] = None) -> Tuple[str, str]:
    """
    Intelligently selects the best layer for a transformation.
    
    Args:
        adata: AnnData object with .layers
        transform: One of 'raw', 'log2', 'zscore'
        requested_layer: User's explicitly requested layer (optional)
    
    Returns:
        Tuple of (layer_key, reasoning_string)
    """
    recommendation = TRANSFORM_LAYER_RECOMMENDATIONS.get(transform, {})
    
    # For 'raw' transform, use user's choice or look for 'raw' layer
    if transform == "raw":
        if requested_layer:
            layer = requested_layer
        elif "raw" in adata.layers:
            layer = "raw"
        else:
            layer = "X"
        layer_info = LAYER_DESCRIPTIONS.get(layer, {})
        return layer, f"Displaying {layer_info.get('name', layer)} values directly."
    
    # Check if requested layer is inappropriate for this transform
    avoid_layers = recommendation.get("avoid", [])
    if requested_layer and requested_layer in avoid_layers:
        layer_info = LAYER_DESCRIPTIONS.get(requested_layer, {})
        return requested_layer, f"⚠️ Warning: {transform} on {layer_info.get('name', requested_layer)} may be inappropriate (already transformed)"
    
    # If user explicitly requested a layer, use it
    if requested_layer:
        layer_info = LAYER_DESCRIPTIONS.get(requested_layer, {})
        return requested_layer, recommendation.get("reasoning", f"Using {layer_info.get('name', requested_layer)} as base layer")
    
    # Auto-select optimal layer
    available_layers = ["X"] + list(adata.layers.keys())
    
    # Try preferred layer first
    preferred = recommendation.get("preferred")
    if preferred and preferred in available_layers:
        return preferred, recommendation.get("reasoning", "")
    
    # Preferred layer not available - log warning and try fallbacks
    if preferred:
        logger.warning(f"Preferred layer '{preferred}' not available for {transform}. Trying fallbacks...")
    
    # Try fallback layers
    for fallback in recommendation.get("fallbacks", []):
        if fallback in available_layers:
            layer_info = LAYER_DESCRIPTIONS.get(fallback, {})
            logger.info(f"Using fallback layer '{fallback}' for {transform} (preferred '{preferred}' not available)")
            return fallback, f"Using {layer_info.get('name', fallback)} (preferred layer '{preferred}' not available)"
    
    # Ultimate fallback: X
    return "X", "Using raw counts (no preferred layer available)"


# ============================================================================
# GenXBrowser-specific Storage Classes (NOT in h5ad-lib)
# ============================================================================

class SequenceStore:
    """Loads and caches FASTA sequences for genes."""
    
    def __init__(self, sequences_dir: str):
        self._sequences_dir = Path(sequences_dir)
        self._cache: Dict[str, Dict[str, str]] = {}
    
    def _load_fasta(self, file_path: Path) -> Dict[str, str]:
        """Load FASTA file and return dict of gene_id -> sequence."""
        sequences = {}
        current_id = None
        current_seq = []
        
        if not file_path.exists():
            logger.warning(f"FASTA file not found: {file_path}")
            return sequences
        
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('>'):
                    if current_id:
                        sequences[current_id] = ''.join(current_seq)
                    current_id = line[1:].split()[0]
                    current_seq = []
                elif current_id:
                    current_seq.append(line)
            
            if current_id:
                sequences[current_id] = ''.join(current_seq)
        
        return sequences
    
    def get_protein_seq(self, species_code: str, gene_id: str) -> str:
        """Get protein sequence for a gene."""
        cache_key = f"{species_code}_protein"
        
        if cache_key not in self._cache:
            fasta_file = self._sequences_dir / f"{species_code}.protein.fas"
            self._cache[cache_key] = self._load_fasta(fasta_file)
            logger.info(f"Loaded {len(self._cache[cache_key])} protein sequences for {species_code}")
        
        return self._cache[cache_key].get(gene_id, '')
    
    def get_rna_seq(self, species_code: str, gene_id: str) -> str:
        """Get RNA sequence for a gene."""
        cache_key = f"{species_code}_RNA"
        
        if cache_key not in self._cache:
            fasta_file = self._sequences_dir / f"{species_code}.RNA.fas"
            self._cache[cache_key] = self._load_fasta(fasta_file)
            logger.info(f"Loaded {len(self._cache[cache_key])} RNA sequences for {species_code}")
        
        return self._cache[cache_key].get(gene_id, '')


class GeneTreeStore:
    """Stores and retrieves Newick gene trees by orthogroup ID."""
    
    def __init__(self, path: str):
        self._trees: Dict[str, str] = {}
        self._load(path)
    
    def _load(self, path: str) -> None:
        if not Path(path).exists():
            logger.warning(f"Gene trees file not found: {path}")
            return
        
        logger.info(f"Loading gene trees from {path}")
        
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or ':' not in line:
                    continue
                
                parts = line.split(':', 1)
                if len(parts) == 2:
                    og_id = parts[0].strip()
                    newick = parts[1].strip()
                    self._trees[og_id] = newick
        
        logger.info(f"Loaded {len(self._trees)} gene trees")
    
    def get(self, og_id: str) -> Optional[str]:
        return self._trees.get(og_id)


# ============================================================================
# GenXBrowser Service - Wrapper over h5ad-lib
# ============================================================================

class GenXBrowserService:
    """
    Main service for GenXBrowser H5AD data access.
    
    Wraps h5ad-lib components and adds GenXBrowser-specific features:
    - Virtual columns (newick_str, protein_seq, rna_seq)
    - _meta table support
    - Response format compatibility with frontend
    """
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize with h5ad-lib ConfigManager."""
        self.config_manager = config_manager
        self.config = self._load_config()
        
        # Initialize h5ad-lib SpeciesRegistry — module_colors read directly from adata.var
        self.registry = SpeciesRegistry(
            data_dir=self.config['h5ad_dir'],
            max_cache_size_mb=self.config.get('cache_max_size_mb', 2048),
        )
        
        # Register species from config
        self._register_species_from_config()
        
        # GenXBrowser-specific stores
        self.gene_trees = GeneTreeStore(self.config['gene_trees_path'])
        self.sequences = SequenceStore(self.config['sequences_dir'])
        self.filter_store = FilterStore(path=self.config['filter_store_path'])
        
        # Species photos detection
        photos_dir = os.environ.get('SPECIES_PHOTOS_DIR', '/data/species_photos')
        self._available_photos = detect_species_photos(photos_dir)
        
        # Load mappings from config
        self._column_mappings = self.config_manager.get_column_mappings()
        self._reverse_column_mappings = {v: k for k, v in self._column_mappings.items()}
        self._array_columns = self.config_manager.get_array_columns()
        self._meta_columns = self.config_manager.get_meta_columns()
        
        # Cache for unique column values
        self._unique_values_cache: Dict[str, List[str]] = {}

        # Cache for global (all-dataset merged) histogram bins
        self._global_bins_cache: Dict[str, List] = {}

        # Cache for ORA background data: (species_code, column_name) -> DataFrame
        self._ora_background_cache: Dict[tuple, pd.DataFrame] = {}
    
    def _load_config(self) -> Dict[str, Any]:
        """Load environment-based configuration."""
        return {
            'h5ad_dir': os.environ.get('H5AD_DATA_DIR', '/data/prepared'),
            'gene_trees_path': os.environ.get('GENE_TREES_PATH', '/data/Metadata/Resolved_Gene_Trees.txt'),
            'sequences_dir': os.environ.get('SEQUENCES_DIR', '/data/Metadata/fas'),
            'filter_store_path': os.environ.get('FILTER_STORE_PATH', '/data/filters'),
            'cache_max_size_mb': int(os.environ.get('CACHE_MAX_SIZE_MB', '2048')),
        }
    
    def _register_species_from_config(self) -> None:
        """Register all species from ConfigManager into Registry."""
        species_config = self.config_manager.get_species()
        
        for code, spec in species_config.items():
            if not spec.get('enabled', True):
                continue
            
            file_path = Path(self.config['h5ad_dir']) / code / f"{code}_full.h5ad"
            
            self.registry.register_species(
                code=code,
                full_name=spec['full_name'],
                display_name=spec.get('display_name', spec['full_name']),
                file_path=str(file_path),
                available_layers=spec.get('available_layers', ['X']),
                layer_preference=spec.get('layer_preference', 'X'),
                tags=spec.get('tags', []),
                enabled=True,
            )
        
        logger.info(f"Registered {len(self.registry)} species from config")
    
    def reload_config(self) -> None:
        """Reload configuration and update internal state."""
        logger.info("Reloading service configuration...")
        self._column_mappings = self.config_manager.get_column_mappings()
        self._reverse_column_mappings = {v: k for k, v in self._column_mappings.items()}
        self._array_columns = self.config_manager.get_array_columns()
        self._meta_columns = self.config_manager.get_meta_columns()
        self._register_species_from_config()
        self.registry.invalidate_cache()
        self._unique_values_cache = {}
        self._global_bins_cache = {}  # Invalidate so queries fall back to on-demand until recomputed
        logger.info("Service configuration reloaded")
        # Recompute global bins in background after reload
        threading.Thread(target=self.precompute_global_bins, daemon=True).start()
        logger.info("Started background global bin precomputation after config reload")
    
    # =========================================================================
    # Column Name Mapping
    # =========================================================================
    
    def _to_display_column_name(self, h5ad_name: str) -> str:
        """Convert H5AD column name to display column name."""
        if h5ad_name in self._column_mappings:
            return self._column_mappings[h5ad_name]
        return h5ad_name.replace(' ', '_').replace('-', '_').lower()
    
    def _to_h5ad_column_name(self, display_name: str) -> str:
        """Convert display column name to H5AD column name."""
        if display_name in self._reverse_column_mappings:
            return self._reverse_column_mappings[display_name]
        return display_name
    
    def _normalize_table_name(self, table_name: str) -> Optional[str]:
        """Normalize table name to species code."""
        if not table_name:
            return None
        
        # Strip _meta suffix
        if table_name.endswith('_meta'):
            table_name = table_name[:-5]
        
        return self.registry.normalize_code(table_name)
    
    # =========================================================================
    # Column Type Inference
    # =========================================================================
    
    def _get_column_type(self, dtype: str, col_name: str) -> str:
        """Determine column type from config or dtype."""
        display_name = self._to_display_column_name(col_name)
        
        # Check config first
        col_def = self.config_manager.get_column_definitions().get(display_name)
        if col_def:
            return col_def.get('type', 'text')
        
        # Check if it's an array column
        if display_name in self._array_columns:
            return 'array'
        
        # Fallback to dtype inference
        dtype_str = str(dtype).lower()
        if 'int' in dtype_str:
            return 'bigint'
        elif 'float' in dtype_str:
            return 'double precision'
        elif 'bool' in dtype_str:
            return 'boolean'
        else:
            return 'text'
    
    # =========================================================================
    # Public API - Species
    # =========================================================================
    
    def get_available_species(self) -> List[str]:
        """Get list of available species codes."""
        return self.registry.get_available_codes()
    
    def get_tables(self, tags: Optional[List[str]] = None, include_disabled: bool = False) -> List[Dict]:
        """
        Get list of available species/tables.
        
        Args:
            tags: Optional tag filter
            include_disabled: If True, include disabled species (for admin panel)
        
        Returns:
            List of species/table metadata
        """
        tables = []
        
        # Get all species (including disabled if requested)
        for species_info in self.registry.get_species_list(enabled_only=not include_disabled):
            code = species_info['code']
            is_enabled = species_info.get('enabled', True)
            
            # Load species data (ignore enabled status if include_disabled=True)
            adata = self.registry.load(code, ignore_enabled=include_disabled)
            
            if adata is None:
                continue
            
            full_name = species_info['table_name']
            species_tags = species_info.get('tags', [])
            if not species_tags:
                species_tags = full_name.split('_') + ['expression']
            
            # Count unique tissues
            tissue_count = 0
            if 'tissue' in adata.obs.columns:
                tissue_count = adata.obs['tissue'].dropna().nunique()
            
            # Filter by tags if specified
            if tags:
                if not any(t.lower() in [s.lower() for s in species_tags] for t in tags):
                    continue
            
            # Try to match a photo for this species
            matched_photo = None
            if self._available_photos:
                matched_photo = fuzzy_match_photo(full_name, self._available_photos)
                if matched_photo:
                    logger.debug(f"Matched photo '{matched_photo}' for species '{full_name}'")
            
            tables.append({
                'table_name': full_name,
                'description': '',
                'count': adata.n_vars,
                'tags': species_tags,
                'photo': matched_photo,  # Photo filename or None
                '_species_code': code,
                '_tissue_count': tissue_count,
                '_enabled': is_enabled,  # Add enabled status
            })
        
        return tables
    
    # =========================================================================
    # Public API - Columns
    # =========================================================================
    
    def get_all_columns(
        self,
        source: Optional[str] = None,
        table_name: Optional[str] = None,
        is_meta: Optional[bool] = None
    ) -> List[Dict]:
        """Get column metadata matching frontend format."""
        columns = []
        seen: Set[str] = set()
        
        include_sample_meta = table_name and table_name.endswith('_meta') and source in (None, "meta")
        
        if table_name:
            species_list = [self._normalize_table_name(table_name)]
        else:
            species_list = self.get_available_species()
        
        for species_code in species_list:
            if not species_code:
                continue
            adata = self.registry.load(species_code)
            if adata is None:
                continue
            
            if source == "column_meta":
                # Sample metadata from .obs.columns
                # Hide internal/technical columns from the UI
                HIDDEN_SAMPLE_COLUMNS = {'type', 'ismeta'}
                column_defs = self.config_manager.get_column_definitions()
                obs_candidates = []
                for col in adata.obs.columns:
                    pg_name = self._to_display_column_name(col)

                    # Skip hidden internal columns
                    if pg_name.lower() in HIDDEN_SAMPLE_COLUMNS:
                        continue

                    if pg_name not in seen:
                        seen.add(pg_name)
                        dtype = str(adata.obs[col].dtype)
                        col_type = self._get_column_type(dtype, col)

                        format_str = ''
                        if col_type in ('bigint', 'double precision'):
                            try:
                                col_min = float(adata.obs[col].min())
                                col_max = float(adata.obs[col].max())
                                format_str = f"{col_min},{col_max}"
                            except (ValueError, TypeError):
                                pass

                        col_def = column_defs.get(pg_name, {})
                        if not col_def.get('visible', True):
                            continue

                        obs_candidates.append({
                            'column_name': pg_name,
                            'display_name': col_def.get('display_name', pg_name),
                            'type': col_type,
                            'description': '',
                            'format': format_str,
                            'isMeta': False,
                            '_order': col_def.get('order', 9999),
                        })

                # Sort by saved order, then append
                obs_candidates.sort(key=lambda c: (c['_order'], c['column_name']))
                for c in obs_candidates:
                    c.pop('_order', None)
                    columns.append(c)
            
            else:  # source == "meta" or None
                # Sample IDs as expression columns FIRST
                if is_meta is None or is_meta is False:
                    expr_min = float(adata.X.min())
                    expr_max = float(adata.X.max())
                    format_str = f"{expr_min},{expr_max}"
                    
                    for sample_id in adata.obs_names:
                        if sample_id not in seen:
                            seen.add(sample_id)
                            columns.append({
                                'column_name': sample_id,
                                'type': 'double precision',
                                'description': '',
                                'format': format_str,
                                'isMeta': False,
                            })
                
                # Gene metadata from .var.columns SECOND
                if is_meta is None or is_meta is True:
                    column_defs = self.config_manager.get_column_definitions()

                    # Collect candidate meta columns first, then sort by saved order
                    meta_candidates = []
                    for col in adata.var.columns:
                        display_name = self._to_display_column_name(col)

                        # All .var columns are gene/transcript metadata – no whitelist needed.
                        # The column_definitions visibility flag controls what the user sees.

                        if display_name not in seen:
                            seen.add(display_name)
                            dtype = str(adata.var[col].dtype)
                            col_type = self._get_column_type(dtype, col)
                            col_def = column_defs.get(display_name, {})

                            if not col_def.get('visible', True):
                                continue

                            meta_candidates.append({
                                'column_name': display_name,
                                'display_name': col_def.get('display_name', display_name),
                                'type': col_type,
                                'description': '',
                                'format': '',
                                'isMeta': True,
                                '_order': col_def.get('order', 9999),
                            })

                    # Add virtual columns
                    for vcol in ['newick_str', 'protein_seq', 'rna_seq']:
                        if vcol not in seen:
                            col_def = column_defs.get(vcol, {})
                            if col_def.get('visible', True):
                                seen.add(vcol)
                                meta_candidates.append({
                                    'column_name': vcol,
                                    'display_name': col_def.get('display_name', vcol),
                                    'type': 'text',
                                    'description': '',
                                    'format': '',
                                    'isMeta': True,
                                    '_order': col_def.get('order', 9999),
                                })

                    # Sort by saved order field, then append
                    meta_candidates.sort(key=lambda c: (c['_order'], c['column_name']))
                    for c in meta_candidates:
                        c.pop('_order', None)
                        columns.append(c)
                
                # Add sample metadata for _meta tables
                if include_sample_meta:
                    for col in adata.obs.columns:
                        pg_name = self._to_display_column_name(col)
                        if pg_name not in seen:
                            seen.add(pg_name)
                            dtype = str(adata.obs[col].dtype)
                            col_type = self._get_column_type(dtype, col)
                            
                            format_str = ''
                            if col_type in ('bigint', 'double precision'):
                                try:
                                    col_min = float(adata.obs[col].min())
                                    col_max = float(adata.obs[col].max())
                                    format_str = f"{col_min},{col_max}"
                                except (ValueError, TypeError):
                                    pass
                            
                            columns.append({
                                'column_name': pg_name,
                                'type': col_type,
                                'description': '',
                                'format': format_str,
                                'isMeta': False,
                            })
        
        return columns
    
    # =========================================================================
    # Public API - Data
    # =========================================================================
    
    def get_data(
        self,
        table_name: str,
        columns: List[str],
        filters: Optional[Dict[str, Tuple[str, Any]]] = None,
        sample_filters: Optional[Dict[str, Tuple[str, Any]]] = None,
        limit: int = 1001,
        offset: int = 0,
        layer: Optional[str] = None,
        transform: str = "raw",
        include_virtual_columns: bool = True
    ) -> Tuple[pd.DataFrame, Optional[Dict[str, Any]]]:
        """
        Get gene data with columns and filtering.
        
        Returns:
            Tuple of (DataFrame, layer_metadata) where layer_metadata contains
            info about which layer was used and why.
        """
        is_meta_table = table_name.endswith('_meta')
        species_code = self._normalize_table_name(table_name)
        adata = self.registry.load(species_code)
        
        if adata is None:
            return pd.DataFrame(), None
        
        if is_meta_table:
            return self._get_meta_table_data(adata, columns, limit, offset, sample_filters), None
        
        # Determine optimal layer for expression data
        selected_layer, layer_reasoning = select_optimal_layer(adata, transform, layer)
        layer_metadata = {
            "layer_used": selected_layer,
            "layer_reasoning": layer_reasoning,
            "transform": transform,
            "available_layers": ["X"] + list(adata.layers.keys()) if hasattr(adata, 'layers') else ["X"]
        }
        
        # Filter samples
        if sample_filters:
            allowed_sample_ids = self._filter_samples(adata, sample_filters)
        else:
            allowed_sample_ids = set(adata.obs_names)
        
        result_data = {}
        
        if not columns:
            all_cols_info = self.get_all_columns(table_name=table_name)
            columns = [c['column_name'] for c in all_cols_info]
        
        # Always include gene_id first
        if 'gene_id' in adata.var.columns:
            result_data['gene_id'] = adata.var['gene_id'].values
        else:
            result_data['gene_id'] = adata.var_names.values
        
        # Separate metadata columns from sample (expression) columns
        metadata_cols = []
        sample_cols = []
        
        for pg_col in columns:
            if pg_col == 'gene_id':
                continue
            
            h5ad_col = self._to_h5ad_column_name(pg_col)
            
            if h5ad_col in adata.var.columns or pg_col in adata.var.columns:
                metadata_cols.append(pg_col)
            elif pg_col in adata.obs_names and pg_col in allowed_sample_ids:
                sample_cols.append(pg_col)
        
        # IMPORTANT: Add filter columns to metadata_cols so we can filter on them
        # Even if they're not in the requested columns list
        if filters:
            for filter_col in filters.keys():
                h5ad_col = self._to_h5ad_column_name(filter_col)
                if filter_col not in metadata_cols:
                    if h5ad_col in adata.var.columns or filter_col in adata.var.columns:
                        metadata_cols.append(filter_col)
                        logger.info(f"[get_data] Added filter column to metadata: {filter_col}")
        
        # Add metadata columns
        for pg_col in metadata_cols:
            h5ad_col = self._to_h5ad_column_name(pg_col)
            if h5ad_col in adata.var.columns:
                result_data[pg_col] = adata.var[h5ad_col].values
            elif pg_col in adata.var.columns:
                result_data[pg_col] = adata.var[pg_col].values
        
        # Process expression columns - get expression matrix from selected layer
        if sample_cols:
            # Get the full expression matrix from selected layer once
            if selected_layer == "raw" and "raw" in adata.layers:
                X = adata.layers["raw"]
            elif selected_layer == "X" or selected_layer is None:
                X = adata.X
            elif selected_layer in adata.layers:
                X = adata.layers[selected_layer]
            else:
                logger.warning(f"Layer {selected_layer} not found, using X")
                X = adata.X
            
            if hasattr(X, 'toarray'):
                X = X.toarray()
            
            # Get sample indices for requested samples
            sample_indices = [list(adata.obs_names).index(s) for s in sample_cols]
            
            # Extract expression matrix: genes (rows) x samples (cols)
            # X is stored as samples x genes, so we transpose after subsetting
            expr_matrix = X[sample_indices, :].T  # Now: n_genes x n_samples
            
            # Apply transformation
            if transform == "log2":
                # Simple log2(x+1) transformation
                expr_matrix = np.log2(expr_matrix + 1)
            elif transform == "zscore":
                # ROW-WISE z-score: first log2(x+1), then standardize per gene (row)
                expr_matrix = np.log2(expr_matrix + 1)
                
                # Compute mean and std per row (gene)
                row_means = np.nanmean(expr_matrix, axis=1, keepdims=True)
                row_stds = np.nanstd(expr_matrix, axis=1, keepdims=True)
                
                # Avoid division by zero - set std=1 where std=0
                row_stds = np.where(row_stds > 0, row_stds, 1.0)
                
                expr_matrix = (expr_matrix - row_means) / row_stds
            
            # Add each sample column to result_data
            for i, sample_col in enumerate(sample_cols):
                result_data[sample_col] = expr_matrix[:, i]
        
        df = pd.DataFrame(result_data)
        
        # Add virtual columns (only when requested and enabled)
        if include_virtual_columns:
            if 'orthogroup' in df.columns and ('newick_str' in columns or not columns):
                df['newick_str'] = df['orthogroup'].apply(
                    lambda og: self.gene_trees.get(og) if pd.notna(og) and og else None
                )
            
            if 'gene_id' in df.columns:
                if 'protein_seq' in columns or not columns:
                    df['protein_seq'] = df['gene_id'].apply(
                        lambda gid: self.sequences.get_protein_seq(species_code, gid) if pd.notna(gid) else ''
                    )
                if 'rna_seq' in columns or not columns:
                    df['rna_seq'] = df['gene_id'].apply(
                        lambda gid: self.sequences.get_rna_seq(species_code, gid) if pd.notna(gid) else ''
                    )
        
        # Apply filters
        if filters:
            df = self._apply_filters(df, filters)
        
        # Pagination (if limit is None, select all rows from offset)
        if limit is not None:
            df = df.iloc[offset:offset + limit]
        elif offset > 0:
            df = df.iloc[offset:]
        
        # Clean up NaN
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].fillna('')
            else:
                df[col] = df[col].replace({np.nan: None})
        
        return df, layer_metadata
    
    def _get_meta_table_data(
        self,
        adata: Any,
        columns: List[str],
        limit: int,
        offset: int,
        sample_filters: Optional[Dict[str, Tuple[str, Any]]] = None
    ) -> pd.DataFrame:
        """
        Get SAMPLE metadata table data for Metadata dialog.
        
        NOTE: This only returns sample (obs) metadata, NOT gene metadata.
        Gene metadata (go_term, description, gene_name, etc.) is available
        through the Data Manager / Inspect Data modal instead.
        """
        
        # Apply sample filters if provided
        if sample_filters:
            allowed_sample_ids = self._filter_samples(adata, sample_filters)
        else:
            allowed_sample_ids = set(adata.obs_names)
        rows = []
        
        # Sample ID rows with metadata (from adata.obs) - filtered by sample_filters
        for sample_id in adata.obs_names:
            # Skip samples that don't pass the filter
            if sample_filters and sample_id not in allowed_sample_ids:
                continue
            sample_row = adata.obs.loc[sample_id]
            
            row = {
                'column_name': sample_id,
                'type': 'double precision',
                'description': '',
                'format': '',
                'ismeta': False,
            }
            
            # Add sample metadata
            for obs_col, row_key in [
                ('tissue', 'tissue_col'),
                ('tissue', 'tissue_x_col'),
                ('tissue', 'tissue_type_col'),
                ('assigned', 'assigned_reads'),
                ('pct unmapped', 'pct_unmapped'),
                ('pct no_feature', 'pct_no_feature'),
                ('pct trimmed', 'pct_trimmed'),
            ]:
                if obs_col in adata.obs.columns:
                    val = sample_row.get(obs_col, None)
                    row[row_key] = float(val) if isinstance(val, (int, float)) and not pd.isna(val) else val
                else:
                    row[row_key] = None
            
            rows.append(row)
        
        # NOTE: Gene metadata columns (go_term, description, gene_name, ec_number,
        # description_long, interpro_term, pfam_term, is_tf, tf_family, orthogroup,
        # module_colors) are intentionally NOT included here.
        # They are accessible via the Data Manager / Inspect Data modal.
        
        df = pd.DataFrame(rows)
        return df.iloc[offset:offset + limit]
    
    def _filter_samples(
        self,
        adata: Any,
        sample_filters: Dict[str, Tuple[str, Any]]
    ) -> Set[str]:
        """Filter samples based on .obs metadata."""
        if not sample_filters:
            return set(adata.obs_names)
        
        obs_df = adata.obs.copy()
        
        for col in obs_df.columns:
            mapped_col = self._to_display_column_name(col)
            if mapped_col != col:
                obs_df[mapped_col] = obs_df[col]
        
        for col, filter_spec in sample_filters.items():
            pg_col = self._to_display_column_name(col)
            h5ad_col = self._to_h5ad_column_name(col)
            
            actual_col = None
            for candidate in [pg_col, h5ad_col, col]:
                if candidate in obs_df.columns:
                    actual_col = candidate
                    break
            
            if actual_col is None:
                continue
            
            if filter_spec is None or filter_spec == (None, None):
                obs_df = obs_df[obs_df[actual_col].isna() | (obs_df[actual_col] == '')]
                continue
            
            op, value = filter_spec
            
            if op == 'eq':
                if isinstance(value, bool):
                    obs_df = obs_df[obs_df[actual_col] == value]
                else:
                    obs_df = obs_df[obs_df[actual_col].astype(str) == str(value)]
            elif op == 'in':
                if isinstance(value, list):
                    obs_df = obs_df[obs_df[actual_col].astype(str).isin([str(v) for v in value])]
            elif op == 'range':
                min_val, max_val = value
                obs_df = obs_df[(obs_df[actual_col] >= min_val) & (obs_df[actual_col] <= max_val)]
        
        return set(obs_df.index)
    
    def _apply_filters(
        self,
        df: pd.DataFrame,
        filters: Dict[str, Tuple[str, Any]]
    ) -> pd.DataFrame:
        """Apply filters to DataFrame."""
        result = df.copy()
        logger.info(f"[_apply_filters] Applying filters: {filters}")
        logger.info(f"[_apply_filters] DataFrame columns: {list(df.columns)[:20]}...")
        logger.info(f"[_apply_filters] DataFrame shape before: {df.shape}")
        
        for col, filter_spec in filters.items():
            pg_col = self._to_display_column_name(col)
            h5ad_col = self._to_h5ad_column_name(col)
            
            actual_col = None
            for candidate in [pg_col, h5ad_col, col]:
                if candidate in result.columns:
                    actual_col = candidate
                    break
            
            logger.info(f"[_apply_filters] Filter col={col}, pg_col={pg_col}, h5ad_col={h5ad_col}, actual_col={actual_col}")
            
            if actual_col is None:
                logger.warning(f"[_apply_filters] Column '{col}' not found in DataFrame columns: {list(result.columns)[:10]}...")
                continue
            
            if filter_spec is None or filter_spec == (None, None):
                result = result[result[actual_col].isna() | (result[actual_col] == '')]
                continue
            
            op, value = filter_spec

            if op == 'eq':
                if isinstance(value, bool):
                    result = result[result[actual_col] == value]
                else:
                    # Strip whitespace from stored values before comparing
                    result = result[result[actual_col].astype(str).str.strip() == str(value).strip()]
            elif op == 'in':
                if isinstance(value, list):
                    # Strip whitespace from stored values before comparing
                    target_set = {str(v).strip() for v in value}
                    result = result[result[actual_col].astype(str).str.strip().isin(target_set)]
            elif op == 'range':
                min_val, max_val = value
                result = result[(result[actual_col] >= min_val) & (result[actual_col] <= max_val)]
            elif op in ('array_overlap', 'array_contains'):
                # Determine the intra-cell separator for this column from config,
                # falling back to the name-based heuristic used by get_unique_values.
                _col_defs = self.config_manager.get_column_definitions()
                _sep = (
                    _col_defs.get(pg_col, _col_defs.get(col, {})).get('array_separator')
                    or (
                        '|' if (pg_col or col).lower().endswith('desc')
                        else ','
                    )
                )

                def check_array(x, _sep=_sep, _op=op, _value=value):
                    if isinstance(x, (list, np.ndarray)):
                        items = list(x)
                    elif isinstance(x, str) and x:
                        items = [s.strip() for s in x.split(_sep) if s.strip()]
                    else:
                        return False

                    if _op == 'array_overlap':
                        return any(v in items for v in _value)
                    else:
                        return all(v in items for v in _value)

                result = result[result[actual_col].apply(check_array)]
        
        return result
    
    # =========================================================================
    # Public API - Aggregations
    # =========================================================================
    
    def get_row_count(
        self,
        table_name: str,
        filters: Optional[Dict[str, Tuple[str, Any]]] = None
    ) -> int:
        """Get row count with optional filtering."""
        species_code = self._normalize_table_name(table_name)
        adata = self.registry.load(species_code)
        
        if adata is None:
            return 0
        
        if not filters:
            return adata.n_vars
        
        df = pd.DataFrame({'gene_id': adata.var_names})
        for col in adata.var.columns:
            df[self._to_display_column_name(col)] = adata.var[col].values
        
        df = self._apply_filters(df, filters)
        return len(df)
    
    def get_column_bins(
        self,
        table_names: List[str],
        column_name: str,
        n_bins: int = 20
    ) -> List[Dict]:
        """Get histogram bins for a numeric column."""
        values = []
        h5ad_col = self._to_h5ad_column_name(column_name)
        
        for table_name in table_names:
            species_code = self._normalize_table_name(table_name)
            adata = self.registry.load(species_code)
            
            if adata is None:
                continue
            
            # Check .var
            if h5ad_col in adata.var.columns:
                col_values = pd.to_numeric(adata.var[h5ad_col], errors='coerce').dropna()
                values.extend(col_values.tolist())
            elif column_name in adata.var.columns:
                col_values = pd.to_numeric(adata.var[column_name], errors='coerce').dropna()
                values.extend(col_values.tolist())
            # Check .obs
            elif h5ad_col in adata.obs.columns:
                col_values = pd.to_numeric(adata.obs[h5ad_col], errors='coerce').dropna()
                values.extend(col_values.tolist())
            elif column_name in adata.obs.columns:
                col_values = pd.to_numeric(adata.obs[column_name], errors='coerce').dropna()
                values.extend(col_values.tolist())
            # Check if sample ID
            elif column_name in adata.obs_names:
                sample_idx = list(adata.obs_names).index(column_name)
                X = adata.X
                if hasattr(X, 'toarray'):
                    X = X.toarray()
                values.extend(X[sample_idx, :].flatten().tolist())
        
        if not values:
            return []
        
        values = np.array([v for v in values if v is not None and not np.isnan(v)])
        if len(values) == 0:
            return []
        
        hist, bin_edges = np.histogram(values, bins=n_bins)
        
        return [
            {
                'bucket_id': i,
                'bucket_lower': float(bin_edges[i]),
                'bucket_upper': float(bin_edges[i + 1]),
                'frequency': int(hist[i])
            }
            for i in range(len(hist))
        ]
    
    def precompute_global_bins(self, n_bins: int = 50) -> None:
        """Pre-compute merged histogram bins for all numeric columns across all enabled datasets.

        Scans every loaded species' .obs and .var for numeric columns, merges values
        across all datasets, and stores the result in ``_global_bins_cache``.
        Called at app startup and after every config/metadata change.
        """
        logger.info("Precomputing global histogram bins across all datasets...")
        all_species = self.get_available_species()
        if not all_species:
            logger.warning("No species available for global bin precomputation")
            return

        # Collect all numeric display column names across every species
        numeric_columns: Set[str] = set()
        for species_code in all_species:
            adata = self.registry.load(species_code)
            if adata is None:
                continue
            for col in adata.obs.columns:
                dtype = str(adata.obs[col].dtype)
                if self._get_column_type(dtype, col) in ('bigint', 'double precision'):
                    numeric_columns.add(self._to_display_column_name(col))
            for col in adata.var.columns:
                dtype = str(adata.var[col].dtype)
                if self._get_column_type(dtype, col) in ('bigint', 'double precision'):
                    numeric_columns.add(self._to_display_column_name(col))

        if not numeric_columns:
            logger.info("No numeric metadata columns found for global bin precomputation")
            return

        # _meta suffix is what get_column_bins expects (stripped internally)
        table_names_meta = [s + "_meta" for s in all_species]
        new_cache: Dict[str, List] = {}
        for col in numeric_columns:
            try:
                bins = self.get_column_bins(table_names_meta, col, n_bins)
                if bins:
                    new_cache[col] = bins
            except Exception as e:
                logger.warning(f"Failed to precompute global bins for column '{col}': {e}")

        self._global_bins_cache = new_cache  # Atomic replacement
        logger.info(
            f"Global bins precomputed for {len(new_cache)} of {len(numeric_columns)} numeric columns"
        )

    def get_global_column_bins(self, column_name: str, n_bins: int = 50) -> List[Dict]:
        """Return global (all-datasets merged) histogram bins from cache, or compute on demand.

        Falls back to on-demand computation if the background precompute hasn't run yet
        or if the column was not covered in the last precompute pass.
        """
        if column_name in self._global_bins_cache:
            return self._global_bins_cache[column_name]

        # On-demand fallback (e.g. precompute still running at startup)
        logger.debug(f"Global bins cache miss for '{column_name}', computing on demand")
        all_species = self.get_available_species()
        if not all_species:
            return []
        table_names_meta = [s + "_meta" for s in all_species]
        bins = self.get_column_bins(table_names_meta, column_name, n_bins)
        if bins:
            self._global_bins_cache[column_name] = bins
        return bins

    def get_unique_values(self, column_name: str) -> List[str]:
        """Get unique values for a column across all species."""
        if column_name in self._unique_values_cache:
            return self._unique_values_cache[column_name]
        
        h5ad_col = self._to_h5ad_column_name(column_name)
        values = set()
        
        # Determine whether to split stored strings and which delimiter to use.
        # Only split for array columns (is_array=True or type='array').
        # Plain text columns (like 'description') must NOT be split — their
        # values may legitimately contain commas.
        _col_defs = self.config_manager.get_column_definitions()
        col_def = _col_defs.get(column_name, {})
        is_array_col = col_def.get('is_array') or col_def.get('type') == 'array'
        delimiter = col_def.get('array_separator') if is_array_col else None
        if delimiter is None and is_array_col:
            # Fallback heuristic for array columns not yet in config
            delimiter = (
                '|' if (
                    column_name.lower().endswith('desc')
                    or column_name.lower().endswith('_desc')
                )
                else ','
            )
        
        for species_code in self.get_available_species():
            adata = self.registry.load(species_code)
            if adata is None:
                continue
            
            col = None
            if h5ad_col in adata.var.columns:
                col = adata.var[h5ad_col]
            elif column_name in adata.var.columns:
                col = adata.var[column_name]
            elif h5ad_col in adata.obs.columns:
                col = adata.obs[h5ad_col]
            elif column_name in adata.obs.columns:
                col = adata.obs[column_name]
            
            if col is None:
                continue
            
            for val in col.dropna():
                if isinstance(val, (list, np.ndarray)):
                    # Already a list/array - add each item
                    for v in val:
                        if v and str(v).strip():
                            values.add(str(v))
                elif val and str(val).strip():
                    val_str = str(val).strip()
                    # Only split multi-value strings for array columns
                    if delimiter and delimiter in val_str:
                        # Split by delimiter and add each part
                        parts = [p.strip() for p in val_str.split(delimiter) if p.strip()]
                        values.update(parts)
                    else:
                        values.add(val_str)
        
        result = sorted(values)
        self._unique_values_cache[column_name] = result
        return result
    
    def find_similar_values(self, column_name: str, search_term: str, limit: int = 10) -> List[Dict]:
        """Fuzzy search for similar values (case-insensitive)."""
        all_values = self.get_unique_values(column_name)
        
        if not all_values or not search_term:
            return []
        
        from rapidfuzz import fuzz, process
        
        # Case-insensitive substring matches always appear first
        term_lower = search_term.lower()
        exact_matches = [v for v in all_values if term_lower in v.lower()]
        exact_set = set(exact_matches)
        result_terms = exact_matches[:limit]

        # Fill remaining slots with fuzzy results not already included
        if len(result_terms) < limit:
            remaining = limit - len(result_terms)
            fuzzy_results = process.extract(
                search_term,
                all_values,
                limit=limit * 2,
                scorer=fuzz.WRatio,
            )
            for r in fuzzy_results:
                if r[0] not in exact_set:
                    result_terms.append(r[0])
                    exact_set.add(r[0])
                    if len(result_terms) >= limit:
                        break

        # Build similarity scores (1.0 for substring hits, fuzzy score for the rest)
        fuzzy_score_map = {
            r[0]: r[1] / 100.0
            for r in process.extract(search_term, result_terms, limit=len(result_terms), scorer=fuzz.WRatio)
        }
        return [
            {'term': t, 'similarity': fuzzy_score_map.get(t, 1.0 if t in exact_matches[:limit] else 0.0)}
            for t in result_terms
        ]
    
    def find_similar_tags(self, search_term: str, limit: int = 10) -> List[Dict]:
        """Fuzzy search for tags."""
        all_tags = set()
        for table in self.get_tables():
            all_tags.update(table.get('tags', []))
        
        if not all_tags or not search_term:
            return []
        
        from rapidfuzz import fuzz, process
        results = process.extract(search_term, list(all_tags), limit=limit, scorer=fuzz.WRatio)
        return [{'term': r[0], 'similarity': r[1] / 100.0} for r in results]
    
    # =========================================================================
    # Public API - Gene Trees & Filters
    # =========================================================================
    
    def get_gene_tree(self, og_id: str) -> Optional[str]:
        """Get Newick tree for an orthogroup."""
        return self.gene_trees.get(og_id)
    
    def store_filter(self, data: Dict) -> str:
        """Store filter configuration."""
        return self.filter_store.store(data)
    
    def get_filter(self, hash_id: str) -> Optional[Dict]:
        """Retrieve filter by hash ID."""
        return self.filter_store.get(hash_id)
    
    # =========================================================================
    # ORA (Over-Representation Analysis)
    # =========================================================================
    
    def calculate_ora(
        self,
        table_name: str,
        column_name: str,
        filters: List[Dict],
        significance: float = 0.01,
        top_n: int = 50,
        min_count: int = 3,
        column_type: str = 'array',
        topological_filter: bool = True,
        go_hierarchy = None,
        max_subset_size: int = 0,
        go_service = None
    ) -> Dict[str, Any]:
        """
        Calculate Over-Representation Analysis (ORA) for filtered gene set.
        
        Algorithm:
        1. Fetch subset genes (with filters applied)
        2. Fetch background genes (same species, no filters)
        3. For each attribute, count UNIQUE GENES (not occurrences) in both sets
        3b. (Optional) Apply topological filtering for GO terms - keep only most specific
        4. Run Fisher's Exact Test for each attribute
        5. Apply Benjamini-Hochberg FDR correction
        6. Calculate combined score: -log10(q_value) * (subset_count / background_count)
        7. Filter by significance threshold and min_count
        8. Sort by combined_score and return top N
        
        Args:
            table_name: Species table name
            column_name: Attribute column (e.g., 'orthogroup', 'go_term')
            filters: Filter list defining gene subset
            significance: FDR q-value threshold (default: 0.01)
            top_n: Maximum results to return (default: 50)
            min_count: Minimum genes in subset with attribute (default: 3)
            column_type: 'array' or 'text' (affects parsing)
            topological_filter: If True, filter GO terms to most specific (default: True)
            go_hierarchy: GOHierarchyHelper instance for topological filtering
        
        Returns:
            Dict with 'results' (list of enrichment entries) and 'metadata'
        """
        import scipy.stats as stats
        
        logger.info(f"ORA calculation: table={table_name}, column={column_name}, filters={len(filters)}")
        
        # Quick count check to avoid expensive computation on large subsets
        if max_subset_size > 0:
            row_count = self.get_row_count(table_name, filters)
            if row_count == 0 or row_count > max_subset_size:
                return {
                    'results': [],
                    'metadata': {
                        'subset_size': row_count,
                        'background_size': 0,
                        'total_tests': 0,
                        'significant_count': 0,
                        'column_type': column_type,
                        'message': 'No genes in filtered subset' if row_count == 0 else f'Subset too large ({row_count} > {max_subset_size})',
                        'count': row_count
                    }
                }
        
        # Check if this is GO term enrichment
        is_go_enrichment = 'go' in column_name.lower() or column_name.lower() == 'go_term'
        apply_topo_filter = topological_filter and is_go_enrichment and go_hierarchy is not None
        
        if apply_topo_filter:
            logger.info("Topological filtering enabled for GO term enrichment")
        
        # Determine columns to fetch: target column + all filter columns
        columns_to_fetch = [column_name]
        if filters:
            columns_to_fetch.extend(filters.keys())
        columns_to_fetch = list(set(columns_to_fetch))  # Deduplicate
        
        # 1. Get subset data (filtered genes) — no virtual columns needed for ORA
        subset_df, _ = self.get_data(
            table_name=table_name,
            columns=columns_to_fetch,
            filters=filters,
            limit=None,
            include_virtual_columns=False
        )
        
        if subset_df.empty:
            return {
                'results': [],
                'metadata': {
                    'subset_size': 0,
                    'background_size': 0,
                    'total_tests': 0,
                    'significant_count': 0,
                    'column_type': column_type,
                    'message': 'No genes in filtered subset',
                    'count': 0
                }
            }
        
        # 2. Get background data (all genes in species, no filters) — with caching
        species_code = self._normalize_table_name(table_name)
        cache_key = (species_code, column_name)
        if cache_key in self._ora_background_cache:
            background_df = self._ora_background_cache[cache_key]
        else:
            background_df, _ = self.get_data(
                table_name=table_name,
                columns=[column_name],
                filters={},  # Empty dict = no filters = all genes in species
                limit=None,
                include_virtual_columns=False
            )
            self._ora_background_cache[cache_key] = background_df
        
        if background_df.empty:
            raise ValueError("Background dataset is empty")
        
        subset_size = len(subset_df)
        background_size = len(background_df)
        
        logger.info(f"ORA: subset_size={subset_size}, background_size={background_size}")
        
        # 3. Build attribute -> gene index mappings
        def build_gene_attribute_map(df: pd.DataFrame, col: str, apply_filter: bool = False) -> tuple:
            """
            Map each attribute to set of gene indices that contain it.
            
            Returns:
                Tuple of (attr_to_genes dict, removed_parents dict if filtering, else empty dict)
            """
            attr_to_genes = {}
            removed_parents_per_gene = {}  # gene_idx -> list of removed parent GO IDs
            
            for gene_idx, row in df.iterrows():
                value = row[col]
                
                # Handle different value types
                if pd.isna(value):
                    continue
                
                if isinstance(value, list):
                    # Array column: each element is an attribute
                    attributes = [str(v).strip() for v in value if v and str(v).strip()]
                elif isinstance(value, str):
                    if column_type == 'array':
                        # Text column that should be split (comma/pipe delimited)
                        if ',' in value:
                            attributes = [v.strip() for v in value.split(',') if v.strip()]
                        elif '|' in value:
                            attributes = [v.strip() for v in value.split('|') if v.strip()]
                        else:
                            attributes = [value.strip()]
                    else:
                        # Simple text column: single attribute
                        attributes = [value.strip()]
                else:
                    # Numeric or other: convert to string
                    attributes = [str(value)]
                
                # Apply topological filtering if enabled (only for GO terms)
                if apply_filter and go_hierarchy and attributes:
                    filtered_attrs, removed = go_hierarchy.filter_to_most_specific(attributes)
                    if removed:
                        removed_parents_per_gene[gene_idx] = removed
                    attributes = filtered_attrs
                
                # Add gene to each attribute's set
                for attr in attributes:
                    if attr not in attr_to_genes:
                        attr_to_genes[attr] = set()
                    attr_to_genes[attr].add(gene_idx)
            
            return attr_to_genes, removed_parents_per_gene
        
        subset_map, subset_removed = build_gene_attribute_map(subset_df, column_name, apply_filter=apply_topo_filter)
        background_map, _ = build_gene_attribute_map(background_df, column_name, apply_filter=apply_topo_filter)
        
        # Track which parent terms were filtered out (for display in frontend)
        filtered_parent_counts = {}
        if apply_topo_filter and subset_removed:
            for removed_list in subset_removed.values():
                for parent_id in removed_list:
                    filtered_parent_counts[parent_id] = filtered_parent_counts.get(parent_id, 0) + 1
            logger.info(f"Topological filtering removed {len(filtered_parent_counts)} unique parent GO terms")
        
        # 4. Calculate Fisher's Exact Test for each attribute
        all_attributes = set(subset_map.keys()) | set(background_map.keys())
        
        logger.info(f"ORA: Testing {len(all_attributes)} unique attributes")
        
        ora_results = []
        for attr in all_attributes:
            # Count unique genes with this attribute
            genes_in_subset_with_attr = subset_map.get(attr, set())
            genes_in_background_with_attr = background_map.get(attr, set())
            
            a = len(genes_in_subset_with_attr)  # Subset genes WITH attribute
            c = len(genes_in_background_with_attr - genes_in_subset_with_attr)  # Background genes WITH attr (excl. subset)
            b = subset_size - a  # Subset genes WITHOUT attribute
            d = background_size - (a + b + c)  # Background genes WITHOUT attribute and not in subset
            
            # Validate contingency table
            if a < 0 or b < 0 or c < 0 or d < 0:
                logger.warning(f"Invalid contingency table for {attr}: a={a}, b={b}, c={c}, d={d}")
                continue
            
            # Skip if below minimum count threshold
            if a < min_count:
                continue
            
            # Fisher's Exact Test (one-sided, testing for enrichment)
            odds_ratio, p_value = stats.fisher_exact([[a, b], [c, d]], alternative='greater')
            
            # Calculate gene ratio
            total_genes_with_attr = a + c
            gene_ratio = a / total_genes_with_attr if total_genes_with_attr > 0 else 0
            
            # Calculate expected count: expected number of genes in subset with this attribute
            # Under null hypothesis of random distribution
            expected_count = (total_genes_with_attr / background_size) * subset_size if background_size > 0 else 0
            
            # Calculate fold enrichment: (observed_ratio / expected_ratio)
            # This represents how many times more enriched the term is vs random expectation
            observed_ratio = a / subset_size if subset_size > 0 else 0
            expected_ratio = total_genes_with_attr / background_size if background_size > 0 else 0
            fold_enrichment = observed_ratio / expected_ratio if expected_ratio > 0 else 0
            
            # Handle Infinity odds ratio (occurs when c=0, i.e., no background genes without the attribute)
            # JSON doesn't support Infinity, so convert to None
            if np.isinf(odds_ratio):
                odds_ratio = None
            
            ora_results.append({
                'attribute': attr,
                'subset_count': a,
                'background_count': total_genes_with_attr,
                'subset_size': subset_size,
                'background_size': background_size,
                'gene_ratio': gene_ratio,
                'p_value': p_value,
                'odds_ratio': odds_ratio,
                'expected_count': expected_count,
                'fold_enrichment': fold_enrichment
            })
        
        if not ora_results:
            return {
                'results': [],
                'metadata': {
                    'subset_size': subset_size,
                    'background_size': background_size,
                    'total_tests': len(all_attributes),
                    'significant_count': 0,
                    'column_type': column_type,
                    'message': f'No attributes passed min_count threshold (>={min_count})'
                }
            }
        
        # 5. Benjamini-Hochberg FDR correction
        ora_results.sort(key=lambda x: x['p_value'])
        n_tests = len(ora_results)
        
        for rank, result in enumerate(ora_results, start=1):
            # BH correction: q_value = p_value * n_tests / rank
            q_value = result['p_value'] * n_tests / rank
            result['q_value'] = min(q_value, 1.0)
        
        # Ensure monotonicity (q-values should not decrease)
        for i in range(n_tests - 2, -1, -1):
            ora_results[i]['q_value'] = min(ora_results[i]['q_value'], ora_results[i + 1]['q_value'])
        
        # 6. Calculate combined score: -log10(q_value) * gene_ratio
        #    Similar to Enrichr's combined score but simplified
        for result in ora_results:
            q_val = result['q_value']
            if q_val > 0:
                # Combined score: significance × effect size
                result['combined_score'] = -np.log10(q_val) * result['gene_ratio']
            else:
                # Handle q_value = 0 (extremely significant)
                result['combined_score'] = 300.0 * result['gene_ratio']  # Cap at log10(1e-300)
        
        # 7. Filter by significance threshold
        significant_results = [r for r in ora_results if r['q_value'] < significance]
        
        logger.info(f"ORA: {len(significant_results)}/{n_tests} significant (q < {significance})")
        
        # 8. Sort by combined score (descending) and take top N
        significant_results.sort(key=lambda x: x['combined_score'], reverse=True)
        top_results = significant_results[:top_n]
        
        # Build metadata
        metadata = {
            'subset_size': subset_size,
            'background_size': background_size,
            'total_tests': n_tests,
            'significant_count': len(significant_results),
            'column_type': column_type,
            'filters_applied': len(filters),
            'significance_threshold': significance,
            'min_count_threshold': min_count,
            'top_n': top_n,
            'topological_filter_applied': apply_topo_filter,
            'count': subset_size,
        }
        
        # Add filtered parents info if topological filtering was applied
        if apply_topo_filter and filtered_parent_counts:
            metadata['filtered_parent_count'] = len(filtered_parent_counts)
            # Include the top filtered parent terms (by frequency)
            top_filtered = sorted(filtered_parent_counts.items(), key=lambda x: x[1], reverse=True)[:20]
            metadata['filtered_parents_sample'] = [p[0] for p in top_filtered]
        
        # Inline GO term details if go_service is available
        go_terms = {}
        is_go = 'go' in column_name.lower() or column_name.lower() == 'go_term'
        if is_go and go_service and hasattr(go_service, 'get_term') and go_service.is_available():
            for entry in top_results:
                go_id = entry.get('attribute', '')
                term = go_service.get_term(go_id)
                if term:
                    if go_hierarchy:
                        term['depth'] = go_hierarchy.get_depth(go_id)
                    go_terms[go_id] = term
        
        result = {
            'results': top_results,
            'metadata': metadata
        }
        if go_terms:
            result['go_terms'] = go_terms
        
        return result

    def perform_clustering(
        self,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None,
        sample_filters: Optional[Dict[str, Any]] = None,
        layer: Optional[str] = None,
        transform: str = 'zscore',
        cluster_rows: bool = True,
        cluster_cols: bool = True,
        method: str = 'average',
        distance: str = 'correlation'
    ) -> Dict[str, Any]:
        """
        Perform hierarchical clustering on expression data.
        
        Args:
            table_name: Name of the table (species)
            filters: Row filters (genes/transcripts)
            sample_filters: Column filters (samples)
            layer: Expression layer to use (tpm, tmm, getmm, etc.)
            transform: Transform to apply ('raw', 'log2', 'zscore')
            cluster_rows: Whether to cluster rows
            cluster_cols: Whether to cluster columns  
            method: Linkage method ('average', 'complete', 'ward')
            distance: Distance metric ('correlation', 'euclidean')
            
        Returns:
            Dict with row_order and col_order (0-indexed permutation arrays)
        """
        from scipy.cluster.hierarchy import linkage, leaves_list, optimal_leaf_ordering
        from scipy.spatial.distance import pdist, squareform
        
        try:
            # Normalize table name and load adata
            species_code = self._normalize_table_name(table_name)
            adata = self.registry.load(species_code)
            if adata is None:
                raise ValueError(f"Unknown table: {table_name}")
            
            # Select optimal layer
            actual_layer, reasoning = select_optimal_layer(adata, transform, layer)
            
            # Get expression matrix with transform
            if actual_layer == 'X' or actual_layer == 'raw':
                expr_matrix = adata.X
            elif actual_layer in adata.layers:
                expr_matrix = adata.layers[actual_layer]
            else:
                expr_matrix = adata.X
            
            # Convert to dense if sparse
            if hasattr(expr_matrix, 'toarray'):
                expr_matrix = expr_matrix.toarray()
            
            # expr_df shape: (n_obs/samples × n_var/genes)
            # In the heatmap: rows = genes (var), cols = samples (obs)
            # → filters     = gene filters  → filter adata.var → filter columns of expr_df
            # → sample_filters = sample filters → filter adata.obs → filter rows of expr_df
            expr_df = pd.DataFrame(
                expr_matrix,
                index=adata.obs_names,    # rows = samples
                columns=adata.var_names   # cols = genes
            )

            # Apply gene filters via _apply_filters on adata.var
            # filters are already in (op, val) tuple format from parse_filters()
            if filters:
                filtered_var = self._apply_filters(adata.var.copy(), filters)
                expr_df = expr_df.loc[:, filtered_var.index]

            # Apply sample filters via _apply_filters on adata.obs
            if sample_filters:
                filtered_obs = self._apply_filters(adata.obs.copy(), sample_filters)
                expr_df = expr_df.loc[filtered_obs.index, :]

            n_genes   = len(expr_df.columns)   # heatmap rows
            n_samples = len(expr_df.index)      # heatmap cols

            # Apply transform (normalize per gene across samples)
            if transform == 'log2':
                expr_df = np.log2(expr_df + 1)
            elif transform == 'zscore':
                expr_df = np.log2(expr_df + 1)
                # z-score each gene (column) across samples (rows)
                means = expr_df.mean(axis=0)
                stds  = expr_df.std(axis=0)
                expr_df = (expr_df - means) / (stds + 1e-10)

            result = {
                'row_order': None,
                'col_order': None,
                'metadata': {
                    'n_rows': n_genes,
                    'n_cols': n_samples,
                    'method': method,
                    'distance': distance,
                    'layer_used': actual_layer,
                    'transform': transform
                }
            }

            # Map method / distance names for scipy
            linkage_method = 'average' if method == 'average' else method
            dist_metric    = 'correlation' if distance == 'correlation' else 'euclidean'

            # optimal_leaf_ordering is O(n³) — skip for large n to avoid OOM/timeout
            OLO_THRESHOLD = 300

            # cluster_rows → cluster genes (heatmap rows = var dimension = columns of expr_df)
            # → use transposed matrix: shape (n_genes × n_samples)
            if cluster_rows and n_genes > 1:
                try:
                    gene_data = np.nan_to_num(expr_df.values.T, nan=0.0, posinf=0.0, neginf=0.0)
                    row_dist    = pdist(gene_data, metric=dist_metric)
                    row_linkage = linkage(row_dist, method=linkage_method)
                    if n_genes <= OLO_THRESHOLD:
                        row_linkage = optimal_leaf_ordering(row_linkage, row_dist)
                    result['row_order'] = leaves_list(row_linkage).tolist()
                except Exception as e:
                    logger.warning(f"Row (gene) clustering failed: {e}")

            # cluster_cols → cluster samples (heatmap cols = obs dimension = rows of expr_df)
            # → use matrix as-is: shape (n_samples × n_genes)
            if cluster_cols and n_samples > 1:
                try:
                    sample_data = np.nan_to_num(expr_df.values, nan=0.0, posinf=0.0, neginf=0.0)
                    col_dist    = pdist(sample_data, metric=dist_metric)
                    col_linkage = linkage(col_dist, method=linkage_method)
                    if n_samples <= OLO_THRESHOLD:
                        col_linkage = optimal_leaf_ordering(col_linkage, col_dist)
                    result['col_order'] = leaves_list(col_linkage).tolist()
                except Exception as e:
                    logger.warning(f"Col (sample) clustering failed: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Clustering error: {e}", exc_info=True)
            raise
