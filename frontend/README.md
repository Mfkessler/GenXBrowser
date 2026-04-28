# GenXBrowser Frontend

> Vue.js frontend for the [GenXBrowser](../README.md) gene expression browser.

[![Vue 3](https://img.shields.io/badge/Vue-3.x-4FC08D?logo=vue.js&logoColor=white)](https://vuejs.org/)
[![Vite](https://img.shields.io/badge/Vite-7.x-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-4.x-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)

---

## Quick Start

### Via GenXPrep (Recommended)

```bash
cd ../prepare
genxprep app config.yml
```

This automatically sets up and starts the frontend along with the backend.

### Manual Development

```bash
npm install
npm run dev
# Frontend available at http://localhost:5173
# API requests are proxied to http://localhost:5000
```

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server with HMR |
| `npm run build` | Build for production |
| `npm run build:check` | Type-check + build in parallel |
| `npm run build-only` | Build without type-checking |
| `npm run preview` | Preview production build |
| `npm run test:unit` | Run unit tests (Vitest) |
| `npm run type-check` | TypeScript type checking (`vue-tsc`) |
| `npm run lint` | Lint and auto-fix with ESLint |

## Views / Routes

| Route | View | Description |
|-------|------|-------------|
| `/` | CatalogView | Browse and select species/datasets |
| `/about` | AboutView | About page (rendered from `public/about.md`) |
| `/admin` | AdminView | Runtime configuration panel |
| `/h/:table_names` | HeatmapView | Interactive gene expression heatmap |
| `/o/:table_names` | OraView | Over-Representation Analysis results |
| `/c/:table_names` | CompareExpression | Cross-species expression comparison (box plots) |
| `/p/:table_names` | PhylogeneticTreeView | Newick gene tree visualization |

## Configuration

### AI Assistant

When the backend exposes the assistant endpoints (see [backend/README.md](../backend/README.md#ai-assistant)), the frontend renders a slide-in chat panel via [`AssistantPanel.vue`](src/components/AssistantPanel.vue) (state in [`stores/assistant.ts`](src/stores/assistant.ts)).

- The panel sends the live UI context (`view`, `selected_table_names`, `filters`, `visualizations`, optional analysis digests) on every message, so the model always reflects where the user is right now.
- Backend responses include typed action blocks (`add_filter`, `viz_update`, `select_tables`, `set_expression_display`, `deeplink`, …) which the panel turns into one-click chips with an Undo step.
- An **Auto-execute** toggle in the panel header (persisted in `localStorage` under `genx.assistant.autoExecute`) applies actions — including deep-link navigation — directly when streaming completes, without requiring per-action confirmation.
- Data-bearing views (`/h`, `/c`, `/o`, `/p`) watch `route.query.id` and re-load the persisted filter / visualization state whenever the assistant points to a new hash on the same path, so re-runs (e.g. orthogroup ORA → GO ORA) refresh the view automatically.

### Frontend Config (`public/genxbrowser_config.yaml`)

Controls branding, feature access, and visualization settings. The config is loaded **at runtime** (not baked into the build):

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

### Assets

- **`src/assets/main.css`** — Tailwind CSS entry point with custom color theme
- **`public/`** — Static assets served as-is (logo, about.md, favicon)

The `main.css` file must import Tailwind and define the color theme:

```css
@import "tailwindcss";
@plugin '@tailwindcss/typography';

@theme {
  --color-primary-100: #e4f6b2;
  --color-primary-300: #cfea83;
  --color-primary-500: #a6c550;
  --color-primary-700: #85a52e;
  --color-primary-900: #628010;
  --color-accent1-100: #f7b3bc;
  --color-accent1-300: #eb8492;
  --color-accent1-500: #c65060;
  --color-accent1-700: #a62e3f;
  --color-accent1-900: #80101f;
  --color-accent2-100: #b195c9;
  --color-accent2-300: #8862a6;
  --color-accent2-500: #693e8c;
  --color-accent2-700: #522675;
  --color-accent2-900: #39115b;
}
```

## Project Structure

```
frontend/
├── src/
│   ├── App.vue                 # Root layout (sidebar + router-view + footer)
│   ├── main.ts                 # App entry point
│   ├── assets/
│   │   ├── main.css            # Tailwind + custom theme
│   │   └── phylotree.css       # Phylogenetic tree styles
│   ├── components/             # Reusable Vue components
│   │   ├── HeatmapComponent    # Core heatmap (Plotly.js)
│   │   ├── AssistantPanel      # AI assistant chat (SSE + action chips, optional)
│   │   ├── CatalogComponent    # Dataset browser with CatalogEntry cards
│   │   ├── SidebarComponent    # Navigation sidebar
│   │   ├── OraComponent        # ORA results display
│   │   ├── PhylogeneticTree    # Newick tree (D3 + phylotree)
│   │   ├── Compare             # Expression comparison (box plots)
│   │   ├── VisualizationSettings # Heatmap display settings (layers, scales)
│   │   ├── SettingsOverlay     # Settings panel overlay
│   │   ├── *Filter components  # Numeric, Text, Boolean, Search filters
│   │   ├── ExportModal         # TSV/PNG/PDF export
│   │   ├── ShareOverlay        # URL-based filter sharing
│   │   ├── BatchInputModal     # Batch gene ID input/validation
│   │   ├── DataManagerModal    # Data management dialog
│   │   ├── BlastWarningModal   # NCBI BLAST redirect warning
│   │   ├── OverlayTable        # Tabular overlay for gene details
│   │   ├── AnalysisCard        # Analysis type selection card
│   │   ├── LoadingOverlay      # Loading animation overlay
│   │   ├── CheckboxSelector    # Checkbox-based multi-select
│   │   ├── DropdownMenu        # Reusable dropdown menu
│   │   ├── CollapseWrapper     # Collapsible section wrapper
│   │   ├── ToggleSwitch        # Toggle switch component
│   │   ├── SortToggleButton    # Column sort toggle
│   │   ├── InfoTooltip         # Info icon with tooltip
│   │   └── ...                 # Modals, tooltips, empty states
│   ├── stores/                 # Pinia state management
│   │   ├── assistant.ts        # AI assistant chat state + action dispatch
│   │   ├── catalog.ts          # Dataset catalog state
│   │   ├── columns.ts          # Column definitions
│   │   ├── filters.ts          # Active filter state
│   │   └── visualization.ts    # Heatmap/display settings
│   ├── shared/                 # Utilities and type definitions
│   │   ├── Config.ts           # Config interface + API_BASE_URL
│   │   ├── ExpressionDisplay.ts # Expression display mode types
│   │   ├── MetaFormat.ts       # Metadata formatting utilities
│   │   ├── RowType.ts          # Row type definitions
│   │   ├── CatalogMeta.ts      # Catalog metadata types
│   │   ├── OverlayConfig.ts    # Overlay configuration types
│   │   ├── Colorscales.ts      # Color scale definitions
│   │   ├── colorMapping.ts     # Color scale utilities
│   │   ├── blast.ts            # NCBI BLAST integration
│   │   ├── clustering.ts       # Clustering logic
│   │   ├── clustering.worker.ts # Web worker for clustering
│   │   ├── useClustering.ts    # Clustering composable
│   │   ├── useFilterSeparation.ts # Filter separation composable
│   │   ├── utils.ts            # Shared helpers (label formatting)
│   │   ├── dataTypeLabels.ts   # Gene/Isoform terminology labels
│   │   ├── metadataDisplayNames.ts # Metadata display name mappings
│   │   ├── tooltipDirective.ts # Custom Vue tooltip directive
│   │   └── ccByMappings.ts     # Creative Commons license mappings
│   ├── types/
│   │   └── plotly.d.ts         # Plotly type declarations
│   ├── router/index.ts         # Vue Router configuration
│   └── views/                  # Page-level view components
├── public/
│   ├── genxbrowser_config.yaml # Frontend configuration (loaded at runtime)
│   └── about.md                # About page content (Markdown)
├── vite.config.ts              # Vite configuration
├── package.json
└── tsconfig.json
```

## Key Dependencies

- **Vue 3 + Pinia** — Reactive UI framework + state management
- **Vue Router** — Client-side routing
- **Vite 7** — Build tool and dev server
- **Tailwind CSS 4** — Utility-first CSS
- **Plotly.js** — Interactive heatmaps and box plots
- **D3 + phylotree** — Phylogenetic tree visualization
- **Axios** — HTTP client for API communication
- **ml-hclust** — Client-side hierarchical clustering
- **jsPDF + html2canvas-pro + JSZip** — Export (PDF, PNG, ZIP)
- **marked** — Markdown rendering (About page)
- **Floating UI** — Tooltip and popover positioning
- **lodash-es** — Utility functions (debounce, throttle)
- **yaml** — YAML config file parsing

## IDE Setup

[VSCode](https://code.visualstudio.com/) + [Vue - Official](https://marketplace.visualstudio.com/items?itemName=Vue.volar) extension (replaces Vetur).

`vue-tsc` is used instead of `tsc` for type checking `.vue` files.
