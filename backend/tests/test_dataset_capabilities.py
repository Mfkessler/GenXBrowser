from types import SimpleNamespace

import pandas as pd

from h5ad_lib.core.capabilities import has_orthogroups


def _adata(var, uns=None):
    return SimpleNamespace(var=pd.DataFrame(var), uns=uns or {})


def test_capability_infers_legacy_populated_orthogroups() -> None:
    assert has_orthogroups(_adata({"gene_id": ["g1", "g2"], "ortho_id": ["", "OG1"]}))


def test_capability_rejects_missing_or_empty_orthogroups() -> None:
    assert not has_orthogroups(_adata({"gene_id": ["g1"]}))
    assert not has_orthogroups(_adata({"gene_id": ["g1"], "ortho_id": [""]}))


def test_explicit_capability_is_authoritative() -> None:
    assert not has_orthogroups(_adata({"ortho_id": ["OG1"]}, {"has_orthogroups": False}))
    assert has_orthogroups(_adata({"gene_id": ["g1"]}, {"has_orthogroups": True}))