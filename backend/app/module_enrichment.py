"""
Module Enrichment for GenXBrowser
=================================
Enriches full-AnnData .var with module_colors from WGCNA output,
and assigns pseudo-modules for genes that were filtered out during PreNetQC.

This module is used as a transform_fn callback when loading AnnData files.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Set

import pandas as pd
import anndata as ad

logger = logging.getLogger(__name__)

# Pseudo-module labels for filtered genes
PSEUDO_MODULE_FILTERED_CPM = "Filtered CPM"
PSEUDO_MODULE_FILTERED_VARIANCE = "Filtered Variance"
PSEUDO_MODULE_UNASSIGNED = "Unassigned"


class ModuleEnricher:
    """
    Enriches AnnData objects with module_colors from WGCNA output.
    
    For genes not present in WGCNA output (i.e., filtered during PreNetQC),
    assigns pseudo-modules based on which filter file they appear in:
    - "Filtered CPM" if gene is in filtered_cpm.tsv
    - "Filtered Variance" if gene is in filtered_variance.tsv
    - "Unassigned" if gene is in neither (shouldn't happen in practice)
    
    CPM filter takes precedence over Variance filter.
    """
    
    def __init__(
        self,
        wgcna_dir: str = "/data/wgcna",
        prenetqc_dir: str = "/data/prenetqc",
    ):
        """
        Initialize the ModuleEnricher.
        
        Args:
            wgcna_dir: Path to WGCNA output directory (contains {species_code}/{species_code}.h5ad)
            prenetqc_dir: Path to PreNetQC output directory (contains {species_code}/filtered/)
        """
        self.wgcna_dir = Path(wgcna_dir)
        self.prenetqc_dir = Path(prenetqc_dir)
        
        # Cache for filter gene sets per species
        self._cpm_filtered_cache: dict[str, Set[str]] = {}
        self._variance_filtered_cache: dict[str, Set[str]] = {}
        
        logger.info(f"ModuleEnricher initialized: wgcna_dir={wgcna_dir}, prenetqc_dir={prenetqc_dir}")
    
    def _load_wgcna_module_colors(self, species_code: str) -> Optional[pd.Series]:
        """
        Load module_colors from WGCNA output h5ad file.
        
        Args:
            species_code: Species code (e.g., 'CS')
            
        Returns:
            Series with gene_id as index and module_color as values, or None if not found
        """
        wgcna_path = self.wgcna_dir / species_code / f"{species_code}.h5ad"
        
        if not wgcna_path.exists():
            logger.warning(f"WGCNA output not found: {wgcna_path}")
            return None
        
        try:
            wgcna_adata = ad.read_h5ad(wgcna_path, backed='r')
            
            # Look for module_colors column (or fallbacks)
            module_col = None
            for col_name in ['module_colors', 'moduleColors', 'module_color', 'moduleColor']:
                if col_name in wgcna_adata.var.columns:
                    module_col = col_name
                    break
            
            if module_col is None:
                logger.warning(f"No module_colors column found in {wgcna_path}")
                return None
            
            # Extract module colors as Series
            module_colors = wgcna_adata.var[module_col].copy()
            logger.info(f"Loaded {len(module_colors)} module assignments from {wgcna_path}")
            
            return module_colors
            
        except Exception as e:
            logger.error(f"Failed to load WGCNA output {wgcna_path}: {e}")
            return None
    
    def _load_filtered_genes(self, species_code: str, filter_type: str) -> Set[str]:
        """
        Load gene IDs from a PreNetQC filter file.
        
        Args:
            species_code: Species code (e.g., 'CS')
            filter_type: Either 'cpm' or 'variance'
            
        Returns:
            Set of filtered gene IDs
        """
        filter_file = self.prenetqc_dir / species_code / "filtered" / f"filtered_{filter_type}.tsv"
        
        if not filter_file.exists():
            logger.debug(f"Filter file not found: {filter_file}")
            return set()
        
        try:
            df = pd.read_csv(filter_file, sep='\t', usecols=['ID'])
            genes = set(df['ID'].tolist())
            logger.debug(f"Loaded {len(genes)} genes from {filter_file}")
            return genes
        except Exception as e:
            logger.warning(f"Failed to load filter file {filter_file}: {e}")
            return set()
    
    def _get_cpm_filtered_genes(self, species_code: str) -> Set[str]:
        """Get cached or load CPM-filtered genes."""
        if species_code not in self._cpm_filtered_cache:
            self._cpm_filtered_cache[species_code] = self._load_filtered_genes(species_code, 'cpm')
        return self._cpm_filtered_cache[species_code]
    
    def _get_variance_filtered_genes(self, species_code: str) -> Set[str]:
        """Get cached or load variance-filtered genes."""
        if species_code not in self._variance_filtered_cache:
            self._variance_filtered_cache[species_code] = self._load_filtered_genes(species_code, 'variance')
        return self._variance_filtered_cache[species_code]
    
    def enrich(self, adata: ad.AnnData, species_code: str) -> ad.AnnData:
        """
        Enrich AnnData with module_colors column.
        
        This is the main entry point, designed to be used as a transform_fn.
        
        Args:
            adata: AnnData object (full h5ad with all genes)
            species_code: Species code for looking up WGCNA/PreNetQC files
            
        Returns:
            AnnData with module_colors column added to .var
        """
        logger.info(f"Enriching {species_code} with module_colors...")
        
        # Load WGCNA module colors
        wgcna_modules = self._load_wgcna_module_colors(species_code)
        
        # Load filtered gene sets
        cpm_filtered = self._get_cpm_filtered_genes(species_code)
        variance_filtered = self._get_variance_filtered_genes(species_code)
        
        # Build module_colors column for all genes in full AnnData
        all_genes = adata.var_names.tolist()
        module_colors = []
        
        stats = {'wgcna': 0, 'cpm': 0, 'variance': 0, 'unassigned': 0}
        
        for gene_id in all_genes:
            # Check WGCNA assignment first
            if wgcna_modules is not None and gene_id in wgcna_modules.index:
                module_colors.append(wgcna_modules[gene_id])
                stats['wgcna'] += 1
            # Check CPM filter (takes precedence)
            elif gene_id in cpm_filtered:
                module_colors.append(PSEUDO_MODULE_FILTERED_CPM)
                stats['cpm'] += 1
            # Check Variance filter
            elif gene_id in variance_filtered:
                module_colors.append(PSEUDO_MODULE_FILTERED_VARIANCE)
                stats['variance'] += 1
            # Fallback to unassigned
            else:
                module_colors.append(PSEUDO_MODULE_UNASSIGNED)
                stats['unassigned'] += 1
        
        # Add to .var
        adata.var['module_colors'] = module_colors
        
        logger.info(
            f"Module enrichment for {species_code}: "
            f"WGCNA={stats['wgcna']}, "
            f"Filtered CPM={stats['cpm']}, "
            f"Filtered Variance={stats['variance']}, "
            f"Unassigned={stats['unassigned']}"
        )
        
        return adata


# Global enricher instance (initialized lazily)
_enricher: Optional[ModuleEnricher] = None


def get_enricher() -> ModuleEnricher:
    """Get or create the global ModuleEnricher instance."""
    global _enricher
    if _enricher is None:
        wgcna_dir = os.environ.get('WGCNA_DATA_DIR', '/data/wgcna')
        prenetqc_dir = os.environ.get('PRENETQC_DATA_DIR', '/data/prenetqc')
        _enricher = ModuleEnricher(wgcna_dir=wgcna_dir, prenetqc_dir=prenetqc_dir)
    return _enricher


def module_enrichment_transform(adata: ad.AnnData, species_code: str) -> ad.AnnData:
    """
    Transform function for use with SpeciesRegistry.
    
    This function is passed to SpeciesRegistry as transform_fn and is called
    after loading each AnnData file but before caching.
    
    Args:
        adata: Loaded AnnData object
        species_code: Species code (passed by h5ad-lib loader)
        
    Returns:
        Enriched AnnData with module_colors in .var
    """
    enricher = get_enricher()
    return enricher.enrich(adata, species_code)
