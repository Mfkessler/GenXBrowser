import anndata as ad
import numpy as np
import pandas as pd

from h5ad_lib.core.discovery import discover_species_from_file


def test_discover_species_reads_default_sample_metadata_column(tmp_path):
    h5ad_path = tmp_path / "AT_full.h5ad"
    adata = ad.AnnData(
        X=np.array([[1.0, 2.0], [3.0, 4.0]]),
        obs=pd.DataFrame(
            {"condition": ["control", "treated"], "group": ["A", "B"]},
            index=["S1", "S2"],
        ),
        var=pd.DataFrame(index=["G1", "G2"]),
        uns={
            "name": "AT",
            "species": "Arabidopsis thaliana",
            "default_sample_metadata_column": "condition",
        },
    )
    adata.write_h5ad(h5ad_path)

    discovered = discover_species_from_file(str(h5ad_path))

    assert discovered is not None
    assert discovered["default_sample_metadata_column"] == "condition"