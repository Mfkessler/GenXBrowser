"""
Column type inference for H5AD data.

Infers column types from pandas dtypes and column naming conventions.
"""

import logging
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


# Known array columns
KNOWN_ARRAY_COLUMNS = {
    "go_terms",
    "ipr_id",
    "pfam_id",
    "uniprot_term",
    "family",
    # Pipe-delimited description arrays
    "ipr_desc", "pfam_desc",
}

# Known boolean columns (by name pattern)
BOOLEAN_PATTERNS = {"is_", "_tf"}

# Known numeric columns (by name pattern)
NUMERIC_PATTERNS = {"count", "number", "pct", "coverage", "score", "value"}


class ColumnTypeInference:
    """
    Infers column types from dtypes and naming conventions.
    
    Maps pandas dtypes to database-style types:
    - int* / uint* -> "bigint"
    - float* / double* -> "double precision"
    - bool* -> "boolean"
    - object/category with array pattern -> "array"
    - default -> "text"
    
    Example:
        inference = ColumnTypeInference()
        
        col_type = inference.infer_type("assigned_reads", "int64")
        # Returns: "bigint"
        
        col_type = inference.infer_type("go_terms", "object")
        # Returns: "array"
    """
    
    def __init__(
        self,
        array_columns: Optional[Set[str]] = None,
        boolean_patterns: Optional[Set[str]] = None,
        numeric_patterns: Optional[Set[str]] = None,
    ):
        """
        Initialize type inference.
        
        Args:
            array_columns: Set of known array column names
            boolean_patterns: Set of patterns indicating boolean columns
            numeric_patterns: Set of patterns indicating numeric columns
        """
        self.array_columns = array_columns or KNOWN_ARRAY_COLUMNS
        self.boolean_patterns = boolean_patterns or BOOLEAN_PATTERNS
        self.numeric_patterns = numeric_patterns or NUMERIC_PATTERNS
    
    def infer_type(self, column_name: str, dtype: str) -> str:
        """
        Infer column type from name and dtype.
        
        Args:
            column_name: Column name
            dtype: Pandas dtype as string
            
        Returns:
            Type string: "text", "bigint", "double precision", "boolean", "array"
        """
        dtype_lower = dtype.lower()
        name_lower = column_name.lower()
        
        # Check for array columns
        if column_name in self.array_columns or name_lower in self.array_columns:
            return "array"
        
        # Check dtype first
        if "int" in dtype_lower or "uint" in dtype_lower:
            return "bigint"
        
        if "float" in dtype_lower or "double" in dtype_lower:
            return "double precision"
        
        if "bool" in dtype_lower:
            return "boolean"
        
        # Check name patterns for type hints
        if self._matches_patterns(name_lower, self.boolean_patterns):
            return "boolean"
        
        if self._matches_patterns(name_lower, self.numeric_patterns):
            return "double precision"
        
        return "text"
    
    def _matches_patterns(self, name: str, patterns: Set[str]) -> bool:
        """Check if name matches any pattern."""
        for pattern in patterns:
            if pattern in name:
                return True
        return False
    
    @staticmethod
    def detect_array_separator(column_name: str) -> str:
        """
        Heuristic: columns whose name ends in 'desc' or '_desc' store
        pipe-delimited multi-values; everything else uses comma.
        """
        name_lower = column_name.lower()
        if name_lower.endswith('desc') or name_lower.endswith('_desc'):
            return '|'
        return ','

    def build_column_definition(
        self,
        column_name: str,
        dtype: str,
        is_array: bool = False,
        is_meta: bool = False,
        is_sample_metadata: bool = False,
        visible: bool = True,
        order: int = 0,
        array_separator: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build a complete column definition.
        
        Args:
            column_name: Column name
            dtype: Pandas dtype
            is_array: If True, mark as array column
            is_meta: If True, mark as meta column
            is_sample_metadata: If True, mark as sample metadata
            visible: If True, column is visible by default
            order: Sort order
            array_separator: Override the intra-cell multi-value separator.
                             Defaults to auto-detection from column name.
            
        Returns:
            Column definition dict
        """
        col_type = self.infer_type(column_name, dtype)
        
        # Override type if explicitly marked as array
        if is_array:
            col_type = "array"
        
        # Determine per-column multi-value separator
        resolved_is_array = is_array or (col_type == "array")
        sep = array_separator if array_separator is not None else (
            self.detect_array_separator(column_name) if resolved_is_array else ','
        )

        return {
            "display_name": self.beautify_name(column_name),
            "type": col_type,
            "is_array": resolved_is_array,
            "array_separator": sep,
            "is_meta": is_meta,
            "is_sample_metadata": is_sample_metadata,
            "visible": visible,
            "sortable": True,
            "order": order,
        }
    
    def beautify_name(self, column_name: str) -> str:
        """
        Convert column name to human-readable display name.
        
        Args:
            column_name: Raw column name
            
        Returns:
            Human-readable name
        """
        # Special cases
        special_cases = {
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
            "rna_seq": "RNA Sequence",
            "protein_seq": "Protein Sequence",
            "newick_str": "Newick Tree",
            "tissue": "Tissue",
            "assigned": "Assigned Reads",
            "pct_unmapped": "% Unmapped",
            "pct_no_feature": "% No Feature",
            "pct_trimmed": "% Trimmed",
            "uniprot_term": "UniProt Term",
            "module_colors": "Module",
        }
        
        if column_name.lower() in special_cases:
            return special_cases[column_name.lower()]
        
        if column_name in special_cases:
            return special_cases[column_name]
        
        # Default: replace underscores with spaces and title case
        return column_name.replace("_", " ").title()
    
    def add_array_column(self, column_name: str) -> None:
        """Add a column to the known array columns."""
        self.array_columns.add(column_name)
    
    def remove_array_column(self, column_name: str) -> None:
        """Remove a column from the known array columns."""
        self.array_columns.discard(column_name)


def infer_column_type(column_name: str, dtype: str) -> str:
    """
    Convenience function to infer column type.
    
    Args:
        column_name: Column name
        dtype: Pandas dtype
        
    Returns:
        Type string
    """
    inference = ColumnTypeInference()
    return inference.infer_type(column_name, dtype)
