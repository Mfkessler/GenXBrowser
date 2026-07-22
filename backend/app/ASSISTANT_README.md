# GAIA Architecture

GAIA uses one native function-calling loop and exactly three public tools:

- `search_metadata`: resolve visible metadata columns, values, ontology terms, and registered UI controls.
- `compute_analytics`: count, rank, or summarize filtered data.
- `build_state_token`: validate and return the complete target UI state.

Every chat request contains:

- `INSTANCE_MANIFEST`: visible datasets, visible/filterable `.var` and `.obs` columns, views, controls, and actions.
- `LIVE_UI_STATE`: current route, selected datasets, filters, visualization state, and dataset visibility.

UI mutations are represented only by a fenced `state_token` block returned after a successful `build_state_token` call. The frontend parses and applies only `state_token`; there are no action blocks, regex intent paths, micro-tools, repair loops, compute endpoints, or assistant deeplink endpoints.

The Admin Panel schema is authoritative. Hidden columns are excluded from the manifest and rejected by all three tools. Display Names are used in prose; internal keys are used in payloads.