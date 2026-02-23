"""Sample mapping validator – validates sample → tissue mapping files.

Expected format: TSV with a ``sample`` column (case-insensitive) and at least
one additional column for grouping (e.g. ``tissue``, ``condition``,
``cell_type``, ``group``).  The grouping column is always normalised to
``tissue`` in the returned DataFrame so that downstream H5AD files use a
consistent obs column name.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from genxprep.reporter import ValidationResult

# Common names for the sample-ID column
_SAMPLE_COLUMN_ALIASES = {"sample", "sample_id", "sampleid", "sample id", "id"}

# Preferred names for the grouping column (checked in order)
_TISSUE_COLUMN_ALIASES = [
    "tissue", "condition", "group", "cell_type", "celltype",
    "cell type", "treatment", "genotype", "stage",
]


def validate_sample_mapping(
    path: Path,
    sample_ids: set[str],
    vr: ValidationResult,
) -> pd.DataFrame | None:
    """Read and validate a sample mapping TSV.

    Requires a column that identifies samples (e.g. ``sample``) and any
    additional column for grouping (e.g. ``tissue``, ``condition``).
    The grouping column is renamed to ``tissue`` and the sample column to
    ``Sample`` in the returned DataFrame.

    *sample_ids* are the sample IDs from the expression matrix for
    cross-validation.  Returns the parsed DataFrame or *None* on fatal error.
    """
    if not path.exists():
        vr.error(f"Sample mapping file not found: {path}")
        return None

    try:
        df = pd.read_csv(path, sep="\t")
    except Exception as exc:
        vr.error(f"Could not read sample mapping: {exc}")
        return None

    if df.empty:
        vr.error("Sample mapping file is empty.")
        return None

    col_lower = {c.lower().strip(): c for c in df.columns}

    # -- locate sample-ID column ------------------------------------------
    sample_col = None
    for alias in _SAMPLE_COLUMN_ALIASES:
        if alias in col_lower:
            sample_col = col_lower[alias]
            break

    if sample_col is None:
        vr.error(
            "No sample-ID column found.",
            suggestion=f"Your file has columns: {', '.join(df.columns)}. "
            f"Expected one of: {', '.join(sorted(_SAMPLE_COLUMN_ALIASES))} (case-insensitive).",
        )
        return None

    # -- locate grouping column -------------------------------------------
    grouping_col = None
    grouping_alias_used = None
    for alias in _TISSUE_COLUMN_ALIASES:
        if alias in col_lower:
            grouping_col = col_lower[alias]
            grouping_alias_used = alias
            break

    if grouping_col is None:
        # Fall back to the first column that is not the sample column
        other_cols = [c for c in df.columns if c != sample_col]
        if other_cols:
            grouping_col = other_cols[0]
            grouping_alias_used = grouping_col
            vr.info(
                f"No recognised grouping column found. "
                f"Using '{grouping_col}' as the sample-grouping column (stored as 'tissue' in H5AD).",
            )
        else:
            vr.warn(
                "Sample mapping has only one column; no grouping information available.",
                suggestion="Add a second column (e.g. 'condition' or 'tissue') for sample grouping.",
            )

    # Normalise column names
    rename = {sample_col: "Sample"}
    if grouping_col and grouping_col != sample_col:
        if grouping_alias_used != "tissue":
            vr.info(
                f"Column '{grouping_col}' will be used as tissue/condition grouping "
                f"(stored as 'tissue' in the H5AD obs)."
            )
        rename[grouping_col] = "tissue"

    df = df.rename(columns=rename)

    # -- cross-validate with matrix ----------------------------------------
    mapping_samples = set(df["Sample"].astype(str))
    in_matrix = mapping_samples & sample_ids
    only_in_mapping = mapping_samples - sample_ids
    only_in_matrix = sample_ids - mapping_samples

    if len(in_matrix) == 0:
        vr.error(
            "No samples in mapping match the expression matrix.",
            suggestion=(
                f"Mapping samples look like: {', '.join(sorted(mapping_samples)[:3])}\n"
                f"      Matrix samples look like: {', '.join(sorted(sample_ids)[:3])}\n"
                f"      Make sure the sample column uses the same IDs as your matrix column headers."
            ),
        )
        return None

    if only_in_mapping:
        vr.warn(
            f"{len(only_in_mapping)} sample(s) in mapping are not in the matrix: "
            f"{', '.join(sorted(only_in_mapping)[:5])}{'…' if len(only_in_mapping) > 5 else ''}",
            suggestion="These extra entries will be ignored.",
        )

    if only_in_matrix:
        vr.warn(
            f"{len(only_in_matrix)} sample(s) in the matrix have no tissue assignment: "
            f"{', '.join(sorted(only_in_matrix)[:5])}{'…' if len(only_in_matrix) > 5 else ''}",
            suggestion="These samples will appear without a tissue label.",
        )

    # -- tissue values -----------------------------------------------------
    if "tissue" in df.columns:
        n_unique = df["tissue"].nunique()
        if n_unique < 2:
            vr.warn(
                f"Only {n_unique} unique tissue value(s) found.",
                suggestion="The heatmap column side-colors work best with ≥2 tissue categories.",
            )

        vr.success(
            f"Sample mapping: {len(in_matrix)} sample(s) matched, "
            f"{n_unique} tissue(s)."
        )
    else:
        vr.success(f"Sample mapping: {len(in_matrix)} sample(s) matched.")

    return df

