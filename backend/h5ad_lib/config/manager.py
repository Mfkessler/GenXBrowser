"""
Configuration manager for H5AD applications.

Provides:
- Auto-discovery of species and columns from H5AD files
- Persistent JSON configuration
- Thread-safe access
- Hot-reload support
"""

import json
import logging
import os
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional, Set

import anndata as ad

from h5ad_lib.core.discovery import auto_discover_species, discover_columns, generate_tags
from h5ad_lib.config.schema import ColumnTypeInference

logger = logging.getLogger(__name__)


# Default column name mappings (H5AD -> display)
DEFAULT_COLUMN_MAPPINGS = {
    "ortho_id": "orthogroup",
    "description long": "description_long",
    "db accession": "db_accession",
    "query coverage": "query_coverage",
    "db coverage": "db_coverage",
    "tax-id": "tax_id",
    "genename": "gene_name",
    "ecnumber": "ec_number",
    "go_terms": "go_term",
    "ipr_id": "interpro_term",
    "pfam_id": "pfam_term",
    "is_tf": "is_tf",
    "tf_family": "tf_family",
    "pct unmapped": "pct_unmapped",
    "pct no_feature": "pct_no_feature",
    "pct trimmed": "pct_trimmed",
    "assigned": "assigned_reads",
    "tissue": "tissue_col",
}

# Default array columns
DEFAULT_ARRAY_COLUMNS = {
    "go_terms", "go_term",
    "ipr_id", "interpro_term",
    "pfam_id", "pfam_term",
    "uniprot_term",
    "family",
}

# Default meta columns (shown in Genes tab)
DEFAULT_META_COLUMNS = {
    "gene_id", "description", "description_long", "orthogroup", "hog",
    "gene_name", "ec_number", "go_term", "interpro_term", "pfam_term",
    "uniprot_term", "family", "is_tf", "tf_family",
    "protein_seq", "rna_seq", "newick_str",
    "module_colors",  # WGCNA module assignments
}


class ConfigManager:
    """
    Thread-safe configuration manager with auto-discovery.
    
    Manages:
    - Species configuration (codes, names, layers)
    - Column definitions (types, visibility, mappings)
    - Frontend settings (default columns, hidden columns)
    
    Example:
        # Auto-discover from H5AD directory
        config = ConfigManager(
            config_path="/data/config/project_config.json",
            h5ad_dir="/data/prepared"
        )
        
        # Get species
        species = config.get_species()
        
        # Get column mappings
        mappings = config.get_column_mappings()
        
        # Update and save
        config.set_species_layer_preference("AC", "tmm")
        config.save()
    """
    
    DEFAULT_VERSION = "1.0.0"
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        h5ad_dir: Optional[str] = None,
        project_name: Optional[str] = None,
        auto_discover: bool = True,
    ):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to config JSON file
            h5ad_dir: Base directory for H5AD files
            project_name: Project name (used in auto-discovery)
            auto_discover: If True, auto-discover if no config exists
        """
        self._lock = RLock()
        
        self._config_path = Path(
            config_path or os.environ.get("PROJECT_CONFIG_PATH", "/data/config/project_config.json")
        )
        self._h5ad_dir = Path(
            h5ad_dir or os.environ.get("H5AD_DATA_DIR", "/data/prepared")
        )
        self._project_name = project_name or os.environ.get("PROJECT_NAME", "H5AD Project")
        
        self._config: Dict[str, Any] = {}
        
        # Ensure config directory exists
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize
        if self._config_path.exists():
            self._load_config()
        elif auto_discover:
            self._auto_discover()
            self._save_config()
        else:
            self._config = self._get_empty_config()
    
    def _load_config(self) -> None:
        """Load configuration from JSON file."""
        with self._lock:
            try:
                with open(self._config_path, "r") as f:
                    self._config = json.load(f)
                logger.info(f"Loaded config: {self._config.get('project_name', 'Unknown')}")
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                self._config = self._get_empty_config()
    
    def _save_config(self) -> None:
        """Save configuration to JSON file."""
        with self._lock:
            try:
                with open(self._config_path, "w") as f:
                    json.dump(self._config, f, indent=2, sort_keys=False)
                logger.info(f"Saved config to {self._config_path}")
            except Exception as e:
                logger.error(f"Failed to save config: {e}")
    
    def _auto_discover(self) -> None:
        """Auto-discover configuration from H5AD files."""
        logger.info(f"Auto-discovering from {self._h5ad_dir}")
        
        if not self._h5ad_dir.exists():
            logger.warning(f"H5AD directory not found: {self._h5ad_dir}")
            self._config = self._get_empty_config()
            return
        
        # Discover species
        species_data = auto_discover_species(str(self._h5ad_dir))
        
        # Convert to config format
        species = {}
        for code, data in species_data.items():
            # Determine default layer preference
            available = data.get("available_layers", ["X"])
            default_layer = "tmm" if "tmm" in available else ("tpm" if "tpm" in available else "X")
            
            species[code] = {
                "code": code,
                "full_name": data["full_name"],
                "display_name": data.get("display_name", data["full_name"]),
                "enabled": True,
                "tags": generate_tags(data["full_name"]),
                "available_layers": available,
                "layer_preference": default_layer,
            }
        
        # Discover columns
        var_cols, obs_cols, var_dtypes, obs_dtypes = discover_columns(str(self._h5ad_dir))
        
        # Build column definitions
        type_inference = ColumnTypeInference()
        column_definitions = {}
        
        for col in var_cols:
            display_col = DEFAULT_COLUMN_MAPPINGS.get(col, col)
            column_definitions[display_col] = type_inference.build_column_definition(
                column_name=display_col,
                dtype=var_dtypes.get(col, "object"),
                is_array=col in DEFAULT_ARRAY_COLUMNS or display_col in DEFAULT_ARRAY_COLUMNS,
                is_meta=col in DEFAULT_META_COLUMNS or display_col in DEFAULT_META_COLUMNS,
                is_sample_metadata=False,
            )
        
        for col in obs_cols:
            display_col = DEFAULT_COLUMN_MAPPINGS.get(col, col)
            if display_col not in column_definitions:
                column_definitions[display_col] = type_inference.build_column_definition(
                    column_name=display_col,
                    dtype=obs_dtypes.get(col, "object"),
                    is_array=False,
                    is_meta=False,
                    is_sample_metadata=True,
                )
        
        # Ensure module_colors is in column_definitions if it's in DEFAULT_META_COLUMNS
        # (it gets added at runtime by transform functions, not from H5AD files)
        if "module_colors" not in column_definitions and "module_colors" in DEFAULT_META_COLUMNS:
            column_definitions["module_colors"] = type_inference.build_column_definition(
                column_name="module_colors",
                dtype="object",
                is_array=False,
                is_meta=True,
                is_sample_metadata=False,
            )
        
        # Build config
        self._config = {
            "project_name": self._project_name,
            "version": self.DEFAULT_VERSION,
            "description": "Auto-generated configuration",
            "species": species,
            "column_mappings": {"h5ad_to_display": DEFAULT_COLUMN_MAPPINGS.copy()},
            "column_definitions": column_definitions,
            "array_columns": list(DEFAULT_ARRAY_COLUMNS),
            "meta_columns": list(DEFAULT_META_COLUMNS),
            "sample_metadata_columns": {
                "enabled": True,
                "columns": list(obs_cols),
            },
            "frontend_settings": {
                "default_columns": ["gene_id", "description", "orthogroup"],
                "hidden_columns": [],
            },
            "data_paths": {
                "h5ad_dir": str(self._h5ad_dir),
            },
        }
        
        logger.info(f"Auto-discovered {len(species)} species, {len(var_cols)} var columns")
    
    def _get_empty_config(self) -> Dict[str, Any]:
        """Get empty config template."""
        return {
            "project_name": self._project_name,
            "version": self.DEFAULT_VERSION,
            "description": "Empty configuration",
            "species": {},
            "column_mappings": {"h5ad_to_display": {}},
            "column_definitions": {},
            "array_columns": [],
            "meta_columns": [],
            "sample_metadata_columns": {"enabled": True, "columns": []},
            "frontend_settings": {"default_columns": [], "hidden_columns": []},
            "data_paths": {"h5ad_dir": str(self._h5ad_dir)},
        }
    
    # =========================================================================
    # Public API
    # =========================================================================
    
    def get_config(self) -> Dict[str, Any]:
        """Get a copy of the current configuration."""
        with self._lock:
            return self._config.copy()
    
    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """
        Replace the entire configuration.
        
        Args:
            new_config: New configuration dict
            
        Returns:
            True if successful
        """
        with self._lock:
            try:
                self._config = new_config
                self._save_config()
                return True
            except Exception as e:
                logger.error(f"Failed to update config: {e}")
                return False
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()
    
    def save(self) -> None:
        """Save current configuration to file."""
        self._save_config()
    
    def rediscover(self) -> None:
        """Re-run auto-discovery and save."""
        self._auto_discover()
        self._save_config()
    
    # Species methods
    
    def get_species(self) -> Dict[str, Dict[str, Any]]:
        """Get all species configurations."""
        return self._config.get("species", {})
    
    def get_species_list(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """Get species as a list."""
        species = self.get_species()
        result = []
        for code, info in species.items():
            if enabled_only and not info.get("enabled", True):
                continue
            result.append({"code": code, **info})
        return result
    
    def add_species(
        self,
        code: str,
        full_name: str,
        display_name: Optional[str] = None,
        available_layers: Optional[List[str]] = None,
        layer_preference: str = "X",
        tags: Optional[List[str]] = None,
        enabled: bool = True,
    ) -> None:
        """Add or update a species."""
        with self._lock:
            self._config.setdefault("species", {})[code] = {
                "code": code,
                "full_name": full_name,
                "display_name": display_name or full_name,
                "enabled": enabled,
                "tags": tags or generate_tags(full_name),
                "available_layers": available_layers or ["X"],
                "layer_preference": layer_preference,
            }
    
    def remove_species(self, code: str) -> bool:
        """Remove a species."""
        with self._lock:
            if code in self._config.get("species", {}):
                del self._config["species"][code]
                return True
            return False
    
    def get_species_layer_preference(self, species_code: str) -> str:
        """Get layer preference for a species."""
        species = self._config.get("species", {}).get(species_code, {})
        return species.get("layer_preference", "X")
    
    def set_species_layer_preference(self, species_code: str, layer: str) -> bool:
        """Set layer preference for a species."""
        with self._lock:
            species = self._config.get("species", {}).get(species_code)
            if not species:
                return False
            
            available = species.get("available_layers", ["X"])
            if layer not in available:
                logger.error(f"Layer '{layer}' not available for {species_code}")
                return False
            
            species["layer_preference"] = layer
            self._save_config()
            return True
    
    def update_species_field(self, species_code: str, field: str, value: Any) -> bool:
        """
        Update any field for a species.
        
        Args:
            species_code: Species code
            field: Field name (e.g., 'enabled', 'display_name', etc.)
            value: New value
        
        Returns:
            True if successful, False if species not found
        """
        with self._lock:
            species = self._config.get("species", {}).get(species_code)
            if not species:
                logger.error(f"Species {species_code} not found")
                return False
            
            species[field] = value
            self._save_config()
            logger.info(f"Updated {species_code}.{field} = {value}")
            return True
    
    def get_species_available_layers(self, species_code: str) -> List[str]:
        """Get available layers for a species."""
        species = self._config.get("species", {}).get(species_code, {})
        return species.get("available_layers", ["X"])
    
    # Column methods
    
    def get_column_mappings(self) -> Dict[str, str]:
        """Get H5AD to display column mappings."""
        return self._config.get("column_mappings", {}).get("h5ad_to_display", {})
    
    def get_column_definitions(self) -> Dict[str, Any]:
        """Get all column definitions."""
        return self._config.get("column_definitions", {})
    
    def get_array_columns(self) -> Set[str]:
        """Get set of array column names."""
        cols = self._config.get("array_columns", [])
        if cols:
            return set(cols)
        # Fallback to column_definitions
        col_defs = self.get_column_definitions()
        return {col for col, defn in col_defs.items() if defn.get("is_array", False)}
    
    def get_meta_columns(self) -> Set[str]:
        """Get set of meta column names."""
        cols = self._config.get("meta_columns", [])
        if cols:
            return set(cols)
        # Fallback to column_definitions
        col_defs = self.get_column_definitions()
        return {col for col, defn in col_defs.items() if defn.get("is_meta", False)}
    
    def get_sample_metadata_columns(self) -> Set[str]:
        """Get set of sample metadata column names."""
        smc = self._config.get("sample_metadata_columns", {})
        return set(smc.get("columns", []))
    
    def is_sample_metadata_enabled(self) -> bool:
        """Check if sample metadata display is enabled."""
        return self._config.get("sample_metadata_columns", {}).get("enabled", True)
    
    def add_column_definition(
        self,
        column_name: str,
        column_type: str = "text",
        display_name: Optional[str] = None,
        is_array: bool = False,
        is_meta: bool = False,
        is_sample_metadata: bool = False,
        visible: bool = True,
    ) -> None:
        """Add or update a column definition."""
        with self._lock:
            self._config.setdefault("column_definitions", {})[column_name] = {
                "display_name": display_name or self._beautify_name(column_name),
                "type": column_type,
                "is_array": is_array,
                "is_meta": is_meta,
                "is_sample_metadata": is_sample_metadata,
                "visible": visible,
            }
    
    def _beautify_name(self, name: str) -> str:
        """Convert column name to display name."""
        special = {
            "gene_id": "Gene ID",
            "go_term": "GO Term",
            "ec_number": "EC Number",
            "is_tf": "Is TF",
            "tf_family": "TF Family",
            "module_colors": "Module",
        }
        if name in special:
            return special[name]
        return name.replace("_", " ").title()
    
    # Frontend settings
    
    def get_frontend_settings(self) -> Dict[str, Any]:
        """Get frontend settings."""
        return self._config.get("frontend_settings", {})
    
    def set_default_columns(self, columns: List[str]) -> None:
        """Set default columns for display."""
        with self._lock:
            self._config.setdefault("frontend_settings", {})["default_columns"] = columns
    
    def set_hidden_columns(self, columns: List[str]) -> None:
        """Set hidden columns."""
        with self._lock:
            self._config.setdefault("frontend_settings", {})["hidden_columns"] = columns
    
    # Path properties
    
    @property
    def config_path(self) -> Path:
        """Path to configuration file."""
        return self._config_path
    
    @property
    def h5ad_dir(self) -> Path:
        """Path to H5AD directory."""
        return self._h5ad_dir
    
    @property
    def project_name(self) -> str:
        """Project name."""
        return self._config.get("project_name", self._project_name)
