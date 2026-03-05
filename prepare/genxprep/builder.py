"""Builder – assembles validated data into AnnData (H5AD) objects.

Combines expression matrices, sample metadata, gene annotations, and
orthogroup assignments into a single ``.h5ad`` file per species, structured
exactly as the GenXBrowser backend expects.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse

from genxprep.config import SpeciesConfig, GlobalMetadata
from genxprep.reporter import Reporter, ValidationResult
from genxprep.validators import (
    matrix as mat_val,
    sample_mapping as sm_val,
    metrics as met_val,
    annotations as ann_val,
    sequences as seq_val,
    orthogroups as og_val,
)


def build_species(
    sp: SpeciesConfig,
    global_meta: GlobalMetadata,
    ortho_df: pd.DataFrame | None,
    reporter: Reporter,
) -> ad.AnnData | None:
    """Build an AnnData object for a single species.

    Returns the AnnData or *None* if fatal errors occurred.
    """
    vr = reporter.new(f"Build → {sp.code} ({sp.name})")

    # ------------------------------------------------------------------
    # 1. Load primary expression matrix
    # ------------------------------------------------------------------
    primary_key, primary_path = sp.matrix.primary
    primary_df = mat_val.validate_matrix(primary_path, f"{sp.code} {primary_key} matrix", vr)
    if primary_df is None:
        return None

    gene_ids = mat_val.get_gene_ids(primary_df)
    sample_ids = set(mat_val.get_sample_ids(primary_df))

    # Expression matrix: AnnData convention = obs × var = samples × genes
    # Our TSV is genes × samples, so we transpose.
    X = primary_df.T  # now samples × genes

    # ------------------------------------------------------------------
    # 2. Load additional layers
    # ------------------------------------------------------------------
    layers: dict[str, Any] = {}

    # Map layer names to H5AD keys expected by backend
    layer_key_map = {"raw": "raw", "tpm": "tpm", "tmm": "tmm", "getmm": "getmm"}

    for mat_key, mat_path in sp.matrix.available.items():
        if mat_key == primary_key:
            continue  # already loaded as X
        layer_vr = reporter.new(f"Layer → {sp.code} {mat_key}")
        layer_df = mat_val.validate_matrix(mat_path, f"{sp.code} {mat_key} matrix", layer_vr)
        if layer_df is None:
            continue

        # Ensure same genes and samples
        common_genes = primary_df.index.intersection(layer_df.index)
        common_samples = [c for c in primary_df.columns if c in layer_df.columns]

        if len(common_genes) != len(primary_df.index) or len(common_samples) != len(primary_df.columns):
            layer_vr.warn(
                f"Layer '{mat_key}' dimensions differ from primary matrix. "
                f"Using intersection: {len(common_genes)} genes, {len(common_samples)} samples.",
            )

        # Reindex to match primary matrix
        layer_aligned = layer_df.reindex(index=primary_df.index, columns=primary_df.columns)
        layers[layer_key_map.get(mat_key, mat_key)] = layer_aligned.T.values  # samples × genes

    # If primary is not raw, also store it as a named layer
    if primary_key != "raw" and primary_key in layer_key_map:
        layers[layer_key_map[primary_key]] = X.values.copy()

    # ------------------------------------------------------------------
    # 3. Build obs (sample metadata)
    # ------------------------------------------------------------------
    obs = pd.DataFrame(index=X.index)
    obs.index.name = None

    # Sample mapping → tissue column
    if sp.sample_mapping and sp.sample_mapping.exists():
        sm_vr = reporter.new(f"Sample mapping → {sp.code}")
        sm_df = sm_val.validate_sample_mapping(sp.sample_mapping, sample_ids, sm_vr)
        if sm_df is not None:
            sm_df = sm_df.set_index("Sample")
            obs = obs.join(sm_df[["tissue"]], how="left")

    # Metrics → assigned, pct unmapped, etc.
    if sp.metrics and sp.metrics.exists():
        met_vr = reporter.new(f"Metrics → {sp.code}")
        met_df = met_val.validate_metrics(sp.metrics, sample_ids, met_vr)
        if met_df is not None:
            # Align to obs index
            obs = obs.join(met_df, how="left")

    # ------------------------------------------------------------------
    # 4. Build var (gene metadata)
    # ------------------------------------------------------------------
    var = pd.DataFrame(index=primary_df.index)
    var.index.name = None

    # --- UniProt annotations ---
    if sp.metadata.uniprot and sp.metadata.uniprot.exists():
        uni_vr = reporter.new(f"UniProt → {sp.code}")
        uni_df = ann_val.validate_uniprot(sp.metadata.uniprot, gene_ids, uni_vr)
        if uni_df is not None:
            # Map columns to H5AD names expected by backend (manager.py)
            col_map = {
                "Description": "description",
                "Description long": "description_long",
                "Genename": "genename",
                "ECNumber": "ecnumber",
                "GO": "go_terms",
                "DB Accession": "db_accession",
                "Query Coverage": "query_coverage",
                "DB Coverage": "db_coverage",
                "Tax-ID": "tax_id",
            }
            # Find columns case-insensitively
            available = {c.lower().strip(): c for c in uni_df.columns}
            for target_lower, h5ad_name in {k.lower(): v for k, v in col_map.items()}.items():
                src_col = available.get(target_lower)
                if src_col:
                    var[col_map.get(src_col, h5ad_name)] = uni_df[src_col].reindex(var.index)

    # --- InterPro ---
    if sp.metadata.interpro and sp.metadata.interpro.exists():
        ipr_vr = reporter.new(f"InterPro → {sp.code}")
        ipr_df = ann_val.validate_interpro(sp.metadata.interpro, gene_ids, ipr_vr)
        if ipr_df is not None:
            if "ipr_id" in ipr_df.columns:
                var["ipr_id"] = ipr_df["ipr_id"].reindex(var.index).fillna("")
            if "ipr_desc" in ipr_df.columns:
                var["ipr_desc"] = ipr_df["ipr_desc"].reindex(var.index).fillna("")

    # --- Pfam ---
    if sp.metadata.pfam and sp.metadata.pfam.exists():
        pfam_vr = reporter.new(f"Pfam → {sp.code}")
        pfam_df = ann_val.validate_pfam(sp.metadata.pfam, gene_ids, pfam_vr)
        if pfam_df is not None:
            if "pfam_id" in pfam_df.columns:
                var["pfam_id"] = pfam_df["pfam_id"].reindex(var.index)

    # --- Transcription Factors ---
    if sp.metadata.tf and sp.metadata.tf.exists():
        tf_vr = reporter.new(f"TF → {sp.code}")
        tf_df = ann_val.validate_tf(sp.metadata.tf, gene_ids, tf_vr)
        if tf_df is not None:
            if "is_tf" in tf_df.columns:
                var["is_tf"] = tf_df["is_tf"].reindex(var.index).fillna(False).infer_objects(copy=False).astype(bool)
            if "tf_family" in tf_df.columns:
                var["tf_family"] = tf_df["tf_family"].reindex(var.index).fillna("")

    # --- Orthogroups ---
    if ortho_df is not None:
        og_map = og_val.extract_orthogroup_map(ortho_df, sp.name, sp.code)
        if og_map:
            var["ortho_id"] = var.index.map(lambda gid: og_map.get(gid, ""))

    # Add gene_id column explicitly (backend reads this from var)
    if "gene_id" not in var.columns:
        var["gene_id"] = var.index

    # ------------------------------------------------------------------
    # 5. Assemble AnnData
    # ------------------------------------------------------------------
    adata = ad.AnnData(
        X=X.values.astype(np.float32),
        obs=obs,
        var=var,
        layers={k: v.astype(np.float32) for k, v in layers.items()},
        uns={
            "name": sp.code,
            "species": sp.name,
        },
    )

    # Set proper string index
    adata.obs_names = pd.Index(X.index.astype(str))
    adata.var_names = pd.Index(X.columns.astype(str))

    # Convert sparse if large to save disk space
    if adata.n_obs * adata.n_vars > 1_000_000:
        adata.X = sparse.csr_matrix(adata.X)
        for lk in list(adata.layers.keys()):
            adata.layers[lk] = sparse.csr_matrix(adata.layers[lk])

    n_layers = len(adata.layers)
    n_var_cols = len([c for c in var.columns if var[c].notna().any()])

    vr.success(
        f"{sp.code}: AnnData built — {adata.n_obs} samples × {adata.n_vars} genes, "
        f"{n_layers} extra layer(s), {n_var_cols} annotation column(s)."
    )

    return adata
