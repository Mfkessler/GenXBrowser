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
# Empty: column names are used as-is from h5ad files (single source of truth).
# Pipelines (genxprep, CoNeXForge) normalize column names at creation time.
DEFAULT_COLUMN_MAPPINGS = {}

# Legacy mapping for auto-migration of old configs
_LEGACY_DISPLAY_TO_H5AD = {
    "orthogroup": "ortho_id",
    "gene_name": "genename",
    "ec_number": "ecnumber",
    "go_term": "go_terms",
    "interpro_term": "ipr_id",
    "pfam_term": "pfam_id",
    "assigned_reads": "assigned",
    "tissue_col": "tissue",
    "description_long": "description_long",
    "db_accession": "db_accession",
    "query_coverage": "query_coverage",
    "db_coverage": "db_coverage",
    "tax_id": "tax_id",
    "pct_unmapped": "pct_unmapped",
    "pct_no_feature": "pct_no_feature",
    "pct_trimmed": "pct_trimmed",
}

# Default array columns
DEFAULT_ARRAY_COLUMNS = {
    "go_terms",
    "ipr_id",
    "pfam_id",
    "uniprot_term",
    "family",
    # Pipe-delimited description arrays
    "ipr_desc", "pfam_desc",
}

# Default meta columns (shown in Genes tab)
DEFAULT_META_COLUMNS = {
    "gene_id", "description", "description_long", "ortho_id", "hog",
    "genename", "ecnumber", "go_terms", "ipr_id", "pfam_id",
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
        
        # Apply config profile if specified via ENV
        config_profile = os.environ.get("CONFIG_PROFILE", "").strip()
        if config_profile:
            self._apply_profile(config_profile)
    
    def _load_config(self) -> None:
        """Load configuration from JSON file."""
        with self._lock:
            try:
                with open(self._config_path, "r") as f:
                    self._config = json.load(f)
                logger.info(f"Loaded config: {self._config.get('project_name', 'Unknown')}")
                # Auto-migrate old configs with legacy column names
                self._migrate_config()
                self._strip_deprecated_frontend_settings()
                # Ensure all .var columns from h5ad files are in config and marked is_meta=True
                self._ensure_all_var_columns_in_config()
                # Back-fill any virtual columns that weren't present when config was created
                self._ensure_virtual_columns()
                # Back-fill array_separator for columns that pre-date the field
                self._ensure_array_separators()
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                self._config = self._get_empty_config()
    
    def _save_config(self) -> None:
        """Save configuration to JSON file."""
        with self._lock:
            try:
                self._strip_deprecated_frontend_settings()
                with open(self._config_path, "w") as f:
                    json.dump(self._config, f, indent=2, sort_keys=False)
                logger.info(f"Saved config to {self._config_path}")
            except Exception as e:
                logger.error(f"Failed to save config: {e}")

    def _strip_deprecated_frontend_settings(self) -> None:
        """Drop deprecated admin frontend display settings from config."""
        if isinstance(self._config, dict):
            self._config.pop("frontend_settings", None)

    def _migrate_config(self) -> None:
        """Auto-migrate old configs that used legacy display column names.

        Detects old-style column_mappings (e.g. ortho_id→orthogroup) and renames
        keys in column_definitions, meta_columns, and array_columns to use
        h5ad-native names.
        Also migrates the legacy default sample metadata role key, and clears old column_mappings.
        """
        changed = False

        # 1. Check if migration is needed by looking for old display names
        col_defs = self._config.get("column_definitions", {})
        old_mappings = self._config.get("column_mappings", {}).get("h5ad_to_display", {})
        needs_migration = any(
            old_display in col_defs
            for old_display in _LEGACY_DISPLAY_TO_H5AD
            if old_display != _LEGACY_DISPLAY_TO_H5AD[old_display]  # skip identity mappings
        )
        has_old_mappings = bool(old_mappings)

        obs_cols = [k for k, v in col_defs.items() if v.get("is_sample_metadata")]
        if "default_trait_column" not in self._config:
            self._config["default_trait_column"] = self._config.get("tissue_column")
            changed = True
        if "tissue_column" in self._config:
            del self._config["tissue_column"]
            changed = True

        if not needs_migration and not has_old_mappings:
            if changed:
                self._save_config()
            return

        logger.info("Migrating config: renaming legacy display column names to h5ad names")

        # 2. Rename keys in column_definitions
        for old_display, h5ad_name in _LEGACY_DISPLAY_TO_H5AD.items():
            if old_display == h5ad_name:
                continue  # Identity mapping, skip
            if old_display in col_defs and h5ad_name not in col_defs:
                col_defs[h5ad_name] = col_defs.pop(old_display)
                changed = True

        # 3. Rename entries in meta_columns list
        meta_cols = self._config.get("meta_columns", [])
        if meta_cols:
            new_meta = []
            for c in meta_cols:
                new_meta.append(_LEGACY_DISPLAY_TO_H5AD.get(c, c))
            self._config["meta_columns"] = new_meta
            changed = True

        # 4. Rename entries in array_columns list
        array_cols = self._config.get("array_columns", [])
        if array_cols:
            new_array = []
            for c in array_cols:
                new_array.append(_LEGACY_DISPLAY_TO_H5AD.get(c, c))
            # Deduplicate
            self._config["array_columns"] = list(dict.fromkeys(new_array))
            changed = True

        if self._config.pop("frontend_settings", None) is not None:
            changed = True

        # 5. Clear old column_mappings (no longer needed)
        if has_old_mappings:
            self._config["column_mappings"] = {"h5ad_to_display": {}}
            changed = True

        if changed:
            self._save_config()
            logger.info("Config migration complete: legacy column names updated to h5ad names")

    def _ensure_virtual_columns(self) -> None:
        """
        Ensure virtual gene columns (newick_str, protein_seq, rna_seq) exist in
        column_definitions. Called after loading an existing config so that configs
        created before these columns were added get them automatically.
        """
        col_defs = self._config.setdefault("column_definitions", {})
        from h5ad_lib.config.schema import ColumnTypeInference
        type_inference = ColumnTypeInference()

        VIRTUAL_GENE_COLUMNS = [
            ("newick_str",  "text"),
            ("protein_seq", "text"),
            ("rna_seq",     "text"),
        ]
        next_order = max((v.get("order", -1) for v in col_defs.values()), default=-1) + 1
        added = False
        for vcol, vtype in VIRTUAL_GENE_COLUMNS:
            if vcol not in col_defs:
                col_def = type_inference.build_column_definition(
                    column_name=vcol,
                    dtype="object",
                    is_array=False,
                    is_meta=True,
                    is_sample_metadata=False,
                    order=next_order,
                )
                col_def["type"] = vtype
                col_def["sortable"] = False
                col_defs[vcol] = col_def
                next_order += 1
                added = True
        if added:
            self._save_config()
            logger.info("Back-filled virtual columns (newick_str, protein_seq, rna_seq) into config")

    def _ensure_array_separators(self) -> None:
        """
        Back-fill 'array_separator' on any column_definition that is an array
        column but was created before this field existed.  Uses the same
        heuristic as ColumnTypeInference.detect_array_separator().

        Also promotes known multi-value columns (e.g. ipr_desc, pfam_desc) that
        were previously stored as type='text'/is_array=False to type='array'/
        is_array=True with the correct separator.  This fixes existing configs
        created before these columns were added to DEFAULT_ARRAY_COLUMNS.
        """
        from h5ad_lib.config.schema import ColumnTypeInference
        col_defs = self._config.get("column_definitions", {})
        changed = False

        for col_name, col_def in col_defs.items():
            is_array = col_def.get("is_array") or col_def.get("type") == "array"

            # Promote columns that should be arrays but are still typed as text.
            # Heuristic: column name is in DEFAULT_ARRAY_COLUMNS
            if not is_array and col_name in DEFAULT_ARRAY_COLUMNS:
                col_def["is_array"] = True
                col_def["type"] = "array"
                is_array = True
                changed = True

            # Back-fill array_separator for all array columns
            if is_array and "array_separator" not in col_def:
                col_def["array_separator"] = ColumnTypeInference.detect_array_separator(col_name)
                changed = True

        if changed:
            self._save_config()
            logger.info("Back-filled array_separator / promoted array columns in column_definitions")

    def _ensure_all_var_columns_in_config(self) -> None:
        """
        Ensure every .var column in the H5AD files is registered in column_definitions.
        Called after loading an existing config so that columns added later to the h5ad
        (or not yet known when the config was first created) are picked up automatically.
        Also corrects any existing entries that were wrongly stored with is_meta=False
        for .var columns.
        """
        if not self._h5ad_dir.exists():
            return
        try:
            from h5ad_lib.core.discovery import discover_columns
            var_cols, _obs_cols, var_dtypes, _obs_dtypes = discover_columns(str(self._h5ad_dir))
        except Exception as e:
            logger.warning(f"_ensure_all_var_columns_in_config: could not discover columns: {e}")
            return
        if not var_cols:
            return

        col_defs = self._config.setdefault("column_definitions", {})
        type_inference = ColumnTypeInference()
        next_order = max((v.get("order", -1) for v in col_defs.values()), default=-1) + 1
        changed = False

        for col in var_cols:
            display_col = DEFAULT_COLUMN_MAPPINGS.get(col, col)
            if display_col not in col_defs:
                # New column – add it
                col_defs[display_col] = type_inference.build_column_definition(
                    column_name=display_col,
                    dtype=var_dtypes.get(col, "object"),
                    is_array=col in DEFAULT_ARRAY_COLUMNS or display_col in DEFAULT_ARRAY_COLUMNS,
                    is_meta=True,
                    is_sample_metadata=False,
                    order=next_order,
                )
                next_order += 1
                changed = True
                logger.info(f"Discovered new .var column: {display_col}")
            else:
                # Column exists but may have wrong is_meta flag from old behaviour
                entry = col_defs[display_col]
                if not entry.get("is_meta", False) and not entry.get("is_sample_metadata", False):
                    entry["is_meta"] = True
                    changed = True

        if changed:
            self._save_config()
            logger.info("Updated column_definitions with newly discovered .var columns")

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
            column_definitions[col] = type_inference.build_column_definition(
                column_name=col,
                dtype=var_dtypes.get(col, "object"),
                is_array=col in DEFAULT_ARRAY_COLUMNS,
                is_meta=True,  # All .var columns are gene/transcript metadata by definition
                is_sample_metadata=False,
            )
        
        for col in obs_cols:
            if col not in column_definitions:
                column_definitions[col] = type_inference.build_column_definition(
                    column_name=col,
                    dtype=obs_dtypes.get(col, "object"),
                    is_array=False,
                    is_meta=False,
                    is_sample_metadata=True,
                )

        default_sample_metadata_column = None
        for data in species_data.values():
            candidate = data.get("default_sample_metadata_column")
            if candidate in obs_cols:
                default_sample_metadata_column = candidate
                break
        # Add virtual gene columns (served dynamically, not stored in .var)
        VIRTUAL_GENE_COLUMNS = [
            ("newick_str",   "text"),
            ("protein_seq",  "text"),
            ("rna_seq",      "text"),
        ]
        next_order = max((v.get("order", -1) for v in column_definitions.values()), default=-1) + 1
        for vcol, vtype in VIRTUAL_GENE_COLUMNS:
            if vcol not in column_definitions:
                col_def = type_inference.build_column_definition(
                    column_name=vcol,
                    dtype="object",
                    is_array=False,
                    is_meta=True,
                    is_sample_metadata=False,
                    order=next_order,
                )
                col_def["type"] = vtype
                col_def["sortable"] = False
                column_definitions[vcol] = col_def
                next_order += 1
        
        # Build config
        self._config = {
            "project_name": self._project_name,
            "version": self.DEFAULT_VERSION,
            "description": "Auto-generated configuration",
            "species": species,
            "column_mappings": {"h5ad_to_display": {}},
            "column_definitions": column_definitions,
            "array_columns": list(DEFAULT_ARRAY_COLUMNS),
            "meta_columns": list(DEFAULT_META_COLUMNS),
            "sample_metadata_columns": {
                "enabled": True,
                "columns": list(obs_cols),
            },
            "default_trait_column": default_sample_metadata_column,
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
            "default_trait_column": None,
            "data_paths": {"h5ad_dir": str(self._h5ad_dir)},
        }
    
    def _apply_profile(self, profile_name: str) -> None:
        """
        Apply a config profile on top of current config.
        
        Profiles are stored as JSON in {config_dir}/profiles/{name}.json.
        Profile values override current config (deep merge for dicts).
        """
        profiles_dir = self._config_path.parent / "profiles"
        profile_path = profiles_dir / f"{profile_name}.json"
        
        if not profile_path.exists():
            logger.warning(f"Config profile '{profile_name}' not found at {profile_path}")
            return
        
        try:
            with open(profile_path, "r") as f:
                profile_data = json.load(f)
            
            # Deep merge: profile overrides current config
            self._deep_merge(self._config, profile_data)
            self._strip_deprecated_frontend_settings()
            self._save_config()
            logger.info(f"Applied config profile: {profile_name}")
        except Exception as e:
            logger.error(f"Failed to apply config profile '{profile_name}': {e}")
    
    def _deep_merge(self, base: Dict, override: Dict) -> None:
        """Deep merge override into base (in-place)."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
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
                self._config = dict(new_config)
                self._strip_deprecated_frontend_settings()
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
            "ortho_id": "Orthogroup",
            "genename": "Gene Name",
            "ecnumber": "EC Number",
            "go_terms": "GO Terms",
            "ipr_id": "InterPro",
            "pfam_id": "Pfam",
            "ipr_desc": "InterPro Desc",
            "pfam_desc": "Pfam Desc",
            "is_tf": "Is TF",
            "tf_family": "TF Family",
            "module_colors": "Module",
        }
        if name in special:
            return special[name]
        return name.replace("_", " ").title()
    
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
