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
        self._ancestor_ids_cache: dict = {}
        
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
    
    def get_ancestor_ids(self, go_id: str) -> set:
        """
        Get all ancestor GO IDs (not including self).
        Uses cache for performance.
        
        Args:
            go_id: GO identifier
            
        Returns:
            Set of ancestor GO IDs
        """
        go_id = go_id.upper().strip()
        
        if go_id in self._ancestor_ids_cache:
            return self._ancestor_ids_cache[go_id]
        
        if not self.go_service or not self.go_service.is_available():
            return set()
        
        ancestors = self.go_service.get_ancestors(go_id)
        ancestor_ids = {a.get("id", "") for a in ancestors if a.get("id")}
        
        self._ancestor_ids_cache[go_id] = ancestor_ids
        return ancestor_ids
    
    def filter_to_most_specific(self, go_ids: list) -> tuple:
        """
        Filter GO terms to keep only the most specific ones.
        Removes any term that is an ancestor of another term in the list.
        
        This is the "topological filtering" - bottom-up approach.
        
        Args:
            go_ids: List of GO IDs for a single gene
            
        Returns:
            Tuple of (filtered_go_ids, removed_parent_ids)
        """
        if len(go_ids) <= 1:
            return (list(go_ids), [])
        
        go_ids_set = set(go_ids)
        removed_parents = set()
        
        # For each GO term, check if it's an ancestor of any other term
        for go_id in go_ids:
            ancestors = self.get_ancestor_ids(go_id)
            # Remove any ancestors that are in our set
            for ancestor in ancestors:
                if ancestor in go_ids_set:
                    removed_parents.add(ancestor)
        
        filtered = [g for g in go_ids if g not in removed_parents]
        return (filtered, list(removed_parents))
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "depth_cache_size": len(self._depth_cache),
            "ancestor_cache_size": len(self._ancestor_ids_cache)
        }


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
    else:
        logger.warning("GO service not available - GO term names will not be shown")
        app.go_hierarchy = None
    
    # Register routes
    register_routes(app)
    
    logger.info("H5AD Backend initialized (using h5ad-lib)")
    logger.info(f"Project: {app.config_manager.get_config().get('project_name', 'Unknown')}")
    logger.info(f"Data dir: {h5ad_dir}")
    logger.info(f"Species found: {app.h5ad_service.get_available_species()}")
    
    return app
