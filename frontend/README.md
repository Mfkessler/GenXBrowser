# GenXBrowser Frontend

[![Vue 3](https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vue.js&logoColor=white)](https://vuejs.org/)
[![Vite](https://img.shields.io/badge/Vite-7.x-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-4.x-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.8-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)

Vue 3 single-page application for the [GenXBrowser](../README.md) gene-expression browser. Talks to the Flask backend over `/api/*` (proxied by Vite in development, rewritten by nginx in production builds).

## Tech Stack

- **Vue 3.5** (`<script setup>` SFCs, Composition API) + **Pinia 3** for state.
- **Vue Router 4** with content-aware data-loading on `/h`, `/o`, `/c`, `/p` routes.
- **Vite 7** dev server + build tool; TypeScript 5.8 (`vue-tsc --build`).
- **Tailwind CSS 4** (via `@tailwindcss/vite`) with a custom `@theme` token block in `src/assets/main.css`.
- **Plotly.js (`plotly.js-dist-min` 3.x)** for the heatmap and box-plot visualisations.
- **D3 7** + the bundled `phylotree.js` for phylogenetic trees.
- **ml-hclust** for in-browser hierarchical clustering, with a dedicated `clustering.worker.ts` Web Worker.
- **Axios** HTTP, **lodash-es** (debounce/throttle), **yaml** for the runtime config, **marked** for the About page.
- **jsPDF + html2canvas-pro + JSZip** for PDF/PNG/ZIP exports.
- **ESLint 9** + Vitest 3 + Playwright 1.53 for lint, unit and E2E tests.

## Development Workflow

Prerequisite: Node ≥ 20 (the production Dockerfile uses `node:20-alpine`).

```bash
cd frontend/
npm install
npm run dev            # Vite dev server on :5173, HMR enabled
                       # /api/* is proxied to http://localhost:5000 - start the backend first
```

| Command | Purpose |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Type-checked production build (writes `dist/`) |
| `npm run build:check` | Parallel `vue-tsc --build` + `vite build` |
| `npm run build-only` | Production build without type-checking (matches the Dockerfile) |
| `npm run preview` | Serve the production build locally |
| `npm run type-check` | `vue-tsc --build` |
| `npm run lint` | ESLint with `--fix` |
| `npm run test:unit` | Vitest unit tests |
| `npm run test:e2e` | Playwright E2E (`e2e/`, see `playwright.config.ts`) |

For a one-shot launch that also starts the backend, use `genxprep app config.yml` from the [`prepare/`](../prepare/README.md) directory.

### Build-time Environment

The Dockerfile reads the following `VITE_*` build args:

| Arg | Default | Purpose |
|---|---|---|
| `VITE_BASE_URL` | `/` | Public base path for the SPA |
| `VITE_API_BASE_URL` | `/api` | Where the SPA sends API requests at runtime |
| `VITE_DATA_TYPE` | `Genes` | UI terminology - `Genes` or `Isoforms` |
| `VITE_ALLOWED_HOSTS` | `""` | Comma-separated allow-list; `localhost` and `127.0.0.1` are always included |

### Runtime Config - `public/genxbrowser_config.yaml`

Branding and feature toggles are fetched at runtime (not baked into the bundle), so a single build can be re-skinned per deployment. `genxprep build` emits this file alongside the H5AD bundle; in a containerised setup it is mounted into `/usr/share/nginx/html/genxbrowser_config.yaml`.

```yaml
corporate_identity:
  company_name: "Your Organization"
  logo:         your-logo.png       # file in public/
  about:        about.md            # rendered on /about
  llm_name:     ""                  # display name for the AI assistant
  cc_by:        ""                  # CC short code (e.g. "NC-SA")
access:
  data:     true
  download: true
visualization:
  id_column: gene_id
  hide_columns:                     # columns elided from the heatmap to save RAM
    - rna_seq
    - newick_str
```

## Routes

| Path | View | Purpose |
|---|---|---|
| `/` | `CatalogView` | Dataset browser / multi-select |
| `/about` | `AboutView` | Markdown rendered from `public/about.md` |
| `/admin` | `AdminView` | Runtime config editor (Admin API) |
| `/h/:table_names` | `HeatmapView` | Interactive heatmap |
| `/o/:table_names` | `OraView` | Over-Representation Analysis |
| `/c/:table_names` | `CompareExpression` | Cross-species box plots |
| `/p/:table_names` | `PhylogeneticTreeView` | Newick gene-tree viewer |

Data-bearing views (`/h`, `/o`, `/c`, `/p`) watch `route.query.id` and re-hydrate persisted filter / visualization state when the assistant or a share link points at a new hash.

## Directory Structure

```
frontend/
├── src/
│   ├── App.vue                  # Root layout (sidebar + router-view + footer)
│   ├── main.ts                  # Bootstraps the app + runtime config fetch
│   ├── router/index.ts          # Vue Router config (catalog, heatmap, ORA, …)
│   ├── views/                   # One component per top-level route
│   ├── components/              # Reusable UI (Heatmap, AssistantPanel, filters, modals…)
│   ├── stores/                  # Pinia stores
│   │   ├── assistant.ts         # AI chat state + action dispatch
│   │   ├── catalog.ts           # Dataset selection
│   │   ├── columns.ts           # Column definitions from /api/columns
│   │   ├── filters.ts           # Active filter state (gene + sample)
│   │   └── visualization.ts     # Heatmap / display settings
│   ├── shared/                  # Framework-agnostic helpers and types
│   │   ├── Config.ts            # API_BASE_URL + runtime config interface
│   │   ├── clustering.ts        # Hierarchical clustering entry point
│   │   ├── clustering.worker.ts # Web Worker variant
│   │   ├── Colorscales.ts       # Plotly colour-scale presets
│   │   ├── blast.ts             # NCBI BLAST link builder
│   │   ├── metadataDisplayNames.ts
│   │   ├── tooltipDirective.ts  # Custom v-tooltip
│   │   └── … (utility modules)
│   ├── utils/                   # Lower-level helpers
│   ├── types/plotly.d.ts        # Plotly ambient types
│   └── assets/
│       ├── main.css             # Tailwind entry + @theme tokens
│       └── phylotree.css
├── public/
│   ├── genxbrowser_config.yaml  # Runtime config (fetched on startup)
│   └── about.md                 # About-page content
├── e2e/                         # Playwright specs
├── vite.config.ts               # Dev proxy: /api → http://localhost:5000
├── vite.config.local.ts         # Local-only overrides
├── nginx.conf                   # Used by the production image
├── Dockerfile                   # Node-20 build → nginx:stable-alpine
└── package.json
```

## AI Assistant Integration

When the backend exposes `/api/assistant/*` (see [backend/README.md](../backend/README.md)), the SPA renders a slide-in chat panel ([`AssistantPanel.vue`](src/components/AssistantPanel.vue), state in [`stores/assistant.ts`](src/stores/assistant.ts)). Every message ships the live UI context (`view`, `selected_table_names`, `filters`, `visualizations`, analysis digests). Streamed responses carry typed action blocks (`add_filter`, `viz_update`, `select_tables`, `set_expression_display`, `deeplink`, …) that the panel turns into one-click chips with Undo; an **Auto-execute** toggle (persisted in `localStorage` under `genx.assistant.autoExecute`) applies them automatically when streaming completes. Empty-state prompts come from `/api/assistant/suggestions` and refresh via the panel's **Shuffle** button. The Heatmap and ORA views also probe `/api/count` per dataset and hide species that fall entirely outside the active filters.
