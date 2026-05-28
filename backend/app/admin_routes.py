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
- POST /admin/metadata/import          - Validate metadata import
- POST /admin/metadata/import/confirm  - Confirm and apply metadata import
- DELETE /admin/metadata/<column_name>  - Remove metadata column
- GET  /admin/config/profiles          - List config profiles
- POST /admin/config/save-profile      - Save current config as profile
- POST /admin/config/load-profile      - Load a config profile
"""

from flask import Blueprint, jsonify, request, current_app
from marshmallow import Schema, fields
from functools import wraps
import logging
import os
import io
import csv
import numpy as np
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


# ============================================================================
# Auth
# ============================================================================

def require_admin_token(f):
    """
    Decorator to require admin token for protected endpoints.
    
    If ADMIN_TOKEN env var is not set, auth is disabled (local dev).
    Token is passed via Authorization: Bearer <token> header.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        admin_token = os.environ.get('ADMIN_TOKEN', '').strip()
        if not admin_token:
            # No token configured = auth disabled
            return f(*args, **kwargs)
        
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({
                "success": False,
                "error": "Authentication required"
            }), 401
        
        provided_token = auth_header[7:].strip()
        if provided_token != admin_token:
            return jsonify({
                "success": False,
                "error": "Invalid admin token"
            }), 403
        
        return f(*args, **kwargs)
    return decorated


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

@admin_bp.route('/auth/check', methods=['GET'])
def check_auth():
    """
    Check if admin token auth is enabled and validate provided token.
    """
    admin_token = os.environ.get('ADMIN_TOKEN', '').strip()
    if not admin_token:
        return jsonify({"success": True, "auth_required": False})
    
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer ') and auth_header[7:].strip() == admin_token:
        return jsonify({"success": True, "auth_required": True, "authenticated": True})
    
    return jsonify({"success": True, "auth_required": True, "authenticated": False})


@admin_bp.route('/llm/test', methods=['POST'])
@require_admin_token
def llm_test():
    """Probe the configured LLM endpoint (or a candidate one from the body).

    Body may contain partial overrides ``{api_base, api_key, model, fallback_model,
    temperature, max_tokens, request_timeout_s}``. If ``api_key`` is omitted or
    equals the redacted placeholder, the stored key is used. Never echoes the
    key back to the caller.
    """
    from . import assistant as _assistant
    config_mgr = get_config_manager()
    stored = config_mgr.get_config().get('llm_config') or {}
    body = request.get_json(silent=True) or {}
    merged = _assistant.merge_llm_config_update(stored, body or {})

    result = _assistant.test_connection(merged)
    status = 200 if result.get("ok") else 502
    return jsonify(result), status


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
    Get current project configuration.

    Returns column_definitions sorted by their saved 'order' field, so the
    admin panel always reflects the last-saved user ordering.

    The ``llm_config.api_key`` field is always redacted to a placeholder so
    the secret never leaves the backend; empty/placeholder values submitted
    in a subsequent PUT preserve the stored key.

    Returns:
        Complete configuration as JSON
    """
    from . import assistant as _assistant
    config_mgr = get_config_manager()
    config = config_mgr.get_config()

    # Sort column_definitions by saved 'order' field (preserves user drag-order)
    if 'column_definitions' in config:
        sorted_defs = dict(
            sorted(
                config['column_definitions'].items(),
                key=lambda kv: (kv[1].get('order', 9999), kv[0])
            )
        )
        config['column_definitions'] = sorted_defs

    # Always redact the LLM API key on read.
    if 'llm_config' in config and config['llm_config']:
        config['llm_config'] = _assistant.redact_llm_config(config['llm_config'])

    return jsonify({
        "success": True,
        "config": config
    })


@admin_bp.route('/config', methods=['PUT'])
@require_admin_token
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

        # Never let a redacted/empty api_key overwrite the stored secret.
        if 'llm_config' in new_config:
            from . import assistant as _assistant
            stored = config_mgr.get_config().get('llm_config') or {}
            new_config['llm_config'] = _assistant.merge_llm_config_update(
                stored, new_config['llm_config'] or {}
            )

        success = config_mgr.update_config(new_config)
        
        if success:
            # Reload service with new config
            get_service().reload_config()

            # Invalidate landing overview cache so next /api/overview reflects changes.
            try:
                from . import overview as _overview
                _overview.invalidate_cache()
            except Exception:
                pass
            try:
                from . import assistant_tools as _assistant_tools
                _assistant_tools.invalidate_runtime_cache()
                _assistant_tools.warmup_runtime_cache(get_service(), config_mgr)
            except Exception:
                pass

            # Redact api_key in the echo response.
            response_config = dict(new_config)
            if 'llm_config' in response_config and response_config['llm_config']:
                from . import assistant as _assistant
                response_config['llm_config'] = _assistant.redact_llm_config(response_config['llm_config'])

            return jsonify({
                "success": True,
                "message": "Configuration updated successfully",
                "config": response_config
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
@require_admin_token
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
        try:
            from . import assistant_tools as _assistant_tools
            _assistant_tools.invalidate_runtime_cache()
            _assistant_tools.warmup_runtime_cache(get_service(), config_mgr)
        except Exception:
            pass
        
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
@require_admin_token
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
@require_admin_token
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
    Get all column definitions sorted by saved 'order' field.

    Returns:
        Column definitions dictionary (ordered by user-defined order)
    """
    config_mgr = get_config_manager()
    column_defs = config_mgr.get_column_definitions()

    ordered = dict(
        sorted(
            column_defs.items(),
            key=lambda kv: (kv[1].get('order', 9999), kv[0])
        )
    )

    return jsonify({
        "success": True,
        "columns": ordered
    })


@admin_bp.route('/columns/<column_name>', methods=['PUT'])
@require_admin_token
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
        get_service().reload_config()
        try:
            from . import assistant_tools as _assistant_tools
            _assistant_tools.invalidate_runtime_cache()
            _assistant_tools.warmup_runtime_cache(get_service(), config_mgr)
        except Exception:
            pass
        
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
@require_admin_token
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


# ============================================================================
# Metadata Import Endpoints
# ============================================================================

import re as _re

def _parse_rows(data_str: str, separator: str) -> list:
    """Parse delimited data string into a list of rows (list of lists).
    Supports '\\s+' as a special sentinel for splitting on any whitespace."""
    if separator == '\\s+' or separator == r'\s+':
        return [
            _re.split(r'\s+', line.strip())
            for line in data_str.strip().splitlines()
            if line.strip()
        ]
    reader = csv.reader(io.StringIO(data_str.strip()), delimiter=separator)
    return list(reader)


@admin_bp.route('/metadata/import', methods=['POST'])
@require_admin_token
def validate_metadata_import():
    """
    Validate a metadata import (TSV data with ID + value columns).
    
    Request body:
        {
            "dataset": "AC",           // Species code
            "target": "var" | "obs",   // Gene (.var) or Sample (.obs) metadata
            "column_name": "my_col",   // Column name in config
            "display_name": "My Column", // Human-readable name
            "data": "ID\\tValue\\ngene1\\t42\\n...",  // TSV string
            "separator": "\\t"         // Optional, default is tab
        }
    
    Returns:
        Validation result with match statistics
    """
    if not request.is_json:
        return jsonify({"success": False, "error": "Request must be JSON"}), 400
    
    body = request.get_json()
    dataset = body.get('dataset')
    target = body.get('target')  # "var" or "obs"
    column_name = body.get('column_name', '').strip()
    display_name = body.get('display_name', '').strip()
    data_str = body.get('data', '')
    separator = body.get('separator', '\t')
    id_column = body.get('id_column')   # column name or None
    value_column = body.get('value_column')  # column name or None

    # Validation
    if not dataset:
        return jsonify({"success": False, "error": "Missing 'dataset' (species code)"}), 400
    if target not in ('var', 'obs'):
        return jsonify({"success": False, "error": "'target' must be 'var' or 'obs'"}), 400
    if not column_name:
        return jsonify({"success": False, "error": "Missing 'column_name'"}), 400
    if not data_str.strip():
        return jsonify({"success": False, "error": "Missing 'data' (TSV content)"}), 400
    
    config_mgr = get_config_manager()
    existing_cols = config_mgr.get_column_definitions()
    existing_def = existing_cols.get(column_name)
    if existing_def:
        existing_target = 'obs' if existing_def.get('is_sample_metadata', False) else 'var'
        if existing_target != target:
            return jsonify({
                "success": False,
                "error": f"Column '{column_name}' already exists for .{existing_target}. Choose a different name or import into .{existing_target}."
            }), 400

    legacy_axis_conflict = False
    try:
        service = get_service()
        adata = service.registry.load(dataset)
        if adata is not None:
            axis = adata.var if target == 'var' else adata.obs
            legacy_axis_conflict = column_name in axis.columns and column_name not in existing_cols
    except Exception:
        legacy_axis_conflict = False

    if legacy_axis_conflict:
        return jsonify({
            "success": False,
            "error": f"Column '{column_name}' exists in the H5AD file but is not registered in the Admin metadata configuration. Add it to the metadata configuration before updating it."
        }), 400
    
    try:
        # Parse TSV data
        rows = _parse_rows(data_str, separator)
        
        header = rows[0]
        if len(header) < 2:
            return jsonify({
                "success": False,
                "error": f"Expected at least 2 columns (ID + value), got {len(header)}"
            }), 400

        # Resolve id_col / value_col indices from column names (or default to 0/1)
        if id_column and id_column in header:
            id_idx = header.index(id_column)
        else:
            id_idx = 0
        if value_column and value_column in header:
            val_idx = header.index(value_column)
        else:
            val_idx = 1 if id_idx != 1 else 0

        if id_idx == val_idx:
            return jsonify({"success": False, "error": "ID column and value column must be different"}), 400

        # Parse into dict: ID -> value
        data_dict = {}
        for row in rows[1:]:
            if len(row) > max(id_idx, val_idx):
                data_dict[row[id_idx].strip()] = row[val_idx].strip()

        if not data_dict:
            return jsonify({"success": False, "error": "No valid data rows found"}), 400
        
        # Load dataset and compare IDs
        service = get_service()
        adata = service.registry.load(dataset)
        
        if adata is None:
            return jsonify({"success": False, "error": f"Dataset '{dataset}' not found or failed to load"}), 404
        
        if target == 'var':
            existing_ids = set(adata.var.index.astype(str))
        else:
            existing_ids = set(adata.obs.index.astype(str))
        
        provided_ids = set(data_dict.keys())
        matched_ids = provided_ids & existing_ids
        unmatched_ids = provided_ids - existing_ids
        missing_ids = existing_ids - provided_ids
        
        # Infer type from values
        from h5ad_lib.config.schema import ColumnTypeInference
        type_inference = ColumnTypeInference()
        
        # Try to infer if numeric
        sample_values = list(data_dict.values())[:100]
        inferred_type = "text"
        try:
            [float(v) for v in sample_values if v]
            # Check if all integers
            if all(float(v) == int(float(v)) for v in sample_values if v):
                inferred_type = "bigint"
            else:
                inferred_type = "double precision"
        except (ValueError, TypeError):
            # Check boolean
            bool_values = {"true", "false", "1", "0", "yes", "no"}
            if all(v.lower() in bool_values for v in sample_values if v):
                inferred_type = "boolean"
        
        return jsonify({
            "success": True,
            "validation": {
                "total_provided": len(data_dict),
                "total_existing": len(existing_ids),
                "matched": len(matched_ids),
                "unmatched": len(unmatched_ids),
                "missing_in_data": len(missing_ids),
                "unmatched_ids": sorted(list(unmatched_ids))[:50],  # Cap at 50
                "type_inferred": inferred_type,
                "header": header,
                "sample_values": sample_values[:5],
            }
        })
    
    except Exception as e:
        logger.error(f"Metadata import validation failed: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/metadata/import/confirm', methods=['POST'])
@require_admin_token
def confirm_metadata_import():
    """
    Confirm and apply metadata import.
    
    Request body:
        {
            "dataset": "AC",
            "target": "var" | "obs",
            "column_name": "my_col",
            "display_name": "My Column",
            "data": "ID\\tValue\\n...",
            "separator": "\\t",
            "type_override": "text",        // Optional override for inferred type
            "persist_to_h5ad": false,        // If true, writes to .h5ad file
            "apply_to_all_datasets": false   // If true, applies to all species where IDs match
        }
    
    Returns:
        Success status with applied metadata info
    """
    if not request.is_json:
        return jsonify({"success": False, "error": "Request must be JSON"}), 400
    
    body = request.get_json()
    dataset = body.get('dataset')
    target = body.get('target')
    column_name = body.get('column_name', '').strip()
    display_name = body.get('display_name', '').strip()
    data_str = body.get('data', '')
    separator = body.get('separator', '\t')
    type_override = body.get('type_override')
    persist = body.get('persist_to_h5ad', False)
    apply_all = body.get('apply_to_all_datasets', False)
    id_column = body.get('id_column')
    value_column = body.get('value_column')

    if not all([dataset, target, column_name, data_str]):
        return jsonify({"success": False, "error": "Missing required fields"}), 400

    try:
        # Parse data
        rows = _parse_rows(data_str, separator)
        header = rows[0]

        # Resolve id/value column indices
        if id_column and id_column in header:
            id_idx = header.index(id_column)
        else:
            id_idx = 0
        if value_column and value_column in header:
            val_idx = header.index(value_column)
        else:
            val_idx = 1 if id_idx != 1 else 0

        data_dict = {}
        for row in rows[1:]:
            if len(row) > max(id_idx, val_idx):
                data_dict[row[id_idx].strip()] = row[val_idx].strip()
        
        config_mgr = get_config_manager()
        existing_cols = config_mgr.get_column_definitions()
        existing_def = existing_cols.get(column_name, {})
        existing_target = 'obs' if existing_def.get('is_sample_metadata', False) else 'var'
        if existing_def and existing_target != target:
            return jsonify({
                "success": False,
                "error": f"Column '{column_name}' already exists for .{existing_target}. Choose a different name or import into .{existing_target}."
            }), 400

        # Determine type
        inferred_type = type_override or existing_def.get("type") or "text"
        if not type_override:
            sample_values = list(data_dict.values())[:100]
            try:
                [float(v) for v in sample_values if v]
                if all(float(v) == int(float(v)) for v in sample_values if v):
                    inferred_type = "bigint"
                else:
                    inferred_type = "double precision"
            except (ValueError, TypeError):
                bool_values = {"true", "false", "1", "0", "yes", "no"}
                if all(v.lower() in bool_values for v in sample_values if v):
                    inferred_type = "boolean"
        
        service = get_service()
        
        # Determine datasets to apply to
        datasets_to_apply = [dataset]
        if apply_all:
            species = config_mgr.get_species()
            datasets_to_apply = [code for code, spec in species.items() if spec.get('enabled', True)]
        
        results = {}
        for ds_code in datasets_to_apply:
            try:
                adata = service.registry.load(ds_code)
                if adata is None:
                    results[ds_code] = {"status": "skip", "reason": "Not loaded"}
                    continue
                
                if target == 'var':
                    existing_ids = set(adata.var.index.astype(str))
                else:
                    existing_ids = set(adata.obs.index.astype(str))
                
                axis_df = adata.var if target == 'var' else adata.obs
                column_exists = column_name in axis_df.columns

                # Build values series, aligned to existing IDs. Existing
                # columns are patched only for provided IDs so admin edits are
                # true partial upserts; new columns still get typed defaults.
                values = {}
                for id_val in existing_ids:
                    if id_val in data_dict:
                        raw_val = data_dict[id_val]
                        if inferred_type == "bigint":
                            values[id_val] = int(float(raw_val)) if raw_val else 0
                        elif inferred_type == "double precision":
                            values[id_val] = float(raw_val) if raw_val else np.nan
                        elif inferred_type == "boolean":
                            values[id_val] = raw_val.lower() in ("true", "1", "yes")
                        else:
                            values[id_val] = raw_val
                    elif column_exists:
                        values[id_val] = axis_df.loc[id_val, column_name]
                    else:
                        # Fill with default
                        if inferred_type in ("bigint", "double precision"):
                            values[id_val] = np.nan
                        elif inferred_type == "boolean":
                            values[id_val] = False
                        else:
                            values[id_val] = ""
                
                # Apply to AnnData
                if target == 'var':
                    series = pd.Series(values, index=adata.var.index, name=column_name)
                    adata.var[column_name] = series
                    overlay_axis = adata.var
                else:
                    series = pd.Series(values, index=adata.obs.index, name=column_name)
                    adata.obs[column_name] = series
                    overlay_axis = adata.obs

                overlay_values = {}
                for idx, val in overlay_axis[column_name].items():
                    try:
                        missing = bool(pd.isna(val))
                    except (TypeError, ValueError):
                        missing = False
                    if missing:
                        overlay_values[str(idx)] = None
                    elif isinstance(val, np.generic):
                        overlay_values[str(idx)] = val.item()
                    else:
                        overlay_values[str(idx)] = val

                # Register overlay so the column survives cache eviction /
                # config reload / backend restart, even when the admin does
                # not persist it to the .h5ad file on disk.
                try:
                    service.register_custom_overlay(
                        species_code=ds_code,
                        column_name=column_name,
                        target=target,
                        values=overlay_values,
                        dtype=inferred_type,
                    )
                except Exception as oe:
                    logger.warning(
                        f"Failed to register overlay for {ds_code}/{column_name}: {oe}"
                    )

                matched = len([v for v in data_dict if v in existing_ids])
                results[ds_code] = {"status": "applied", "matched": matched, "total": len(existing_ids)}
                
                # Optionally persist to h5ad file
                if persist:
                    try:
                        h5ad_dir = config_mgr.h5ad_dir
                        # Find the h5ad file
                        h5ad_files = list(Path(h5ad_dir).glob(f"{ds_code}/{ds_code}_full.h5ad"))
                        if not h5ad_files:
                            h5ad_files = list(Path(h5ad_dir).glob(f"**/{ds_code}_full.h5ad"))
                        
                        if h5ad_files:
                            import anndata
                            # Re-read from disk, add column, write back
                            disk_adata = anndata.read_h5ad(str(h5ad_files[0]))
                            if target == 'var':
                                disk_adata.var[column_name] = adata.var[column_name]
                            else:
                                disk_adata.obs[column_name] = adata.obs[column_name]
                            disk_adata.write_h5ad(str(h5ad_files[0]))
                            results[ds_code]["persisted"] = True
                            logger.info(f"Persisted column '{column_name}' to {h5ad_files[0]}")
                        else:
                            results[ds_code]["persisted"] = False
                            results[ds_code]["persist_warning"] = "H5AD file not found"
                    except Exception as pe:
                        results[ds_code]["persisted"] = False
                        results[ds_code]["persist_error"] = str(pe)
                        logger.error(f"Failed to persist to h5ad for {ds_code}: {pe}")
                
            except Exception as e:
                results[ds_code] = {"status": "error", "error": str(e)}
                logger.error(f"Failed to apply metadata to {ds_code}: {e}")
        
        # Add column definition to config
        is_meta = (target == 'var')
        is_sample_metadata = (target == 'obs')
        
        config = config_mgr.get_config()
        column_defs = config.setdefault('column_definitions', {})
        existing_def = column_defs.get(column_name, {})
        column_defs[column_name] = {
            "display_name": display_name or existing_def.get("display_name") or column_name.replace("_", " ").title(),
            "type": type_override or existing_def.get("type") or inferred_type,
            "is_array": existing_def.get("is_array", False),
            "array_separator": existing_def.get("array_separator", ","),
            "is_meta": is_meta,
            "is_sample_metadata": is_sample_metadata,
            "visible": existing_def.get("visible", True),
            "sortable": existing_def.get("sortable", True),
            "order": existing_def.get("order", len(column_defs)),
            "source": existing_def.get("source", "custom"),
        }
        
        # Add to meta_columns or sample_metadata_columns
        if is_meta:
            meta_cols = set(config.get('meta_columns', []))
            meta_cols.add(column_name)
            config['meta_columns'] = list(meta_cols)
        elif is_sample_metadata:
            smc = config.get('sample_metadata_columns', {'enabled': True, 'columns': []})
            if column_name not in smc.get('columns', []):
                smc.setdefault('columns', []).append(column_name)
            config['sample_metadata_columns'] = smc
        
        config_mgr.update_config(config)
        service.reload_config()
        try:
            from . import assistant_tools as _assistant_tools
            _assistant_tools.invalidate_runtime_cache()
            _assistant_tools.warmup_runtime_cache(service, config_mgr)
        except Exception:
            pass
        
        return jsonify({
            "success": True,
            "message": f"Column '{column_name}' imported successfully",
            "results": results,
            "column_definition": config['column_definitions'][column_name]
        })
    
    except Exception as e:
        logger.error(f"Metadata import confirm failed: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/metadata/<column_name>', methods=['DELETE'])
@require_admin_token
def delete_metadata_column(column_name):
    """
    Delete a metadata column.
    
    Query params:
        persist: If "true", also removes from h5ad files
    
    Returns:
        Success status
    """
    config_mgr = get_config_manager()
    config = config_mgr.get_config()
    
    col_defs = config.get('column_definitions', {})
    if column_name not in col_defs:
        return jsonify({"success": False, "error": f"Column '{column_name}' not found"}), 404
    
    col_def = col_defs[column_name]
    
    persist = request.args.get('persist', 'false').lower() == 'true'
    service = get_service()
    
    # Remove from in-memory AnnData objects
    species = config_mgr.get_species()
    for code, spec in species.items():
        if not spec.get('enabled', True):
            continue
        try:
            adata = service.registry.load(code)
            if adata is not None:
                is_var = col_def.get('is_meta', False)
                changed_memory = False
                if is_var and column_name in adata.var.columns:
                    adata.var.drop(columns=[column_name], inplace=True)
                    changed_memory = True
                elif not is_var and column_name in adata.obs.columns:
                    adata.obs.drop(columns=[column_name], inplace=True)
                    changed_memory = True
                if changed_memory:
                    logger.info(f"Removed metadata column '{column_name}' from cached {code} .{'var' if is_var else 'obs'}")
                
                # Optionally remove from h5ad file on disk
                if persist:
                    try:
                        import anndata
                        h5ad_dir = config_mgr.h5ad_dir
                        h5ad_files = list(Path(h5ad_dir).glob(f"{code}/{code}_full.h5ad"))
                        if not h5ad_files:
                            h5ad_files = list(Path(h5ad_dir).glob(f"**/{code}_full.h5ad"))
                        if h5ad_files:
                            disk_adata = anndata.read_h5ad(str(h5ad_files[0]))
                            if is_var and column_name in disk_adata.var.columns:
                                disk_adata.var.drop(columns=[column_name], inplace=True)
                                logger.info(f"Removed metadata column '{column_name}' from {h5ad_files[0]} .var")
                            elif not is_var and column_name in disk_adata.obs.columns:
                                disk_adata.obs.drop(columns=[column_name], inplace=True)
                                logger.info(f"Removed metadata column '{column_name}' from {h5ad_files[0]} .obs")
                            disk_adata.write_h5ad(str(h5ad_files[0]))
                    except Exception as pe:
                        logger.error(f"Failed to persist deletion for {code}: {pe}")
        except Exception as e:
            logger.warning(f"Could not clean column from {code}: {e}")
    
    # Remove from config
    del col_defs[column_name]
    
    # Remove from meta_columns / sample_metadata_columns
    meta_cols = config.get('meta_columns', [])
    if column_name in meta_cols:
        meta_cols.remove(column_name)
    smc = config.get('sample_metadata_columns', {})
    smc_cols = smc.get('columns', [])
    if column_name in smc_cols:
        smc_cols.remove(column_name)
    default_visible_cols = smc.get('default_visible_columns', [])
    if column_name in default_visible_cols:
        default_visible_cols.remove(column_name)

    if config.get('default_trait_column') == column_name:
        config['default_trait_column'] = None
    
    config_mgr.update_config(config)
    service.reload_config()

    # Remove any runtime overlay so the column is fully gone.
    try:
        service.unregister_custom_overlay(column_name)
    except Exception as oe:
        logger.warning(f"Failed to unregister overlay for {column_name}: {oe}")

    return jsonify({
        "success": True,
        "message": f"Column '{column_name}' deleted successfully"
    })


# ============================================================================
# Config Profile Endpoints
# ============================================================================

@admin_bp.route('/config/profiles', methods=['GET'])
@require_admin_token
def list_profiles():
    """List available config profiles."""
    config_mgr = get_config_manager()
    profiles_dir = config_mgr.config_path.parent / "profiles"
    
    if not profiles_dir.exists():
        return jsonify({"success": True, "profiles": []})
    
    profiles = []
    for f in sorted(profiles_dir.glob("*.json")):
        try:
            import json
            with open(f) as fh:
                data = json.load(fh)
            profiles.append({
                "name": f.stem,
                "project_name": data.get("project_name", "Unknown"),
                "description": data.get("description", ""),
                "species_count": len(data.get("species", {})),
                "columns_count": len(data.get("column_definitions", {})),
                "modified": f.stat().st_mtime,
            })
        except Exception:
            profiles.append({"name": f.stem, "error": "Could not read"})
    
    return jsonify({"success": True, "profiles": profiles})


@admin_bp.route('/config/save-profile', methods=['POST'])
@require_admin_token
def save_profile():
    """
    Save current config as a named profile.
    
    Request body:
        { "name": "my_profile", "description": "Optional description" }
    """
    if not request.is_json:
        return jsonify({"success": False, "error": "Request must be JSON"}), 400
    
    body = request.get_json()
    name = body.get('name', '').strip()
    
    if not name:
        return jsonify({"success": False, "error": "Profile name is required"}), 400
    
    # Sanitize name
    import re
    safe_name = re.sub(r'[^\w\-]', '_', name)
    
    config_mgr = get_config_manager()
    profiles_dir = config_mgr.config_path.parent / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    
    config = config_mgr.get_config()
    if body.get('description'):
        config['description'] = body['description']
    
    profile_path = profiles_dir / f"{safe_name}.json"
    
    import json
    with open(profile_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    logger.info(f"Saved config profile: {safe_name}")
    
    return jsonify({
        "success": True,
        "message": f"Profile '{safe_name}' saved successfully",
        "path": str(profile_path)
    })


@admin_bp.route('/config/load-profile', methods=['POST'])
@require_admin_token
def load_profile():
    """
    Load a config profile by name.
    
    Request body:
        { "name": "my_profile" }
    """
    if not request.is_json:
        return jsonify({"success": False, "error": "Request must be JSON"}), 400
    
    body = request.get_json()
    name = body.get('name', '').strip()
    
    if not name:
        return jsonify({"success": False, "error": "Profile name is required"}), 400
    
    import re
    safe_name = re.sub(r'[^\w\-]', '_', name)
    
    config_mgr = get_config_manager()
    profile_path = config_mgr.config_path.parent / "profiles" / f"{safe_name}.json"
    
    if not profile_path.exists():
        return jsonify({"success": False, "error": f"Profile '{safe_name}' not found"}), 404
    
    try:
        import json
        with open(profile_path, 'r') as f:
            profile_config = json.load(f)
        
        config_mgr.update_config(profile_config)
        get_service().reload_config()
        
        logger.info(f"Loaded config profile: {safe_name}")
        
        return jsonify({
            "success": True,
            "message": f"Profile '{safe_name}' loaded successfully",
            "config": profile_config
        })
    except Exception as e:
        logger.error(f"Failed to load profile: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
