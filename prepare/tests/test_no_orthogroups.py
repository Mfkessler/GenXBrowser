from pathlib import Path

import pandas as pd

from genxprep.builder import build_species
from genxprep.cli import _TEMPLATE_CONFIG
from genxprep.config import GlobalMetadata, MatrixPaths, SpeciesConfig
from genxprep.reporter import Reporter


def _write_matrix(path: Path, values: list[list[float]]) -> None:
    pd.DataFrame(values, index=["gene1", "gene2"], columns=["sample1", "sample2"]).to_csv(
        path, sep="\t"
    )


def test_template_supports_no_orthogroup_config() -> None:
    assert "# orthogroups:" in _TEMPLATE_CONFIG
    assert "# gene_trees:" in _TEMPLATE_CONFIG
    assert "# vst:" in _TEMPLATE_CONFIG


def test_build_without_orthogroups_uses_gene_ids_and_vst_layer(tmp_path: Path) -> None:
    raw = tmp_path / "raw.tsv"
    vst = tmp_path / "vst.tsv"
    _write_matrix(raw, [[1, 2], [3, 4]])
    _write_matrix(vst, [[0.1, 0.2], [0.3, 0.4]])

    species = SpeciesConfig(
        code="CR",
        name="Ceratopteris richardii",
        matrix=MatrixPaths(raw=raw, vst=vst),
    )
    adata = build_species(species, GlobalMetadata(), None, Reporter())

    assert adata is not None
    assert adata.var["gene_id"].tolist() == ["gene1", "gene2"]
    assert "ortho_id" not in adata.var.columns
    assert bool(adata.uns["has_orthogroups"]) is False
    assert "vst" in adata.layers


def test_build_with_orthogroups_preserves_mapping(tmp_path: Path) -> None:
    raw = tmp_path / "raw.tsv"
    _write_matrix(raw, [[1, 2], [3, 4]])
    species = SpeciesConfig(
        code="CR",
        name="Ceratopteris richardii",
        matrix=MatrixPaths(raw=raw),
    )
    orthogroups = pd.DataFrame(
        {"Orthogroup": ["OG1", "OG2"], "Ceratopteris richardii": ["gene1", "gene2"]}
    )

    adata = build_species(species, GlobalMetadata(), orthogroups, Reporter())

    assert adata is not None
    assert adata.var["ortho_id"].tolist() == ["OG1", "OG2"]
    assert bool(adata.uns["has_orthogroups"]) is True