# GenXBrowser Backend

[![Python](https://img.shields.io/badge/Python-≥3.12-blue?logo=python&logoColor=gold)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)

Flask REST API that serves the GenXBrowser frontend directly from AnnData (`.h5ad`) files - no database, no ORM, no migrations. The data layer is the H5AD bundle emitted by [GenXPrep](../prepare/README.md); the backend is stateless apart from an in-process LRU cache of loaded `AnnData` objects.

## Tech Stack

- **Python 3.12** + **Flask 3.1** + **Flask-CORS** (development); **gunicorn 23** with the `gthread` worker class in production (see [gunicorn.conf.py](gunicorn.conf.py)).
- **AnnData ≥ 0.10** + **h5py ≥ 3.10** for H5AD access.
- **pandas ≥ 2.0**, **NumPy ≥ 1.24** for tabular operations.
- **SciPy ≥ 1.11** - Fisher's exact test (ORA) and hierarchical clustering.
- **Marshmallow ≥ 3.20** for request validation.
- **RapidFuzz ≥ 3.6** for fuzzy gene / tag search.
- **Pronto ≥ 2.5** for parsing `go-basic.obo`.

Single-worker / multi-thread is deliberate: every thread shares the same in-process H5AD cache. Multi-worker deployments multiply memory usage linearly and are only worth the trade-off behind an external cache.

## Data Ingestion Interface

The backend never writes to the data directory at runtime (apart from the auto-generated config and the filter-hash store). It expects exactly the layout produced by `genxprep build`:

```
$H5AD_DATA_DIR/
├── <SPECIES>/<SPECIES>_full.h5ad   # .X, .layers, .var, .obs, .uns
├── Metadata/
│   ├── fas/                        # protein / RNA FASTA (served by /sequences)
│   └── Resolved_Gene_Trees.txt     # newick gene trees (one per line: OG_ID:newick)
├── config/
│   └── project_config.json         # auto-generated on first launch
└── filters/                        # content-addressed filter hashes ($FILTER_STORE_PATH)
```

On first boot, `h5ad_lib.core.discovery` scans `$H5AD_DATA_DIR` for `.h5ad` files, infers species (from `.uns`) and column types (from `.var` / `.obs` dtypes), and writes `project_config.json`. Projects may set `default_trait_column` to any `.obs` sample metadata column; the frontend exposes that role as the `default_trait` pseudo-column for sample-axis colouring and ordering. The schema lives in [`app/config_schema.json`](app/config_schema.json); validation is handled by `h5ad_lib.config.schema`. All subsequent edits are made through the Admin API and the schema is re-validated on write.

H5AD invariants the backend relies on:

| Slot | Contents |
|---|---|
| `.X` | Primary expression matrix (genes × samples) |
| `.layers["tpm" \| "tmm" \| "getmm" \| …]` | Optional secondary matrices; surfaced via *Expression display* |
| `.var` | Gene metadata (index = gene ID) |
| `.obs` | Sample metadata (index = sample ID) |
| `.uns` | Species name, project name, free-form annotations |

Dynamic display names and the default trait role are managed through the Admin metadata editor.

## Development Workflow

```bash
cd backend/
conda create -n genxbrowser-backend python=3.12 -y
conda activate genxbrowser-backend
pip install -r requirements.txt

export H5AD_DATA_DIR=/absolute/path/to/prepare/data
export FLASK_DEBUG=true
python run.py            # Flask dev server on :5000 (host 0.0.0.0)
```

The full stack (this backend + the frontend + a sensible `H5AD_DATA_DIR`) starts in one command via [`genxprep app config.yml`](../prepare/README.md#-cli-reference).

### Tests

```bash
pip install pytest
pytest tests/            # unit + integration tests for filters, ORA, discovery, assistant
```

### Production

```bash
gunicorn -c gunicorn.conf.py "app:create_app()"
```

Tunable env vars (see [gunicorn.conf.py](gunicorn.conf.py)): `GUNICORN_BIND` (default `0.0.0.0:5000`), `GUNICORN_WORKERS` (default `1`), `GUNICORN_THREADS` (default `8`). The Dockerfile (`python:3.12-slim`, port `5000`, `HEALTHCHECK` on `/health`) wraps this exact command.

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `H5AD_DATA_DIR` | Directory containing the H5AD bundle | *(required)* |
| `PROJECT_CONFIG_PATH` | Project config JSON | `$H5AD_DATA_DIR/config/project_config.json` |
| `FILTER_STORE_PATH` | Content-addressed filter hashes | `$H5AD_DATA_DIR/filters` |
| `GENE_TREES_PATH` | Newick gene-tree file | `$H5AD_DATA_DIR/Metadata/Resolved_Gene_Trees.txt` |
| `CACHE_MAX_SIZE_MB` | LRU cache budget for `AnnData` objects | `2048` |
| `GO_OBO_PATH` | Gene Ontology OBO file | `$H5AD_DATA_DIR/go-basic.obo` |
| `GO_AUTO_DOWNLOAD` | Download OBO when missing | `true` |
| `SPECIES_PHOTOS_DIR` | Optional species thumbnails | *(unset)* |
| `ADMIN_TOKEN` | Bearer token gating `/api/admin/*` | *(unset → admin auth off)* |
| `FLASK_DEBUG` | Enable Flask debug mode | `false` |
| `PORT` | Dev-server port (`run.py`) | `5000` |
| `LLM_API_BASE` | OpenAI-compatible LLM endpoint for the AI assistant | *(unset → assistant disabled)* |
| `LLM_API_KEY` | LLM endpoint key | *(unset)* |
| `LLM_MODEL` | Primary model identifier | *(unset)* |
| `LLM_FALLBACK_MODEL` | Optional fallback model on primary failure | *(unset)* |

## API Surface

All endpoints are mounted via [`app/__init__.py`](app/__init__.py); `api_bp` lives in [`app/routes.py`](app/routes.py), `admin_bp` in [`app/admin_routes.py`](app/admin_routes.py), and the assistant routes are also registered from `routes.py` against [`app/assistant.py`](app/assistant.py).

### Data - `/api/*`

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/api/setup` | Frontend readiness check |
| `GET` | `/api/tables` | List available species/datasets (optional `?tags=`) |
| `GET` | `/api/columns` | Column metadata (`?table_name=`, `?meta=`, `?columns=`) |
| `GET` | `/api/column_bins` | Histogram bin edges for numeric columns |
| `POST` | `/api/data` | Gene expression + metadata query |
| `POST` | `/api/count` | `{count, sample_count, total_samples}` for `filters` + `sample_filters` |
| `GET` | `/api/col` | Unique values for a column |
| `POST` | `/api/data/distinct` | Validate values against column uniques |
| `GET` | `/api/find` | Fuzzy gene search |
| `GET` | `/api/tags` | Fuzzy tag search |
| `POST` | `/api/id` | Store a filter configuration (content-addressed hash) |
| `GET` | `/api/id/<hash>` | Retrieve a stored filter configuration |
| `GET` | `/api/gene_tree/<og_id>` | Newick gene tree by orthogroup |
| `GET` | `/api/species_photos/<filename>` | Serve a species photo (when `SPECIES_PHOTOS_DIR` is set) |

### Gene Ontology & ORA - `/api/go/*`, `/api/ora`, `/api/cluster`

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/go/search` | Search GO terms by name (`?q=`) |
| `GET` | `/api/go/term/<go_id>` | GO term details |
| `POST` | `/api/go/terms/batch` | Batch GO term lookup |
| `GET` | `/api/go/status` | GO service availability |
| `POST` | `/api/ora` | Over-Representation Analysis (Fisher's exact + BH-FDR) |
| `POST` | `/api/cluster` | Server-side hierarchical clustering |

### AI Assistant - `/api/assistant/*`

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/assistant/chat` | Streaming SSE chat with read-only tool calls over the loaded data |
| `GET` | `/api/assistant/suggestions` | Dataset-grounded prompt suggestions (`?n=`, `?seed=`) |
| `POST` | `/api/assistant/deeplink` | Resolve `(view, tables, filters, visualizations)` → `?id=` URL |
| `POST` | `/api/assistant/compute` | Compute small derived statistics (`top_orthogroups`, `top_tfs`, `summary_stats`) |

The assistant activates only when `LLM_API_BASE`, `LLM_API_KEY` and `LLM_MODEL` are set. Tools (`list_schema`, `list_view_settings`, `resolve_value`, `count_rows`, `top_groups`, `common_values`, `summary_stats`, `build_deeplink`, …) live in [`app/assistant_tools.py`](app/assistant_tools.py). `list_view_settings` is instance-aware: it returns only the expression-display options whose backing layer (`tpm`, `tmm`, `getmm`, …) is present in every selected H5AD file, so the model never picks a value the UI cannot offer. The visualization patch schema is strict - `.var` (gene) metadata may only appear in row annotation / row ordering / tooltip / ORA-column slots, and `.obs` (sample) metadata only in column annotation / grouping / column ordering / custom x-axis slots. Per-tool rate limits and a 32 000-character prompt cap are enforced in `routes.py`.

### Admin - `/api/admin/*`

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/admin/auth/check` | Reports whether `ADMIN_TOKEN` is set and whether the supplied token is valid |
| `GET` | `/api/admin/health` | Admin health check |
| `GET/PUT` | `/api/admin/config` | Read / replace the project config |
| `POST` | `/api/admin/config/reload` | Reload config from disk |
| `GET` | `/api/admin/config/profiles` | List saved config profiles |
| `POST` | `/api/admin/config/save-profile` | Save the current config as a named profile |
| `POST` | `/api/admin/config/load-profile` | Load a saved config profile |
| `POST` | `/api/admin/restart` | Trigger backend restart |
| `GET` | `/api/admin/species` | List all species configs |
| `PUT` | `/api/admin/species/<code>` | Update a species configuration |
| `GET` | `/api/admin/columns` | List column definitions |
| `PUT` | `/api/admin/columns/<name>` | Update a column definition |
| `GET` | `/api/admin/datasets` | Datasets + status info |
| `PATCH` | `/api/admin/datasets/<code>/enabled` | Toggle a dataset on/off |
| `POST` | `/api/admin/metadata/import` | Validate a metadata CSV against an H5AD |
| `POST` | `/api/admin/metadata/import/confirm` | Apply a validated metadata import |
| `DELETE` | `/api/admin/metadata/<column_name>` | Remove a custom metadata column |

### Example `POST /api/data`

```json
{
  "table_name": "AT",
  "columns": ["gene_id", "description", "sample_1", "sample_2"],
  "filters": {
    "go_term": ["GO:0005515"],
    "expression_col": {"type": "array", "values": [0, 100], "strict": false}
  },
  "limit": 1000,
  "offset": 0
}
```

## Project Structure

```
backend/
├── app/
│   ├── __init__.py            # Flask application factory
│   ├── routes.py              # /api + /api/assistant blueprints
│   ├── admin_routes.py        # /api/admin blueprint
│   ├── services.py            # Data access layer (AnnData loading, queries, gene trees)
│   ├── assistant.py           # SSE chat handler + LLM client
│   ├── assistant_tools.py     # Read-only tools callable by the LLM
│   ├── prompt_builder.py      # System prompt + tool catalogue assembly
│   ├── suggestions.py         # Data-grounded prompt suggestions
│   ├── overview.py            # Dataset overview statistics
│   ├── filter_parser.py       # Filter expression → AnnData mask
│   └── config_schema.json     # JSON Schema for project_config.json
├── h5ad_lib/                  # Inlined H5AD utility library
│   ├── config/{manager,schema}.py
│   ├── core/{discovery,loader,registry}.py
│   ├── filters/storage.py     # Content-addressed filter hash store
│   └── search/go_service.py   # Gene Ontology service (Pronto-backed)
├── tests/                     # pytest suite
├── requirements.txt
├── gunicorn.conf.py
├── run.py                     # Dev-server entry point
└── Dockerfile
```

## Performance Notes

- **Single-process, multi-threaded** by default - every thread shares the same H5AD LRU cache, so each file is read at most once per process lifetime.
- **Lazy loading** - species datasets are loaded on first request only.
- **Cache budget** - controlled by `CACHE_MAX_SIZE_MB` (default `2048`). Sized to the working set, not the total dataset.
