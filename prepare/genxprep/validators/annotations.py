"""Annotations validator – validates UniProt, InterPro, Pfam, and TF files.

Each file type has its own expected format:

* **UniProt**: TSV with header; required column ``ID``
* **InterPro**: TSV, no header, 3 columns (ID, IPR accession, description)
* **Pfam**: TSV, no header, 3 columns (ID, PF accession, description)
* **TF**: TSV with header; columns ``Gene``, ``Family``
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from genxprep.id_checker import check_id_overlap
from genxprep.reporter import ValidationResult


# ---------------------------------------------------------------------------
# UniProt annotation
# ---------------------------------------------------------------------------

_UNIPROT_EXPECTED = {
    "id", "description", "genename", "ecnumber", "go",
    "description long", "db accession", "query coverage", "db coverage",
    "tax-id",
}


def validate_uniprot(
    path: Path,
    gene_ids: set[str],
    vr: ValidationResult,
) -> pd.DataFrame | None:
    """Read and validate a UniProt annotation file.

    Returns a DataFrame indexed by gene ID with relevant annotation columns,
    or *None* on fatal error.
    """
    if not path.exists():
        vr.error(f"UniProt file not found: {path}")
        return None

    try:
        df = pd.read_csv(path, sep="\t", low_memory=False)
    except Exception as exc:
        vr.error(f"Could not read UniProt file: {exc}")
        return None

    if df.empty:
        vr.error("UniProt file is empty.")
        return None

    # Find ID column (case-insensitive)
    col_lower = {c.lower().strip(): c for c in df.columns}
    if "id" not in col_lower:
        vr.error(
            "Missing 'ID' column in UniProt file.",
            suggestion=f"Available columns: {', '.join(df.columns[:10])}",
        )
        return None

    id_col = col_lower["id"]
    df = df.rename(columns={id_col: "ID"})

    # Check missing expected columns (informational)
    found_lower = set(col_lower.keys())
    missing = _UNIPROT_EXPECTED - found_lower - {"id"}
    if missing:
        vr.info(f"UniProt: optional columns not found: {', '.join(sorted(missing))}. They will be empty.")

    # ID overlap check
    uniprot_ids = set(df["ID"].dropna().astype(str))
    check_id_overlap(gene_ids, uniprot_ids, "UniProt annotations", vr, id_column_name="ID")

    # Normalize GO column: semicolons → commas
    go_col = col_lower.get("go")
    if go_col and go_col in df.columns:
        df[go_col] = df[go_col].astype(str).str.replace(";", ",", regex=False)

    df = df.set_index("ID")
    vr.success(f"UniProt: {len(df):,} entries loaded.")
    return df


# ---------------------------------------------------------------------------
# InterPro
# ---------------------------------------------------------------------------

def validate_interpro(
    path: Path,
    gene_ids: set[str],
    vr: ValidationResult,
) -> pd.DataFrame | None:
    """Read and validate an InterPro TSV (no header, 3 columns).

    Returns a DataFrame with columns ``id``, ``ipr_id``, ``ipr_desc``
    (aggregated per gene: comma-separated), or *None* on fatal error.
    """
    return _validate_term_file(
        path, gene_ids, vr,
        label="InterPro",
        accession_col="ipr_id",
        desc_col="ipr_desc",
    )


# ---------------------------------------------------------------------------
# Pfam
# ---------------------------------------------------------------------------

def validate_pfam(
    path: Path,
    gene_ids: set[str],
    vr: ValidationResult,
) -> pd.DataFrame | None:
    """Read and validate a Pfam TSV (no header, 3 columns).

    Returns a DataFrame with columns ``id``, ``pfam_id``, ``pfam_desc``
    (aggregated per gene: comma-separated), or *None* on fatal error.
    """
    return _validate_term_file(
        path, gene_ids, vr,
        label="Pfam",
        accession_col="pfam_id",
        desc_col="pfam_desc",
    )


def _validate_term_file(
    path: Path,
    gene_ids: set[str],
    vr: ValidationResult,
    *,
    label: str,
    accession_col: str,
    desc_col: str,
) -> pd.DataFrame | None:
    """Generic validator for headerless 3-column term files (InterPro / Pfam)."""
    if not path.exists():
        vr.error(f"{label} file not found: {path}")
        return None

    try:
        df = pd.read_csv(
            path, sep="\t", header=None,
            names=["id", accession_col, desc_col],
            dtype=str,
        )
    except Exception as exc:
        vr.error(f"Could not read {label} file: {exc}")
        return None

    if df.empty:
        vr.error(f"{label} file is empty.")
        return None

    # Check column count
    if df.shape[1] < 2:
        vr.error(
            f"{label}: Expected at least 2 columns (ID, accession), got {df.shape[1]}.",
            suggestion="File should be tab-separated with columns: ID  accession  description",
        )
        return None

    # ID overlap
    file_ids = set(df["id"].dropna().astype(str))
    check_id_overlap(gene_ids, file_ids, f"{label} annotations", vr, id_column_name="ID")

    # Aggregate per gene: comma-separated accessions and pipe-separated descriptions
    grouped = df.groupby("id").agg({
        accession_col: lambda x: ",".join(x.dropna().unique()),
        desc_col: lambda x: "|".join(x.dropna().unique()) if desc_col in df.columns else "",
    }).reset_index()

    vr.success(f"{label}: {len(df):,} entries → {len(grouped):,} genes.")
    return grouped.set_index("id")


# ---------------------------------------------------------------------------
# Transcription Factors
# ---------------------------------------------------------------------------

def validate_tf(
    path: Path,
    gene_ids: set[str],
    vr: ValidationResult,
) -> pd.DataFrame | None:
    """Read and validate a TF file (TSV with header, cols ``Gene``, ``Family``).

    Returns a DataFrame indexed by gene ID with column ``tf_family``,
    or *None* on fatal error.
    """
    if not path.exists():
        vr.error(f"TF file not found: {path}")
        return None

    try:
        df = pd.read_csv(path, sep="\t", dtype=str)
    except Exception as exc:
        vr.error(f"Could not read TF file: {exc}")
        return None

    if df.empty:
        vr.error("TF file is empty.")
        return None

    col_lower = {c.lower().strip(): c for c in df.columns}

    gene_col = col_lower.get("gene")
    family_col = col_lower.get("family")

    if gene_col is None:
        vr.error(
            "Missing 'Gene' column in TF file.",
            suggestion=f"Available columns: {', '.join(df.columns)}",
        )
        return None

    if family_col is None:
        vr.warn(
            "Missing 'Family' column in TF file.",
            suggestion="TF entries will be flagged but without family classification.",
        )

    df = df.rename(columns={gene_col: "gene_id"})
    if family_col:
        df = df.rename(columns={family_col: "tf_family"})

    # ID overlap
    tf_ids = set(df["gene_id"].dropna().astype(str))
    check_id_overlap(gene_ids, tf_ids, "TF annotations", vr, id_column_name="Gene")

    # Build result
    result = df[["gene_id"]].copy()
    result["is_tf"] = True
    if "tf_family" in df.columns:
        result["tf_family"] = df["tf_family"]
    else:
        result["tf_family"] = ""

    result = result.drop_duplicates(subset="gene_id").set_index("gene_id")
    vr.success(f"TF: {len(result):,} transcription factors loaded.")
    return result
