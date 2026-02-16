"""Matrix validator – validates expression count / normalised matrices.

Expected format: TSV (tab-separated), first column = gene/transcript IDs,
remaining columns = sample IDs with numeric values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from genxprep.reporter import ValidationResult


def _sniff_separator(path: Path) -> str:
    """Detect whether *path* is tab- or comma-separated."""
    with open(path, errors="replace") as fh:
        first_line = fh.readline()
    n_tabs = first_line.count("\t")
    n_commas = first_line.count(",")
    return "\t" if n_tabs >= n_commas else ","


def validate_matrix(path: Path, label: str, vr: ValidationResult) -> pd.DataFrame | None:
    """Read and validate an expression matrix TSV.

    Returns the parsed DataFrame (genes × samples) or *None* on fatal error.
    The DataFrame index is set to gene IDs.
    """
    if not path.exists():
        vr.error(f"File not found: {path}")
        return None

    sep = _sniff_separator(path)
    if sep == ",":
        vr.warn(
            f"{label}: File appears to be comma-separated.",
            suggestion="GenXBrowser expects tab-separated (TSV) files. The tool will try to read it anyway.",
        )

    try:
        df = pd.read_csv(path, sep=sep, index_col=0, engine="c", low_memory=False)
    except Exception as exc:
        vr.error(
            f"{label}: Could not read file – {exc}",
            suggestion="Ensure the file is a valid TSV/CSV with gene IDs in the first column.",
        )
        return None

    # -- basic checks -------------------------------------------------------
    if df.empty:
        vr.error(f"{label}: File is empty (0 genes × 0 samples).")
        return None

    if df.shape[0] == 0:
        vr.error(f"{label}: No data rows found.")
        return None

    if df.shape[1] == 0:
        vr.error(
            f"{label}: No sample columns found.",
            suggestion="Check that the file has more than one column (first column = IDs, rest = samples).",
        )
        return None

    # -- index (gene IDs) ---------------------------------------------------
    if df.index.name and df.index.name.lower() in ("", "unnamed: 0"):
        df.index.name = None  # unnamed first col is normal

    n_dup = df.index.duplicated().sum()
    if n_dup > 0:
        examples = df.index[df.index.duplicated(keep=False)].unique().tolist()[:5]
        vr.warn(
            f"{label}: {n_dup} duplicate gene ID(s) found.",
            suggestion=f"Duplicates include: {', '.join(str(e) for e in examples)}. "
            "Duplicates will be kept but may cause issues.",
        )

    # -- numeric check -------------------------------------------------------
    non_numeric_cols = []
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            # Try coercing
            coerced = pd.to_numeric(df[col], errors="coerce")
            n_bad = coerced.isna().sum() - df[col].isna().sum()
            if n_bad > 0:
                non_numeric_cols.append((col, n_bad))

    if non_numeric_cols:
        details = "; ".join(f"'{c}' ({n} non-numeric values)" for c, n in non_numeric_cols[:5])
        vr.error(
            f"{label}: Some columns contain non-numeric values: {details}",
            suggestion="All expression values must be numbers (integers or decimals). "
            "Common cause: Excel auto-formatted gene names to dates.",
        )
        return None

    # coerce everything to numeric to be safe
    df = df.apply(pd.to_numeric, errors="coerce")

    # -- empty rows / cols ---------------------------------------------------
    empty_rows = df.index[df.isna().all(axis=1)]
    if len(empty_rows) > 0:
        vr.warn(f"{label}: {len(empty_rows)} gene(s) have only missing values — they will be kept but are effectively empty.")

    empty_cols = [c for c in df.columns if df[c].isna().all()]
    if empty_cols:
        vr.warn(
            f"{label}: {len(empty_cols)} sample(s) have only missing values: {', '.join(empty_cols[:5])}.",
            suggestion="Consider removing empty sample columns.",
        )

    # -- negative values (for raw counts) ------------------------------------
    if "raw" in label.lower():
        n_neg = (df < 0).sum().sum()
        if n_neg > 0:
            vr.warn(
                f"{label}: {n_neg} negative value(s) found in raw count matrix.",
                suggestion="Raw counts should be non-negative integers.",
            )

    vr.success(f"{label}: {df.shape[0]:,} genes × {df.shape[1]:,} samples.")
    return df


def get_gene_ids(df: pd.DataFrame) -> set[str]:
    """Extract the set of gene IDs from a validated matrix DataFrame."""
    return set(str(i) for i in df.index)


def get_sample_ids(df: pd.DataFrame) -> list[str]:
    """Extract ordered sample IDs from a validated matrix DataFrame."""
    return [str(c) for c in df.columns]
