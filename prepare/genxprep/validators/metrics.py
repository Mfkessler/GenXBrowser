"""Metrics validator – validates RNA-seq quality metrics files.

Expected format: TSV with columns ``sample``, ``assigned``,
``pct_unmapped``, ``pct_no_feature``, ``pct_trimmed``.

Column names are normalized on read: spaces → underscores, hyphens → underscores,
lowercase. This ensures consistent column names in the resulting h5ad files regardless
of the original TSV header style.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from genxprep.reporter import ValidationResult

_EXPECTED_COLUMNS = {
    "sample",
    "assigned",
    "pct_unmapped",
    "pct_no_feature",
    "pct_trimmed",
}


def validate_metrics(
    path: Path,
    sample_ids: set[str],
    vr: ValidationResult,
) -> pd.DataFrame | None:
    """Read and validate an RNA-seq metrics TSV.

    Returns the parsed DataFrame (indexed by sample) or *None* on fatal error.
    """
    if not path.exists():
        vr.error(f"Metrics file not found: {path}")
        return None

    try:
        df = pd.read_csv(path, sep="\t")
    except Exception as exc:
        vr.error(f"Could not read metrics file: {exc}")
        return None

    # Normalize column names: spaces → underscores, hyphens → underscores, lowercase
    df.columns = [c.strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]

    if df.empty:
        vr.error("Metrics file is empty.")
        return None

    # -- column check (case-insensitive) -----------------------------------
    col_lower = {c.lower().strip(): c for c in df.columns}
    found = _EXPECTED_COLUMNS & set(col_lower.keys())
    missing = _EXPECTED_COLUMNS - set(col_lower.keys())

    if "sample" not in col_lower:
        vr.error(
            "Missing required 'sample' column in metrics file.",
            suggestion=f"Available columns: {', '.join(df.columns)}",
        )
        return None

    if missing - {"sample"}:
        vr.warn(
            f"Some metrics columns are missing: {', '.join(missing - {'sample'})}.",
            suggestion="These metric columns will not be available in the app. "
            "Expected columns: " + ", ".join(sorted(_EXPECTED_COLUMNS)),
        )

    # Normalize the sample column
    sample_col = col_lower["sample"]
    df = df.rename(columns={sample_col: "sample"})

    # -- cross-validate samples -------------------------------------------
    metric_samples = set(df["sample"].astype(str))
    in_matrix = metric_samples & sample_ids

    if len(in_matrix) == 0:
        vr.error(
            "No samples in metrics match the expression matrix.",
            suggestion=(
                f"Metrics samples: {', '.join(sorted(metric_samples)[:3])}\n"
                f"      Matrix samples: {', '.join(sorted(sample_ids)[:3])}"
            ),
        )
        return None

    not_in_matrix = metric_samples - sample_ids
    if not_in_matrix:
        vr.warn(f"{len(not_in_matrix)} sample(s) in metrics not found in matrix.")

    not_in_metrics = sample_ids - metric_samples
    if not_in_metrics:
        vr.warn(
            f"{len(not_in_metrics)} sample(s) in matrix have no metrics.",
            suggestion="Missing samples will show empty metric values.",
        )

    # -- numeric check on metric cols --------------------------------------
    metric_cols = [col_lower[c] for c in ("assigned", "pct_unmapped", "pct_no_feature", "pct_trimmed") if c in col_lower]
    for mc in metric_cols:
        if not pd.api.types.is_numeric_dtype(df[mc]):
            coerced = pd.to_numeric(df[mc], errors="coerce")
            n_bad = coerced.isna().sum() - df[mc].isna().sum()
            if n_bad > 0:
                vr.warn(f"Column '{mc}' has {n_bad} non-numeric values.")

    df = df.set_index("sample")
    vr.success(f"Metrics: {len(in_matrix)} sample(s) matched.")
    return df
