"""Dataset capability detection with backward-compatible inference."""

from __future__ import annotations

from typing import Any


def has_orthogroups(adata: Any) -> bool:
    """Return whether an AnnData object contains usable orthogroup mappings."""
    try:
        declared = adata.uns.get("has_orthogroups")
    except (AttributeError, TypeError):
        declared = None
    if declared is not None:
        return bool(declared)

    try:
        if "ortho_id" not in adata.var.columns:
            return False
        values = adata.var["ortho_id"].dropna().astype(str).str.strip()
        return bool(values.ne("").any())
    except (AttributeError, KeyError, TypeError, ValueError):
        return False