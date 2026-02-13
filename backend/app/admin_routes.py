"""
Admin Routes - Configuration Management
========================================
REST API endpoints for managing project configuration.

Endpoints:
- GET  /admin/config         - Get current configuration
- PUT  /admin/config         - Update configuration
- POST /admin/config/reload  - Reload configuration
- POST /admin/restart        - Trigger backend restart
- GET  /admin/health         - Admin health check
- GET  /admin/datasets       - Get all datasets with layer info
- PATCH /admin/datasets/{code}/layer - Update dataset layer preference
"""

from flask import Blueprint, jsonify, request, current_app
from marshmallow import Schema, fields
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


# ============================================================================
# Schemas
# ============================================================================

# ============================================================================
# Helper Functions
# ============================================================================

def get_config_manager():
    """Get config manager from app context."""
    return current_app.config_manager


def get_service():
    """Get H5AD service from app context."""
    return current_app.h5ad_service


# ============================================================================
# Endpoints
# ============================================================================

@admin_bp.route('/health', methods=['GET'])
def admin_health():
    """
    Health check for admin panel.
    
    Returns:
        Status of backend and configuration system
    """
    config_mgr = get_config_manager()
    config = config_mgr.get_config()
    
    return jsonify({
        "status": "healthy",
        "project_name": config.get('project_name', 'Unknown'),
        "version": config.get('version', '0.0.0'),
        "species_count": len(config.get('species', {})),
        "columns_count": len(config.get('column_definitions', {})),
        "config_path": str(config_mgr.config_path)
    })


@admin_bp.route('/config', methods=['GET'])
def get_config():
    """
    Get current project configuration with sorted column_definitions.
    
    Ensures columns are in same order as /api/columns (Genes tab order).
    
    Returns:
        Complete configuration as JSON
    """
    from collections import OrderedDict
    
    config_mgr = get_config_manager()
    h5ad_service = current_app.h5ad_service
    config = config_mgr.get_config()
    
    # Sort column_definitions to match /api/columns order
    if 'column_definitions' in config:
        # Get columns from service in display order
        api_columns = h5ad_service.get_all_columns(source="meta")
        api_columns_obs = h5ad_service.get_all_columns(source="column_meta")
        
        # Build ordered dict with corrected order values
        ordered_col_defs = OrderedDict()
        order_counter = 0
        
        # First: gene metadata columns in API order
        for col_info in api_columns:
            col_name = col_info['column_name']
            if col_name in config['column_definitions']:
                col_def = config['column_definitions'][col_name].copy()
                col_def['order'] = order_counter
                ordered_col_defs[col_name] = col_def
                order_counter += 1
        
        # Then: sample metadata columns in API order
        for col_info in api_columns_obs:
            col_name = col_info['column_name']
            if col_name in config['column_definitions']:
                col_def = config['column_definitions'][col_name].copy()
                col_def['order'] = order_counter
                ordered_col_defs[col_name] = col_def
                order_counter += 1
        
        # Finally: any remaining columns (shouldn't happen)
        for col_name, col_def in config['column_definitions'].items():
            if col_name not in ordered_col_defs:
                col_def_copy = col_def.copy()
                col_def_copy['order'] = order_counter
                ordered_col_defs[col_name] = col_def_copy
                order_counter += 1
        
        config['column_definitions'] = ordered_col_defs
    
    return jsonify({
        "success": True,
        "config": config
    })


@admin_bp.route('/config', methods=['PUT'])
def update_config():
    """
    Update project configuration.
    
    Request body:
        Full or partial configuration object
    
    Returns:
        Success status and updated config
    """
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "Request must be JSON"
        }), 400
    
    new_config = request.get_json()
    
    if not new_config:
        return jsonify({
            "success": False,
            "error": "Empty configuration"
        }), 400
    
    config_mgr = get_config_manager()
    
    # Validate and update
    try:
        # Merge with existing config if partial update
        if not all(key in new_config for key in ['project_name', 'species', 'column_definitions']):
            current = config_mgr.get_config()
            current.update(new_config)
            new_config = current
        
        success = config_mgr.update_config(new_config)
        
        if success:
            # Reload service with new config
            get_service().reload_config()
            
            return jsonify({
                "success": True,
                "message": "Configuration updated successfully",
                "config": new_config
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to save configuration"
            }), 500
    
    except Exception as e:
        logger.error(f"Config update failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@admin_bp.route('/config/reload', methods=['POST'])
def reload_config():
    """
    Reload configuration from file.
    
    Returns:
        Success status and reloaded config
    """
    try:
        config_mgr = get_config_manager()
        config_mgr.reload()
        
        # Reload service with new config
        get_service().reload_config()
        
        config = config_mgr.get_config()
        
        return jsonify({
            "success": True,
            "message": "Configuration reloaded successfully",
            "config": config
        })
    
    except Exception as e:
        logger.error(f"Config reload failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@admin_bp.route('/restart', methods=['POST'])
def restart_backend():
    """
    Trigger backend restart by touching a reload trigger file.
    
    Works with gunicorn's --reload option by modifying a watched file.
    More reliable than sending signals directly.
    
    Returns:
        Acknowledgment message
    """
    logger.info("Backend restart requested via admin API")
    
    try:
        # Touch the main app file to trigger gunicorn reload
        app_init_file = os.path.join(os.path.dirname(__file__), '__init__.py')
        Path(app_init_file).touch()
        
        return jsonify({
            "success": True,
            "message": "Restart triggered. Backend will reload within a few seconds."
        }), 200
        
    except Exception as e:
        logger.error(f"Restart trigger failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@admin_bp.route('/species', methods=['GET'])
def get_species():
    """
    Get all species configurations.
    
    Returns:
        Species dictionary
    """
    config_mgr = get_config_manager()
    species = config_mgr.get_species()
    
    return jsonify({
        "success": True,
        "species": species
    })


@admin_bp.route('/species/<code>', methods=['PUT'])
def update_species(code: str):
    """
    Update a specific species configuration.
    
    Args:
        code: Species code (e.g., 'AC', 'CS')
    
    Request body:
        Species configuration object
    
    Returns:
        Success status
    """
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "Request must be JSON"
        }), 400
    
    species_data = request.get_json()
    
    try:
        config_mgr = get_config_manager()
        config = config_mgr.get_config()
        
        if 'species' not in config:
            config['species'] = {}
        
        config['species'][code] = species_data
        config_mgr.update_config(config)
        
        return jsonify({
            "success": True,
            "message": f"Species {code} updated successfully"
        })
    
    except Exception as e:
        logger.error(f"Species update failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@admin_bp.route('/columns', methods=['GET'])
def get_columns():
    """
    Get all column definitions sorted in the same order as /api/columns.
    
    This ensures admin panel shows columns in same order as Genes tab.
    
    Returns:
        Column definitions dictionary (ordered)
    """
    from collections import OrderedDict
    
    config_mgr = get_config_manager()
    h5ad_service = current_app.h5ad_service
    
    # Get columns from /api/columns in their display order
    api_columns = h5ad_service.get_all_columns(source="meta")
    
    # Get column definitions from config
    column_defs = config_mgr.get_column_definitions()
    
    # Build ordered dict matching /api/columns order
    ordered_columns = OrderedDict()
    
    # First: add columns in API order (if they exist in config)
    for col_info in api_columns:
        col_name = col_info['column_name']
        if col_name in column_defs:
            ordered_columns[col_name] = column_defs[col_name]
    
    # Then: add any remaining columns from config (shouldn't happen, but just in case)
    for col_name, col_def in column_defs.items():
        if col_name not in ordered_columns and not col_def.get('is_sample_metadata', False):
            ordered_columns[col_name] = col_def
    
    return jsonify({
        "success": True,
        "columns": ordered_columns
    })


@admin_bp.route('/columns/<column_name>', methods=['PUT'])
def update_column(column_name: str):
    """
    Update a specific column definition.
    
    Args:
        column_name: Column name
    
    Request body:
        Column definition object
    
    Returns:
        Success status
    """
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "Request must be JSON"
        }), 400
    
    column_data = request.get_json()
    
    try:
        config_mgr = get_config_manager()
        config = config_mgr.get_config()
        
        if 'column_definitions' not in config:
            config['column_definitions'] = {}
        
        config['column_definitions'][column_name] = column_data
        config_mgr.update_config(config)
        
        return jsonify({
            "success": True,
            "message": f"Column {column_name} updated successfully"
        })
    
    except Exception as e:
        logger.error(f"Column update failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@admin_bp.route('/frontend-settings', methods=['GET'])
def get_frontend_settings():
    """
    Get frontend settings.
    
    Returns:
        Frontend settings object
    """
    config_mgr = get_config_manager()
    settings = config_mgr.get_frontend_settings()
    
    return jsonify({
        "success": True,
        "settings": settings
    })


@admin_bp.route('/frontend-settings', methods=['PUT'])
def update_frontend_settings():
    """
    Update frontend settings.
    
    Request body:
        Frontend settings object
    
    Returns:
        Success status
    """
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "Request must be JSON"
        }), 400
    
    settings_data = request.get_json()
    
    try:
        config_mgr = get_config_manager()
        config = config_mgr.get_config()
        config['frontend_settings'] = settings_data
        config_mgr.update_config(config)
        
        return jsonify({
            "success": True,
            "message": "Frontend settings updated successfully"
        })
    
    except Exception as e:
        logger.error(f"Frontend settings update failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@admin_bp.route('/datasets', methods=['GET'])
def get_datasets():
    """
    Get all datasets with their status information.
    
    Admin panel shows ALL species (including disabled) so they can be enabled/disabled.
    
    Returns:
        List of datasets with enabled status, names, and tags
    """
    config_mgr = get_config_manager()
    
    # Reload config to get latest state (in case it was modified by another process)
    config_mgr.reload()
    
    species_config = config_mgr.get_species()
    
    datasets = []
    for code, spec in species_config.items():
        # Include ALL species (even disabled ones) for admin management
        datasets.append({
            "code": code,
            "full_name": spec.get('full_name', code),
            "display_name": spec.get('display_name', code),
            "tags": spec.get('tags', []),
            "enabled": spec.get('enabled', True)
        })
    
    return jsonify({
        "success": True,
        "datasets": datasets
    })


@admin_bp.route('/datasets/<species_code>/enabled', methods=['PATCH'])
def toggle_species_enabled(species_code):
    """
    Toggle enabled/disabled status for a species.
    
    Request body:
        {
            "enabled": true/false
        }
    
    Returns:
        Success status with updated dataset info
    """
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "Request must be JSON"
        }), 400
    
    data = request.get_json()
    enabled = data.get('enabled')
    
    if enabled is None:
        return jsonify({
            "success": False,
            "error": "Missing 'enabled' field (must be true or false)"
        }), 400
    
    config_mgr = get_config_manager()
    species_config = config_mgr.get_species()
    
    if species_code not in species_config:
        return jsonify({
            "success": False,
            "error": f"Unknown species code: {species_code}"
        }), 404
    
    # Update enabled status
    old_status = species_config[species_code].get('enabled', True)
    success = config_mgr.update_species_field(species_code, 'enabled', enabled)
    
    if success:
        logger.info(f"Species {species_code} enabled status changed: {old_status} -> {enabled}")
        
        # If disabling, clear from cache
        if not enabled:
            h5ad_service = current_app.h5ad_service
            if hasattr(h5ad_service.registry, '_cache'):
                if species_code in h5ad_service.registry._cache._cache:
                    del h5ad_service.registry._cache._cache[species_code]
                    h5ad_service.registry._cache._access_order.remove(species_code)
                    logger.info(f"Cleared cache for disabled species {species_code}")
        
        return jsonify({
            "success": True,
            "message": f"Species {species_code} {'enabled' if enabled else 'disabled'}",
            "dataset": {
                "code": species_code,
                "enabled": enabled,
                "full_name": species_config[species_code].get('full_name', species_code)
            }
        })
    else:
        return jsonify({
            "success": False,
            "error": f"Failed to update enabled status for {species_code}"
        }), 500

