from genxprep.builder import build_species
from genxprep.config import GlobalMetadata, MatrixPaths, SpeciesConfig
from genxprep.reporter import Reporter, ValidationResult
from genxprep.validators.sample_mapping import validate_sample_mapping


def test_validate_sample_mapping_preserves_all_metadata_columns(tmp_path):
    mapping_path = tmp_path / "mapping.tsv"
    mapping_path.write_text(
        "sample\ttissue\tgroup\tcondition\n"
        "S1\tleaf\tA\tcontrol\n"
        "S2\troot\tB\ttreated\n"
    )
    validation = ValidationResult("sample mapping")

    mapping = validate_sample_mapping(mapping_path, {"S1", "S2"}, validation)

    assert mapping is not None
    assert list(mapping.columns) == ["Sample", "tissue", "group", "condition"]
    assert mapping.loc[0, "tissue"] == "leaf"
    assert validation.ok


def test_build_species_writes_sample_metadata_and_default_marker(tmp_path):
    matrix_path = tmp_path / "counts.tsv"
    matrix_path.write_text(
        "gene\tS1\tS2\n"
        "G1\t1\t2\n"
        "G2\t3\t4\n"
    )
    mapping_path = tmp_path / "mapping.tsv"
    mapping_path.write_text(
        "sample\ttissue\tgroup\tcondition\n"
        "S1\tleaf\tA\tcontrol\n"
        "S2\troot\tB\ttreated\n"
    )
    species = SpeciesConfig(
        code="AT",
        name="Arabidopsis thaliana",
        matrix=MatrixPaths(raw=matrix_path),
        sample_mapping=mapping_path,
    )

    adata = build_species(species, GlobalMetadata(), None, Reporter())

    assert adata is not None
    assert list(adata.obs.columns) == ["tissue", "group", "condition"]
    assert adata.uns["default_sample_metadata_column"] == "tissue"
    assert adata.obs.loc["S2", "condition"] == "treated"