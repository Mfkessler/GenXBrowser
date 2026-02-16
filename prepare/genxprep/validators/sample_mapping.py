"""Sample mapping validator – validates sample → tissue mapping files.

Expected format: TSV with columns ``Sample`` and ``tissue``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from genxprep.reporter import ValidationResult


_REQUIRED_COLUMNS = {"sample", "tissue"}


def validate_sample_mapping(
    path: Path,
    sample_ids: set[str],
    vr: ValidationResult,
) -> pd.DataFrame | None:
    """Read and validate a sample mapping TSV.

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

    # -- column check (case-insensitive) -----------------------------------
    col_lower = {c.lower().strip(): c for c in df.columns}
    missing = _REQUIRED_COLUMNS - set(col_lower.keys())

    if missing:
        vr.error(
            f"Missing required column(s): {', '.join(missing)}.",
            suggestion=f"Your file has columns: {', '.join(df.columns)}. "
            "Required: 'Sample' and 'tissue' (case-insensitive).",
        )
        return None

    # Normalise column names to canonical form
    df = df.rename(columns={col_lower["sample"]: "Sample", col_lower["tissue"]: "tissue"})

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
                f"      Make sure the 'Sample' column uses the same IDs as your matrix column headers."
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
    return df
