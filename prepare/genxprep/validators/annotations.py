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

# Column indices for the full InterPro5 TSV output (no header, 15 columns)
_IPR_COL_GENE = 0
_IPR_COL_ACC = 11   # IPR accession (e.g. IPR029044 or "-")
_IPR_COL_DESC = 12  # IPR description (or "-")
_IPR_FULL_MIN_COLS = 13  # minimum columns to be considered full format


def validate_interpro(
    path: Path,
    gene_ids: set[str],
    vr: ValidationResult,
) -> pd.DataFrame | None:
    """Read and validate an InterPro TSV.

    Accepts two formats:
    * **Full InterPro5 output** (no header, ≥13 columns): gene_id is col 0,
      IPR accession is col 11, IPR description is col 12.  Rows where the
      IPR accession column is ``"-"`` (no IPR entry) are skipped.
    * **Simplified 3-column format** (no header): gene_id, IPR accession,
      description.

    Returns a DataFrame indexed by gene ID with columns ``ipr_id`` and
    ``ipr_desc`` (aggregated per gene, comma-separated), or *None* on fatal
    error.
    """
    if not path.exists():
        vr.error(f"InterPro file not found: {path}")
        return None

    # Peek at column count to decide which format we have
    try:
        peek = pd.read_csv(path, sep="\t", header=None, nrows=5, dtype=str)
    except Exception as exc:
        vr.error(f"Could not read InterPro file: {exc}")
        return None

    if peek.empty:
        vr.error("InterPro file is empty.")
        return None

    n_cols = peek.shape[1]

    if n_cols >= _IPR_FULL_MIN_COLS:
        # Full InterPro5 output — only load the three relevant columns
        vr.info(
            f"InterPro: detected full InterPro5 format ({n_cols} columns). "
            "Extracting gene_id (col 1), IPR accession (col 12), IPR description (col 13)."
        )
        try:
            df_raw = pd.read_csv(
                path, sep="\t", header=None,
                usecols=[_IPR_COL_GENE, _IPR_COL_ACC, _IPR_COL_DESC],
                names=["id", "ipr_id", "ipr_desc"],
                dtype=str,
            )
        except Exception as exc:
            vr.error(f"Could not read InterPro file: {exc}")
            return None

        # Drop rows where no IPR entry was assigned
        df_raw = df_raw[df_raw["ipr_id"].str.strip() != "-"].copy()
        df_raw = df_raw[df_raw["ipr_id"].notna()].copy()

    else:
        # Simplified 3-column format
        try:
            df_raw = pd.read_csv(
                path, sep="\t", header=None,
                names=["id", "ipr_id", "ipr_desc"],
                dtype=str,
            )
        except Exception as exc:
            vr.error(f"Could not read InterPro file: {exc}")
            return None

    if df_raw.empty:
        vr.warn("InterPro file has no usable IPR entries (all rows had no IPR assignment).")
        return None

    # ID overlap
    file_ids = set(df_raw["id"].dropna())
    check_id_overlap(gene_ids, file_ids, "InterPro annotations", vr, id_column_name="ID")

    # Aggregate per gene: unique IPR accessions (comma-sep), unique descriptions (pipe-sep)
    grouped = (
        df_raw.groupby("id")
        .agg(
            ipr_id=("ipr_id", lambda x: ",".join(x.dropna().unique())),
            ipr_desc=("ipr_desc", lambda x: "|".join(x.dropna().unique())),
        )
        .reset_index()
    )

    vr.success(f"InterPro: {len(df_raw):,} entries → {len(grouped):,} genes.")
    return grouped.set_index("id")


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
