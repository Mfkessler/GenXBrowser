"""Orthogroups validator – validates an Orthogroups TSV.

Expected format: TSV with an ``Orthogroup`` column plus one column per species
(matched by full species name).  Cells contain comma-separated gene IDs.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from genxprep.reporter import ValidationResult


def validate_orthogroups(
    path: Path,
    species_names: dict[str, str],
    gene_id_sets: dict[str, set[str]],
    vr: ValidationResult,
) -> pd.DataFrame | None:
    """Read and validate an Orthogroups TSV.

    Parameters
    ----------
    species_names:
        Mapping of species code → full name (from config).
    gene_id_sets:
        Mapping of species code → set of gene IDs (from expression matrices).

    Returns the parsed DataFrame or *None* on fatal error.
    """
    if not path.exists():
        vr.error(f"Orthogroups file not found: {path}")
        return None

    try:
        df = pd.read_csv(path, sep="\t")
    except Exception as exc:
        vr.error(f"Could not read orthogroups file: {exc}")
        return None

    if df.empty:
        vr.error("Orthogroups file is empty.")
        return None

    # -- Orthogroup column --------------------------------------------------
    og_col = None
    for c in df.columns:
        if c.lower().strip() == "orthogroup":
            og_col = c
            break

    if og_col is None:
        vr.error(
            "Missing 'Orthogroup' column.",
            suggestion=f"Available columns: {', '.join(df.columns[:10])}…",
        )
        return None

    # -- match species columns ---------------------------------------------
    available_cols = {c.strip(): c for c in df.columns if c != og_col}
    available_lower = {k.lower(): k for k in available_cols}

    matched_species: dict[str, str] = {}  # code → column name in TSV

    for code, full_name in species_names.items():
        # try exact match first, then case-insensitive
        if full_name in available_cols:
            matched_species[code] = full_name
        elif full_name.lower() in available_lower:
            matched_species[code] = available_lower[full_name.lower()]
        else:
            # try partial match (genus)
            genus = full_name.split()[0] if " " in full_name else full_name
            candidates = [c for c in available_cols if genus.lower() in c.lower()]
            if len(candidates) == 1:
                matched_species[code] = candidates[0]
                vr.info(
                    f"Species '{full_name}' matched to column '{candidates[0]}' by genus.",
                )
            elif len(candidates) > 1:
                vr.warn(
                    f"Ambiguous match for '{full_name}': {candidates}. Skipping.",
                    suggestion="Rename the column in the Orthogroups file to exactly match the species name in your config.",
                )
            else:
                # fallback: try species code (exact, then case-insensitive)
                if code in available_cols:
                    matched_species[code] = code
                    vr.info(
                        f"Species '{full_name}' matched to column '{code}' by species code.",
                    )
                elif code.lower() in available_lower:
                    col = available_lower[code.lower()]
                    matched_species[code] = col
                    vr.info(
                        f"Species '{full_name}' matched to column '{col}' by species code (case-insensitive).",
                    )
                else:
                    vr.warn(
                        f"No column found for species '{full_name}' (code: {code}).",
                        suggestion=f"Available columns: {', '.join(sorted(available_cols.keys())[:10])}…\n"
                        f"      Add or rename a column to '{full_name}' or '{code}' in your Orthogroups TSV.",
                    )

    if not matched_species:
        vr.error(
            "No species from your config matched any column in the Orthogroups file.",
            suggestion="Check that species names in config match column headers in Orthogroups.tsv.",
        )
        return None

    # -- build per-species orthogroup mapping --------------------------------
    og_data: dict[str, dict[str, str]] = {}  # code → {gene_id: orthogroup}

    for code, col_name in matched_species.items():
        gene_ids = gene_id_sets.get(code, set())
        mapping: dict[str, str] = {}
        n_matched = 0

        for _, row in df.iterrows():
            og_id = str(row[og_col])
            cell = row.get(col_name)
            if pd.isna(cell) or str(cell).strip() == "":
                continue
            ids_in_cell = [g.strip() for g in str(cell).split(",") if g.strip()]
            for gid in ids_in_cell:
                mapping[gid] = og_id
                if gid in gene_ids:
                    n_matched += 1

        og_data[code] = mapping

        total = len(gene_ids)
        if total > 0:
            pct = n_matched / total * 100
            if n_matched == 0:
                vr.warn(
                    f"Species {code}: 0 gene IDs matched orthogroups.",
                    suggestion="Check that gene IDs in the Orthogroups TSV match those in your count matrix.",
                )
            else:
                vr.success(
                    f"Species {code}: {n_matched:,}/{total:,} genes ({pct:.0f}%) assigned to orthogroups."
                )

    vr.success(f"Orthogroups: {df.shape[0]:,} orthogroups, {len(matched_species)} species matched.")
    return df


def extract_orthogroup_map(
    df: pd.DataFrame,
    species_full_name: str,
    species_code: str | None = None,
) -> dict[str, str]:
    """Extract a gene_id → orthogroup_id mapping for one species.

    Returns a dict mapping gene IDs to their orthogroup.
    """
    og_col = None
    for c in df.columns:
        if c.lower().strip() == "orthogroup":
            og_col = c
            break
    if og_col is None:
        return {}

    available_cols = [c for c in df.columns if c != og_col]
    available_lower = {c.lower(): c for c in available_cols}

    # Find the species column
    sp_col = None
    for c in available_cols:
        if c.strip() == species_full_name or c.strip().lower() == species_full_name.lower():
            sp_col = c
            break

    # Genus fallback
    if sp_col is None:
        genus = species_full_name.split()[0] if " " in species_full_name else species_full_name
        candidates = [c for c in available_cols if genus.lower() in c.lower()]
        if len(candidates) == 1:
            sp_col = candidates[0]

    # Species code fallback
    if sp_col is None and species_code is not None:
        if species_code in available_cols:
            sp_col = species_code
        elif species_code.lower() in available_lower:
            sp_col = available_lower[species_code.lower()]

    if sp_col is None:
        return {}

    mapping: dict[str, str] = {}
    for _, row in df.iterrows():
        og_id = str(row[og_col])
        cell = row.get(sp_col)
        if pd.isna(cell) or str(cell).strip() == "":
            continue
        for gid in str(cell).split(","):
            gid = gid.strip()
            if gid:
                mapping[gid] = og_id
    return mapping
