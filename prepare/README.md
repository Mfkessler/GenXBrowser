# GenXPrep – Data Preparation for GenXBrowser

**GenXPrep** is a CLI tool that validates and converts your raw expression data into the H5AD format required by [GenXBrowser](../README.md). It is designed to be user-friendly — clear error messages guide you through fixing any data issues.

## Quick Start

### 1. Install

```bash
# Using conda (recommended)
cd prepare/
conda env create -f environment.yml
conda activate genxprep

# Or using pip
pip install -e .
```

### 2. Create a config file

```bash
genxprep init
```

This generates a `config.yml` template. Edit it to point to your data files.

### 3. Validate your data

```bash
genxprep validate config.yml
```

The tool checks every file for correctness and reports errors with suggestions.

### 4. Build H5AD files

```bash
genxprep build config.yml
```

This creates the `data/` directory with everything GenXBrowser needs.

### 5. Start GenXBrowser

```bash
cd /path/to/GenXBrowser
H5AD_DATA_DIR=/path/to/data docker compose up
```

---

## Input Data Overview

### Required (minimum)

| File | Description |
|------|-------------|
| **Count matrix** (TSV) | At least one expression matrix per species. Tab-separated, first column = gene IDs, remaining columns = sample IDs with numeric values. |

### Optional (improves the app)

| File | Description |
|------|-------------|
| TPM / TMM / geTMM matrix | Additional normalised expression matrices (same format as count matrix) |
| Sample mapping (TSV) | Columns: `Sample`, `tissue` — assigns tissue labels to samples |
| RNA-seq metrics (TSV) | Columns: `sample`, `assigned`, `pct unmapped`, `pct no_feature`, `pct trimmed` |
| Orthogroups (TSV) | `Orthogroup` column + one column per species with comma-separated gene IDs |
| Gene trees (TXT) | One line per tree: `OG_ID:newick_string` |
| UniProt annotations (TSV) | Columns: `ID`, `Description`, `Genename`, `GO`, `ECNumber`, etc. |
| InterPro (TSV) | No header, 3 columns: ID, IPR accession, description |
| Pfam (TSV) | No header, 3 columns: ID, PF accession, description |
| Transcription factors (TSV) | Columns: `Gene`, `Family` |
| Protein FASTA | Standard FASTA with gene IDs matching the count matrix |
| RNA FASTA | Standard FASTA with gene IDs matching the count matrix |

### Important: Gene IDs must be consistent

**All input files must use the same gene/transcript ID system.** If your count matrix uses IDs like `Aqcoe0008s0001.v3.1`, then your UniProt, InterPro, Pfam, TF, and FASTA files must also use those exact same IDs.

The tool will tell you when IDs don't match and show examples from both files.

---

## Config File Structure

```yaml
project:
  name: "My Project"           # Project name (shown in GenXBrowser)
  output_dir: ./data            # Where to write output files

global_metadata:                # Shared across all species (optional)
  orthogroups: path/to/Orthogroups.tsv
  gene_trees: path/to/Resolved_Gene_Trees.txt

species:
  AC:                           # Species code (2-10 uppercase letters)
    name: "Aquilegia coerulea"  # Full species name
    matrix:                     # At least ONE matrix is required
      raw: path/to/raw_counts.tsv
      tpm: path/to/tpm.tsv     # optional
      tmm: path/to/tmm.tsv     # optional
      getmm: path/to/getmm.tsv # optional
    sample_mapping: path/to/mapping.tsv   # optional
    metrics: path/to/metrics.tsv           # optional
    metadata:                              # all optional
      uniprot: path/to/uniprot.csv
      interpro: path/to/interpro.tsv
      pfam: path/to/pfam.tsv
      tf: path/to/tf.csv
    sequences:                             # optional
      protein: path/to/protein.fas
      rna: path/to/rna.fas
```

All paths are **relative to the config file's location**.

---

## Output Directory Structure

After running `genxprep build`, the output directory looks like this:

```
data/
├── AC/
│   └── AC_full.h5ad              ← Main data file per species
├── PS/
│   └── PS_full.h5ad
├── Metadata/
│   ├── fas/
│   │   ├── AC.protein.fas        ← Protein sequences
│   │   ├── AC.RNA.fas            ← RNA sequences
│   │   └── ...
│   └── Resolved_Gene_Trees.txt   ← Phylogenetic trees
├── genxbrowser_config.yaml       ← Frontend configuration
└── docker-compose.override.yml   ← Docker mount instructions
```

---

## CLI Reference

```
genxprep --help                  Show help
genxprep --version               Show version
genxprep init [-o FILE]          Generate template config.yml
genxprep validate CONFIG         Validate without building
genxprep build CONFIG [--force]  Validate + build + export
```

### Flags

| Flag | Description |
|------|-------------|
| `-v` / `--verbose` | Show detailed info messages (not just errors/warnings) |
| `--force` | Overwrite existing output files |
| `-o` / `--output` | Output path for `init` command (default: `config.yml`) |

---

## Troubleshooting

### "No gene IDs match"
Your annotation files use different IDs than your count matrix. All files must use the same ID system. Check the error message — it shows example IDs from both files.

### "File not found"
Check the file path in your `config.yml`. Paths are relative to the config file location.

### "Non-numeric values"
Your expression matrix contains text in data columns. Common cause: Excel auto-formatted gene names (e.g., `MARCH1` → `1-Mar`). Re-export from the original source as TSV.

### "Missing column"
A required column is missing or named differently. The error message lists available columns and the expected name.
