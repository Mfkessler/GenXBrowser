"""CLI – Click command-line interface for genxprep.

Commands::

    genxprep init              Generate a template config.yml
    genxprep validate config.yml   Validate all inputs (dry-run)
    genxprep build config.yml      Validate + build H5AD + export
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from genxprep import __version__
from genxprep.reporter import Reporter


# ======================================================================
# Main group
# ======================================================================

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="genxprep")
def main() -> None:
    """GenXPrep – Prepare your data for GenXBrowser.

    Validates raw expression data, annotations, and metadata, then
    converts everything into H5AD format ready for GenXBrowser.
    """


# ======================================================================
# init – generate template config
# ======================================================================

_TEMPLATE_CONFIG = """\
# ══════════════════════════════════════════════════════════════════════
# GenXPrep – Configuration File
# ══════════════════════════════════════════════════════════════════════
#
# FILE PATHS
# ──────────
# You can use three kinds of paths:
#   1. Relative:   Matrices/AC.raw.counts.tsv   (resolved from root_dir)
#   2. Absolute:   /home/user/data/counts.tsv
#   3. Home-dir:   ~/data/counts.tsv
#
# Set root_dir below to define where relative paths are resolved from.
# If root_dir is not set, relative paths are resolved from this config
# file's directory.
#
# Lines starting with '#' are comments – remove '#' to activate a line.
#

project:
  name: "My Project"          # REQUIRED – project name shown in GenXBrowser
  output_dir: ./data           # REQUIRED – where output H5AD files will be written

  # Root directory for relative paths (optional).
  # All relative file paths below will be resolved from this directory.
  # If omitted, the directory containing this config file is used.
  # Supports ~ for home directory.
  # root_dir: /home/ubuntu/projects/MyProject/Input
  # root_dir: ~/projects/MyProject/Input


# ══════════════════════════════════════════════════════════════════════
# GLOBAL METADATA  (shared across all species – optional)
# ══════════════════════════════════════════════════════════════════════

global_metadata:

  # ── Orthogroups ────────────────────────────────────────────────────
  # Format: TSV with header
  # Required column: "Orthogroup"
  # Remaining columns: one per species, named by full species name
  #   (e.g. "Aquilegia coerulea"). Each cell contains a comma-separated
  #   list of gene IDs belonging to that orthogroup.
  #
  # Example:
  #   Orthogroup    Aquilegia coerulea         Papaver somniferum
  #   OG0000000     GeneA1, GeneA2             GeneP1
  #   OG0000001     GeneB1                     GeneP2, GeneP3
  #
  orthogroups: Metadata/Orthogroups.tsv

  # ── Gene Trees ────────────────────────────────────────────────────
  # Format: Plain text, one tree per line
  # Each line: OG_ID:newick_string
  #
  # Example:
  #   OG0000000:((GeneA1:0.1,GeneP1:0.2):0.3,GeneA2:0.4);
  #   OG0000001:(GeneB1:0.1,GeneP2:0.2);
  #
  gene_trees: Metadata/Resolved_Gene_Trees.txt

  # ── Species Mapping (optional) ────────────────────────────────────
  # Format: TSV, no header, 2 columns: code <TAB> full_species_name
  # Example:
  #   AC    Aquilegia coerulea
  #   PS    Papaver somniferum
  #
  # species_mapping: Metadata/Species_Mapping.tsv


# ══════════════════════════════════════════════════════════════════════
# SPECIES DEFINITIONS
# ══════════════════════════════════════════════════════════════════════
# Add one block per species. The key (e.g. "AC") is the species code
# (2–10 uppercase letters). At least one species is required.

species:

  AC:
    name: "Aquilegia coerulea"    # REQUIRED – full species name

    # ── Expression matrices ─────────────────────────────────────────
    # At least ONE matrix is required (any of: raw, tpm, tmm, getmm).
    #
    # Format: TSV (tab-separated)
    #   - First column: gene / transcript IDs (may have no column header)
    #   - Remaining columns: one per sample, column header = sample ID
    #   - Values: numeric (integers for raw counts, decimals for normalised)
    #
    # Example (raw counts):
    #            Sample1  Sample2  Sample3
    #   GeneA      120      340       55
    #   GeneB        0       12        7
    #
    # IMPORTANT: Gene IDs in the first column must be identical across
    # ALL input files (matrices, annotations, FASTA, etc.).
    #
    matrix:
      raw: Matrices/AC.matrix.raw.counts.tsv
      tpm: Matrices/AC.matrix.TPM.normalized.tsv
      tmm: Matrices/AC.matrix.TMM.normalized.tsv
      getmm: Matrices/AC.matrix.geTMM.normalized.tsv

    # ── Sample mapping (optional) ──────────────────────────────────
    # Format: TSV with header
    # Required columns: "Sample", "tissue"
    #   - "Sample" must match the column headers in your matrix
    #
    # Example:
    #   Sample    tissue
    #   AC_J_1    Petal early stage
    #   AC_Q_2    Young leaf
    #
    sample_mapping: Sample_Mapping/AC_mapping.tsv

    # ── RNA-seq metrics (optional) ─────────────────────────────────
    # Format: TSV with header
    # Expected columns: "sample", "assigned", "pct unmapped",
    #                    "pct no_feature", "pct trimmed"
    #   - "sample" must match the column headers in your matrix
    #
    # Example:
    #   sample   assigned   pct unmapped   pct no_feature   pct trimmed
    #   AC_J_1   71688634   7.076          2.672            3.666
    #
    metrics: Metrics/AC.rnaseq_metrics.tsv

    # ── Per-species annotation files (all optional) ────────────────
    metadata:

      # UniProt annotation
      # Format: TSV with header
      # Required column: "ID" (must match gene IDs in your matrix)
      # Optional columns: "Description", "Description long", "Genename",
      #   "ECNumber", "GO" (semicolon-separated GO IDs), "DB Accession",
      #   "Query Coverage", "DB Coverage", "Tax-ID"
      #
      # Example:
      #   ID          Description        GO                    Genename
      #   GeneA       Kinase protein     GO:0004672;GO:0005524 KIN1
      #
      uniprot: Metadata/uniprot/AC.faa.annotation.csv

      # InterPro domain annotations
      # Format: TSV, NO header, 3 columns:
      #   gene_id <TAB> IPR_accession <TAB> description
      # Multiple rows per gene are allowed (one per domain hit).
      #
      # Example:
      #   GeneA    IPR000719    Protein kinase domain
      #   GeneA    IPR008271    Active site
      #   GeneB    IPR002290    Serine/threonine-protein kinase
      #
      interpro: Metadata/interpro/AC.iprid.tsv

      # Pfam domain annotations
      # Format: TSV, NO header, 3 columns:
      #   gene_id <TAB> PF_accession <TAB> description
      # Same structure as InterPro.
      #
      # Example:
      #   GeneA    PF00069    Protein kinase domain
      #   GeneB    PF07714    Protein tyrosine kinase
      #
      pfam: Metadata/pfam/AC.pfam.tsv

      # Transcription factors
      # Format: TSV with header
      # Required columns: "Gene" (must match gene IDs), "Family"
      #
      # Example:
      #   Gene      Family
      #   GeneA     MYB
      #   GeneB     bHLH
      #
      tf: Metadata/TFs/AC.TF.csv

    # ── Sequence files (optional) ──────────────────────────────────
    # Standard FASTA format. The sequence ID (first word after ">")
    # must match gene IDs in your expression matrix.
    #
    # Example:
    #   >GeneA
    #   MSKLLVFAPG...
    #   >GeneB
    #   MDRTKQIENG...
    #
    sequences:
      protein: Metadata/fas/AC.protein.fas
      rna: Metadata/fas/AC.RNA.fas


  # ── Add more species below ──────────────────────────────────────
  # PS:
  #   name: "Papaver somniferum"
  #   matrix:
  #     raw: Matrices/PS.matrix.raw.counts.tsv
  #   sample_mapping: Sample_Mapping/PS_mapping.tsv
  #   ...
"""


@main.command()
@click.option(
    "-o", "--output", "output_path",
    default="config.yml",
    show_default=True,
    help="Path for the generated config file.",
)
@click.option("--force", is_flag=True, help="Overwrite existing file.")
def init(output_path: str, force: bool) -> None:
    """Generate a template config.yml with comments."""
    p = Path(output_path)
    if p.exists() and not force:
        click.echo(f"File already exists: {p}  (use --force to overwrite)", err=True)
        sys.exit(1)
    p.write_text(_TEMPLATE_CONFIG)
    click.echo(f"Template config written to: {p}")
    click.echo("Edit it to match your data and then run: genxprep validate config.yml")


# ======================================================================
# validate – dry-run validation
# ======================================================================

@main.command()
@click.argument("config", type=click.Path(exists=True, dir_okay=False))
@click.option("-v", "--verbose", is_flag=True, help="Show detailed info messages.")
def validate(config: str, verbose: bool) -> None:
    """Validate all input files without building H5AD.

    CONFIG is the path to your config.yml file.
    """
    reporter = Reporter(verbose=verbose)
    _run_validation(Path(config), reporter)

    reporter.print_all()
    reporter.print_summary()

    if reporter.has_errors:
        sys.exit(1)


# ======================================================================
# build – validate + build
# ======================================================================

@main.command()
@click.argument("config", type=click.Path(exists=True, dir_okay=False))
@click.option("-v", "--verbose", is_flag=True, help="Show detailed info messages.")
@click.option("--force", is_flag=True, help="Overwrite existing output files.")
def build(config: str, verbose: bool, force: bool) -> None:
    """Validate inputs and build H5AD files for GenXBrowser.

    CONFIG is the path to your config.yml file.
    """
    reporter = Reporter(verbose=verbose)
    cfg, species_data = _run_validation(Path(config), reporter)

    # Abort on errors
    if reporter.has_errors:
        reporter.print_all()
        reporter.print_summary()
        sys.exit(1)

    if cfg is None:
        reporter.print_all()
        reporter.print_summary()
        sys.exit(1)

    # Build phase
    reporter.section("Building H5AD files")

    from genxprep.builder import build_species
    from genxprep.exporter import (
        export_species,
        export_sequences,
        copy_gene_trees_file,
        write_frontend_config,
        write_docker_compose_snippet,
    )

    output_dir = cfg.output_dir
    if output_dir.exists() and not force:
        # Check if there are existing H5AD files
        existing = list(output_dir.glob("*/*_full.h5ad"))
        if existing:
            click.echo(
                f"\nOutput directory already contains {len(existing)} H5AD file(s).\n"
                "Use --force to overwrite, or choose a different output_dir.",
                err=True,
            )
            sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    ortho_df = species_data.get("_ortho_df")
    species_stats: dict[str, dict] = {}

    for code, sp in cfg.species.items():
        reporter.section(f"Species: {code} ({sp.name})")

        adata = build_species(sp, cfg.global_metadata, ortho_df, reporter)
        if adata is None:
            species_stats[code] = {"name": sp.name, "ok": False, "n_genes": 0, "n_samples": 0, "layers": []}
            continue

        h5ad_path = export_species(adata, sp, output_dir, reporter)
        export_sequences(sp, output_dir, reporter)

        species_stats[code] = {
            "name": sp.name,
            "ok": True,
            "n_genes": adata.n_vars,
            "n_samples": adata.n_obs,
            "layers": ["X"] + sorted(adata.layers.keys()),
        }

    # Global exports
    if cfg.global_metadata.gene_trees and cfg.global_metadata.gene_trees.exists():
        copy_gene_trees_file(cfg.global_metadata.gene_trees, output_dir, reporter)

    write_frontend_config(cfg, output_dir, reporter)
    write_docker_compose_snippet(output_dir, reporter)

    # Final summary
    reporter.print_all()
    reporter.print_species_table(species_stats)
    reporter.print_summary()

    if reporter.has_errors:
        sys.exit(1)

    reporter.console.print(
        f"\n[bold green]Done![/bold green] Output written to: [bold]{output_dir.resolve()}[/bold]\n\n"
        f"To start GenXBrowser with your data:\n"
        f"  [dim]cd /path/to/GenXBrowser[/dim]\n"
        f"  [bold]H5AD_DATA_DIR={output_dir.resolve()} docker compose up[/bold]\n"
    )


# ======================================================================
# Internal: shared validation logic
# ======================================================================

def _run_validation(
    config_path: Path,
    reporter: Reporter,
) -> tuple:
    """Run all validation steps.  Returns (ProjectConfig | None, data_dict)."""
    from genxprep.config import load_config
    from genxprep.validators.matrix import validate_matrix, get_gene_ids, get_sample_ids
    from genxprep.validators.sample_mapping import validate_sample_mapping
    from genxprep.validators.metrics import validate_metrics
    from genxprep.validators.orthogroups import validate_orthogroups
    from genxprep.validators.annotations import (
        validate_uniprot, validate_interpro, validate_pfam, validate_tf,
    )
    from genxprep.validators.sequences import validate_fasta
    from genxprep.validators.gene_trees import validate_gene_trees

    reporter.section("Loading configuration")
    cfg = load_config(config_path, reporter)
    if cfg is None:
        return None, {}

    data: dict = {}
    gene_id_sets: dict[str, set[str]] = {}
    sample_id_sets: dict[str, set[str]] = {}

    # ── Per-species validation ──
    for code, sp in cfg.species.items():
        reporter.section(f"Validating: {code} ({sp.name})")

        # Primary matrix
        primary_key, primary_path = sp.matrix.primary
        vr = reporter.new(f"{code} → {primary_key} matrix")
        df = validate_matrix(primary_path, f"{code} {primary_key}", vr)
        if df is not None:
            gene_id_sets[code] = get_gene_ids(df)
            sample_id_sets[code] = set(get_sample_ids(df))
        else:
            gene_id_sets[code] = set()
            sample_id_sets[code] = set()
            continue

        # Additional matrices
        for mat_key, mat_path in sp.matrix.available.items():
            if mat_key == primary_key:
                continue
            vr2 = reporter.new(f"{code} → {mat_key} matrix")
            validate_matrix(mat_path, f"{code} {mat_key}", vr2)

        gene_ids = gene_id_sets[code]
        sample_ids = sample_id_sets[code]

        # Sample mapping
        if sp.sample_mapping and sp.sample_mapping.exists():
            sm_vr = reporter.new(f"{code} → sample mapping")
            validate_sample_mapping(sp.sample_mapping, sample_ids, sm_vr)

        # Metrics
        if sp.metrics and sp.metrics.exists():
            met_vr = reporter.new(f"{code} → metrics")
            validate_metrics(sp.metrics, sample_ids, met_vr)

        # Annotations
        if sp.metadata.uniprot and sp.metadata.uniprot.exists():
            uni_vr = reporter.new(f"{code} → UniProt")
            validate_uniprot(sp.metadata.uniprot, gene_ids, uni_vr)

        if sp.metadata.interpro and sp.metadata.interpro.exists():
            ipr_vr = reporter.new(f"{code} → InterPro")
            validate_interpro(sp.metadata.interpro, gene_ids, ipr_vr)

        if sp.metadata.pfam and sp.metadata.pfam.exists():
            pfam_vr = reporter.new(f"{code} → Pfam")
            validate_pfam(sp.metadata.pfam, gene_ids, pfam_vr)

        if sp.metadata.tf and sp.metadata.tf.exists():
            tf_vr = reporter.new(f"{code} → TF")
            validate_tf(sp.metadata.tf, gene_ids, tf_vr)

        # Sequences
        if sp.sequences.protein and sp.sequences.protein.exists():
            seq_vr = reporter.new(f"{code} → protein FASTA")
            validate_fasta(sp.sequences.protein, gene_ids, f"{code} protein", seq_vr)

        if sp.sequences.rna and sp.sequences.rna.exists():
            seq_vr = reporter.new(f"{code} → RNA FASTA")
            validate_fasta(sp.sequences.rna, gene_ids, f"{code} RNA", seq_vr)

    # ── Global metadata ──
    reporter.section("Validating global metadata")

    ortho_df = None
    if cfg.global_metadata.orthogroups and cfg.global_metadata.orthogroups.exists():
        og_vr = reporter.new("Orthogroups")
        species_names = {code: sp.name for code, sp in cfg.species.items()}
        ortho_df = validate_orthogroups(
            cfg.global_metadata.orthogroups,
            species_names,
            gene_id_sets,
            og_vr,
        )
        data["_ortho_df"] = ortho_df

    # Gene trees
    orthogroup_ids: set[str] | None = None
    if ortho_df is not None:
        for c in ortho_df.columns:
            if c.lower().strip() == "orthogroup":
                orthogroup_ids = set(ortho_df[c].astype(str))
                break

    if cfg.global_metadata.gene_trees and cfg.global_metadata.gene_trees.exists():
        gt_vr = reporter.new("Gene trees")
        validate_gene_trees(cfg.global_metadata.gene_trees, orthogroup_ids, gt_vr)

    return cfg, data


if __name__ == "__main__":
    main()
