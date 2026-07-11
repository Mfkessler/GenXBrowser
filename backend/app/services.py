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

try:
    from . import filter_parser
except ImportError:  # pragma: no cover - supports direct module loading in tests
    import importlib.util

    _filter_parser_path = Path(__file__).resolve().parent / "filter_parser.py"
    _filter_parser_spec = importlib.util.spec_from_file_location("genxbrowser_filter_parser", _filter_parser_path)
    assert _filter_parser_spec is not None and _filter_parser_spec.loader is not None
    filter_parser = importlib.util.module_from_spec(_filter_parser_spec)
    _filter_parser_spec.loader.exec_module(filter_parser)

logger = logging.getLogger(__name__)

VIRTUAL_GENE_COLUMNS = {'newick_str', 'protein_seq', 'rna_seq'}


# ============================================================================
# Species Photo Utilities
# ============================================================================

def fuzzy_match_photo(species_name: str, photo_files: List[str]) -> Optional[str]:
    """
    Match species name to photo filename using sequence-aware fuzzy matching.

    Algorithm:
    1. Normalize both species name and filenames (lowercase, strip extension,
       replace separators with spaces to get word tokens).
    2. Require ALL words of the binomial name to appear as substrings in the
       photo stem — if both words match, the file is a strong candidate.
    3. Among all candidates also compute a SequenceMatcher ratio and require
       it to be >= 0.80 to avoid false positives.

    Args:
        species_name: Species display name (e.g., 'Aquilegia coerulea')
        photo_files: List of photo filenames in the photos directory.

    Returns:
        Best-matching filename, or None if no confident match is found.
    """
    from difflib import SequenceMatcher

    def normalize(s: str) -> str:
        """Lowercase, strip extension, replace separators with space, keep alnum+space."""
        s = s.lower()
        s = re.sub(r'\.[^.]+$', '', s)          # strip extension
        s = re.sub(r'[_\-]+', ' ', s)           # separators → space
        s = re.sub(r'[^a-z0-9 ]', '', s)        # keep alnum + space
        return s.strip()

    normalized_species = normalize(species_name)
    species_words = normalized_species.split()

    if not species_words:
        return None

    best_match = None
    best_score = 0.0

    for photo_file in photo_files:
        normalized_photo = normalize(photo_file)

        # All words of the species name must appear as substrings in the photo stem
        if not all(w in normalized_photo for w in species_words):
            continue

        # Sequence-aware similarity (order-sensitive)
        score = SequenceMatcher(None, normalized_species, normalized_photo).ratio()

        if score > best_score:
            best_score = score
            best_match = photo_file

    # Only return a match when similarity is high (>= 0.80)
    if best_score >= 0.80:
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
    """Loads and caches FASTA sequences for genes.

    Sequence files are discovered by scanning the directory at initialisation
    time.  The filename is parsed as follows:

        <species_code><separator><type_label>[.<ext>]

    where separator is any run of dots or underscores that separates the
    species code prefix from the remainder of the stem, and type_label is
    matched case-insensitively against two keyword sets:
        protein  - 'protein', 'proteins', 'prot', 'pep', 'aa'
        RNA      - 'rna', 'transcript', 'transcripts', 'mrna', 'cdna', 'cds', 'nucl', 'mrna'

    This handles all observed naming conventions across projects:
        AT.protein.fas
        AT.RNA.fas
        AT_proteins.faa 
        AT_transcripts.fa
    """

    _FASTA_SUFFIXES: frozenset = frozenset({'.fas', '.fa', '.faa', '.fasta', '.fna'})
    _PROTEIN_KEYWORDS: frozenset = frozenset({'protein', 'proteins', 'prot', 'pep', 'aa'})
    _RNA_KEYWORDS: frozenset = frozenset({'rna', 'transcript', 'transcripts', 'mrna', 'cdna', 'cds', 'nucl'})

    def __init__(self, sequences_dir: str):
        self._sequences_dir = Path(sequences_dir)
        self._cache: Dict[str, Dict[str, str]] = {}
        # index: {species_code: {'protein': Path, 'RNA': Path}}
        self._index: Dict[str, Dict[str, Path]] = self._build_index()

    def _build_index(self) -> Dict[str, Dict[str, Path]]:
        """Scan sequences_dir and build a lookup index keyed by species code and sequence type."""
        index: Dict[str, Dict[str, Path]] = {}

        if not self._sequences_dir.exists():
            logger.warning(f"Sequences directory not found: {self._sequences_dir}")
            return index

        for path in self._sequences_dir.iterdir():
            if not path.is_file():
                continue
            # Collect multi-part suffixes like .protein.fas → suffix is the last part only
            # Use the full stem (everything before the last dot-extension) for parsing
            suffix = path.suffix.lower()
            if suffix not in self._FASTA_SUFFIXES:
                continue

            # Strip the recognised file extension to get the full stem
            stem = path.stem  # e.g. "AT.protein", "AT_proteins", "AT.RNA"

            # Split stem on the first dot or underscore to separate species code from type label
            parts = re.split(r'[._]', stem, maxsplit=1)
            if len(parts) != 2:
                logger.debug(f"Skipping sequence file with unexpected name format: {path.name}")
                continue

            code, type_label = parts[0], parts[1].lower()

            if type_label in self._PROTEIN_KEYWORDS:
                seq_type = 'protein'
            elif type_label in self._RNA_KEYWORDS:
                seq_type = 'RNA'
            else:
                logger.debug(f"Skipping sequence file with unrecognised type label '{type_label}': {path.name}")
                continue

            index.setdefault(code, {})[seq_type] = path

        if index:
            summary = ', '.join(
                f"{code}:[{','.join(sorted(types))}]" for code, types in sorted(index.items())
            )
            logger.info(f"SequenceStore: indexed {len(index)} species — {summary}")
        else:
            logger.warning(f"SequenceStore: no sequence files found in {self._sequences_dir}")

        return index

    def _resolve_fasta_path(self, species_code: str, seq_type: str) -> Optional[Path]:
        """Return the indexed FASTA path for a species code and sequence type, or None."""
        return self._index.get(species_code, {}).get(seq_type)

    def _load_fasta(self, file_path: Optional[Path]) -> Dict[str, str]:
        """Load a FASTA file and return a mapping of sequence ID to sequence string."""
        sequences: Dict[str, str] = {}

        if file_path is None:
            return sequences

        if not file_path.exists():
            logger.warning(f"FASTA file not found: {file_path}")
            return sequences

        current_id = None
        current_seq: list = []

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
        """Return the protein sequence for a gene, or an empty string if unavailable."""
        cache_key = f"{species_code}_protein"

        if cache_key not in self._cache:
            fasta_file = self._resolve_fasta_path(species_code, 'protein')
            if fasta_file is None:
                logger.warning(f"No protein sequence file indexed for species '{species_code}'")
            self._cache[cache_key] = self._load_fasta(fasta_file)
            logger.info(f"Loaded {len(self._cache[cache_key])} protein sequences for {species_code}")

        return self._cache[cache_key].get(gene_id, '')

    def get_rna_seq(self, species_code: str, gene_id: str) -> str:
        """Return the RNA/transcript sequence for a gene, or an empty string if unavailable."""
        cache_key = f"{species_code}_RNA"

        if cache_key not in self._cache:
            fasta_file = self._resolve_fasta_path(species_code, 'RNA')
            if fasta_file is None:
                logger.warning(f"No RNA sequence file indexed for species '{species_code}'")
            self._cache[cache_key] = self._load_fasta(fasta_file)
            logger.info(f"Loaded {len(self._cache[cache_key])} RNA sequences for {species_code}")

        return self._cache[cache_key].get(gene_id, '')


class GeneTreeStore:
    """Stores and retrieves Newick gene trees by orthogroup ID."""
    
    def __init__(self, path: str):
        self._trees: Dict[str, str] = {}
        self._tree_key_lookup: Dict[str, str] = {}
        self._load(path)
    
    def _load(self, path: str) -> None:
        if not Path(path).exists():
            logger.warning(f"Gene trees file not found: {path}")
            return
        
        logger.info(f"Loading gene trees from {path}")

        # Pre-compiled regex to strip duplicated species prefixes in leaf labels.
        # Some pipelines (e.g. OrthoFinder with full-name prefixes) produce IDs like:
        #   Thalictrum_thalictroides_Thalictrum_thalictroides_evm.model.ptg000008l.2819
        # but the h5ad gene IDs (matching Orthogroups.tsv) are:
        #   Thalictrum_thalictroides_evm.model.ptg000008l.2819
        # The pattern [A-Z][a-z]+_[a-z]+ matches a two-word binomial species name;
        # if it appears twice consecutively the second copy is stripped.
        _dup_prefix_re = re.compile(r'([A-Z][a-z]+_[a-z]+)_\1_')
        
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or ':' not in line:
                    continue
                
                parts = line.split(':', 1)
                if len(parts) == 2:
                    og_id = parts[0].strip()
                    newick = parts[1].strip()
                    # Strip duplicated species prefixes if present
                    newick = _dup_prefix_re.sub(r'\1_', newick)
                    self._trees[og_id] = newick
                    self._tree_key_lookup.setdefault(og_id.lower(), og_id)
        
        logger.info(f"Loaded {len(self._trees)} gene trees")
    
    def get(self, og_id: str) -> Optional[str]:
        normalized = str(og_id or '').strip()
        if not normalized:
            return None
        direct = self._trees.get(normalized)
        if direct is not None:
            return direct
        canonical = self._tree_key_lookup.get(normalized.lower())
        return self._trees.get(canonical) if canonical else None


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

        # Custom metadata column overlays — values applied to each AnnData on load
        # so that admin-imported columns stay available even after cache eviction /
        # config reload, without requiring persistence to the .h5ad file.
        self._custom_overlays_path = (
            Path(self.config_manager.config_path).parent / 'custom_overlays.json'
        )
        self._custom_overlays: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._load_custom_overlays()
        # Register post-load transform so every loaded AnnData gets overlays applied
        self.registry.transform_fn = self._apply_custom_overlays

        # Register species from config
        self._register_species_from_config()
        
        # GenXBrowser-specific stores
        self.gene_trees = GeneTreeStore(self.config['gene_trees_path'])
        self.sequences = SequenceStore(self.config['sequences_dir'])
        self.filter_store = self._build_filter_store(self.config['filter_store_path'])
        
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
        h5ad_dir = os.environ.get('H5AD_DATA_DIR', '/data/prepared')
        # Default the share-ID store under the data dir so local/dev installs
        # don't try to write to the root-owned /data/filters. Matches the
        # behaviour documented in README.md.
        default_filter_store = os.path.join(h5ad_dir, 'filters')
        return {
            'h5ad_dir': h5ad_dir,
            'gene_trees_path': os.environ.get('GENE_TREES_PATH', '/data/Metadata/Resolved_Gene_Trees.txt'),
            'sequences_dir': os.environ.get('SEQUENCES_DIR', '/data/Metadata/fas'),
            'filter_store_path': os.environ.get('FILTER_STORE_PATH', default_filter_store),
            'cache_max_size_mb': int(os.environ.get('CACHE_MAX_SIZE_MB', '2048')),
        }

    @staticmethod
    def _build_filter_store(path: str) -> FilterStore:
        """Construct the share-ID FilterStore, falling back to a tempdir
        when the configured path is not writable. Avoids hard-failing deep-link
        creation (and the AI assistant) on mis-configured installs where the
        default `/data/filters` is root-owned or doesn't exist."""
        import tempfile
        try:
            store = FilterStore(path=path)
            # Probe writability with a throwaway entry so we fail loudly here
            # rather than later during an assistant tool call.
            probe_path = Path(path) / ".write_probe"
            probe_path.write_text("ok")
            probe_path.unlink(missing_ok=True)
            return store
        except (PermissionError, OSError) as e:
            fallback = os.path.join(tempfile.gettempdir(), "genxbrowser_filters")
            logger.warning(
                "FilterStore path %r not writable (%s); falling back to %r. "
                "Set FILTER_STORE_PATH to a writable directory to silence this warning.",
                path, e, fallback,
            )
            return FilterStore(path=fallback)
    
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
    
    # =========================================================================
    # Custom Metadata Overlays
    # =========================================================================
    #
    # An "overlay" is a column that the admin added at runtime (see
    # admin_routes.confirm_metadata_import). Overlays are stored in a sidecar
    # JSON file next to the main config and applied to each AnnData right after
    # load via ``self.registry.transform_fn``.  This ensures admin-imported
    # columns remain available after cache eviction, reload_config, or full
    # backend restarts — even when the admin chose not to persist to the .h5ad
    # file on disk.

    def _load_custom_overlays(self) -> None:
        """Load custom metadata overlays from disk, if present."""
        try:
            if self._custom_overlays_path.exists():
                import json
                with open(self._custom_overlays_path, 'r') as fh:
                    raw = json.load(fh)
                if isinstance(raw, dict):
                    self._custom_overlays = {
                        str(species): {
                            str(col): dict(entry)
                            for col, entry in cols.items()
                        }
                        for species, cols in raw.items()
                        if isinstance(cols, dict)
                    }
                    logger.info(
                        f"Loaded custom metadata overlays for {len(self._custom_overlays)} species"
                    )
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Failed to load custom overlays: {e}")
            self._custom_overlays = {}

    def _save_custom_overlays(self) -> None:
        """Persist custom metadata overlays to disk."""
        try:
            import json
            self._custom_overlays_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._custom_overlays_path, 'w') as fh:
                json.dump(self._custom_overlays, fh)
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Failed to save custom overlays: {e}")

    def _apply_custom_overlays(self, adata: Any, species_code: str) -> Any:
        """Apply registered overlay columns to an AnnData instance."""
        overlays = self._custom_overlays.get(species_code)
        if not overlays:
            return adata
        for column_name, entry in overlays.items():
            try:
                target = entry.get('target', 'obs')
                values = entry.get('values', {}) or {}
                dtype = entry.get('dtype', 'text')
                axis_df = adata.var if target == 'var' else adata.obs
                series = self._build_overlay_series(axis_df.index, values, dtype)
                axis_df[column_name] = series
            except Exception as e:
                logger.warning(
                    f"Failed to apply overlay '{column_name}' on {species_code}: {e}"
                )
        return adata

    @staticmethod
    def _build_overlay_series(index: Any, values: Dict[str, Any], dtype: str) -> pd.Series:
        """Build a pandas Series aligned to ``index`` from a dict of id->value."""
        default: Any
        if dtype == 'bigint' or dtype == 'double precision':
            default = np.nan
        elif dtype == 'boolean':
            default = False
        else:
            default = ''
        data = []
        for idx in index.astype(str):
            if idx in values:
                raw = values[idx]
                try:
                    if dtype == 'bigint':
                        data.append(int(float(raw)) if raw not in (None, '', 'nan') else default)
                    elif dtype == 'double precision':
                        data.append(float(raw) if raw not in (None, '', 'nan') else default)
                    elif dtype == 'boolean':
                        if isinstance(raw, bool):
                            data.append(raw)
                        else:
                            data.append(str(raw).strip().lower() in ('true', '1', 'yes'))
                    else:
                        data.append('' if raw is None else str(raw))
                except (TypeError, ValueError):
                    data.append(default)
            else:
                data.append(default)
        return pd.Series(data, index=index)

    def register_custom_overlay(
        self,
        species_code: str,
        column_name: str,
        target: str,
        values: Dict[str, Any],
        dtype: str,
    ) -> None:
        """Register a runtime metadata overlay for a species.

        Args:
            species_code: Species code the overlay applies to.
            column_name: Name of the overlay column.
            target: ``"var"`` for gene metadata, ``"obs"`` for sample metadata.
            values: Mapping of id -> raw value.
            dtype: One of ``text``, ``bigint``, ``double precision``, ``boolean``.
        """
        if target not in ('var', 'obs'):
            raise ValueError(f"Invalid overlay target '{target}' (expected 'var' or 'obs')")
        species_entry = self._custom_overlays.setdefault(species_code, {})
        species_entry[column_name] = {
            'target': target,
            'dtype': dtype,
            'values': {str(k): v for k, v in values.items()},
        }
        self._save_custom_overlays()
        # Re-apply immediately to cached adata so the column is usable without
        # waiting for a cache eviction.
        adata = self.registry._cache.get(species_code) if hasattr(self.registry, '_cache') else None
        if adata is not None:
            try:
                axis_df = adata.var if target == 'var' else adata.obs
                series = self._build_overlay_series(axis_df.index, values, dtype)
                axis_df[column_name] = series
            except Exception as e:
                logger.warning(
                    f"Failed to apply overlay '{column_name}' on cached {species_code}: {e}"
                )

    def unregister_custom_overlay(self, column_name: str) -> None:
        """Remove an overlay column from all species."""
        changed = False
        for species_code in list(self._custom_overlays.keys()):
            cols = self._custom_overlays[species_code]
            if column_name in cols:
                del cols[column_name]
                changed = True
            if not cols:
                del self._custom_overlays[species_code]
        if changed:
            self._save_custom_overlays()

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

    def _resolve_axis_column(self, axis, column_name: str) -> Optional[str]:
        """Resolve a configured column name to the actual AnnData axis column.

        Handles the common case where H5AD columns use spaces (e.g. ``pct unmapped``)
        while config keys normalise those to underscores (``pct_unmapped``).  Both
        sides are lowercased and spaces/underscores are collapsed to underscores for
        the comparison, but the *actual* column name present in the axis is returned
        so downstream ``adata.obs[actual]`` lookups work correctly.
        """
        h5ad_col = self._to_h5ad_column_name(column_name)
        for candidate in (h5ad_col, column_name):
            if candidate in axis.columns:
                return candidate
        # Fallback: normalise spaces ↔ underscores (case-insensitive)
        normalised = column_name.lower().replace(' ', '_')
        for actual_col in axis.columns:
            if actual_col.lower().replace(' ', '_') == normalised:
                return actual_col
        return None

    def _get_configured_metadata_columns(
        self,
        adata: Any,
        *,
        sample_metadata: bool,
    ) -> List[Dict[str, Any]]:
        """Return visible metadata columns backed by the current config."""
        column_defs = self.config_manager.get_column_definitions()
        configured_columns: List[Dict[str, Any]] = []
        default_trait_column = self.config_manager.get_config().get('default_trait_column')

        for column_name, col_def in column_defs.items():
            if not col_def.get('visible', True):
                continue

            if sample_metadata:
                if not col_def.get('is_sample_metadata', False):
                    continue
                actual_col = self._resolve_axis_column(adata.obs, column_name)
                if actual_col is None:
                    continue
                dtype = str(adata.obs[actual_col].dtype)
            else:
                if col_def.get('is_sample_metadata', False) or not col_def.get('is_meta', False):
                    continue
                actual_col = self._resolve_axis_column(adata.var, column_name)
                if actual_col is None and column_name not in VIRTUAL_GENE_COLUMNS:
                    continue
                dtype = str(adata.var[actual_col].dtype) if actual_col is not None else 'object'

            configured_columns.append({
                'column_name': column_name,
                'display_name': col_def.get('display_name', column_name),
                'actual_name': actual_col,
                'type': col_def.get('type') or self._get_column_type(dtype, actual_col or column_name),
                'order': col_def.get('order', 9999),
                'is_default_trait': sample_metadata and column_name == default_trait_column,
            })

        configured_columns.sort(key=lambda item: (item['order'], item['column_name']))
        return configured_columns
    
    # =========================================================================
    # Column Name Mapping
    # =========================================================================
    
    def _to_display_column_name(self, h5ad_name: str) -> str:
        """Normalize column name for display (identity: h5ad names are the standard)."""
        if h5ad_name in self._column_mappings:
            return self._column_mappings[h5ad_name]
        return h5ad_name
    
    def _to_h5ad_column_name(self, display_name: str) -> str:
        """Convert display column name to H5AD column name (identity: names match)."""
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
            
            default_trait_count = 0
            default_trait_column = self.config_manager.get_config().get('default_trait_column')
            if default_trait_column in adata.obs.columns:
                default_trait_count = adata.obs[default_trait_column].dropna().nunique()
            
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
                '_default_trait_count': default_trait_count,
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
                obs_candidates = []
                for col_info in self._get_configured_metadata_columns(adata, sample_metadata=True):
                    actual_name = col_info['actual_name']
                    if col_info['column_name'] in seen or actual_name is None:
                        continue

                    seen.add(col_info['column_name'])
                    format_str = ''
                    if col_info['type'] in ('bigint', 'double precision'):
                        try:
                            col_min = float(adata.obs[actual_name].min())
                            col_max = float(adata.obs[actual_name].max())
                            format_str = f"{col_min},{col_max}"
                        except (ValueError, TypeError):
                            pass

                    obs_candidates.append({
                        'column_name': col_info['column_name'],
                        'display_name': col_info['display_name'],
                        'type': col_info['type'],
                        'description': '',
                        'format': format_str,
                        'isMeta': False,
                        'is_default_trait': col_info['is_default_trait'],
                    })

                columns.extend(obs_candidates)
            
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
                    meta_candidates = []
                    for col_info in self._get_configured_metadata_columns(adata, sample_metadata=False):
                        if col_info['column_name'] in seen:
                            continue
                        seen.add(col_info['column_name'])
                        meta_candidates.append({
                            'column_name': col_info['column_name'],
                            'display_name': col_info['display_name'],
                            'type': col_info['type'],
                            'description': '',
                            'format': '',
                            'isMeta': True,
                        })

                    columns.extend(meta_candidates)
                
                # Add sample metadata for _meta tables
                if include_sample_meta:
                    for col_info in self._get_configured_metadata_columns(adata, sample_metadata=True):
                        actual_name = col_info['actual_name']
                        if col_info['column_name'] in seen or actual_name is None:
                            continue

                        seen.add(col_info['column_name'])
                        format_str = ''
                        if col_info['type'] in ('bigint', 'double precision'):
                            try:
                                col_min = float(adata.obs[actual_name].min())
                                col_max = float(adata.obs[actual_name].max())
                                format_str = f"{col_min},{col_max}"
                            except (ValueError, TypeError):
                                pass

                        columns.append({
                            'column_name': col_info['column_name'],
                            'type': col_info['type'],
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
        filter_chain: Optional[Dict[str, Any]] = None,
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

        # Track whether caller passed explicit columns. When no columns are
        # given we fall back to get_all_columns(), which respects the admin-panel
        # visibility flag. Protein/RNA virtual sequence columns follow that same
        # visibility rule because they are Data Manager / tooltip metadata, not
        # sidebar filter columns. newick_str is still injected for tree assembly.
        explicit_columns_requested = bool(columns)

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
        
        # Add virtual columns (only when requested and enabled).
        # Virtual columns are injected whenever:
        #   a) the caller explicitly listed them in `columns`, OR
        #   b) no explicit column list was given (default full fetch) –
        #      regardless of admin-panel visibility so trees/sequences are
        #      always available even when the sidebar column is hidden.
        if include_virtual_columns:
            add_all_virtual = not explicit_columns_requested
            if 'ortho_id' in df.columns and ('newick_str' in columns or add_all_virtual):
                df['newick_str'] = df['ortho_id'].apply(
                    lambda og: self.gene_trees.get(og) if pd.notna(og) and og else None
                )
            
            if 'gene_id' in df.columns:
                visible_default_virtuals = set(columns) if add_all_virtual else set()
                if 'protein_seq' in columns or (add_all_virtual and 'protein_seq' in visible_default_virtuals):
                    df['protein_seq'] = df['gene_id'].apply(
                        lambda gid: self.sequences.get_protein_seq(species_code, gid) if pd.notna(gid) else ''
                    )
                if 'rna_seq' in columns or (add_all_virtual and 'rna_seq' in visible_default_virtuals):
                    df['rna_seq'] = df['gene_id'].apply(
                        lambda gid: self.sequences.get_rna_seq(species_code, gid) if pd.notna(gid) else ''
                    )
        
        # Apply filters
        if filters:
            df = self._apply_filters(df, filters, filter_chain=filter_chain)
        
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
        configured_sample_columns = self._get_configured_metadata_columns(adata, sample_metadata=True)
        configured_names = {item['column_name'] for item in configured_sample_columns}
        requested_columns = [
            column_name for column_name in columns
            if column_name in configured_names
        ] if columns else []

        if requested_columns:
            selected_sample_columns = [
                item for item in configured_sample_columns
                if item['column_name'] in requested_columns
            ]
        else:
            selected_sample_columns = configured_sample_columns
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
            
            for col_info in selected_sample_columns:
                actual_name = col_info['actual_name']
                if actual_name is None:
                    row[col_info['column_name']] = None
                    continue

                val = sample_row.get(actual_name, None)
                row[col_info['column_name']] = float(val) if isinstance(val, (int, float)) and not pd.isna(val) else val
            
            rows.append(row)
        
        # NOTE: Gene metadata columns (go_terms, description, genename, ecnumber,
        # description_long, ipr_id, pfam_id, is_tf, tf_family, ortho_id,
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
            
            if op == 'has_value':
                obs_df = obs_df[obs_df[actual_col].apply(filter_parser.is_non_missing_value)]
            elif op == 'eq':
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
        filters: Dict[str, Tuple[str, Any]],
        filter_chain: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """Apply filters to DataFrame."""
        result = df.copy()
        logger.debug("[_apply_filters] Applying %d filters to DataFrame shape %s", len(filters), df.shape)

        chain_columns, chain_operators, chain_groups, chain_nots = self._normalize_filter_chain(filters, filter_chain)
        if chain_columns:
            masks = {}
            for col in chain_columns:
                mask = self._filter_mask(result, col, filters[col])
                if col in chain_nots:
                    mask = ~mask
                masks[col] = mask
            combined = self._evaluate_filter_chain(
                chain_columns,
                chain_operators,
                chain_groups,
                masks,
                result.index,
            )
            return result[combined]
        
        for col, filter_spec in filters.items():
            pg_col = self._to_display_column_name(col)
            h5ad_col = self._to_h5ad_column_name(col)
            
            actual_col = None
            for candidate in [pg_col, h5ad_col, col]:
                if candidate in result.columns:
                    actual_col = candidate
                    break
            
            logger.debug(
                "[_apply_filters] Resolved filter column %r to %r",
                col,
                actual_col,
            )
            
            if actual_col is None:
                logger.warning(f"[_apply_filters] Column '{col}' not found in DataFrame columns: {list(result.columns)[:10]}...")
                continue
            
            if filter_spec is None or filter_spec == (None, None):
                result = result[result[actual_col].isna() | (result[actual_col] == '')]
                continue
            
            op, value = filter_spec

            if op == 'has_value':
                result = result[result[actual_col].apply(filter_parser.is_non_missing_value)]
            elif op == 'eq':
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
            elif op in ('text_substr_any', 'text_substr_all'):
                # Substring matching on text columns. ``_any`` matches if at
                # least one of the configured values is a substring of the
                # cell (OR), ``_all`` requires every value to be a substring
                # of the cell (AND). Case-insensitive for usability.
                if not isinstance(value, list):
                    value = [value]
                if not value:
                    continue
                lowered = result[actual_col].astype(str).str.lower()
                masks = [lowered.str.contains(re.escape(str(v).lower()), regex=True, na=False)
                         for v in value]
                if not masks:
                    continue
                combined = masks[0].copy()
                for m in masks[1:]:
                    combined = (combined & m) if op == 'text_substr_all' else (combined | m)
                result = result[combined]
            elif op == 'range':
                min_val, max_val = value
                result = result[(result[actual_col] >= min_val) & (result[actual_col] <= max_val)]
            elif op in ('array_overlap', 'array_contains', 'array_substr_any', 'array_substr_all'):
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
                    if _op == 'array_contains':
                        return all(v in items for v in _value)
                    # Substring variants: case-insensitive substring of any
                    # array element matches the configured value.
                    items_lc = [str(it).lower() for it in items]
                    if _op == 'array_substr_any':
                        return any(
                            any(str(v).lower() in it for it in items_lc)
                            for v in _value
                        )
                    # array_substr_all
                    return all(
                        any(str(v).lower() in it for it in items_lc)
                        for v in _value
                    )

                result = result[result[actual_col].apply(check_array)]
        
        return result

    @staticmethod
    def _normalize_filter_chain(
        filters: Dict[str, Tuple[str, Any]],
        filter_chain: Optional[Dict[str, Any]],
    ) -> Tuple[List[str], List[str], Dict[str, Dict[str, int]], set]:
        if not filters or not isinstance(filter_chain, dict):
            return [], [], {}, set()

        raw_columns = filter_chain.get('columns') or []
        if not isinstance(raw_columns, list):
            return [], [], {}, set()

        seen = set()
        columns = []
        for column in raw_columns:
            column = str(column)
            if column in filters and column not in seen:
                columns.append(column)
                seen.add(column)
        for column in filters.keys():
            if column not in seen:
                columns.append(column)

        raw_nots = filter_chain.get('nots') or []
        if not isinstance(raw_nots, list):
            raw_nots = []
        nots = {str(n) for n in raw_nots} & set(columns)

        # A chain is only meaningful with 2+ columns (to combine with AND/OR),
        # unless a single column is negated (NOT), in which case the chain
        # path is still needed to invert its mask.
        if len(columns) < 2 and not nots:
            return [], [], {}, set()

        raw_operators = filter_chain.get('operators') or []
        if not isinstance(raw_operators, list):
            raw_operators = []
        operators = [str(op).lower() if str(op).lower() == 'or' else 'and' for op in raw_operators]
        while len(operators) < len(columns) - 1:
            operators.append('and')
        groups = GenXBrowserService._normalize_filter_chain_groups(columns, filter_chain.get('groups'))
        return columns, operators[:len(columns) - 1], groups, nots

    @staticmethod
    def _normalize_filter_chain_groups(
        columns: List[str],
        raw_groups: Any,
    ) -> Dict[str, Dict[str, int]]:
        if not isinstance(raw_groups, dict):
            return {}

        column_set = set(columns)
        groups: Dict[str, Dict[str, int]] = {}
        for column, group in raw_groups.items():
            column = str(column)
            if column not in column_set or not isinstance(group, dict):
                continue
            open_count = max(0, int(group.get('open') or 0))
            close_count = max(0, int(group.get('close') or 0))
            if open_count or close_count:
                groups[column] = {'open': open_count, 'close': close_count}

        depth = 0
        for column in columns:
            depth += groups.get(column, {}).get('open', 0)
            depth -= groups.get(column, {}).get('close', 0)
            if depth < 0:
                logger.warning("Ignoring invalid filter_chain groups: closing parenthesis before open")
                return {}
        if depth != 0:
            logger.warning("Ignoring invalid filter_chain groups: unbalanced parentheses")
            return {}
        return groups

    @staticmethod
    def _evaluate_filter_chain(
        columns: List[str],
        operators: List[str],
        groups: Dict[str, Dict[str, int]],
        masks: Dict[str, pd.Series],
        index: pd.Index,
    ) -> pd.Series:
        if not groups:
            combined = masks[columns[0]].copy()
            for idx, col in enumerate(columns[1:]):
                operator = operators[idx] if idx < len(operators) else 'and'
                combined = (combined | masks[col]) if operator == 'or' else (combined & masks[col])
            return combined

        output: List[Any] = []
        op_stack: List[str] = []

        def push_operator(operator: str) -> None:
            while op_stack and op_stack[-1] != '(':
                output.append(op_stack.pop())
            op_stack.append(operator)

        for idx, column in enumerate(columns):
            for _ in range(groups.get(column, {}).get('open', 0)):
                op_stack.append('(')

            output.append(column)

            for _ in range(groups.get(column, {}).get('close', 0)):
                while op_stack and op_stack[-1] != '(':
                    output.append(op_stack.pop())
                if op_stack and op_stack[-1] == '(':
                    op_stack.pop()

            if idx < len(columns) - 1:
                push_operator(operators[idx] if idx < len(operators) else 'and')

        while op_stack:
            operator = op_stack.pop()
            if operator != '(':
                output.append(operator)

        stack: List[pd.Series] = []
        for token in output:
            if token in ('and', 'or'):
                if len(stack) < 2:
                    return pd.Series(True, index=index)
                right = stack.pop()
                left = stack.pop()
                stack.append((left | right) if token == 'or' else (left & right))
            else:
                stack.append(masks[str(token)])

        return stack[0] if stack else pd.Series(True, index=index)

    def _resolve_filter_column(self, df: pd.DataFrame, col: str) -> Optional[str]:
        pg_col = self._to_display_column_name(col)
        h5ad_col = self._to_h5ad_column_name(col)
        for candidate in [pg_col, h5ad_col, col]:
            if candidate in df.columns:
                return candidate
        return None

    def _filter_mask(
        self,
        df: pd.DataFrame,
        col: str,
        filter_spec: Tuple[str, Any],
    ) -> pd.Series:
        actual_col = self._resolve_filter_column(df, col)
        if actual_col is None:
            logger.warning(f"[_filter_mask] Column '{col}' not found in DataFrame columns: {list(df.columns)[:10]}...")
            return pd.Series(True, index=df.index)

        if filter_spec is None or filter_spec == (None, None):
            return df[actual_col].isna() | (df[actual_col] == '')

        op, value = filter_spec

        if op == 'has_value':
            return df[actual_col].apply(filter_parser.is_non_missing_value)
        if op == 'eq':
            if isinstance(value, bool):
                return df[actual_col] == value
            return df[actual_col].astype(str).str.strip() == str(value).strip()
        if op == 'in':
            if isinstance(value, list):
                target_set = {str(v).strip() for v in value}
                return df[actual_col].astype(str).str.strip().isin(target_set)
            return pd.Series(True, index=df.index)
        if op in ('text_substr_any', 'text_substr_all'):
            if not isinstance(value, list):
                value = [value]
            if not value:
                return pd.Series(True, index=df.index)
            lowered = df[actual_col].astype(str).str.lower()
            masks = [lowered.str.contains(re.escape(str(v).lower()), regex=True, na=False)
                     for v in value]
            combined = masks[0].copy()
            for mask in masks[1:]:
                combined = (combined & mask) if op == 'text_substr_all' else (combined | mask)
            return combined
        if op == 'range':
            min_val, max_val = value
            return (df[actual_col] >= min_val) & (df[actual_col] <= max_val)
        if op in ('array_overlap', 'array_contains', 'array_substr_any', 'array_substr_all'):
            col_defs = self.config_manager.get_column_definitions()
            pg_col = self._to_display_column_name(col)
            sep = (
                col_defs.get(pg_col, col_defs.get(col, {})).get('array_separator')
                or ('|' if (pg_col or col).lower().endswith('desc') else ',')
            )

            def check_array(x, _sep=sep, _op=op, _value=value):
                if isinstance(x, (list, np.ndarray)):
                    items = list(x)
                elif isinstance(x, str) and x:
                    items = [s.strip() for s in x.split(_sep) if s.strip()]
                else:
                    return False

                if _op == 'array_overlap':
                    return any(v in items for v in _value)
                if _op == 'array_contains':
                    return all(v in items for v in _value)
                items_lc = [str(it).lower() for it in items]
                if _op == 'array_substr_any':
                    return any(any(str(v).lower() in it for it in items_lc) for v in _value)
                return all(any(str(v).lower() in it for it in items_lc) for v in _value)

            return df[actual_col].apply(check_array)

        return pd.Series(True, index=df.index)
    
    # =========================================================================
    # Public API - Aggregations
    # =========================================================================
    
    def get_row_count(
        self,
        table_name: str,
        filters: Optional[Dict[str, Tuple[str, Any]]] = None,
        filter_chain: Optional[Dict[str, Any]] = None,
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
        
        df = self._apply_filters(df, filters, filter_chain=filter_chain)
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
            actual_var = self._resolve_axis_column(adata.var, column_name)
            actual_obs = self._resolve_axis_column(adata.obs, column_name)
            if actual_var is not None:
                col_values = pd.to_numeric(adata.var[actual_var], errors='coerce').dropna()
                values.extend(col_values.tolist())
            # Check .obs
            elif actual_obs is not None:
                col_values = pd.to_numeric(adata.obs[actual_obs], errors='coerce').dropna()
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
        col_defs = self.config_manager.get_column_definitions()
        # Build a reverse lookup: normalised(raw_h5ad_name) -> config_key
        # so that columns stored with spaces in H5AD get keyed by their config name.
        _normalised_to_config: Dict[str, str] = {}
        for cfg_key in col_defs:
            _normalised_to_config[cfg_key.lower().replace(' ', '_')] = cfg_key

        def _column_key(col: str) -> str:
            """Return the config key for a raw H5AD column name, falling back to display name."""
            cfg_key = _normalised_to_config.get(col.lower().replace(' ', '_'))
            if cfg_key:
                return cfg_key
            return self._to_display_column_name(col)

        for species_code in all_species:
            adata = self.registry.load(species_code)
            if adata is None:
                continue
            for col in adata.obs.columns:
                dtype = str(adata.obs[col].dtype)
                if self._get_column_type(dtype, col) in ('bigint', 'double precision'):
                    numeric_columns.add(_column_key(col))
            for col in adata.var.columns:
                dtype = str(adata.var[col].dtype)
                if self._get_column_type(dtype, col) in ('bigint', 'double precision'):
                    numeric_columns.add(_column_key(col))

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
        filter_chain: Optional[Dict[str, Any]] = None,
        significance: float = 0.01,
        top_n: int = 10,
        min_count: int = 3,
        go_depth_min: int = 0,
        column_type: str = 'array',
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
        4. Run Fisher's Exact Test for each attribute
        5. Apply Benjamini-Hochberg FDR correction
        6. Calculate combined score: -log10(q_value) * (subset_count / background_count)
        7. Filter by significance threshold and min_count
        8. Sort by combined_score and return top N
        
        Args:
            table_name: Species table name
            column_name: Attribute column (e.g., 'ortho_id', 'go_terms')
            filters: Filter list defining gene subset
            significance: FDR q-value threshold (default: 0.01)
            top_n: Maximum results to return (default: 10)
            min_count: Minimum genes in subset with attribute (default: 3)
            column_type: 'array' or 'text' (affects parsing)
            go_hierarchy: GOHierarchyHelper instance for GO depth metadata
        
        Returns:
            Dict with 'results' (list of enrichment entries) and 'metadata'
        """
        import scipy.stats as stats
        
        logger.info(f"ORA calculation: table={table_name}, column={column_name}, filters={len(filters)}")
        
        # Quick count check to avoid expensive computation on large subsets
        if max_subset_size > 0:
            row_count = self.get_row_count(table_name, filters, filter_chain=filter_chain)
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
            filter_chain=filter_chain,
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
        
        # 3. Build attribute -> gene index mappings
        def build_gene_attribute_map(df: pd.DataFrame, col: str) -> tuple:
            """
            Map each attribute to set of gene indices that contain it.
            
            Returns:
                Tuple of (attr_to_genes dict, annotated_genes set)
            """
            attr_to_genes = {}
            annotated_genes = set()
            
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
                            attributes = [value.strip()] if value.strip() else []
                    else:
                        # Simple text column: single attribute
                        attributes = [value.strip()] if value.strip() else []
                else:
                    # Numeric or other: convert to string
                    text_value = str(value).strip()
                    attributes = [text_value] if text_value else []
                
                if not attributes:
                    continue

                annotated_genes.add(gene_idx)
                
                # Add gene to each attribute's set
                for attr in attributes:
                    if attr not in attr_to_genes:
                        attr_to_genes[attr] = set()
                    attr_to_genes[attr].add(gene_idx)
            
            return attr_to_genes, annotated_genes
        
        subset_map, annotated_subset_genes = build_gene_attribute_map(subset_df, column_name)
        background_map, annotated_background_genes = build_gene_attribute_map(background_df, column_name)

        subset_size = len(annotated_subset_genes)
        background_size = len(annotated_background_genes)
        raw_subset_size = len(subset_df)
        raw_background_size = len(background_df)

        logger.info(
            f"ORA: subset_size={subset_size}/{raw_subset_size} annotated, "
            f"background_size={background_size}/{raw_background_size} annotated"
        )

        if subset_size == 0:
            return {
                'results': [],
                'metadata': {
                    'subset_size': 0,
                    'background_size': background_size,
                    'raw_subset_size': raw_subset_size,
                    'raw_background_size': raw_background_size,
                    'unannotated_subset_count': raw_subset_size,
                    'unannotated_background_count': raw_background_size - background_size,
                    'total_tests': 0,
                    'significant_count': 0,
                    'column_type': column_type,
                    'message': f"No filtered genes have annotations in column '{column_name}'",
                    'count': raw_subset_size,
                }
            }
        if background_size == 0:
            return {
                'results': [],
                'metadata': {
                    'subset_size': subset_size,
                    'background_size': 0,
                    'raw_subset_size': raw_subset_size,
                    'raw_background_size': raw_background_size,
                    'unannotated_subset_count': raw_subset_size - subset_size,
                    'unannotated_background_count': raw_background_size,
                    'total_tests': 0,
                    'significant_count': 0,
                    'column_type': column_type,
                    'message': f"No background genes have annotations in column '{column_name}'",
                    'count': raw_subset_size,
                }
            }
        
        # 4. Calculate Fisher's Exact Test for each attribute
        all_attributes = set(subset_map.keys())
        
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
                    'raw_subset_size': raw_subset_size,
                    'raw_background_size': raw_background_size,
                    'unannotated_subset_count': raw_subset_size - subset_size,
                    'unannotated_background_count': raw_background_size - background_size,
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
        
        # Add GO metadata before final Top N so GO depth participates in the
        # same filter sequence as significance and min_count.
        go_terms = {}
        available_go_depths = []
        is_go = 'go' in column_name.lower() or column_name.lower() == 'go_term'
        has_go_service = go_service and hasattr(go_service, 'get_term') and go_service.is_available()
        if is_go and (go_hierarchy or has_go_service):
            for entry in significant_results:
                go_id = entry.get('attribute', '')
                if has_go_service:
                    term = go_service.get_term(go_id)
                    if term:
                        entry['go_name'] = term.get('name')
                        entry['go_namespace'] = term.get('namespace')
                        go_terms[go_id] = term
                if go_hierarchy:
                    depth = go_hierarchy.get_depth(go_id)
                    if isinstance(depth, int) and depth >= 0:
                        entry['go_depth'] = depth
                        available_go_depths.append(depth)
                        if go_id in go_terms:
                            go_terms[go_id]['depth'] = depth

        depth_filtered_results = significant_results
        if is_go and go_depth_min > 0:
            depth_filtered_results = [
                result for result in significant_results
                if isinstance(result.get('go_depth'), int) and result.get('go_depth') >= go_depth_min
            ]

        # 8. Sort by combined score (descending) and take top N after all filters.
        # top_n <= 0 is used by the frontend to fetch the full scored result set
        # once and apply visualization-only filters locally.
        depth_filtered_results.sort(key=lambda x: x['combined_score'], reverse=True)
        top_results = depth_filtered_results if top_n <= 0 else depth_filtered_results[:top_n]
        if go_terms:
            top_ids = {entry.get('attribute', '') for entry in top_results}
            go_terms = {go_id: term for go_id, term in go_terms.items() if go_id in top_ids}
        
        # Build metadata
        metadata = {
            'subset_size': subset_size,
            'background_size': background_size,
            'raw_subset_size': raw_subset_size,
            'raw_background_size': raw_background_size,
            'unannotated_subset_count': raw_subset_size - subset_size,
            'unannotated_background_count': raw_background_size - background_size,
            'total_tests': n_tests,
            'significant_count': len(significant_results),
            'filtered_count': len(depth_filtered_results),
            'column_type': column_type,
            'filters_applied': len(filters),
            'significance_threshold': significance,
            'min_count_threshold': min_count,
            'go_depth_min': go_depth_min,
            'available_go_depths': sorted(set(available_go_depths)),
            'max_go_depth': max(available_go_depths) if available_go_depths else 0,
            'top_n': top_n,
            'count': raw_subset_size,
        }
        
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
                    row_dist    = np.nan_to_num(pdist(gene_data, metric=dist_metric), nan=0.0, posinf=0.0, neginf=0.0)
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
                    col_dist    = np.nan_to_num(pdist(sample_data, metric=dist_metric), nan=0.0, posinf=0.0, neginf=0.0)
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
