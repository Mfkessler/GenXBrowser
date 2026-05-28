"""Regression tests for config-driven metadata visibility."""

from __future__ import annotations

import importlib.util
from types import SimpleNamespace
from pathlib import Path

import pandas as pd
from flask import Flask

def _load_module(name: str, relative_path: str):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


admin_routes = _load_module("genxbrowser_admin_routes", "app/admin_routes.py")
services_module = _load_module("genxbrowser_services", "app/services.py")

admin_bp = admin_routes.admin_bp
GenXBrowserService = services_module.GenXBrowserService


class DummyRegistry:
    def __init__(self, adata_by_species):
        self._adata_by_species = adata_by_species

    def load(self, species_code):
        return self._adata_by_species.get(species_code)


class DummyConfigManager:
    def __init__(self, config):
        self._config = config

    def get_column_definitions(self):
        return self._config.get("column_definitions", {})

    def get_config(self):
        return self._config

    def update_config(self, config):
        self._config = config
        return True

    def get_species(self):
        return self._config.get("species", {})


def build_service(config, adata_by_species):
    service = GenXBrowserService.__new__(GenXBrowserService)
    service.config_manager = DummyConfigManager(config)
    service.registry = DummyRegistry(adata_by_species)
    service._normalize_table_name = lambda table_name: table_name.removesuffix("_meta")
    service._to_h5ad_column_name = lambda column_name: column_name
    service._to_display_column_name = lambda column_name: column_name
    service._get_column_type = lambda dtype, _column: {
        "int64": "bigint",
        "float64": "double precision",
        "bool": "boolean",
    }.get(dtype, "text")
    service._custom_overlays = {}
    service._save_custom_overlays = lambda: None
    service.reload_config = lambda: None
    service.gene_trees = {}
    service.sequences = SimpleNamespace(
        get_protein_seq=lambda _species_code, gene_id: f"PROT:{gene_id}",
        get_rna_seq=lambda _species_code, gene_id: f"RNA:{gene_id}",
    )
    return service


def build_adata():
    return SimpleNamespace(
        obs=pd.DataFrame(
            {
                "tissue": ["leaf", "root"],
                "condition": ["stress", "control"],
                "assigned": [10, 12],
            },
            index=["sample_a", "sample_b"],
        ),
        var=pd.DataFrame(
            {
                "gene_id": ["g1", "g2"],
                "description": ["desc1", "desc2"],
            },
            index=["g1", "g2"],
        ),
        obs_names=pd.Index(["sample_a", "sample_b"]),
        var_names=pd.Index(["g1", "g2"]),
        X=pd.DataFrame([[1.0, 2.0], [3.0, 4.0]]).to_numpy(),
        layers={},
    )


def test_get_all_columns_hides_removed_sample_metadata_from_sidebar():
    adata = build_adata()
    config = {
        "species": {"AT": {"enabled": True}},
        "default_trait_column": "tissue",
        "column_definitions": {
            "tissue": {
                "display_name": "Tissue",
                "type": "text",
                "is_meta": False,
                "is_sample_metadata": True,
                "visible": True,
                "order": 0,
            },
            "assigned": {
                "display_name": "Assigned",
                "type": "bigint",
                "is_meta": False,
                "is_sample_metadata": True,
                "visible": True,
                "order": 1,
            },
            "description": {
                "display_name": "Description",
                "type": "text",
                "is_meta": True,
                "is_sample_metadata": False,
                "visible": True,
                "order": 2,
            },
        },
    }
    service = build_service(config, {"AT": adata})

    columns = service.get_all_columns(source="column_meta", table_name="AT")
    column_names = [column["column_name"] for column in columns]

    assert column_names == ["tissue", "assigned"]
    assert "condition" not in column_names


def test_meta_table_data_uses_dynamic_configured_sample_metadata_columns():
    adata = build_adata()
    config = {
        "species": {"AT": {"enabled": True}},
        "default_trait_column": "tissue",
        "column_definitions": {
            "tissue": {
                "display_name": "Tissue",
                "type": "text",
                "is_meta": False,
                "is_sample_metadata": True,
                "visible": True,
                "order": 0,
            },
            "condition": {
                "display_name": "Condition",
                "type": "text",
                "is_meta": False,
                "is_sample_metadata": True,
                "visible": True,
                "order": 1,
            },
        },
    }
    service = build_service(config, {"AT": adata})

    df = service._get_meta_table_data(adata, columns=[], limit=10, offset=0)

    assert list(df.columns) == ["column_name", "type", "description", "format", "ismeta", "tissue", "condition"]
    assert df.iloc[0]["condition"] == "stress"


def test_default_data_respects_sequence_visibility_for_tooltip_metadata():
    adata = build_adata()
    config = {
        "species": {"AT": {"enabled": True}},
        "column_definitions": {
            "description": {
                "display_name": "Description",
                "type": "text",
                "is_meta": True,
                "is_sample_metadata": False,
                "visible": True,
                "order": 0,
            },
            "protein_seq": {
                "display_name": "Protein Sequence",
                "type": "text",
                "is_meta": True,
                "is_sample_metadata": False,
                "visible": False,
                "order": 1,
            },
            "rna_seq": {
                "display_name": "RNA Sequence",
                "type": "text",
                "is_meta": True,
                "is_sample_metadata": False,
                "visible": True,
                "order": 2,
            },
        },
    }
    service = build_service(config, {"AT": adata})

    df, _ = service.get_data(table_name="AT", columns=[], filters={}, limit=10)

    assert "description" in df.columns
    assert "rna_seq" in df.columns
    assert "protein_seq" not in df.columns


def test_delete_metadata_column_cleans_stale_config_references():
    adata = build_adata()
    config = {
        "species": {"AT": {"enabled": True}},
        "default_trait_column": "condition",
        "meta_columns": [],
        "sample_metadata_columns": {
            "enabled": True,
            "columns": ["condition", "tissue"],
            "default_visible_columns": ["condition"],
        },
        "column_definitions": {
            "condition": {
                "display_name": "Condition",
                "type": "text",
                "is_meta": False,
                "is_sample_metadata": True,
                "visible": True,
                "order": 0,
                "source": "custom",
            },
            "tissue": {
                "display_name": "Tissue",
                "type": "text",
                "is_meta": False,
                "is_sample_metadata": True,
                "visible": True,
                "order": 1,
                "source": "auto",
            },
        },
    }

    app = Flask(__name__)
    app.register_blueprint(admin_bp)
    app.config_manager = DummyConfigManager(config)
    app.h5ad_service = build_service(config, {"AT": adata})

    with app.test_client() as client:
        response = client.delete("/api/admin/metadata/condition?persist=false")

    assert response.status_code == 200
    updated = app.config_manager.get_config()
    assert "condition" not in updated["column_definitions"]
    assert updated["sample_metadata_columns"]["columns"] == ["tissue"]
    assert updated["sample_metadata_columns"]["default_visible_columns"] == []
    assert updated["default_trait_column"] is None


def test_metadata_import_upserts_existing_custom_sample_column_for_another_dataset():
    at = build_adata()
    ps = build_adata()
    ps.obs.index = ["ps_sample_a", "ps_sample_b"]
    config = {
        "species": {"AT": {"enabled": True}, "PS": {"enabled": True}},
        "default_trait_column": "tissue",
        "sample_metadata_columns": {
            "enabled": True,
            "columns": ["tissue", "Group"],
            "default_visible_columns": [],
        },
        "column_definitions": {
            "tissue": {
                "display_name": "Tissue",
                "type": "text",
                "is_meta": False,
                "is_sample_metadata": True,
                "visible": True,
                "order": 0,
                "source": "auto",
            },
            "Group": {
                "display_name": "Group",
                "type": "text",
                "is_meta": False,
                "is_sample_metadata": True,
                "visible": True,
                "order": 1,
                "source": "custom",
            },
        },
    }

    app = Flask(__name__)
    app.register_blueprint(admin_bp)
    app.config_manager = DummyConfigManager(config)
    app.h5ad_service = build_service(config, {"AT": at, "PS": ps})

    payload = {
        "dataset": "PS",
        "target": "obs",
        "column_name": "Group",
        "display_name": "Group",
        "data": "sample_id\tgroup\nps_sample_a\ttreated\nps_sample_b\tcontrol\n",
        "separator": "\t",
        "id_column": "sample_id",
        "value_column": "group",
        "persist_to_h5ad": False,
        "apply_to_all_datasets": False,
    }

    with app.test_client() as client:
        validate_response = client.post("/api/admin/metadata/import", json=payload)
        confirm_response = client.post("/api/admin/metadata/import/confirm", json=payload)

    assert validate_response.status_code == 200
    assert validate_response.get_json()["validation"]["matched"] == 2
    assert confirm_response.status_code == 200
    body = confirm_response.get_json()
    assert body["success"] is True
    assert body["results"]["PS"]["status"] == "applied"
    assert list(ps.obs["Group"]) == ["treated", "control"]
    assert app.config_manager.get_config()["column_definitions"]["Group"]["source"] == "custom"
