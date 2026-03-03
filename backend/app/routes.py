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
    COMMA_ARRAY_COLUMNS = {'go_term', 'interpro_term', 'pfam_term'}
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


def parse_filters(filters, get_columns_func, source="meta"):
    """
    Parse filter input from frontend format to internal format.
    
    Frontend sends: {"column": value} or {"column": {"value": v, "strict": bool}}
    Internal format: {"column": (operator, value)}
    
    Args:
        filters: Filter dict from frontend
        get_columns_func: Function to get column metadata
        source: "meta" for gene metadata filters, "column_meta" for sample metadata filters
    """
    if not filters:
        return {}
    
    # Get allowed columns and their types
    allowed_types = {"text", "array", "bigint", "double precision", "boolean"}
    all_columns = get_columns_func(source=source)
    allowed_columns = {
        col["column_name"]: col.get("type", "text").lower()
        for col in all_columns
        if col.get("type", "text").lower() in allowed_types
    }
    
    logger.debug(f"[parse_filters] source={source}, incoming filters keys: {list(filters.keys())}")
    
    def parse_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            val = value.strip().lower()
            if val in {'true', 't'}:
                return True
            if val in {'false', 'f'}:
                return False
        return None
    
    def parse_value(val):
        bval = parse_bool(val)
        if isinstance(bval, bool):
            return bval
        if isinstance(val, str):
            return [v.strip() for v in val.split("|") if v.strip()]
        return val
    
    filter_query = {}
    
    for key, value in filters.items():
        col_type = allowed_columns.get(key)
        if not col_type:
            continue
        
        # Handle None
        if value is None:
            filter_query[key] = (None, None)
            continue
        
        # Handle direct boolean
        if isinstance(value, bool) and col_type == "boolean":
            filter_query[key] = ("eq", value)
            continue
        
        # Handle direct list/array
        if isinstance(value, list):
            values = value
            if col_type == "array":
                filter_query[key] = ("array_overlap", values)
            elif col_type == "text":
                filter_query[key] = ("in", values) if len(values) > 1 else ("eq", values[0])
            elif col_type in ("bigint", "integer", "double precision") and len(values) == 2:
                try:
                    num1 = float(values[0]) if col_type == "double precision" else int(values[0])
                    num2 = float(values[1]) if col_type == "double precision" else int(values[1])
                    if num2 > num1:
                        filter_query[key] = ("range", (num1, num2))
                except (ValueError, TypeError):
                    pass
            continue
        
        # Handle direct string
        if isinstance(value, str):
            values = parse_value(value)
            if col_type == "text":
                if not values:
                    continue
                filter_query[key] = ("in", values) if len(values) > 1 else ("eq", values[0])
            elif col_type == "boolean":
                filter_query[key] = ("eq", values)
            elif col_type == "array":
                filter_query[key] = ("array_overlap", values)
            continue
        
        # Handle dict with "value" key
        if isinstance(value, dict) and "value" in value:
            values = parse_value(value["value"])
            if values is None:
                filter_query[key] = (None, None)
            elif col_type == "text":
                if not values:
                    continue
                filter_query[key] = ("in", values) if len(values) > 1 else ("eq", values[0])
            elif col_type == "array":
                if value.get("strict") is True:
                    filter_query[key] = ("array_contains", values)
                else:
                    filter_query[key] = ("array_overlap", values)
            elif col_type in ("bigint", "integer"):
                if len(values) != 2:
                    continue
                try:
                    num1, num2 = int(values[0]), int(values[1])
                    if num2 > num1:
                        filter_query[key] = ("range", (num1, num2))
                except ValueError:
                    continue
            elif col_type == "double precision":
                if len(values) != 2:
                    continue
                try:
                    num1, num2 = float(values[0]), float(values[1])
                    if num2 > num1:
                        filter_query[key] = ("range", (num1, num2))
                except ValueError:
                    continue
            elif col_type == "boolean":
                filter_query[key] = ("eq", values)
            continue
        
        # Handle dict with "type" and "values" keys (new format)
        if isinstance(value, dict) and "type" in value and "values" in value:
            col_type_from_filter = value["type"]
            values = value["values"]
            
            if not isinstance(values, list):
                values = [values]
            
            if col_type_from_filter == "array":
                if value.get("strict") is True:
                    filter_query[key] = ("array_contains", values)
                else:
                    filter_query[key] = ("array_overlap", values)
            elif col_type_from_filter == "text":
                if not values:
                    continue
                filter_query[key] = ("in", values) if len(values) > 1 else ("eq", values[0])
            elif col_type_from_filter in ("bigint", "integer", "double precision"):
                if len(values) == 2:
                    try:
                        num1 = float(values[0]) if col_type_from_filter == "double precision" else int(values[0])
                        num2 = float(values[1]) if col_type_from_filter == "double precision" else int(values[1])
                        if num2 > num1:
                            filter_query[key] = ("range", (num1, num2))
                    except (ValueError, TypeError):
                        continue
            elif col_type_from_filter == "boolean":
                filter_query[key] = ("eq", values[0] if values else False)
            continue
        
        # Handle dict with other keys
        if isinstance(value, dict):
            values = parse_value(value.get("value", ""))
            if col_type == "text":
                if not values:
                    continue
                filter_query[key] = ("in", values) if len(values) > 1 else ("eq", values[0])
            elif col_type == "array":
                filter_query[key] = ("array_overlap", values)
            elif col_type == "boolean":
                filter_query[key] = ("eq", values)
    
    return filter_query


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
    """Get row count for a table with optional filters."""
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "Missing or invalid JSON payload"}), 400
        
        schema = QueryRequestSchema()
        data = schema.load(data)
        table_name = data.get('table_name')
        filters = data.get('filters')
        
        service = get_service()
        
        # Validate table (accepts both full names and short codes)
        is_valid, err = validate_table_name(table_name, service.get_tables)
        if not is_valid:
            return jsonify({"error": "Invalid 'table_name'"}), 400
        
        # Parse and apply filters
        parsed_filters = parse_filters(filters, service.get_all_columns)
        count = service.get_row_count(table_name, parsed_filters)
        
        return jsonify({"count": count})
    
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
        
        # Debug: Log parsed filters
        logger.info(f"[list_data] parsed_filters: {parsed_filters}")
        logger.info(f"[list_data] parsed_sample_filters: {parsed_sample_filters}")
        
        # Add gene_ids filter if provided
        if gene_ids:
            parsed_filters['gene_id'] = ('in', gene_ids)
        
        # Get data with layer metadata
        df, layer_metadata = service.get_data(
            table_name, 
            columns, 
            filters=parsed_filters,
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

@api_bp.route('/gene_tree/<og_id>', methods=['GET'])
def get_gene_tree(og_id: str):
    """Get Newick tree for an orthogroup."""
    service = get_service()
    tree = service.get_gene_tree(og_id)
    
    if tree is None:
        return jsonify({'error': 'Gene tree not found'}), 404
    
    return jsonify({'og_id': og_id, 'newick': tree}), 200


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
        dataset_go_terms = set(service.get_unique_values('go_term'))
        
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
            "column_name": "orthogroup",  // Column containing attributes (e.g., GO terms, orthogroups)
            "filters": [...],              // Filters defining the gene subset (e.g., TF Family = MIKC)
            "significance": 0.01,          // FDR threshold (default: 0.01)
            "top_n": 50,                   // Max results to return (default: 50)
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
        
        if not table_name or not column_name:
            return jsonify({'error': 'table_name and column_name are required'}), 400
        
        # Optional parameters with defaults
        significance = float(data.get('significance', 0.01))
        top_n = int(data.get('top_n', 50))
        min_count = int(data.get('min_count', 3))
        
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
        
        # Get topological filter setting (default True for GO terms)
        topological_filter = data.get('topological_filter', True)
        max_subset_size = int(data.get('max_subset_size', 0))
        
        # Get GO hierarchy helper if available
        go_hierarchy = getattr(current_app, 'go_hierarchy', None)
        go_service = getattr(current_app, 'go_service', None)
        
        # Call service method to compute ORA
        ora_result = service.calculate_ora(
            table_name=table_name,
            column_name=column_name,
            filters=parsed_filters,
            significance=significance,
            top_n=top_n,
            min_count=min_count,
            column_type=column_type,
            topological_filter=topological_filter,
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
            "filters": [{"column": "orthogroup", "value": "OG0000001"}],
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
        # objects ({value, strict, empty}) are converted to internal (op, val) tuples.
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
# Route Registration
# ============================================================================

def register_routes(app):
    """Register all routes with the Flask app."""
    from .admin_routes import admin_bp
    
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
