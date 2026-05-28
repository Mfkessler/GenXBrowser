"""Sample mapping validator – validates sample metadata mapping files.

Expected format: TSV with a ``sample`` column (case-insensitive) and any
number of additional sample metadata columns (e.g. ``trait``, ``condition``,
``cell_type``, ``group``). The first metadata column is treated as the default
sample metadata column by the builder; all metadata columns are preserved.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from genxprep.reporter import ValidationResult

# Common names for the sample-ID column
_SAMPLE_COLUMN_ALIASES = {"sample", "sample_id", "sampleid", "sample id", "id"}

def validate_sample_mapping(
    path: Path,
    sample_ids: set[str],
    vr: ValidationResult,
) -> pd.DataFrame | None:
    """Read and validate a sample mapping TSV.

    Requires a column that identifies samples (e.g. ``sample``). Any additional
    columns are interpreted as sample metadata and preserved with their original
    names. The sample column is renamed to ``Sample`` in the returned DataFrame.

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

    if df.columns.duplicated().any():
        duplicated = list(df.columns[df.columns.duplicated()])
        vr.error(
            f"Sample mapping has duplicate column name(s): {', '.join(map(str, duplicated))}.",
            suggestion="Rename duplicate columns so each sample metadata field has a unique name.",
        )
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

    metadata_cols = [c for c in df.columns if c != sample_col]
    if not metadata_cols:
        vr.warn(
            "Sample mapping has only one column; no sample metadata available.",
            suggestion="Add one or more columns (e.g. 'trait', 'group', 'condition') for sample metadata.",
        )

    df = df.rename(columns={sample_col: "Sample"})

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
            f"{len(only_in_matrix)} sample(s) in the matrix have no sample metadata row: "
            f"{', '.join(sorted(only_in_matrix)[:5])}{'…' if len(only_in_matrix) > 5 else ''}",
            suggestion="These samples will appear without sample metadata values.",
        )

    # -- metadata values ---------------------------------------------------
    metadata_cols = [c for c in df.columns if c != "Sample"]
    if metadata_cols:
        default_col = metadata_cols[0]
        n_unique = df[default_col].nunique()
        if n_unique < 2:
            vr.warn(
                f"Only {n_unique} unique value(s) found in default sample metadata column '{default_col}'.",
                suggestion="The heatmap column side-colors work best with at least two categories.",
            )

        vr.success(
            f"Sample mapping: {len(in_matrix)} sample(s) matched, "
            f"{len(metadata_cols)} sample metadata column(s); default: '{default_col}'."
        )
    else:
        vr.success(f"Sample mapping: {len(in_matrix)} sample(s) matched.")

    return df

