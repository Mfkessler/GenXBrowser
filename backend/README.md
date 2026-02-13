# GenXBrowser Backend

[![Python 3.12+](https://img.shields.io/badge/Python-≥3.12-blue?logo=python&logoColor=gold)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](../LICENSE)

> Backend API for [GenXBrowser](../README.md) — serving gene expression data from AnnData H5AD files.

A high-performance Flask backend for gene expression analysis that serves comparative transcriptomics data directly from AnnData H5AD files, eliminating the need for database infrastructure.

## Overview

This backend implements a RESTful API for accessing multi-species gene expression data stored in H5AD format. It provides efficient data retrieval through in-memory caching, Gene Ontology services, Over-Representation Analysis (ORA), hierarchical clustering, and complex filtering on gene metadata and expression matrices.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Nginx (Frontend)                         │
│              Reverse-proxies /api/* → backend               │
└─────────────────────┬────────────────┬──────────────────────┘
                      │                │
              /api/*  │        /       │  (static SPA)
                      ▼                ▼
┌──────────────────────────┐  ┌────────────────────────┐
│  Backend                 │  │  Vue Frontend          │
│  Flask + Gunicorn        │  │  Static Assets         │
│  (gthread worker)        │  │                        │
└───────────┬──────────────┘  └────────────────────────┘
            │
            ▼
┌──────────────────────────┐
│  H5AD Files (read-only)  │
│  /data/                  │
│   ├── AC/AC_full.h5ad    │
│   ├── AT/AT_full.h5ad    │
│   └── config/            │
│       └── project_config │
└──────────────────────────┘
```

## Quick Start

### Docker (via root docker-compose.yml)

```bash
cd ..  # GenXBrowser root
docker compose up -d --build
```

### Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export H5AD_DATA_DIR=/path/to/your/h5ad/data
python run.py
# Backend available at http://localhost:5000
```

## API Endpoints

### Data API (`/api`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check (root level) |
| `GET` | `/api/setup` | Frontend readiness check |
| `GET` | `/api/tables` | List available species/datasets (optional `?tags=`) |
| `GET` | `/api/columns` | Column metadata (`?table_name=`, `?meta=`, `?columns=`) |
| `GET` | `/api/column_bins` | Histogram bin edges for numeric columns |
| `POST` | `/api/count` | Filtered row count |
| `POST` | `/api/data` | Query gene expression + metadata |
| `GET` | `/api/col` | Unique values for a column |
| `POST` | `/api/data/distinct` | Validate values against column uniques |
| `GET` | `/api/find` | Fuzzy gene search |
| `GET` | `/api/tags` | Fuzzy tag search |
| `POST` | `/api/id` | Store filter configuration (content-addressed hash) |
| `GET` | `/api/id/<hash>` | Retrieve stored filter configuration |
| `GET` | `/gene_tree/<og_id>` | Newick gene tree by orthogroup (root level) |

### Gene Ontology & ORA (`/api/go`, `/api/ora`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/go/search` | Search GO terms by name (`?q=`) |
| `GET` | `/api/go/term/<go_id>` | GO term details |
| `POST` | `/api/go/terms/batch` | Batch GO term lookup |
| `GET` | `/api/go/status` | GO service availability |
| `POST` | `/api/ora` | Over-Representation Analysis (Fisher's exact + BH-FDR) |
| `POST` | `/api/cluster` | Server-side hierarchical clustering |

### Admin API (`/api/admin`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/health` | Admin health check |
| `GET/PUT` | `/api/admin/config` | Get/update project configuration |
| `POST` | `/api/admin/config/reload` | Reload config from disk |
| `POST` | `/api/admin/restart` | Trigger backend restart |
| `GET` | `/api/admin/species` | List all species configs |
| `PUT` | `/api/admin/species/<code>` | Update species configuration |
| `GET` | `/api/admin/columns` | List column definitions |
| `PUT` | `/api/admin/columns/<name>` | Update column definition |
| `GET/PUT` | `/api/admin/frontend-settings` | Frontend display settings |
| `GET` | `/api/admin/datasets` | List datasets with status info |
| `PATCH` | `/api/admin/datasets/<code>/enabled` | Enable/disable dataset |

### Example Data Query

```json
POST /api/data
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

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `H5AD_DATA_DIR` | Directory containing `.h5ad` files | — (required) |
| `PROJECT_CONFIG_PATH` | Path to project config JSON | `<H5AD_DATA_DIR>/config/project_config.json` |
| `FILTER_STORE_PATH` | Directory for shareable filter storage | `<H5AD_DATA_DIR>/filters` |
| `CACHE_MAX_SIZE_MB` | LRU cache size in MB | `2048` |
| `GO_OBO_PATH` | Path to Gene Ontology OBO file | `<H5AD_DATA_DIR>/go-basic.obo` |
| `GO_AUTO_DOWNLOAD` | Auto-download GO OBO if missing | `true` |
| `GUNICORN_WORKERS` | Number of Gunicorn workers | `1` |
| `GUNICORN_THREADS` | Threads per worker | `8` |
| `GUNICORN_TIMEOUT` | Request timeout in seconds | `120` |

### Auto-Discovery

On first startup, the backend scans `H5AD_DATA_DIR` for `.h5ad` files and generates a `project_config.json` with discovered species, column definitions, and default settings. Configuration can be managed at runtime through the Admin API.

## Project Structure

```
backend/
├── app/
│   ├── __init__.py            # Flask application factory
│   ├── routes.py              # Main API endpoint definitions
│   ├── admin_routes.py        # Admin CRUD API
│   ├── services.py            # Core data access layer
│   ├── module_enrichment.py   # WGCNA module color enrichment
│   └── config_schema.json     # JSON Schema for project config
├── h5ad_lib/                  # Inlined H5AD utility library
│   ├── config/                # Configuration management
│   │   ├── manager.py         # ConfigManager
│   │   └── schema.py          # Config validation
│   ├── core/                  # Core data operations
│   │   ├── discovery.py       # H5AD file auto-discovery
│   │   ├── loader.py          # AnnData file loading
│   │   └── registry.py        # Species registry
│   ├── filters/
│   │   └── storage.py         # Content-addressed filter storage
│   └── search/
│       └── go_service.py      # Gene Ontology service (OBO parsing)
├── Dockerfile
├── gunicorn.conf.py           # Production server settings
├── requirements.txt
└── run.py                     # Application entry point
```

## Core Dependencies

- **Flask + Flask-CORS**: Web framework
- **Gunicorn**: Production WSGI server (gthread worker)
- **AnnData + h5py**: H5AD file format support
- **Pandas / NumPy**: Data manipulation
- **SciPy**: ORA (Fisher's exact test) and hierarchical clustering
- **RapidFuzz**: Fuzzy string matching
- **Marshmallow**: Request/response validation
- **Pronto**: Gene Ontology OBO parsing

## Performance

- **Single worker + multiple threads**: All threads share the same in-memory H5AD cache, avoiding redundant file loading (recommended for <10 concurrent users)
- **LRU Cache**: Configurable memory limit for loaded AnnData objects
- **Lazy Loading**: Species datasets loaded on first request only
- **Direct File Access**: Reads H5AD files directly — no database needed
