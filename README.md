# GenXBrowser

**Interactive gene expression browser for comparative genomics.**

GenXBrowser visualizes gene expression data stored in AnnData (`.h5ad`) files. It provides a heatmap-based interface with advanced filtering, Gene Ontology (GO) enrichment analysis, phylogenetic tree visualization, and cross-species expression comparison.

## Architecture

```
GenXBrowser/
├── frontend/          Vue 3 + Vite + Tailwind CSS → served via Nginx
├── backend/           Flask + Gunicorn → serves H5AD data as REST API
│   └── h5ad_lib/      Inlined H5AD utility library (caching, config, GO)
├── docker-compose.yml Orchestrates both services
└── LICENSE
```

| Layer | Technology | Port |
|-------|-----------|------|
| Frontend | Vue 3, Pinia, Plotly, D3, Tailwind CSS | 80 (Nginx) |
| Backend  | Python 3.12, Flask, Gunicorn (gthread) | 5000 |
| Data     | AnnData `.h5ad` files | — |

The Nginx frontend reverse-proxies `/api/*` requests to the Flask backend.

## Quick Start

### Docker Compose (recommended)

```bash
# 1. Clone the repository
git clone https://github.com/Mfkessler/GenXBrowser.git
cd GenXBrowser

# 2. Place your .h5ad files in a data directory
#    Expected layout: data/<species_code>/<species_code>_full.h5ad

# 3. Start both services
H5AD_DATA_DIR=./data docker compose up -d --build

# 4. Open http://localhost in your browser
```

### Development Setup

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Set environment variables
export H5AD_DATA_DIR=/path/to/your/h5ad/data
export PROJECT_CONFIG_PATH=/path/to/config.json  # auto-generated if absent

# Run development server
python run.py
# Backend available at http://localhost:5000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
# Frontend available at http://localhost:5173
# API requests are proxied to http://backend:5000 (see vite.config.ts)
```

## Configuration

GenXBrowser uses a JSON-based configuration system with auto-discovery. On first startup, the backend scans `H5AD_DATA_DIR` for `.h5ad` files and generates a `project_config.json` with:

- Discovered species (from `.uns` metadata in each H5AD file)
- Column definitions (inferred from `.var` and `.obs` DataFrames)
- Default frontend settings

Configuration can be managed at runtime through the **Admin Panel** (`/admin` route) or via the REST API.

The frontend loads its branding/display config from `public/genxbrowser_config.yaml` **at runtime** (not baked into the build). For per-deployment customization, mount your own config and logo into the frontend container:

```yaml
# docker-compose.yml
frontend:
  volumes:
    - ./my_config.yaml:/usr/share/nginx/html/genxbrowser_config.yaml:ro
    - ./my_logo.png:/usr/share/nginx/html/my_logo.png:ro
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `H5AD_DATA_DIR` | — | Directory containing `.h5ad` files (required) |
| `PROJECT_CONFIG_PATH` | `<H5AD_DATA_DIR>/config/project_config.json` | Path to project config JSON |
| `FILTER_STORE_PATH` | `<H5AD_DATA_DIR>/filters` | Directory for shareable filter storage |
| `CACHE_MAX_SIZE_MB` | `2048` | LRU cache size for loaded AnnData objects |
| `GO_OBO_PATH` | `<H5AD_DATA_DIR>/go-basic.obo` | Path to Gene Ontology OBO file |
| `GO_AUTO_DOWNLOAD` | `true` | Auto-download GO OBO if missing |
| `GUNICORN_WORKERS` | `1` | Number of Gunicorn workers |
| `GUNICORN_THREADS` | `8` | Threads per worker (shares in-memory cache) |
| `GUNICORN_TIMEOUT` | `120` | Request timeout in seconds |
| `VITE_BASE_URL` | `/` | Base path for the app (build-time) |
| `VITE_API_BASE_URL` | `/api` | Frontend API base URL (build-time) |
| `VITE_DATA_TYPE` | `Genes` | Display label — `Genes` or `Isoforms` |
| `VITE_PHOTO_DISPLAY_MODE` | `circular` | Species photo display mode (`circular` or `watermark`) |
| `SPECIES_PHOTOS_DIR` | `/data/species_photos` | Directory containing species photos |

### Species Photos (Optional)

GenXBrowser supports displaying species photos in catalog cards. Photos are automatically matched to species using fuzzy name matching.

**Setup:**

1. **Prepare photos** — PNG, JPEG, or WebP files.
2. **Name photos** — Match species names (e.g., `capnoides_sempervirens.jpg` for "Capnoides sempervirens")
3. **Mount photos directory** — Add volume mount in your `docker-compose.yml`:

```yaml
services:
  backend:
    volumes:
      - ./photos:/data/species_photos:ro  # Backend serves photos
    environment:
      - SPECIES_PHOTOS_DIR=/data/species_photos
  
  frontend:
    build:
      args:
        VITE_PHOTO_DISPLAY_MODE: circular  # or "watermark"
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
| POST | `/api/count` | Count rows matching filters |
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
| GET | `/api/species_photos/<filename>` | Serve species photo images |
| GET | `/health` | Health check |

### Admin API (`/api/admin`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/health` | Admin health check |
| GET/PUT | `/api/admin/config` | Get/update project configuration |
| POST | `/api/admin/config/reload` | Reload config from disk |
| POST | `/api/admin/restart` | Trigger backend restart |
| GET | `/api/admin/species` | List all species configs |
| PUT | `/api/admin/species/<code>` | Update species configuration |
| GET | `/api/admin/columns` | List column definitions |
| PUT | `/api/admin/columns/<name>` | Update column definition |
| GET/PUT | `/api/admin/frontend-settings` | Frontend display settings |
| GET | `/api/admin/datasets` | List datasets with status info |
| PATCH | `/api/admin/datasets/<code>/enabled` | Enable/disable dataset |

## Build & Deployment

### Docker Build

```bash
# Build both images
docker compose build

# Build with custom settings
docker compose build --build-arg VITE_DATA_TYPE=Isoforms frontend
```

### Production Notes

- **Single Gunicorn worker** is recommended for small deployments (<10 users) — all threads share the same in-memory H5AD cache, avoiding redundant file loading
- The frontend build skips TypeScript checking (`npm run build-only`) for faster CI; run `npm run type-check` separately
- Nginx handles SPA routing (`try_files ... /index.html`), gzip compression, and reverse proxy to the backend

## License

MIT License — see [LICENSE](LICENSE) for details.
