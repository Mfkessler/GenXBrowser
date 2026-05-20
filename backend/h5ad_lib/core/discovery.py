"""
Auto-discovery of H5AD files and their metadata.

Provides functions to scan directories for H5AD files and
extract species information, available layers, and column definitions.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import anndata as ad

logger = logging.getLogger(__name__)


def auto_discover_species(
    h5ad_dir: str,
    file_pattern: str = "*/*_full.h5ad",
) -> Dict[str, Dict[str, Any]]:
    """
    Auto-discover species from H5AD files in a directory.
    
    Scans the directory for H5AD files matching the pattern and extracts
    species information from each file's .uns metadata.
    
    Args:
        h5ad_dir: Base directory containing H5AD files
        file_pattern: Glob pattern to find H5AD files
        
    Returns:
        Dict mapping species codes to their metadata:
        {
            "AC": {
                "code": "AC",
                "full_name": "Aquilegia caerulea",
                "display_name": "Aquilegia caerulea",
                "file_path": "/data/prepared/AC/AC_full.h5ad",
                "available_layers": ["X", "tpm", "tmm"],
                "n_genes": 25000,
                "n_samples": 100,
                "var_columns": ["gene_id", "description", ...],
                "obs_columns": ["tissue", "assigned", ...],
            },
            ...
        }
    """
    h5ad_path = Path(h5ad_dir)
    
    if not h5ad_path.exists():
        logger.warning(f"H5AD directory not found: {h5ad_dir}")
        return {}
    
    species = {}
    
    for h5ad_file in h5ad_path.glob(file_pattern):
        try:
            result = discover_species_from_file(str(h5ad_file))
            if result:
                code = result["code"]
                species[code] = result
                logger.info(f"Discovered: {code} = {result['full_name']}")
        except Exception as e:
            logger.error(f"Failed to process {h5ad_file}: {e}")
    
    logger.info(f"Auto-discovery complete: {len(species)} species found")
    return species


def discover_species_from_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Extract species metadata from a single H5AD file.
    
    Args:
        file_path: Path to the H5AD file
        
    Returns:
        Species metadata dict or None if extraction fails
    """
    path = Path(file_path)
    if not path.exists():
        return None
    
    try:
        adata = ad.read_h5ad(file_path)
        
        # Extract code from directory name or filename
        # Pattern: /path/to/{code}/{code}_full.h5ad
        code = adata.uns.get("name", path.parent.name)
        full_name = adata.uns.get("species", code)
        
        # Discover available layers
        available_layers = discover_layers(adata)
        
        return {
            "code": code,
            "full_name": full_name,
            "display_name": full_name,
            "file_path": str(path.absolute()),
            "available_layers": available_layers,
            "n_genes": adata.n_vars,
            "n_samples": adata.n_obs,
            "var_columns": list(adata.var.columns),
            "obs_columns": list(adata.obs.columns),
            "default_sample_metadata_column": adata.uns.get("default_sample_metadata_column")
            if adata.uns.get("default_sample_metadata_column") in adata.obs.columns else None,
        }
        
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return None


def discover_layers(adata: Any) -> List[str]:
    """
    Discover available expression layers in an AnnData object.
    
    Args:
        adata: AnnData object
        
    Returns:
        List of layer names (always includes 'X' first)
    """
    layers = ["X"]
    
    # Add named layers in consistent order
    standard_layers = ["tpm", "tmm", "raw", "counts", "normalized"]
    for layer in standard_layers:
        if layer in adata.layers:
            layers.append(layer)
    
    # Add any other layers
    for layer in adata.layers.keys():
        if layer not in layers:
            layers.append(layer)
    
    return layers


def discover_columns(
    h5ad_dir: str,
    file_pattern: str = "*/*_full.h5ad",
) -> Tuple[Set[str], Set[str], Dict[str, str], Dict[str, str]]:
    """
    Discover all unique columns across all H5AD files.
    
    Args:
        h5ad_dir: Base directory containing H5AD files
        file_pattern: Glob pattern to find H5AD files
        
    Returns:
        Tuple of:
        - var_columns: Set of all gene metadata columns (.var)
        - obs_columns: Set of all sample metadata columns (.obs)
        - var_dtypes: Dict mapping var column names to dtype strings
        - obs_dtypes: Dict mapping obs column names to dtype strings
    """
    h5ad_path = Path(h5ad_dir)
    
    var_columns: Set[str] = set()
    obs_columns: Set[str] = set()
    var_dtypes: Dict[str, str] = {}
    obs_dtypes: Dict[str, str] = {}
    
    for h5ad_file in h5ad_path.glob(file_pattern):
        try:
            adata = ad.read_h5ad(h5ad_file)
            
            for col in adata.var.columns:
                var_columns.add(col)
                if col not in var_dtypes:
                    var_dtypes[col] = str(adata.var[col].dtype)
            
            for col in adata.obs.columns:
                obs_columns.add(col)
                if col not in obs_dtypes:
                    obs_dtypes[col] = str(adata.obs[col].dtype)
                    
        except Exception as e:
            logger.error(f"Error reading {h5ad_file}: {e}")
    
    return var_columns, obs_columns, var_dtypes, obs_dtypes


def generate_tags(species_name: str) -> List[str]:
    """
    Generate searchable tags from a species name.
    
    Args:
        species_name: Full species name (e.g., "Aquilegia caerulea")
        
    Returns:
        List of lowercase tags
    """
    # Split by spaces and underscores
    parts = species_name.replace("_", " ").split()
    # Add generic tags
    tags = parts + ["expression", "coexpression"]
    return [tag.lower() for tag in tags]
