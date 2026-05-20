"""
Routes for the H5AD Backend API
===============================
Compatible with the existing GenXBrowser frontend (butterfly API).
Matches the exact parameter names and response formats expected by the frontend.
"""

from flask import Blueprint, jsonify, request, current_app, send_from_directory
from marshmallow import Schema, fields, validate, post_load, validates_schema, ValidationError
import numpy as np
import logging
import os
import json
from typing import Any, Dict, List, Optional

from . import filter_parser

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def serialize_dataframe(df, column_defs=None):
    """
    Serialize DataFrame to JSON-compatible dict.
    Handles lists, numpy arrays, NaN values correctly.
    Splits multi-value strings in array columns using the separator stored in
    column_defs (source of truth).  Falls back to hard-coded column sets for
    backwards-compatibility when column_defs is not provided.
    """
    # Legacy fallback sets (used only when no column_defs provided)
    COMMA_ARRAY_COLUMNS = {'go_terms', 'ipr_id', 'pfam_id'}
    PIPE_ARRAY_COLUMNS = {'ipr_desc', 'pfam_desc'}

    records = df.to_dict(orient='records')

    # Convert numpy types and ensure lists are preserved
    for record in records:
        for key, value in record.items():
            # Handle numpy types
            if isinstance(value, (np.integer, np.floating)):
                record[key] = value.item()
            elif isinstance(value, np.ndarray):
                record[key] = value.tolist()
            # Lists should stay as lists (already JSON-serializable)
            elif isinstance(value, list):
                pass  # Keep as-is
            # Handle NaN
            elif isinstance(value, float) and np.isnan(value):
                record[key] = None
            elif isinstance(value, str) and value.strip():
                # Determine whether this column is a multi-value array column
                # and which separator to use.
                sep = None
                if column_defs and key in column_defs:
                    col_def = column_defs[key]
                    if col_def.get('is_array') or col_def.get('type') == 'array':
                        sep = col_def.get('array_separator', ',')
                else:
                    # Legacy fallback
                    if key in COMMA_ARRAY_COLUMNS:
                        sep = ','
                    elif key in PIPE_ARRAY_COLUMNS:
                        sep = '|'

                if sep is not None:
                    record[key] = [v.strip() for v in value.split(sep) if v.strip()] or []
            elif not isinstance(value, str):
                # Non-string, non-numeric: leave as-is (handles None etc.)
                pass

    return records

# ============================================================================
# Schemas for request validation (matching butterfly_schema.py EXACTLY)
# ============================================================================

class CommaSeparatedList(fields.Field):
    """Custom field for comma-separated string to list conversion."""
    def _deserialize(self, value, attr, data, **kwargs):
        if not value:
            return None
        if not isinstance(value, str):
            raise ValidationError("Field should be a comma-separated string.")
        return [item.strip() for item in value.split(",") if item.strip()]


class TagsSchema(Schema):
    """Schema for tags filtering (GET /butterfly/tables)."""
    tags = CommaSeparatedList(required=False, allow_none=True)
    include_disabled = fields.Boolean(required=False, allow_none=True, load_default=False)


class ColumnNameSchema(Schema):
    """Schema for single column name (GET /butterfly/col)."""
    column_name = fields.String(required=True)


class ColumnsSchema(Schema):
    """Schema for columns listing (GET /butterfly/columns)."""
    table_name = fields.String(required=False, allow_none=True)
    meta = fields.Boolean(required=False, allow_none=True)
    columns = fields.Boolean(required=False, allow_none=True)


class ColumnBinSchema(Schema):
    """Schema for histogram bins (GET /butterfly/column_bins)."""
    table_names = fields.String(required=False, allow_none=True, load_default="")
    column_name = fields.String(required=True)
    n_bins = fields.Integer(required=False, allow_none=True)
    
    @post_load
    def split_table_names(self, data, **kwargs):
        table_names_str = data.get('table_names', '')
        if table_names_str and table_names_str.strip():
            # Split by comma and filter out empty strings
            data['table_names'] = [name.strip() for name in table_names_str.split(',') if name.strip()]
        else:
            # Empty string or None → empty list
            data['table_names'] = []
        return data


class QueryRequestSchema(Schema):
    """Schema for data queries (POST /butterfly/data, /butterfly/count)."""
    table_name = fields.String(required=True)
    columns = fields.List(fields.String(), required=False, load_default=list)
    filters = fields.Dict(keys=fields.String(), values=fields.Raw(), required=False, load_default=dict)
    filter_chain = fields.Dict(keys=fields.String(), values=fields.Raw(), required=False, allow_none=True, load_default=None)
    sample_filters = fields.Dict(keys=fields.String(), values=fields.Raw(), required=False, load_default=dict)
    limit = fields.Integer(required=False, load_default=1001, validate=validate.Range(min=1))
    offset = fields.Integer(required=False, load_default=0, validate=validate.Range(min=0))
    # Expression layer parameters
    layer = fields.String(required=False, allow_none=True, load_default=None)
    transform = fields.String(required=False, allow_none=True, load_default="raw", 
                             validate=validate.OneOf(["raw", "log2", "zscore"]))
    # Gene ID list for Data Manager search
    gene_ids = fields.List(fields.String(), required=False, load_default=list)
    # Frontend may send search parameter (not implemented yet, but accept it to avoid validation errors)
    search = fields.String(required=False, allow_none=True, load_default="")



class FindSimilarValuesSchema(Schema):
    """Schema for fuzzy search (GET /butterfly/find)."""
    # NOTE: Frontend sends 'column', not 'column_name'!
    column = fields.String(required=True)
    search_term = fields.String(required=True)
    limit = fields.Integer(required=False, load_default=10, validate=validate.Range(min=1, max=100))


class FindSimilarTagsSchema(Schema):
    """Schema for tag search (GET /butterfly/tags)."""
    search_term = fields.String(required=True)
    limit = fields.Integer(required=False, load_default=10, validate=validate.Range(min=1, max=100))


class FilterIDSchema(Schema):
    """Schema for filter storage (POST /butterfly/id)."""
    id = fields.String(required=False, allow_none=True)
    filters = fields.Dict(
        keys=fields.String(),
        values=fields.Raw(),
        required=False,
        allow_none=True,
        load_default={},
    )
    visualizations = fields.Dict(
        keys=fields.String(),
        values=fields.Raw(),
        required=False,
        allow_none=True,
        load_default={},
    )

    @validates_schema
    def validate_one_of(self, data, **kwargs):
        has_id = data.get("id") is not None
        has_filters = data.get("filters") is not None and data.get("filters") != {}
        has_visualizations = data.get("visualizations") is not None and data.get("visualizations") != {}

        if has_id and (has_filters or has_visualizations):
            raise ValidationError(
                "Cannot provide 'id' together with 'filters' or 'visualizations'."
            )

        if not has_id and not (has_filters and has_visualizations):
            raise ValidationError(
                "Must provide either 'id' or both 'filters' and 'visualizations' (both non-empty)."
            )


# ============================================================================
# API Blueprint
# ============================================================================

api_bp = Blueprint('api', __name__)


def get_service():
    """Get the H5AD service from the app context."""
    return current_app.h5ad_service


def parse_filters(filters, get_columns_func=None, source="meta", *, allowed_columns=None):
    """
    Parse filter input from frontend format to internal ``(operator, value)`` tuples.

    Frontend sends: ``{"column": value}`` or
    ``{"column": {"value": v, "match_mode": "or"|"and", "exact": bool}}``.

    Args:
        filters: Filter dict from frontend.
        get_columns_func: Function returning column metadata (used when
            ``allowed_columns`` is not provided).
        source: ``"meta"`` for gene metadata filters, ``"column_meta"`` for
            sample metadata filters.
        allowed_columns: Optional pre-built ``{col_name: col_type}`` mapping
            from caller-known schema (e.g. AnnData ``.var`` / ``.obs``).
            Bypasses ``get_columns_func`` when supplied so the same grammar
            (including ``match_mode`` and ``exact``) is reused outside the
            DuckDB catalog path.
    """
    if not filters:
        return {}

    if allowed_columns is None:
        if get_columns_func is None:
            return {}
        all_columns = get_columns_func(source=source)
        allowed_columns = {
            col["column_name"]: col.get("type", "text").lower()
            for col in all_columns
            if col.get("type", "text").lower() in filter_parser.ALLOWED_TYPES
        }

    logger.debug(f"[parse_filters] source={source}, incoming filters keys: {list(filters.keys())}")

    _GO_TERM_KEYS = {"go_terms", "go_term", "goterm", "goterms"}

    def _expand_go(col_key, values, exact):
        if exact:
            return values, exact
        if not isinstance(col_key, str) or col_key.lower() not in _GO_TERM_KEYS:
            return values, exact
        go_service = getattr(current_app, 'go_service', None)
        if not go_service or not go_service.is_available():
            return values, exact
        expanded: List[Any] = []
        any_expanded = False
        for v in values:
            sv = str(v).strip()
            if not sv:
                continue
            if sv.upper().startswith('GO:'):
                expanded.append(sv)
                continue
            try:
                hits = go_service.search_terms(sv, limit=200)
            except Exception:
                expanded.append(sv)
                continue
            ids = [h.get('id') for h in hits if isinstance(h, dict) and h.get('id')]
            if ids:
                expanded.extend(ids)
                any_expanded = True
            else:
                expanded.append(sv)
        if not expanded:
            return values, exact
        return (expanded, True) if any_expanded else (expanded, exact)

    return filter_parser.parse_filter_query(
        filters, allowed_columns, go_term_expander=_expand_go,
    )


def validate_table_name(table_names, get_tables_func):
    """Validate table name(s) exist. Accepts both full names and short codes."""
    if isinstance(table_names, str):
        table_names = [table_names]
    
    # Return early if empty list
    if not table_names:
        return False, "No table names provided"
    
    # Get valid table names
    tables_list = get_tables_func()
    valid_tables = set()
    
    for t in tables_list:
        full_name = t["table_name"]
        code = t.get("_species_code", "")
        
        # Add full names
        valid_tables.add(full_name)
        valid_tables.add(f"{full_name}_meta")
        
        # Add short codes
        if code:
            valid_tables.add(code)
            valid_tables.add(f"{code}_meta")
    
    invalid = set(table_names) - valid_tables
    if invalid:
        return False, f"Invalid table name(s): {', '.join(sorted(invalid))}"
    return True, None


def validate_column_by_type(column_name, get_columns_func, allowed_types=('text', 'array', 'bigint', 'double precision', 'boolean')):
    """Check if column exists with specified type."""
    # Get all columns including sample metadata (column_meta)
    all_columns = get_columns_func()
    all_columns.extend(get_columns_func(source="column_meta"))
    
    allowed_columns = {
        c['column_name'] for c in all_columns 
        if c.get('type', 'text').lower() in allowed_types
    }
    if column_name not in allowed_columns:
        return False, f"Invalid 'column': {column_name}"
    return True, None


# ============================================================================
# Health & Setup
# ============================================================================

@api_bp.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'}), 200


@api_bp.route('/api/setup', methods=['GET'])
def setup_complete():
    """Check if backend is ready (for frontend compatibility)."""
    try:
        service = get_service()
        tables = service.get_tables()
        return jsonify(len(tables) > 0), 200
    except Exception as e:
        current_app.logger.error(f"Setup check failed: {e}")
        return jsonify(False), 200


# ============================================================================
# Tables (Species/Datasets)
# ============================================================================

@api_bp.route('/api/tables', methods=['GET'])
def list_tables():
    """Get list of available tables/species, optionally filtered by tags."""
    try:
        data = TagsSchema().load(request.args)
        tags = data.get('tags')
        include_disabled = data.get('include_disabled', False)
        
        service = get_service()
        tables = service.get_tables(tags, include_disabled=include_disabled)
        return jsonify(tables)
    
    except ValidationError as err:
        return jsonify({"error": "Validation error", "details": err.messages}), 400
    except Exception as e:
        return jsonify({"error": "Unexpected server error", "details": str(e)}), 500


@api_bp.route('/api/species_photos/<path:filename>', methods=['GET'])
def get_species_photo(filename):
    """Serve species photos from the photos directory."""
    try:
        photos_dir = os.environ.get('SPECIES_PHOTOS_DIR', '/data/species_photos')
        if not os.path.exists(photos_dir):
            return jsonify({"error": "Photos directory not found"}), 404
        return send_from_directory(photos_dir, filename)
    except FileNotFoundError:
        return jsonify({"error": "Photo not found"}), 404
    except Exception as e:
        logger.error(f"Error serving photo {filename}: {e}")
        return jsonify({"error": "Error serving photo"}), 500


# ============================================================================
# Columns (for Genes and Samples tabs)
# ============================================================================

@api_bp.route('/api/columns', methods=['GET'])
def list_columns():
    """
    Get column metadata.
    
    Query params:
    - table_name: Filter for specific species
    - meta: If True, only return isMeta columns; if False, only non-meta
    - columns: If True, return sample metadata (column_meta) instead of gene metadata
    
    The 'columns' param determines Genes vs Samples tab:
    - columns=false or not set -> source="meta" -> Gene metadata (.var columns)
    - columns=true -> source="column_meta" -> Sample metadata (.obs columns)
    """
    try:
        args = ColumnsSchema().load(request.args)
        table_name = args.get("table_name")
        is_meta = args.get("meta")
        columns_arg = args.get("columns")
        
        service = get_service()
        
        if columns_arg:
            # Samples tab: source="column_meta" -> .obs columns
            columns = service.get_all_columns(source="column_meta", table_name=table_name)
        else:
            # Genes tab: source="meta" -> .var columns  
            columns = service.get_all_columns(source="meta", is_meta=is_meta, table_name=table_name)
        
        return jsonify(columns)
    
    except ValidationError as err:
        return jsonify({"error": "Validation error", "details": err.messages}), 400
    except Exception as e:
        return jsonify({"error": "Unexpected server error", "details": str(e)}), 500


# ============================================================================
# Histogram Bins
# ============================================================================

@api_bp.route('/api/column_bins', methods=['GET'])
def get_column_bins():
    """Get frequency bins for a numeric column."""
    try:
        args = ColumnBinSchema().load(request.args)
        table_names = args.get("table_names", [])
        column_name = args.get("column_name")
        n_bins = args.get("n_bins") or 20
        
        service = get_service()
        
        # If no table names provided, return global (all-dataset merged) bins
        # so sliders are always usable even before any dataset is selected
        if not table_names:
            bins = service.get_global_column_bins(column_name, n_bins)
            return jsonify(bins)
        
        # Validate table names
        is_valid, err = validate_table_name(table_names, service.get_tables)
        if not is_valid:
            return jsonify({"error": err}), 400
        
        # Validate column is numeric
        is_valid, err = validate_column_by_type(
            column_name, 
            service.get_all_columns, 
            allowed_types=('bigint', 'double precision')
        )
        if not is_valid:
            return jsonify({"error": err}), 400
        
        bins = service.get_column_bins(table_names, column_name, n_bins)
        return jsonify(bins)
    
    except ValidationError as err:
        return jsonify({"error": "Validation error", "details": err.messages}), 400
    except Exception as e:
        return jsonify({"error": "Unexpected server error", "details": str(e)}), 500


# ============================================================================
# Row Count
# ============================================================================

@api_bp.route('/api/count', methods=['POST'])
def get_row_count():
    """Get row + sample counts for a table with optional gene/sample filters.

    Body: {table_name, filters?, sample_filters?}.

    Response: {count, sample_count, total_samples}. ``sample_count`` is the
    number of `.obs` rows passing ``sample_filters`` (full ``adata.n_obs``
    when no sample filter is set), and ``count`` is the number of `.var`
    rows passing ``filters`` (= ``adata.n_vars`` when none). The frontend
    uses ``sample_count`` to hide datasets that completely fall through a
    sample filter on a per-view basis.
    """
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "Missing or invalid JSON payload"}), 400
        
        schema = QueryRequestSchema()
        data = schema.load(data)
        table_name = data.get('table_name')
        filters = data.get('filters')
        filter_chain = data.get('filter_chain')
        sample_filters = data.get('sample_filters') or {}
        
        service = get_service()
        
        # Validate table (accepts both full names and short codes)
        is_valid, err = validate_table_name(table_name, service.get_tables)
        if not is_valid:
            return jsonify({"error": "Invalid 'table_name'"}), 400
        
        # Parse and apply gene-level (var) filters via the existing helper.
        parsed_filters = parse_filters(filters, service.get_all_columns)
        count = service.get_row_count(table_name, parsed_filters, filter_chain=filter_chain)

        # Compute the post-filter sample count via the registry directly so
        # we don't have to materialise the full data frame just to count.
        species_code = service._normalize_table_name(table_name)
        adata = service.registry.load(species_code)
        if adata is None:
            sample_count = 0
            total_samples = 0
        else:
            total_samples = int(adata.n_obs)
            if not sample_filters:
                sample_count = total_samples
            else:
                parsed_sample = parse_filters(
                    sample_filters,
                    lambda **kw: service.get_all_columns(table_name=table_name, **kw),
                    source="column_meta",
                )
                allowed = service._filter_samples(adata, parsed_sample) if parsed_sample else None
                sample_count = int(len(allowed)) if allowed is not None else total_samples
        
        return jsonify({
            "count": count,
            "sample_count": sample_count,
            "total_samples": total_samples,
        })
    
    except ValidationError as err:
        return jsonify({"error": "Validation error", "details": err.messages}), 400
    except Exception as e:
        return jsonify({"error": "Unexpected server error", "details": str(e)}), 500


# ============================================================================
# Data Query
# ============================================================================

@api_bp.route('/api/data', methods=['POST'])
def list_data():
    """Get gene data with optional columns, filters, and pagination."""
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "Missing or invalid JSON payload"}), 400
        
        schema = QueryRequestSchema()
        data = schema.load(data)
        table_name = data.get('table_name')
        columns = data.get('columns')
        filters = data.get('filters')
        filter_chain = data.get('filter_chain')
        sample_filters = data.get('sample_filters')
        limit = data.get('limit')
        offset = data.get('offset')
        layer = data.get('layer')
        transform = data.get('transform', 'raw')
        gene_ids = data.get('gene_ids', [])
        
        service = get_service()
        
        # Validate table
        is_valid, err = validate_table_name(table_name, service.get_tables)
        if not is_valid:
            return jsonify({"error": err}), 400
        
        # Parse filters - pass table_name to get correct columns
        parsed_filters = parse_filters(filters, lambda **kw: service.get_all_columns(table_name=table_name, **kw))
        parsed_sample_filters = parse_filters(sample_filters, lambda **kw: service.get_all_columns(table_name=table_name, **kw), source="column_meta") if sample_filters else {}
        
        # Keep request logs compact; full filter payloads can be large.
        logger.debug(
            "[list_data] Parsed %d row filters and %d sample filters",
            len(parsed_filters),
            len(parsed_sample_filters),
        )
        
        # Add gene_ids filter if provided
        if gene_ids:
            parsed_filters['gene_id'] = ('in', gene_ids)
        
        # Get data with layer metadata
        df, layer_metadata = service.get_data(
            table_name, 
            columns, 
            filters=parsed_filters,
            filter_chain=filter_chain,
            sample_filters=parsed_sample_filters,
            limit=limit, 
            offset=offset,
            layer=layer,
            transform=transform
        )
        
        response = {
            "data": serialize_dataframe(df, service.config_manager.get_column_definitions())
        }
        
        # Include layer metadata if available
        if layer_metadata:
            response["layer_metadata"] = layer_metadata
        
        return jsonify(response)
    
    except ValidationError as err:
        return jsonify({"error": "Validation error", "details": err.messages}), 400
    except Exception as e:
        return jsonify({"error": "Unexpected server error", "details": str(e)}), 500


# ============================================================================
# Unique Column Values
# ============================================================================

@api_bp.route('/api/col', methods=['GET'])
def get_column_values():
    """Get unique values for a column."""
    try:
        args = ColumnNameSchema().load(request.args)
        column_name = args.get("column_name")
        
        service = get_service()
        
        is_valid, err = validate_column_by_type(column_name, service.get_all_columns)
        if not is_valid:
            return jsonify({"error": err}), 400
        
        terms = service.get_unique_values(column_name)
        return jsonify({"terms": terms})
    
    except ValidationError as err:
        return jsonify({"error": "Validation error", "details": err.messages}), 400
    except Exception as e:
        return jsonify({"error": "Unexpected server error", "details": str(e)}), 500


# ============================================================================
# Fuzzy Search
# ============================================================================

@api_bp.route('/api/data/distinct', methods=['POST'])
def validate_distinct_values():
    """Validate a list of values against a column's unique values.
    Optionally scoped to a specific table for per-dataset validation.
    """
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "Missing or invalid JSON payload"}), 400
        
        column = data.get('column')
        values = data.get('values', [])
        table_name = data.get('table_name')  # Optional: scope to one dataset
        
        if not column or not values:
            return jsonify({"error": "Missing 'column' or 'values'"}), 400
        
        service = get_service()
        
        if table_name:
            # Per-dataset validation: get unique values from a single table
            h5ad_col = service._to_h5ad_column_name(column)
            species_code = service._normalize_table_name(table_name)
            if not species_code:
                return jsonify({"error": "Invalid table_name"}), 400
            
            adata = service.registry.load(species_code)
            if adata is None:
                return jsonify({"error": f"Table '{table_name}' not found"}), 404
            
            # Check both var and obs for the column
            known = set()
            target_col = None
            if h5ad_col in adata.var.columns:
                target_col = adata.var[h5ad_col]
            elif column in adata.var.columns:
                target_col = adata.var[column]
            elif h5ad_col in adata.obs.columns:
                target_col = adata.obs[h5ad_col]
            elif column in adata.obs.columns:
                target_col = adata.obs[column]
            
            if target_col is not None:
                known = set(target_col.dropna().astype(str).unique())
        else:
            # Global validation: get unique values across all tables
            known = set(service.get_unique_values(column))
        
        # Case-insensitive matching: build a case-insensitive lookup
        known_lower = {v.lower(): v for v in known}
        
        matched = []
        unmatched = []
        for v in values:
            key = v.strip().lower() if isinstance(v, str) else str(v).lower()
            if key in known_lower:
                matched.append(known_lower[key])
            else:
                unmatched.append(v)
        
        return jsonify({"matched": matched, "unmatched": unmatched})
    
    except Exception as e:
        logger.error(f"Error in validate_distinct_values: {e}")
        return jsonify({"error": "Unexpected server error", "details": str(e)}), 500


@api_bp.route('/api/find', methods=['GET'])
def find_similar_values():
    """Fuzzy search for similar values in a column."""
    try:
        # Note: Frontend sends 'column', not 'column_name'!
        data = FindSimilarValuesSchema().load(request.args)
        column_name = data.get('column')  # <- 'column' not 'column_name'!
        search_term = data.get('search_term')
        limit = data.get('limit')
        
        service = get_service()
        
        is_valid, err = validate_column_by_type(column_name, service.get_all_columns)
        if not is_valid:
            return jsonify({"error": err}), 400
        
        values = service.find_similar_values(column_name, search_term, limit)
        return jsonify(values)
    
    except ValidationError as err:
        return jsonify({"error": "Validation error", "details": err.messages}), 400
    except Exception as e:
        return jsonify({"error": "Unexpected server error", "details": str(e)}), 500


@api_bp.route('/api/tags', methods=['GET'])
def find_similar_tags():
    """Fuzzy search for tags."""
    try:
        data = FindSimilarTagsSchema().load(request.args)
        search_term = data.get('search_term')
        limit = data.get('limit')
        
        service = get_service()
        values = service.find_similar_tags(search_term, limit)
        
        return jsonify(values)
    
    except ValidationError as err:
        return jsonify({"error": "Validation error", "details": err.messages}), 400
    except Exception as e:
        return jsonify({"error": "Unexpected server error", "details": str(e)}), 500


# ============================================================================
# Filter Storage
# ============================================================================

@api_bp.route('/api/id', methods=['POST'])
def handle_filter_id():
    """Store or retrieve filter configuration."""
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "Missing or invalid JSON payload"}), 400
        
        schema = FilterIDSchema()
        data = schema.load(data)
        
        service = get_service()
        
        if data.get("id"):
            # Retrieve existing filter
            filter_data = service.get_filter(data["id"])
            if filter_data is None:
                return jsonify({"error": "Filter not found"}), 404
            return jsonify(filter_data)
        else:
            # Store new filter
            hash_id = service.store_filter({
                "filters": data["filters"],
                "visualizations": data["visualizations"]
            })
            return jsonify({"id": hash_id})
    
    except ValidationError as err:
        return jsonify({"error": "Validation error", "details": err.messages}), 400
    except Exception as e:
        return jsonify({"error": "Unexpected server error", "details": str(e)}), 500


@api_bp.route('/api/id/<hash_id>', methods=['GET'])
def get_filter(hash_id: str):
    """Retrieve stored filter by hash ID."""
    service = get_service()
    data = service.get_filter(hash_id)
    
    if data is None:
        return jsonify({'error': 'Filter not found'}), 404
    
    return jsonify(data), 200


# ============================================================================
# Gene Trees
# ============================================================================

@api_bp.route('/api/gene_tree/<og_id>', methods=['GET'])
def get_gene_tree(og_id: str):
    """Get Newick tree for an orthogroup."""
    service = get_service()
    tree = service.get_gene_tree(og_id)
    allow_missing = str(request.args.get('allow_missing', '')).lower() in {'1', 'true', 'yes'}
    
    if tree is None:
        if allow_missing:
            return jsonify({'og_id': og_id, 'newick': None, 'available': False}), 200
        return jsonify({'error': 'Gene tree not found'}), 404
    
    return jsonify({'og_id': og_id, 'newick': tree, 'available': True}), 200


# ============================================================================
# Gene Ontology (GO) Search
# ============================================================================

@api_bp.route('/api/go/search', methods=['GET'])
def go_search():
    """
    Search GO terms by name/description.
    Returns GO terms with human-readable labels for autocomplete.
    Only returns GO terms that exist in the dataset.
    
    Query params:
        q: search query (required)
        limit: max results (default 20)
    
    Response:
        {
            "available": true/false,
            "results": [
                {
                    "id": "GO:0009908",
                    "name": "flower development",
                    "namespace": "biological_process",
                    "definition": "The process...",
                    "label": "GO:0009908 (flower development)"
                },
                ...
            ]
        }
    """
    go_service = getattr(current_app, 'go_service', None)
    
    if not go_service or not go_service.is_available():
        return jsonify({
            'available': False,
            'results': [],
            'message': 'GO service not available'
        }), 200
    
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 20, type=int)
    
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    if limit < 1 or limit > 100:
        limit = 20
    
    try:
        # Get GO terms that exist in the dataset
        service = get_service()
        dataset_go_terms = set(service.get_unique_values('go_terms'))
        
        if not dataset_go_terms:
            return jsonify({
                'available': True,
                'results': [],
                'query': query,
                'count': 0,
                'message': 'No GO terms found in dataset'
            }), 200
        
        # Search GO ontology
        all_results = go_service.search_terms(query, limit=limit * 3)  # Get more to filter
        
        # Filter results to only include GO terms present in dataset
        filtered_results = [
            r for r in all_results 
            if r['id'] in dataset_go_terms
        ][:limit]
        
        return jsonify({
            'available': True,
            'results': filtered_results,
            'query': query,
            'count': len(filtered_results)
        }), 200
    except Exception as e:
        logger.error(f"GO search error: {e}")
        return jsonify({'error': 'Search failed', 'details': str(e)}), 500


@api_bp.route('/api/go/term/<go_id>', methods=['GET'])
def go_term_detail(go_id: str):
    """
    Get detailed information for a specific GO term.
    
    Returns:
        {
            "available": true/false,
            "term": {
                "id": "GO:0009908",
                "name": "flower development",
                "namespace": "biological_process",
                "definition": "...",
                "parents": [...],
                "children": [...]
            }
        }
    """
    go_service = getattr(current_app, 'go_service', None)
    
    if not go_service or not go_service.is_available():
        return jsonify({
            'available': False,
            'message': 'GO service not available'
        }), 200
    
    try:
        term = go_service.get_term(go_id)
        if not term:
            return jsonify({'error': 'GO term not found'}), 404
        
        # Optionally include hierarchy
        include_hierarchy = request.args.get('hierarchy', 'false').lower() == 'true'
        if include_hierarchy:
            term['parents'] = go_service.get_parents(go_id)
            term['children'] = go_service.get_children(go_id)
        
        return jsonify({
            'available': True,
            'term': term
        }), 200
    except Exception as e:
        logger.error(f"GO term detail error: {e}")
        return jsonify({'error': 'Failed to retrieve term', 'details': str(e)}), 500


@api_bp.route('/api/go/terms/batch', methods=['POST'])
def go_terms_batch():
    """
    Get detailed information for multiple GO terms in one request.
    
    Request Body:
        {
            "go_ids": ["GO:0009908", "GO:0003700", ...],
            "include_depth": true  // Optional, default true
        }
    
    Returns:
        {
            "available": true/false,
            "terms": {
                "GO:0009908": {
                    "id": "GO:0009908",
                    "name": "flower development",
                    "namespace": "biological_process",
                    "definition": "...",
                    "depth": 8  // Shortest path to root (0 = root category)
                },
                ...
            },
            "not_found": ["GO:0000000", ...]
        }
    """
    go_service = getattr(current_app, 'go_service', None)
    go_hierarchy = getattr(current_app, 'go_hierarchy', None)
    
    if not go_service or not go_service.is_available():
        return jsonify({
            'available': False,
            'terms': {},
            'not_found': [],
            'message': 'GO service not available'
        }), 200
    
    try:
        data = request.get_json()
        go_ids = data.get('go_ids', [])
        include_depth = data.get('include_depth', True)
        
        if not isinstance(go_ids, list):
            return jsonify({'error': 'go_ids must be a list'}), 400
        
        if len(go_ids) > 500:
            return jsonify({'error': 'Maximum 500 GO IDs per request'}), 400
        
        terms = {}
        not_found = []
        
        for go_id in go_ids:
            term = go_service.get_term(go_id)
            if term:
                # Add depth if requested and hierarchy helper is available
                if include_depth and go_hierarchy:
                    term['depth'] = go_hierarchy.get_depth(go_id)
                terms[go_id] = term
            else:
                not_found.append(go_id)
        
        return jsonify({
            'available': True,
            'terms': terms,
            'not_found': not_found
        }), 200
    except Exception as e:
        logger.error(f"GO terms batch error: {e}")
        return jsonify({'error': 'Failed to retrieve terms', 'details': str(e)}), 500


@api_bp.route('/api/go/status', methods=['GET'])
def go_status():
    """
    Check if GO service is available and loaded.
    
    Returns:
        {
            "available": true/false,
            "term_count": 12345,
            "message": "..."
        }
    """
    go_service = getattr(current_app, 'go_service', None)
    
    if not go_service:
        return jsonify({
            'available': False,
            'term_count': 0,
            'message': 'GO service not initialized'
        }), 200
    
    return jsonify({
        'available': go_service.is_available(),
        'term_count': len(go_service.go_index) if go_service.loaded else 0,
        'message': 'GO service ready' if go_service.is_available() else 'GO service not loaded'
    }), 200


# ============================================================================
# ORA (Over-Representation Analysis) Endpoint
# ============================================================================

@api_bp.route('/api/ora', methods=['POST'])
def calculate_ora():
    """
    Calculate Over-Representation Analysis (ORA) for a filtered gene set.
    
    Request Body:
        {
            "table_name": "species_name",
            "column_name": "ortho_id",  // Column containing attributes (e.g., GO terms, orthogroups)
            "filters": [...],              // Filters defining the gene subset (e.g., TF Family = MIKC)
            "significance": 0.01,          // FDR threshold (default: 0.01)
            "top_n": 10,                   // Max results to return (default: 10)
            "min_count": 3                 // Minimum genes in subset with attribute (default: 3)
        }
    
    Returns:
        {
            "results": [
                {
                    "attribute": "OG0000123",
                    "subset_count": 5,         // Number of genes in subset with this attribute
                    "background_count": 20,    // Total genes in species with this attribute
                    "subset_size": 46,         // Total genes in subset
                    "background_size": 30000,  // Total genes in species
                    "gene_ratio": 0.25,        // subset_count / background_count
                    "p_value": 0.0001,         // Fisher's exact test p-value
                    "q_value": 0.005,          // Benjamini-Hochberg FDR-adjusted p-value
                    "combined_score": 45.2     // -log10(q_value) * (subset_count / background_count)
                },
                ...
            ],
            "metadata": {
                "subset_size": 46,
                "background_size": 30000,
                "total_tests": 1247,
                "significant_count": 23,
                "column_type": "array"
            }
        }
    
    Notes:
        - Background is ALL genes in the same species (not filtered)
        - For array columns (e.g., orthogroups), counts UNIQUE GENES, not occurrences
        - Multiple testing correction using Benjamini-Hochberg FDR
        - Results sorted by combined_score (descending)
        - Only returns terms with q_value < significance AND subset_count >= min_count
    """
    try:
        service = get_service()
        data = request.get_json()
        
        # Validate required parameters
        table_name = data.get('table_name')
        column_name = data.get('column_name')
        filters = data.get('filters', [])
        filter_chain = data.get('filter_chain')
        
        if not table_name or not column_name:
            return jsonify({'error': 'table_name and column_name are required'}), 400
        
        # Optional parameters with defaults
        significance = float(data.get('significance', 0.01))
        top_n = int(data.get('top_n', 10))
        min_count = int(data.get('min_count', 3))
        go_depth_min = int(data.get('go_depth_min', 0) or 0)
        
        # Validate table and column
        validate_table_name([table_name], service.get_tables)
        validate_column_by_type(
            column_name,
            lambda source=None: service.get_all_columns(table_name=table_name, source=source) if source else service.get_all_columns(table_name=table_name),
            allowed_types=('text', 'array')
        )
        
        # Get column metadata
        columns_meta = service.get_all_columns(table_name)
        column_meta = next((c for c in columns_meta if c['column_name'] == column_name), None)
        if not column_meta:
            return jsonify({'error': f'Column {column_name} not found'}), 404
        
        column_type = column_meta['type'].lower()
        
        # Convert filters from list format [{column, value}] to dict format {column: value}
        filters_dict = {}
        if isinstance(filters, list):
            for f in filters:
                if isinstance(f, dict) and 'column' in f and 'value' in f:
                    filters_dict[f['column']] = f['value']
        elif isinstance(filters, dict):
            filters_dict = filters
        
        # Parse filters for subset
        parsed_filters = parse_filters(
            filters_dict,
            lambda source=None: service.get_all_columns(table_name=table_name, source=source) if source else service.get_all_columns(table_name=table_name),
            source="meta"
        )
        
        max_subset_size = int(data.get('max_subset_size', 0))
        
        # Get GO hierarchy helper if available
        go_hierarchy = getattr(current_app, 'go_hierarchy', None)
        go_service = getattr(current_app, 'go_service', None)
        
        # Call service method to compute ORA
        ora_result = service.calculate_ora(
            table_name=table_name,
            column_name=column_name,
            filters=parsed_filters,
            filter_chain=filter_chain,
            significance=significance,
            top_n=top_n,
            min_count=min_count,
            go_depth_min=go_depth_min,
            column_type=column_type,
            go_hierarchy=go_hierarchy,
            max_subset_size=max_subset_size,
            go_service=go_service
        )
        
        return jsonify(ora_result), 200
        
    except ValueError as e:
        logger.error(f"ORA validation error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"ORA calculation error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to calculate ORA', 'details': str(e)}), 500


# ============================================================================
# POST /api/cluster - Hierarchical Clustering (for large datasets)
# ============================================================================

@api_bp.route('/api/cluster', methods=['POST', 'OPTIONS'])
def cluster_data():
    """
    Perform hierarchical clustering on expression data.
    
    Use this endpoint for datasets with > 100 rows to offload computation to the backend.
    
    Request Body:
        {
            "table_name": "gene_expression_aquilegia_coerulea",
            "filters": [{"column": "ortho_id", "value": "OG0000001"}],
            "sample_filters": {},
            "layer": "getmm",           // Optional: expression layer
            "transform": "zscore",      // 'raw', 'log2', 'zscore'
            "cluster_rows": true,       // Whether to cluster rows
            "cluster_cols": true,       // Whether to cluster columns
            "method": "average",        // 'average' (UPGMA), 'complete', 'ward'
            "distance": "correlation"   // 'correlation', 'euclidean'
        }
    
    Returns:
        {
            "row_order": [3, 1, 4, 0, 2, ...],   // Optimal permutation for rows (0-indexed)
            "col_order": [5, 2, 8, 1, ...],      // Optimal permutation for columns (0-indexed)
            "metadata": {
                "n_rows": 150,
                "n_cols": 84,
                "method": "average",
                "distance": "correlation",
                "layer_used": "getmm",
                "transform": "zscore"
            }
        }
    """
    try:
        # Handle OPTIONS preflight request
        if request.method == 'OPTIONS':
            response = jsonify({'status': 'ok'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
            response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
            return response
        
        service = get_service()
        data = request.get_json()
        
        # Required parameters
        table_name = data.get('table_name')
        if not table_name:
            return jsonify({'error': 'table_name is required'}), 400
        
        # Validate table
        validate_table_name([table_name], service.get_tables)
        
        # Optional parameters
        filters = data.get('filters', {})
        sample_filters = data.get('sample_filters', {})
        layer = data.get('layer')
        transform = data.get('transform', 'zscore')
        cluster_rows = data.get('cluster_rows', True)
        cluster_cols = data.get('cluster_cols', True)
        method = data.get('method', 'average')
        distance = data.get('distance', 'correlation')
        
        # Validate method and distance
        if method not in ('average', 'complete', 'ward'):
            return jsonify({'error': f'Invalid method: {method}. Use average, complete, or ward'}), 400
        if distance not in ('correlation', 'euclidean'):
            return jsonify({'error': f'Invalid distance: {distance}. Use correlation or euclidean'}), 400
        
        # Parse filters using the same logic as /api/data so frontend FilterValue
        # objects ({value, match_mode, exact}) are converted to internal (op, val) tuples.
        get_cols = lambda **kw: service.get_all_columns(table_name=table_name, **kw)
        parsed_filters = parse_filters(filters, get_cols) if filters else {}
        parsed_sample_filters = parse_filters(sample_filters, get_cols, source="column_meta") if sample_filters else {}

        # Perform clustering
        result = service.perform_clustering(
            table_name=table_name,
            filters=parsed_filters if parsed_filters else None,
            sample_filters=parsed_sample_filters if parsed_sample_filters else None,
            layer=layer,
            transform=transform,
            cluster_rows=cluster_rows,
            cluster_cols=cluster_cols,
            method=method,
            distance=distance
        )
        
        return jsonify(result), 200
        
    except ValueError as e:
        logger.error(f"Clustering validation error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Clustering error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to perform clustering', 'details': str(e)}), 500


# ============================================================================
# Landing Page / Overview / AI Assistant
# ============================================================================

from . import assistant as assistant_module
from . import assistant_tools as assistant_tools_module
from .overview import build_overview as _build_overview

_assistant_limiter = assistant_module.RateLimiter(max_requests=30, window_seconds=60)

ASSISTANT_DEEPLINK_VIEWS = {"heatmap", "compare", "phylo", "ora", "catalog"}


def _client_ip() -> str:
    return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr or "anon")


@api_bp.route('/api/features', methods=['GET'])
def features():
    """Public feature-flag endpoint. Never exposes secrets."""
    try:
        service = get_service()
        cm = current_app.config_manager
        tables = service.get_tables()
        assistant_on = assistant_module.is_assistant_enabled(cm)
        cfg = assistant_module.get_llm_config(cm) if assistant_on else {}
        corporate = cm.get_config().get("corporate_identity", {}) or {}
        return jsonify({
            "assistant_enabled": assistant_on,
            "assistant": {
                "enabled": assistant_on,
                "display_name": corporate.get("llm_name") or "AI Assistant",
                "model": cfg.get("model") if assistant_on else None,
            },
            "analysis_limits": assistant_tools_module.get_analysis_limits(cm),
            "dataset_count": len(tables),
            "project_name": cm.get_config().get("project_name", "GenXBrowser"),
            "version": cm.get_config().get("version", ""),
        }), 200
    except Exception as e:
        logger.error(f"/api/features failed: {e}", exc_info=True)
        return jsonify({
            "assistant_enabled": False,
            "dataset_count": 0,
            "error": str(e),
        }), 200


@api_bp.route('/api/analysis-limits', methods=['GET'])
def analysis_limits():
    """Public dynamic analysis limits used by UI and assistant guards."""
    try:
        return jsonify(assistant_tools_module.get_analysis_limits(current_app.config_manager)), 200
    except Exception as e:
        logger.error(f"/api/analysis-limits failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/overview', methods=['GET'])
def overview():
    """Aggregate data-agnostic overview for the landing page."""
    try:
        service = get_service()
        cm = current_app.config_manager
        data = _build_overview(service, cm)
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"/api/overview failed: {e}", exc_info=True)
        return jsonify({"error": "Failed to build overview", "details": str(e)}), 500


@api_bp.route('/api/overview/mtime', methods=['GET'])
def overview_mtime():
    """Cheap cache-freshness probe — returns max mtime across H5ADs + config."""
    try:
        from .overview import _overview_mtime
        service = get_service()
        cm = current_app.config_manager
        return jsonify({"mtime": _overview_mtime(service, cm)}), 200
    except Exception as e:
        logger.error(f"/api/overview/mtime failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def _build_assistant_context(service, cm, selected_tables: Optional[List[str]] = None) -> str:
    """Compact JSON description of loaded datasets injected into the system prompt.

    When `selected_tables` is non-empty, the species list is restricted to
    those entries (matching `code`, `full_name`, or `table_name`,
    case-insensitive) plus a short `omitted_species` summary so the LLM
    knows other tables exist but their schemas weren't inlined. This keeps
    the prompt small on multi-species deployments without hiding the
    catalogue entirely.
    """
    import json as _json
    try:
        overview_data = _build_overview(service, cm)
        species_full = overview_data["species"]
        selected_set = None
        if selected_tables:
            selected_set = {str(t).lower() for t in selected_tables if t}

        kept_species: List[Dict[str, Any]] = []
        omitted_codes: List[str] = []
        for s in species_full:
            keys = {str(s.get("code") or "").lower(),
                    str(s.get("full_name") or "").lower(),
                    str(s.get("table_name") or "").lower()}
            keys.discard("")
            if selected_set is None or keys & selected_set:
                kept_species.append(s)
            else:
                omitted_codes.append(s.get("code") or "")

        slim = {
            "project": overview_data["project"],
            "global": {
                k: v for k, v in overview_data["global"].items()
                if k in ("n_species", "n_samples", "n_genes", "orthogroup_count",
                         "gene_tree_count", "tf_total")
            },
            "services": {
                # Surface which optional backend services are wired up so the
                # LLM never has to guess (or worse, claim "not available").
                "go_ontology_loaded": bool(
                    getattr(current_app, "go_service", None)
                    and current_app.go_service.is_available()
                ),
            },
            "species": [
                {
                    "code": s["code"],
                    "full_name": s["full_name"],
                    "n_samples": s["n_samples"],
                    "n_genes": s["n_genes"],
                    "layers": s["layers"],
                    "var_columns": s["var_columns"][:40],
                    "obs_columns": s["obs_columns"][:40],
                    "annotation_coverage": s.get("annotation_coverage", {}),
                    "tissue_distribution": s.get("derived", {}).get("tissue_distribution", [])[:10],
                    "tf_count": s.get("derived", {}).get("tf_count"),
                    "orthogroup_count": s.get("derived", {}).get("orthogroup_count"),
                }
                for s in kept_species
            ],
        }
        if selected_set is not None and omitted_codes:
            slim["omitted_species"] = {
                "count": len(omitted_codes),
                "codes": [c for c in omitted_codes if c][:50],
                "note": "Schema omitted to keep prompt small. Call list_schema for details.",
            }
        return _json.dumps(slim, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Assistant context build failed: {e}")
        return "{}"


@api_bp.route('/api/assistant/chat', methods=['POST'])
def assistant_chat():
    """OpenAI-compatible chat proxy with SSE streaming.

    Request body: {messages: [{role, content}], stream?: bool, include_context?: bool}
    """
    cm = current_app.config_manager
    if not assistant_module.is_assistant_enabled(cm):
        return jsonify({"error": "Assistant is not configured"}), 404

    ok, retry_in = _assistant_limiter.allow(_client_ip())
    if not ok:
        resp = jsonify({"error": "Rate limit exceeded", "retry_after_s": retry_in})
        resp.status_code = 429
        return resp

    body = request.get_json(silent=True) or {}
    messages = body.get("messages") or []
    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "messages[] required"}), 400
    for m in messages:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant", "system") or not isinstance(m.get("content"), str):
            return jsonify({"error": "malformed message"}), 400
    # Hard cap on total prompt size.
    total_chars = sum(len(m["content"]) for m in messages)
    if total_chars > 32000:
        return jsonify({"error": "prompt too large (max 32000 chars)"}), 413

    cfg = assistant_module.get_llm_config(cm)
    include_context = body.get("include_context", True)
    stream = bool(body.get("stream", True))
    tool_calling_enabled = bool(cfg.get("tool_calling_enabled", True))
    max_tool_iterations = int(cfg.get("max_tool_iterations", 6))
    tool_deadline_s = float(cfg.get("tool_deadline_s", 90))

    # Build the rich system prompt (role + action grammar + tool policy + few-shots).
    from .prompt_builder import build_system_prompt
    client_ctx = body.get("client_context") or {}
    # Slim DATA_CONTEXT to the species the user is currently looking at when
    # the frontend tells us which tables are selected. The full catalogue is
    # still discoverable via the `list_schema` tool.
    selected_for_ctx: Optional[List[str]] = None
    if isinstance(client_ctx, dict):
        raw_sel = client_ctx.get("selected_table_names") or client_ctx.get("tables")
        if isinstance(raw_sel, list) and raw_sel:
            selected_for_ctx = [str(x) for x in raw_sel if x]

    data_ctx: Optional[Dict[str, Any]] = None
    if include_context:
        try:
            import json as _json
            data_ctx = _json.loads(
                _build_assistant_context(get_service(), cm, selected_for_ctx)
            )
        except Exception:
            data_ctx = None

    ui_ctx: Optional[Dict[str, Any]] = None
    if isinstance(client_ctx, dict) and client_ctx:
        ui_ctx = {
            k: client_ctx.get(k)
            for k in ("view", "route", "tables", "filters", "visualizations",
                      "selection", "visible_genes", "selected_table_names",
                      "analysis_results")
            if client_ctx.get(k) is not None
        }

    sys_prompt = build_system_prompt(
        base_prompt=cfg.get("system_prompt") or "",
        data_context=data_ctx,
        ui_context=ui_ctx,
        include_fewshot=True,
    )

    final_messages: List[Dict[str, Any]] = (
        [{"role": "system", "content": sys_prompt}]
        + [{"role": m["role"], "content": m["content"]} for m in messages]
    )

    # -- Agentic tool-calling path ------------------------------------------
    if tool_calling_enabled:
        from . import assistant_tools
        service = get_service()
        flask_app = current_app._get_current_object()

        def _dispatch(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
            with flask_app.app_context():
                return assistant_tools.dispatch_tool_call(
                    name, args, service=service, config_manager=cm,
                )

        tools_schema = assistant_tools.openai_schema()

        def _sse_event_generator():
            try:
                for ev in assistant_module.run_agentic_turn(
                    cfg, final_messages,
                    tools=tools_schema,
                    dispatch=_dispatch,
                    max_iterations=max_tool_iterations,
                    tool_deadline_s=tool_deadline_s,
                ):
                    etype = ev.get("type")
                    if etype == "tool_start":
                        yield (
                            f"event: tool\n"
                            f"data: {json.dumps({'status': 'running', 'name': ev.get('name'), 'id': ev.get('id'), 'args': ev.get('args')}, ensure_ascii=False)}\n\n"
                        )
                    elif etype == "tool_result":
                        # Keep result summary compact on the wire.
                        result = ev.get("result") or {}
                        summary: Dict[str, Any]
                        if isinstance(result, dict) and "error" in result:
                            summary = {"error": str(result.get("error"))[:200]}
                        elif isinstance(result, dict):
                            summary = {k: result[k] for k in list(result.keys())[:6]}
                        else:
                            summary = {"_": str(result)[:200]}
                        yield (
                            f"event: tool\n"
                            f"data: {json.dumps({'status': 'done', 'name': ev.get('name'), 'id': ev.get('id'), 'summary': summary}, ensure_ascii=False)}\n\n"
                        )
                    elif etype == "delta":
                        text = ev.get("delta") or ""
                        # Deltas now arrive token-sized straight from the
                        # upstream stream. Forward as-is so the UI sees
                        # tokens the moment the model emits them.
                        frame: Dict[str, Any] = {"delta": text}
                        if ev.get("replace"):
                            frame["replace"] = True
                        yield f"data: {json.dumps(frame)}\n\n"
                    elif etype == "status":
                        yield (
                            f"event: status\n"
                            f"data: {json.dumps({'phase': ev.get('phase'), 'iteration': ev.get('iteration'), 'max_iterations': ev.get('max_iterations')})}\n\n"
                        )
                    elif etype == "thought":
                        yield (
                            f"event: thought\n"
                            f"data: {json.dumps({'content': ev.get('content') or ''}, ensure_ascii=False)}\n\n"
                        )
                    elif etype == "done":
                        # Charge extra rate-limit weight equal to the number of
                        # tool iterations actually consumed (the initial
                        # `allow()` already booked weight=1, so we add the rest).
                        try:
                            iters = int(ev.get("iterations") or 1)
                            _assistant_limiter.charge(_client_ip(), iters)
                        except Exception:
                            pass
                        yield f"event: done\ndata: {json.dumps({'model': ev.get('model'), 'iterations': ev.get('iterations')})}\n\n"
                    elif etype == "error":
                        yield f"event: error\ndata: {json.dumps({'error': ev.get('error')})}\n\n"
            except Exception as e:
                logger.error("assistant tool-loop generator failed: %s", e, exc_info=True)
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        if stream:
            from flask import Response, stream_with_context
            return Response(
                stream_with_context(_sse_event_generator()),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        # Non-streaming: run the generator to completion and return the text.
        text_parts: List[str] = []
        last_err: Optional[str] = None
        model_used: Optional[str] = None
        for ev in assistant_module.run_agentic_turn(
            cfg, final_messages, tools=tools_schema, dispatch=_dispatch,
            max_iterations=max_tool_iterations,
            tool_deadline_s=tool_deadline_s,
        ):
            if ev.get("type") == "delta":
                text_parts.append(ev.get("delta") or "")
                model_used = ev.get("model") or model_used
            elif ev.get("type") == "error":
                last_err = ev.get("error")
        if last_err and not text_parts:
            return jsonify({"error": last_err}), 502
        return jsonify({"ok": True, "model": model_used, "content": "".join(text_parts)}), 200

    # -- Legacy path (tool calling disabled) --------------------------------
    if stream:
        from flask import Response, stream_with_context
        generator = assistant_module.stream_chat(cfg, final_messages)
        return Response(stream_with_context(generator), mimetype="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        })

    result = assistant_module.complete_chat(cfg, final_messages)
    if not result.get("ok"):
        return jsonify({"error": result.get("error", "upstream error")}), 502
    return jsonify(result), 200


@api_bp.route('/api/assistant/suggestions', methods=['GET'])
def assistant_suggestions():
    """Dataset-grounded prompt suggestions for the assistant panel.

    Query params:
        n (int, default 4, max 10): number of suggestions to return.
        seed (int, optional): deterministic seed for reproducible output.

    Each refresh resamples templates + fillers from the live H5AD state, so
    every returned prompt maps to data that is actually loaded.
    """
    ok, retry_in = _assistant_limiter.allow(_client_ip())
    if not ok:
        return jsonify({"error": "Rate limit exceeded", "retry_after": retry_in}), 429
    try:
        n = int(request.args.get("n", "4"))
    except (TypeError, ValueError):
        n = 4
    seed_arg = request.args.get("seed")
    seed: Optional[int] = None
    if seed_arg is not None:
        try:
            seed = int(seed_arg)
        except (TypeError, ValueError):
            seed = None
    try:
        from .suggestions import generate_suggestions
        items = generate_suggestions(get_service(), current_app.config_manager, n=n, seed=seed)
        return jsonify({"suggestions": items, "count": len(items)}), 200
    except Exception as e:
        logger.error("/api/assistant/suggestions failed: %s", e, exc_info=True)
        return jsonify({"error": "Failed to build suggestions", "details": str(e)}), 500


@api_bp.route('/api/assistant/deeplink', methods=['POST'])
def assistant_deeplink():
    """Validate a proposed view state and persist via the share-ID store.

    Body: {view, tables[], filters{}, visualizations{}}. Returns {id, url_path}.

    Resilient against the LLM returning species codes, full names, or a mix.
    """
    body = request.get_json(silent=True) or {}
    view = str(body.get("view") or "catalog").strip().lower()
    raw_tables = body.get("tables") or []
    filters = body.get("filters") or {}
    visualizations = body.get("visualizations") or {}

    if view not in ASSISTANT_DEEPLINK_VIEWS:
        return jsonify({"error": f"Unknown view '{view}'", "allowed": sorted(ASSISTANT_DEEPLINK_VIEWS)}), 400
    if not isinstance(raw_tables, list):
        return jsonify({"error": "'tables' must be a list of strings"}), 400
    raw_tables = [str(t).strip() for t in raw_tables if str(t or "").strip()]
    if not isinstance(filters, dict) or not isinstance(visualizations, dict):
        return jsonify({"error": "'filters' and 'visualizations' must be objects"}), 400

    # Auto-expand the "all loaded species" sentinel so the assistant can
    # request every table without enumerating species codes. Empty input or
    # any of the literals "all" / "*" / "__all__" / "every" / "everything"
    # expands to the full list of enabled tables.
    _sentinels = {"all", "*", "__all__", "every", "everything"}
    if not raw_tables or any(t.lower() in _sentinels for t in raw_tables):
        try:
            entries = get_service().get_tables(include_disabled=False)
            raw_tables = [
                str(e.get("_species_code") or e.get("code"))
                for e in entries
                if (e.get("_species_code") or e.get("code"))
            ]
        except Exception as e:
            logger.warning("auto-expand of 'all tables' failed: %s", e)

    # Normalize multi-value filter entries so the persisted state matches
    # what the frontend filter store / TextFilter pill component expect
    # (pipe-separated values). Accepts arrays, comma- or newline-separated
    # strings from the assistant and rewrites them to "v1|v2|v3".
    try:
        from . import assistant_tools as _at
        filters = _at.normalize_filter_payload(filters)
        flat_filters = _at._deeplink_flat_filters(filters)
        if flat_filters and not isinstance(filters.get("filters"), dict):
            reserved = {
                key: value for key, value in filters.items()
                if key in {
                    "tags", "table_names", "datasetIdFilters", "idColumnName",
                    "filterChainColumns", "filterChainGroups", "filterChainVersion",
                }
            }
            filters = {**reserved, "filters": flat_filters}
    except Exception as e:
        logger.warning(f"filter normalization failed: {e}")

    # Size guardrails so a runaway LLM can't fill disk.
    import json as _json
    try:
        payload_size = len(_json.dumps({"filters": filters, "visualizations": visualizations}))
    except Exception:
        return jsonify({"error": "payload not JSON-serialisable"}), 400
    if payload_size > 32000:
        return jsonify({"error": f"payload too large ({payload_size} > 32000 bytes)"}), 413

    service = get_service()

    # Resolve codes / full names / table_names → canonical table_name for URL.
    resolved: List[str] = []
    unknown: List[str] = []
    try:
        lookup = {}
        for entry in service.get_tables(include_disabled=False):
            tn = entry.get("table_name")
            fn = entry.get("full_name") or tn
            code = entry.get("_species_code") or entry.get("code")
            for key in (tn, fn, code):
                if isinstance(key, str) and key:
                    lookup[key.lower()] = tn
        for t in raw_tables:
            hit = lookup.get(t.lower())
            if hit:
                if hit not in resolved:
                    resolved.append(hit)
            else:
                unknown.append(t)
    except Exception as e:
        logger.warning(f"deeplink table resolution failed: {e}", exc_info=True)

    if unknown:
        return jsonify({
            "error": f"Unknown table(s): {', '.join(unknown)}",
            "known": sorted({v for v in lookup.values()}) if 'lookup' in dir() else [],
        }), 400

    if view != "catalog" and not resolved:
        return jsonify({"error": "'tables' must contain at least one known dataset for this view"}), 400

    # SCHEMA VALIDATION: drop filter columns that don't exist in any of the
    # resolved tables, and surface them as warnings. Without this, the
    # frontend would silently ignore unknown columns and the user would see
    # a deep-link that doesn't filter as expected.
    warnings: List[str] = []
    if resolved and isinstance(filters, dict):
        nested_pre = filters.get("filters") if isinstance(filters.get("filters"), dict) else None
        if isinstance(nested_pre, dict) and nested_pre:
            known_cols: set = set()
            for tn in resolved:
                try:
                    code = service._normalize_table_name(tn)
                    adata = service.registry.load(code)
                except Exception:
                    adata = None
                if adata is None:
                    continue
                known_cols.update(adata.var.columns)
                known_cols.update(adata.obs.columns)
            if known_cols:
                unknown_cols = [c for c in nested_pre.keys() if c not in known_cols]
                if unknown_cols:
                    cleaned = {c: v for c, v in nested_pre.items() if c not in unknown_cols}
                    filters = dict(filters)
                    filters["filters"] = cleaned
                    warnings.append(
                        "Dropped unknown filter column(s): "
                        + ", ".join(sorted(unknown_cols))
                    )
                    logger.info(
                        "deeplink dropped unknown filter cols %s for tables %s",
                        unknown_cols, resolved,
                    )

    # GUARD: don't open empty plots. For data-bearing views, drop tables
    # whose .var or .obs rows are entirely cleared by the requested filters.
    # Filters arrive flat under ``filters.filters`` — we split them per
    # table into var- vs obs-filters by inspecting the loaded AnnData so a
    # sample-metadata filter (e.g. ``tissue=flower``) drops only the
    # species without matching samples instead of failing the whole
    # request with 422.
    dropped: List[Dict[str, Any]] = []
    guard_counts: List[Dict[str, Any]] = []
    if view in {"heatmap", "compare", "phylo", "ora"} and resolved:
        nested = filters.get("filters") if isinstance(filters, dict) else None
        flat_filters: Dict[str, List[str]] = {}
        if isinstance(nested, dict):
            for col, spec in nested.items():
                if not isinstance(spec, dict):
                    continue
                raw = spec.get("value")
                if isinstance(raw, list):
                    vals = [str(x) for x in raw if str(x).strip()]
                elif isinstance(raw, str) and raw:
                    vals = [x for x in raw.split("|") if x]
                else:
                    vals = []
                if vals:
                    flat_filters[col] = vals
        if flat_filters:
            try:
                from . import assistant_tools as _at
                kept: List[str] = []
                for tn in resolved:
                    code = service._normalize_table_name(tn)
                    try:
                        adata = service.registry.load(code)
                    except Exception:
                        adata = None
                    if adata is None:
                        kept.append(tn)
                        continue
                    var_cols = set(adata.var.columns)
                    obs_cols = set(adata.obs.columns)
                    var_f = {c: vs for c, vs in flat_filters.items() if c in var_cols}
                    obs_f = {c: vs for c, vs in flat_filters.items() if c in obs_cols}
                    cr = _at.tool_count_rows(
                        service, table=tn,
                        var_filters=var_f or None,
                        obs_filters=obs_f or None,
                    )
                    cr = cr if isinstance(cr, dict) else {}
                    n_var = int(cr.get("n_var_match", 0))
                    n_obs = int(cr.get("n_obs_match", 0))
                    guard_counts.append({
                        "table": tn,
                        "rows": n_var,
                        "n_var_match": n_var,
                        "n_obs_match": n_obs,
                    })
                    var_ok = (not var_f) or n_var > 0
                    obs_ok = (not obs_f) or n_obs > 0
                    if var_ok and obs_ok:
                        kept.append(tn)
                    else:
                        reason = (
                            "no transcripts match the gene filters"
                            if not var_ok
                            else "no samples match the sample filters"
                        )
                        dropped.append({"table": tn, "reason": reason})
                if not kept:
                    return jsonify({
                        "error": "all selected tables have zero rows matching the filters",
                        "dropped_tables": dropped,
                    }), 422
                resolved = kept
            except Exception as e:
                logger.warning(f"deeplink empty-table check failed: {e}", exc_info=True)

    if view in {"heatmap", "compare", "phylo", "ora"} and resolved:
        try:
            from . import assistant_tools as _at
            limit = _at.get_analysis_limits(current_app.config_manager).get(view, {}).get("max_rows")
            reusable_counts = guard_counts if limit is not None and guard_counts and {
                str(item.get("table")) for item in guard_counts
            } == set(resolved) else []
            if reusable_counts:
                over_limit = [
                    {"table": item["table"], "rows": int(item["rows"]), "max_rows": limit}
                    for item in reusable_counts
                    if int(item.get("rows", 0)) > int(limit)
                ]
                limit_check = {
                    "ok": not over_limit,
                    "view": view,
                    "limit": limit,
                    "over_limit": over_limit,
                    "counts": [
                        {"table": item["table"], "rows": int(item["rows"]), "max_rows": limit}
                        for item in reusable_counts
                    ],
                    "suggestion": "Ask for a gene, orthogroup, TF family, GO term, tissue, or another sidebar filter to reduce the result size.",
                }
                if over_limit:
                    labels = ", ".join(
                        f"{item['table']} ({item['rows']:,}/{int(limit):,})"
                        for item in over_limit
                    )
                    limit_check["error"] = (
                        f"{view} request exceeds the dynamic {int(limit):,} transcript limit: {labels}. "
                        "Ask the user for a narrower filter before opening this analysis."
                    )
            else:
                limit_check = _at.validate_analysis_request_limits(
                    service,
                    current_app.config_manager,
                    view=view,
                    tables=resolved,
                    filters=filters,
                )
            if not limit_check.get("ok", True):
                return jsonify(limit_check), 422
        except Exception as e:
            logger.warning(f"deeplink limit check failed: {e}", exc_info=True)

    stored_payload = {
        "filters": filters or {"__placeholder": True},
        "visualizations": visualizations or {"__placeholder": True},
    }
    try:
        hash_id = service.store_filter(stored_payload)
    except Exception as e:
        logger.error(f"store_filter failed: {e}", exc_info=True)
        return jsonify({"error": "Failed to persist deep-link state"}), 500

    prefix_by_view = {"heatmap": "h", "compare": "c", "phylo": "p", "ora": "o", "catalog": ""}
    prefix = prefix_by_view[view]
    if view == "catalog":
        url_path = f"/catalog?id={hash_id}" if resolved else f"/catalog?id={hash_id}"
    else:
        joined = ",".join(resolved)
        url_path = f"/{prefix}/{joined}?id={hash_id}"

    return jsonify({
        "id": hash_id,
        "url_path": url_path,
        "view": view,
        "tables": resolved,
        "dropped_tables": dropped,
        "warnings": warnings,
    }), 200


@api_bp.route('/api/assistant/compute', methods=['POST'])
def assistant_compute():
    """Compute a small, well-defined derived statistic on the user's current view.

    Body: {op, tables[], filters?: {var?:{col:[values...]}, obs?:{col:[values...]}}, args?: {}}

    Supported ops (all return at most 50 rows):
      - top_orthogroups: count genes per ortho_id within filtered var rows
      - top_tfs:         count TF family occurrences within filtered var rows
      - summary_stats:   basic numeric summary for a column
    """
    ok, _ = _assistant_limiter.allow(_client_ip())
    if not ok:
        return jsonify({"error": "Rate limit exceeded"}), 429

    body = request.get_json(silent=True) or {}
    op = str(body.get("op") or "").strip().lower()
    tables = body.get("tables") or []
    filters = body.get("filters") or {}
    args = body.get("args") or {}

    if op not in {"top_orthogroups", "top_tfs", "summary_stats"}:
        return jsonify({"error": f"Unsupported op '{op}'"}), 400
    if not isinstance(tables, list) or not tables:
        return jsonify({"error": "'tables' must be a non-empty list"}), 400

    service = get_service()
    # Resolve table names → species codes.
    code_lookup = {}
    for entry in service.get_tables(include_disabled=False):
        code = entry.get("_species_code") or entry.get("code")
        for key in (entry.get("table_name"), entry.get("full_name"), code):
            if isinstance(key, str) and key and code:
                code_lookup[key.lower()] = code
    species_codes = []
    for t in tables:
        c = code_lookup.get(str(t).lower())
        if c and c not in species_codes:
            species_codes.append(c)
    if not species_codes:
        return jsonify({"error": "No known tables resolved", "tables": tables}), 400

    import pandas as pd
    from collections import Counter

    def _apply_filters(adata):
        var_df = adata.var
        obs_df = adata.obs
        var_mask = pd.Series([True] * len(var_df), index=var_df.index)
        obs_mask = pd.Series([True] * len(obs_df), index=obs_df.index)
        for ns, colmap in (filters or {}).items():
            if ns not in ("var", "obs") or not isinstance(colmap, dict):
                continue
            target_df = var_df if ns == "var" else obs_df
            target_mask = var_mask if ns == "var" else obs_mask
            for col, spec in colmap.items():
                if col not in target_df.columns:
                    continue
                col_series = target_df[col]
                if isinstance(spec, list):
                    target_mask &= col_series.isin(spec)
                elif isinstance(spec, dict):
                    if "min" in spec:
                        target_mask &= col_series.astype(float) >= float(spec["min"])
                    if "max" in spec:
                        target_mask &= col_series.astype(float) <= float(spec["max"])
                    if "contains" in spec:
                        target_mask &= col_series.astype(str).str.contains(str(spec["contains"]), na=False)
                else:
                    target_mask &= col_series == spec
            if ns == "var":
                var_mask = target_mask
            else:
                obs_mask = target_mask
        return var_df[var_mask], obs_df[obs_mask]

    results = []
    try:
        for code in species_codes:
            adata = service.registry.load(code)
            if adata is None:
                continue
            var_f, obs_f = _apply_filters(adata)
            per_species = {"code": code, "n_var": int(len(var_f)), "n_obs": int(len(obs_f))}

            if op == "top_orthogroups":
                if "ortho_id" not in var_f.columns:
                    per_species["error"] = "ortho_id column not present"
                else:
                    vals = var_f["ortho_id"].dropna().astype(str)
                    vals = vals[vals.str.len() > 0]
                    top_k = int(args.get("top_k", 10))
                    counts = Counter(vals.tolist()).most_common(top_k)
                    per_species["top_orthogroups"] = [
                        {"ortho_id": og, "gene_count": int(n)} for og, n in counts
                    ]
            elif op == "top_tfs":
                if "tf_family" not in var_f.columns:
                    per_species["error"] = "tf_family column not present"
                else:
                    mask = var_f.get("is_tf")
                    src = var_f[mask.astype(bool)] if mask is not None else var_f
                    vals = src["tf_family"].dropna().astype(str)
                    vals = vals[vals.str.len() > 0]
                    top_k = int(args.get("top_k", 10))
                    per_species["top_tf_families"] = [
                        {"family": fam, "gene_count": int(n)}
                        for fam, n in Counter(vals.tolist()).most_common(top_k)
                    ]
            elif op == "summary_stats":
                col = str(args.get("column") or "").strip()
                ns = str(args.get("namespace") or "obs").strip()
                src = obs_f if ns == "obs" else var_f
                if col not in src.columns:
                    per_species["error"] = f"column '{col}' not present"
                else:
                    s = pd.to_numeric(src[col], errors="coerce").dropna()
                    if s.empty:
                        per_species["error"] = f"column '{col}' has no numeric values"
                    else:
                        per_species["stats"] = {
                            "min": float(s.min()), "max": float(s.max()),
                            "mean": float(s.mean()), "median": float(s.median()),
                            "std": float(s.std()), "count": int(s.size),
                        }
            results.append(per_species)
    except Exception as e:
        logger.error(f"/api/assistant/compute failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

    return jsonify({"op": op, "results": results}), 200


# ============================================================================
# Route Registration
# ============================================================================

def register_routes(app):
    """Register all routes with the Flask app."""
    from .admin_routes import admin_bp
    
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
