"""
GenXBrowser H5AD Backend
========================
Minimal Flask backend for serving gene expression data from H5AD files.
Uses h5ad-lib for core functionality.
"""

import os
import logging
import urllib.request
from flask import Flask
from flask_cors import CORS

# h5ad-lib imports
from h5ad_lib.config.manager import ConfigManager
from h5ad_lib.search.go_service import GOService

from .routes import register_routes
from .services import GenXBrowserService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_go_obo(target_path: str) -> bool:
    """
    Download GO OBO file with proper User-Agent to avoid 403 errors.
    
    Args:
        target_path: Where to save the downloaded file
        
    Returns:
        True if successful, False otherwise
    """
    GO_OBO_URL = "http://purl.obolibrary.org/obo/go/go-basic.obo"
    
    try:
        logger.info(f"Downloading GO ontology from {GO_OBO_URL}...")
        
        # Create request with proper User-Agent
        request = urllib.request.Request(
            GO_OBO_URL,
            headers={
                'User-Agent': 'GenXBrowser/1.0 (https://github.com/GenXBrowser; research use)'
            }
        )
        
        # Ensure target directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Download with progress logging
        with urllib.request.urlopen(request, timeout=120) as response:
            total_size = response.headers.get('Content-Length')
            if total_size:
                logger.info(f"GO OBO file size: {int(total_size) / 1024 / 1024:.1f} MB")
            
            with open(target_path, 'wb') as f:
                chunk_size = 8192
                downloaded = 0
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
        logger.info(f"Successfully downloaded GO OBO to {target_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to download GO OBO: {e}")
        return False


class GOHierarchyHelper:
    """
    Helper class for GO hierarchy operations with caching.
    Provides depth calculation (shortest path to root) and ancestor lookups.
    """
    
    def __init__(self, go_service):
        self.go_service = go_service
        self._depth_cache: dict = {}
        
    def get_depth(self, go_id: str) -> int:
        """
        Get depth of GO term (shortest path to root).
        Root terms (biological_process, molecular_function, cellular_component) have depth 0.
        
        Args:
            go_id: GO identifier (e.g., "GO:0009908")
            
        Returns:
            Depth as integer (0 = root, higher = more specific)
        """
        go_id = go_id.upper().strip()
        
        if go_id in self._depth_cache:
            return self._depth_cache[go_id]
        
        if not self.go_service or not self.go_service.is_available():
            return -1
        
        # BFS to find shortest path to root
        depth = self._calculate_depth_bfs(go_id)
        self._depth_cache[go_id] = depth
        return depth
    
    def _calculate_depth_bfs(self, go_id: str) -> int:
        """Calculate depth using BFS (shortest path)."""
        from collections import deque
        
        # Root GO terms
        root_ids = {"GO:0008150", "GO:0003674", "GO:0005575"}  # BP, MF, CC
        
        if go_id in root_ids:
            return 0
        
        visited = {go_id}
        queue = deque([(go_id, 0)])
        
        while queue:
            current_id, current_depth = queue.popleft()
            
            # Get parents
            parents = self.go_service.get_parents(current_id)
            
            for parent in parents:
                parent_id = parent.get("id", "")
                if not parent_id:
                    continue
                
                if parent_id in root_ids:
                    depth = current_depth + 1
                    return depth
                
                if parent_id not in visited:
                    visited.add(parent_id)
                    queue.append((parent_id, current_depth + 1))
        
        # If no path to root found (shouldn't happen), return -1
        return -1
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "depth_cache_size": len(self._depth_cache),
        }


DEFAULT_LLM_SYSTEM_PROMPT = (
    "You are the GenXBrowser scientific assistant. You help biologists explore "
    "gene expression datasets loaded into the current GenXBrowser instance. "
    "Answer questions precisely using only the dataset schema and summary "
    "statistics provided in the CURRENT_DATA_CONTEXT. The USER_UI_CONTEXT "
    "describes the view the user is currently looking at (route, active "
    "tables, filters, visualization settings). Honour that context — when the "
    "user says 'this heatmap' or 'the current selection', they mean the view "
    "described there.\n\n"
    "Format all replies as concise Markdown. Use **bold** for gene IDs / "
    "species names, bullet lists for enumerations, and short code blocks for "
    "identifiers. Never fabricate gene IDs, orthogroup IDs, species, or "
    "metadata columns; if information is not in the context, say so plainly.\n\n"
    "ACTIONS: When the user asks you to *do* something in the UI, emit one "
    "single fenced JSON block per action. Each block has a language tag naming "
    "the action kind and a JSON body. Prefer the most specific kind:\n\n"
    "1) Navigate to another view (deep-link). Use this only when the user is "
    "not already in the view they need. `tables` accepts species full names, "
    "codes, or raw table_names; the backend normalises them.\n"
    "```deeplink\n{\"view\": \"heatmap|compare|phylo|ora|catalog\", "
    "\"tables\": [\"<code or full name>\"], \"filters\": {\"<column>\": {\"value\": \"<v>\", "
    "\"strict\": false, \"empty\": false}}, \"visualizations\": {...}}\n```\n\n"
    "2) Update visualization settings on the CURRENT view (no navigation). "
    "Call list_view_settings first. The `patch` object is validated against "
    "strict UI schemas; row/.var metadata such as Orthogroup/ortho_id may "
    "only be used for row annotations/order/tooltips/ORA columns, never "
    "column-axis structures.\n"
    "```viz_update\n{\"patch\": {\"rowSideColors\": [\"ortho_id\"], "
    "\"colorScale\": \"Viridis\"}}\n```\n\n"
    "3) Add / replace a sidebar filter on the CURRENT view. `column` is the "
    "exact metadata column name; `value` is a string (comma-separated for "
    "multi-value). Set `strict: true` for exact match, `empty: true` to match "
    "empty cells.\n"
    "```add_filter\n{\"column\": \"<column>\", \"value\": \"<value>\", "
    "\"strict\": false, \"empty\": false}\n```\n\n"
    "4) Remove a single sidebar filter:\n"
    "```remove_filter\n{\"column\": \"<column>\"}\n```\n\n"
    "5) Clear all sidebar filters:\n"
    "```clear_filters\n{}\n```\n\n"
    "6) Ask the backend to compute a derived statistic on the CURRENT view. "
    "`tables` and `filters` default to the user's current context; you usually "
    "don't need to set them.\n"
    "```compute\n{\"op\": \"top_orthogroups|top_tfs|summary_stats\", "
    "\"args\": {\"top_k\": 10}}\n```\n\n"
    "Rules:\n"
    "- Emit at most one action per message unless the user clearly requests "
    "several independent steps.\n"
    "- Prefer viz_update / add_filter over a deeplink when the user is "
    "already in the target view.\n"
    "- Before answering a quantitative question over the CURRENT filtered "
    "data (e.g. 'which orthogroup is most represented?'), emit a "
    "```compute``` block first, then interpret the numerical result in your "
    "reply."
)


def _seed_llm_config_from_env(config_manager) -> None:
    """Populate llm_config defaults from environment variables if unset.

    Honors LLM_API_BASE, LLM_API_KEY, LLM_MODEL, LLM_FALLBACK_MODEL. The
    assistant is marked enabled iff both api_base and api_key resolve to a
    non-empty value after merging env + persisted config.
    """
    try:
        cfg = config_manager.get_config()
        existing = dict(cfg.get("llm_config") or {})

        env_base = os.environ.get("LLM_API_BASE", "").strip()
        env_key = os.environ.get("LLM_API_KEY", "").strip()
        env_model = os.environ.get("LLM_MODEL", "").strip()
        env_fallback = os.environ.get("LLM_FALLBACK_MODEL", "").strip()

        seeded = {
            "enabled": existing.get("enabled", False),
            "api_base": existing.get("api_base") or env_base,
            "api_key": existing.get("api_key") or env_key,
            "model": existing.get("model") or env_model,
            "fallback_model": existing.get("fallback_model") or env_fallback,
            "system_prompt": existing.get("system_prompt") or DEFAULT_LLM_SYSTEM_PROMPT,
            "request_timeout_s": int(existing.get("request_timeout_s") or 60),
            "max_tokens": int(existing.get("max_tokens") or 1024),
            "temperature": float(existing.get("temperature") if existing.get("temperature") is not None else 0.2),
        }

        # Auto-enable on first boot when env vars fully configure the endpoint.
        if "enabled" not in existing and seeded["api_base"] and seeded["api_key"]:
            seeded["enabled"] = True

        if seeded != existing:
            cfg["llm_config"] = seeded
            config_manager.update_config(cfg)
            logger.info(
                "Seeded llm_config (enabled=%s, model=%s, fallback=%s, base=%s)",
                seeded["enabled"], seeded["model"], seeded["fallback_model"],
                seeded["api_base"] or "<unset>",
            )
    except Exception as e:
        logger.warning(f"LLM config seeding failed: {e}")


def _prewarm_ai_assistant(app) -> None:
    """Best-effort warmup for assistant examples and tool caches."""
    if os.environ.get('ASSISTANT_WARMUP', 'true').lower() in {'0', 'false', 'no', 'off'}:
        logger.info("AI assistant warmup disabled by ASSISTANT_WARMUP")
        return

    import time

    started = time.perf_counter()
    try:
        with app.app_context():
            from . import assistant_tools
            from .suggestions import build_suggestion_pool, generate_suggestions

            service = app.h5ad_service
            cm = app.config_manager

            pool = build_suggestion_pool(service, cm)
            for seed in (0, 1, 2):
                generate_suggestions(service, cm, n=10, seed=seed)

            schema = assistant_tools.tool_list_schema(service, cm, max_values_per_col=0)
            species = [str(s) for s in (pool.get("species") or []) if s]
            if not species:
                species = [
                    str(t.get("code") or t.get("table_name"))
                    for t in schema.get("tables", [])
                    if t.get("code") or t.get("table_name")
                ]

            sample_filters = []
            if pool.get("tf_family"):
                sample_filters.append(("var_filters", "tf_family", pool["tf_family"][0]))
            if pool.get("ortho_id"):
                sample_filters.append(("var_filters", "ortho_id", pool["ortho_id"][0]))
            if pool.get("tissue"):
                sample_filters.append(("obs_filters", "tissue", pool["tissue"][0]))

            # One resolve_value call builds the reusable per-table value counters.
            for _axis, _column, value in sample_filters[:1]:
                assistant_tools.tool_resolve_value(service, query=str(value), tables=species, max_hits=3)

            # These calls warm the filtered count path used by deeplink guards.
            for axis, column, value in sample_filters:
                kwargs = {axis: {column: {"value": str(value), "match_mode": "or", "exact": True}}}
                assistant_tools.tool_count_rows(service, tables=species, **kwargs)

            elapsed = time.perf_counter() - started
            logger.info(
                "AI assistant warmup complete in %.2fs (species=%d, filters=%d)",
                elapsed,
                len(species),
                len(sample_filters),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI assistant warmup failed: %s", exc, exc_info=True)


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.json.sort_keys = False
    
    # CORS
    CORS(app, origins=os.environ.get('CORS_ORIGINS', '*').split(','))
    
    # Get configuration paths from environment
    h5ad_dir = os.environ.get('H5AD_DATA_DIR', '/data/prepared')
    config_path = os.environ.get('PROJECT_CONFIG_PATH', '/data/config/project_config.json')
    
    # Initialize h5ad-lib ConfigManager
    app.config_manager = ConfigManager(
        config_path=config_path,
        h5ad_dir=h5ad_dir,
    )
    
    # Initialize GenXBrowser service (wrapper over h5ad-lib)
    app.h5ad_service = GenXBrowserService(app.config_manager)
    try:
        from . import assistant_tools
        warm = assistant_tools.warmup_runtime_cache(app.h5ad_service, app.config_manager)
        logger.info(
            "Assistant warmup cached %d dataset(s), %d var column(s), %d obs column(s)",
            len(warm.get("datasets", [])),
            len(warm.get("structural_columns", {}).get("var", [])),
            len(warm.get("structural_columns", {}).get("obs", [])),
        )
    except Exception as e:
        logger.warning("Assistant warmup skipped: %s", e)

    # Seed LLM assistant configuration from environment variables on first boot.
    # Persisted values in project_config.json take precedence once the admin
    # panel has written them; env vars only fill missing fields.
    _seed_llm_config_from_env(app.config_manager)
    
    # Initialize GO service from h5ad-lib
    go_obo_path = os.environ.get('GO_OBO_PATH', '/data/go-basic.obo')
    go_auto_download = os.environ.get('GO_AUTO_DOWNLOAD', 'true').lower() == 'true'
    
    logger.info("Initializing GO service...")
    
    # Check if local file exists
    if os.path.exists(go_obo_path):
        logger.info(f"Using local GO OBO file: {go_obo_path}")
        app.go_service = GOService(obo_path=go_obo_path, auto_download=False)
    elif go_auto_download:
        # Try to download with our custom function (handles User-Agent issues)
        logger.info("GO OBO file not found, attempting download...")
        if download_go_obo(go_obo_path):
            logger.info(f"Loading downloaded GO OBO from {go_obo_path}")
            app.go_service = GOService(obo_path=go_obo_path, auto_download=False)
        else:
            # Fallback: try h5ad-lib's built-in download (might fail with 403)
            logger.warning("Custom download failed, trying h5ad-lib fallback...")
            app.go_service = GOService(obo_path=None, auto_download=True)
    else:
        logger.warning("GO service disabled (no local file and auto-download disabled)")
        app.go_service = GOService(obo_path=None, auto_download=False)
    
    if app.go_service.is_available():
        logger.info(f"GO service ready with {len(app.go_service.go_index)} terms")
        # Initialize GO hierarchy helper with caching
        app.go_hierarchy = GOHierarchyHelper(app.go_service)
        logger.info("GO hierarchy helper initialized")

        # Pre-warm the dataset's unique go_terms cache in the background so
        # the first `search_go_terms` tool call returns immediately instead
        # of paying the H5AD scan cost on the user's critical path. The
        # service caches the result, so a single warmup call is enough.
        import threading as _threading
        def _prewarm_go_terms():
            try:
                vals = app.h5ad_service.get_unique_values('go_terms')
                logger.info("Pre-warmed go_terms cache: %d unique IDs", len(vals))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Pre-warm of go_terms cache failed: %s", exc)

        _threading.Thread(target=_prewarm_go_terms, daemon=True).start()
    else:
        logger.warning("GO service not available - GO term names will not be shown")
        app.go_hierarchy = None

    # Pre-compute global histogram bins in background so sliders are usable before
    # any dataset is selected, and after every config/metadata refresh.
    import threading
    threading.Thread(target=app.h5ad_service.precompute_global_bins, daemon=True).start()
    logger.info("Started background global bin precomputation")

    threading.Thread(target=_prewarm_ai_assistant, args=(app,), daemon=True).start()
    logger.info("Started AI assistant warmup")

    # Register routes
    register_routes(app)

    logger.info("H5AD Backend initialized (using h5ad-lib)")
    logger.info(f"Project: {app.config_manager.get_config().get('project_name', 'Unknown')}")
    logger.info(f"Data dir: {h5ad_dir}")
    logger.info(f"Species found: {app.h5ad_service.get_available_species()}")
    
    return app
