# GenXBrowser

**Interactive gene expression browser for comparative genomics.**

GenXBrowser visualizes gene expression data stored in AnnData (`.h5ad`) files. It provides a heatmap-based interface with advanced filtering, Gene Ontology (GO) enrichment analysis, phylogenetic tree visualization, and cross-species expression comparison.

## Architecture

```
GenXBrowser/
├── frontend/          Vue 3 + Vite + Tailwind CSS
├── backend/           Flask → serves H5AD data as REST API
│   └── h5ad_lib/      Inlined H5AD utility library (caching, config, GO)
├── prepare/           GenXPrep CLI for data preparation
└── LICENSE
```

| Layer | Technology | Port |
|-------|-----------|------|
| Frontend | Vue 3, Pinia, Plotly, D3, Tailwind CSS | 5173 (dev) |
| Backend  | Python 3.12, Flask | 5000 |
| Data     | AnnData `.h5ad` files | — |

## Quick Start

### 1. Install GenXPrep

```bash
cd prepare
conda env create -f environment.yml
conda activate genxprep
# OR: pip install -e .
```

### 2. Prepare Your Data

```bash
# Generate template config
genxprep init

# Edit config.yml to point to your data files

# Validate and build H5AD files
genxprep build config.yml
```

### 3. Run the App

```bash
genxprep app config.yml
```

This command automatically:
- Creates a conda environment for the backend (`genxbrowser-backend`)
- Installs all dependencies
- Configures and starts both backend and frontend
- Opens the app at **http://localhost:5173**

Press **Ctrl+C** to stop both services.

**For faster restarts** (skip dependency installation):
```bash
genxprep app config.yml --skip-setup
```

See [prepare/README.md](prepare/README.md) for detailed data preparation instructions.

## Configuration

GenXBrowser uses a JSON-based configuration system with auto-discovery. On first startup, the backend scans `H5AD_DATA_DIR` for `.h5ad` files and generates a `project_config.json` with:

- Discovered species (from `.uns` metadata in each H5AD file)
- Column definitions (inferred from `.var` and `.obs` DataFrames)
- Default frontend settings

Configuration can be managed at runtime through the **Admin Panel** (`/admin` route) or via the REST API.

The frontend loads its branding/display config from `frontend/public/genxbrowser_config.yaml` **at runtime** (not baked into the build).

### Frontend Config (`frontend/public/genxbrowser_config.yaml`)

```yaml
corporate_identity:
  company_name: "Your Organization"   # Displayed in sidebar/footer
  logo: your-logo.png                 # Logo file in public/ (PNG format)
  about: about.md                     # Markdown file in public/ for the About page
  llm_name: ""                        # Display name for LLM feature (optional)
  cc_by: ""                           # Creative Commons license short (e.g. "NC-SA")
access:
  data: true                          # Enable data access
  download: true                      # Enable data download/export
visualization:
  id_column: gene_id                  # Primary identifier column
  hide_columns:                       # Columns hidden from heatmap (saves RAM)
    - rna_seq
    - newick_str
```

### Environment Variables

Backend environment variables (automatically set by `genxprep app`):

| Variable | Default | Description |
|----------|---------|-------------|
| `H5AD_DATA_DIR` | — | Directory containing `.h5ad` files (required) |
| `PROJECT_CONFIG_PATH` | `<H5AD_DATA_DIR>/config/project_config.json` | Path to project config JSON |
| `FILTER_STORE_PATH` | `<H5AD_DATA_DIR>/filters` | Directory for shareable filter storage |
| `GO_OBO_PATH` | `<H5AD_DATA_DIR>/go-basic.obo` | Path to Gene Ontology OBO file |
| `GO_AUTO_DOWNLOAD` | `true` | Auto-download GO OBO if missing |
| `SPECIES_PHOTOS_DIR` | — | Directory containing species photos (optional) |
| `ADMIN_TOKEN` | — | Bearer token for admin API auth (disabled when unset) |
| `FLASK_DEBUG` | `true` | Enable debug mode for local development |

### Species Photos (Optional)

GenXBrowser supports displaying species photos in catalog cards. Photos are automatically matched to species using fuzzy name matching.

**Setup:**

1. **Prepare photos** — PNG, JPEG, or WebP files.
2. **Name photos** — Match species names (e.g., `capnoides_sempervirens.jpg` for "Capnoides sempervirens").
3. **Set the photos directory** — pass `SPECIES_PHOTOS_DIR` before running `genxprep app`:

```bash
export SPECIES_PHOTOS_DIR=/path/to/photos
genxprep app config.yml
```

**Display Modes:**

- **`circular`** (default) — 64×64px circular thumbnail left of species name
- **`watermark`** — Subtle grayscale watermark in top-right corner

**Fallback:** If no photo is found, a colored placeholder with species initials is generated automatically.

**Photo Requirements:**

- Supported formats: JPG, JPEG, PNG, GIF, WebP
- Naming: Lowercase, underscores (e.g., `species_name.jpg`)
- Recommended size: 256×256px minimum

### H5AD File Requirements

Each species dataset should be a single `.h5ad` file:

```
data/
├── AC/
│   └── AC_full.h5ad
├── AT/
│   └── AT_full.h5ad
└── config/
    └── project_config.json   # auto-generated
```

The `.h5ad` file should contain:
- **`.X`** — Expression matrix (genes × samples)
- **`.var`** — Gene metadata (index = gene IDs, columns = annotations)
- **`.obs`** — Sample metadata (index = sample IDs, columns = conditions/tissues)
- **`.uns`** — Unstructured data (species name, project info)
- **`.layers`** — Optional additional expression matrices (tpm, tmm, getmm, etc.)

## Features

- **Heatmap Visualization** — Interactive gene expression heatmaps with customizable color scales, z-score normalization, and hierarchical clustering
- **Catalog** — Browse and select multiple species/datasets for cross-species comparison
- **Advanced Filtering** — Filter genes by metadata columns (text, numeric, boolean, array) with URL-shareable filter states
- **GO Term Search** — Gene Ontology term lookup with autocomplete and hierarchy navigation
- **ORA (Over-Representation Analysis)** — Fisher's exact test with BH-FDR correction for enrichment analysis on filtered gene sets
- **Phylogenetic Trees** — Newick tree visualization for orthogroup gene families
- **Expression Comparison** — Side-by-side cross-species expression comparison (box plots via Plotly)
- **Sample Metadata** — Filter and color by sample-level metadata (tissue type, condition, etc.)
- **AI Assistant** — Optional in-app chat (`/api/assistant/*`) that reads the live UI state, runs read-only data tools (schema, counts, top groups, ORA digests) and proposes one-click filter / view changes or pre-configured deep-links. An **Auto-execute** toggle in the panel applies the proposed actions directly with an Undo step. See [backend/README.md](backend/README.md#ai-assistant) for the LLM environment variables.
- **Export** — Download filtered data as TSV, share filter states as short URLs, export heatmaps as PNG/PDF
- **Admin Panel** — Runtime configuration management, column visibility, species toggling

## API Endpoints

### Data API (`/api`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tables` | List available species/datasets |
| GET | `/api/setup` | Frontend readiness check |
| GET | `/api/columns` | Get column definitions |
| GET | `/api/column_bins` | Get column histogram bin edges |
| POST | `/api/data` | Query gene expression + metadata |
| POST | `/api/count` | Count rows + samples matching filters (returns `count`, `sample_count`, `total_samples`) |
| GET | `/api/col` | Get column data |
| POST | `/api/data/distinct` | Get distinct values for columns |
| GET | `/api/find` | Fuzzy gene search |
| GET | `/api/tags` | Get searchable tags |
| POST | `/api/id` | Store/retrieve filter state |
| GET | `/api/id/<hash>` | Retrieve stored filter state |
| GET | `/api/go/search` | Search GO terms |
| GET | `/api/go/term/<id>` | Get GO term details |
| POST | `/api/go/terms/batch` | Batch GO term lookup |
| GET | `/api/go/status` | GO service status |
| POST | `/api/ora` | Over-representation analysis |
| POST | `/api/cluster` | Server-side hierarchical clustering |
| POST | `/api/assistant/chat` | Streaming chat endpoint (SSE) for the AI assistant |
| GET | `/api/assistant/suggestions` | Dataset-grounded prompt suggestions (`?n=`, `?seed=`) |
| POST | `/api/assistant/deeplink` | Resolve a view + filter spec into a shareable URL |
| POST | `/api/assistant/compute` | Compute small derived statistics for the assistant |
| GET | `/api/species_photos/<filename>` | Serve species photo images |
| GET | `/health` | Health check |

### Admin API (`/api/admin`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/auth/check` | Check auth requirement and token validity |
| GET | `/api/admin/health` | Admin health check |
| GET/PUT | `/api/admin/config` | Get/update project configuration |
| POST | `/api/admin/config/reload` | Reload config from disk |
| GET | `/api/admin/config/profiles` | List saved config profiles |
| POST | `/api/admin/config/save-profile` | Save current config as a named profile |
| POST | `/api/admin/config/load-profile` | Load a saved config profile |
| POST | `/api/admin/restart` | Trigger backend restart |
| GET | `/api/admin/species` | List all species configs |
| PUT | `/api/admin/species/<code>` | Update species configuration |
| GET | `/api/admin/columns` | List column definitions |
| PUT | `/api/admin/columns/<name>` | Update column definition |
| GET/PUT | `/api/admin/frontend-settings` | Frontend display settings |
| GET | `/api/admin/datasets` | List datasets with status info |
| PATCH | `/api/admin/datasets/<code>/enabled` | Enable/disable dataset |
| POST | `/api/admin/metadata/import` | Validate metadata CSV for import |
| POST | `/api/admin/metadata/import/confirm` | Apply validated metadata import to H5AD |
| DELETE | `/api/admin/metadata/<column_name>` | Remove custom metadata column |

## Development

For manual backend/frontend development without `genxprep app`, see:
- [backend/README.md](backend/README.md) - Backend API documentation
- [frontend/README.md](frontend/README.md) - Frontend development guide

## License

MIT License — see [LICENSE](LICENSE) for details.
