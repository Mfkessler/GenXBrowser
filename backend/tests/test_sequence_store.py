"""Tests for SequenceStore — robust multi-convention FASTA file discovery."""

from __future__ import annotations

import textwrap
import importlib.util
from pathlib import Path

import pytest

def _load_services_module():
    services_path = Path(__file__).resolve().parents[1] / "app" / "services.py"
    spec = importlib.util.spec_from_file_location("genxbrowser_services", services_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SequenceStore = _load_services_module().SequenceStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_fasta(path: Path, entries: dict[str, str]) -> None:
    """Write a minimal FASTA file from {id: sequence} mapping."""
    with open(path, 'w') as fh:
        for seq_id, seq in entries.items():
            fh.write(f">{seq_id}\n{seq}\n")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def seq_dir(tmp_path: Path) -> Path:
    """Return a temporary directory pre-populated with sequence files."""
    return tmp_path


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------

class TestBuildIndex:
    def test_legacy_dot_naming(self, seq_dir: Path) -> None:
        """Files named {code}.protein.fas / {code}.RNA.fas are indexed correctly."""
        write_fasta(seq_dir / "AT.protein.fas", {"gene1": "MSEQ"})
        write_fasta(seq_dir / "AT.RNA.fas", {"gene1": "ATCG"})

        store = SequenceStore(str(seq_dir))

        assert "AT" in store._index
        assert "protein" in store._index["AT"]
        assert "RNA" in store._index["AT"]

    def test_underscore_faa_naming(self, seq_dir: Path) -> None:
        """Files named {code}_proteins.faa / {code}_transcripts.fa are indexed correctly."""
        write_fasta(seq_dir / "OS_proteins.faa", {"OS_g1": "MSTQ"})
        write_fasta(seq_dir / "OS_transcripts.fa", {"OS_g1": "GCTA"})

        store = SequenceStore(str(seq_dir))

        assert "OS" in store._index
        assert "protein" in store._index["OS"]
        assert "RNA" in store._index["OS"]

    def test_multiple_species(self, seq_dir: Path) -> None:
        """Each species code gets its own entry in the index."""
        for code in ("AT", "OS", "SL"):
            write_fasta(seq_dir / f"{code}.protein.fas", {f"{code}_g1": "MPEPTIDE"})
            write_fasta(seq_dir / f"{code}.RNA.fas", {f"{code}_g1": "ATCGATCG"})

        store = SequenceStore(str(seq_dir))

        assert set(store._index.keys()) == {"AT", "OS", "SL"}

    def test_non_fasta_files_ignored(self, seq_dir: Path) -> None:
        """Non-FASTA files (e.g. .txt, .csv) are silently skipped."""
        (seq_dir / "readme.txt").write_text("ignore me")
        (seq_dir / "AT.protein.csv").write_text(">gene1\nMSEQ")
        write_fasta(seq_dir / "AT.protein.fas", {"gene1": "MSEQ"})

        store = SequenceStore(str(seq_dir))

        assert set(store._index.keys()) == {"AT"}

    def test_unrecognised_type_label_ignored(self, seq_dir: Path) -> None:
        """Files with an unknown type label between separator and extension are skipped."""
        write_fasta(seq_dir / "AT.unknown.fas", {"gene1": "MSEQ"})

        store = SequenceStore(str(seq_dir))

        assert store._index == {}

    def test_missing_directory(self, tmp_path: Path) -> None:
        """A non-existent sequences directory results in an empty index (no exception)."""
        store = SequenceStore(str(tmp_path / "nonexistent"))

        assert store._index == {}

    def test_empty_directory(self, seq_dir: Path) -> None:
        """An empty directory results in an empty index (no exception)."""
        store = SequenceStore(str(seq_dir))

        assert store._index == {}


# ---------------------------------------------------------------------------
# Sequence retrieval
# ---------------------------------------------------------------------------

class TestSequenceRetrieval:
    def test_get_protein_seq_legacy(self, seq_dir: Path) -> None:
        """get_protein_seq returns the correct sequence for legacy-named files."""
        write_fasta(seq_dir / "AT.protein.fas", {"AT_gene1": "MSTARVK", "AT_gene2": "MQVWER"})

        store = SequenceStore(str(seq_dir))

        assert store.get_protein_seq("AT", "AT_gene1") == "MSTARVK"
        assert store.get_protein_seq("AT", "AT_gene2") == "MQVWER"

    def test_get_rna_seq_underscore(self, seq_dir: Path) -> None:
        """get_rna_seq returns the correct sequence for underscore-named files."""
        write_fasta(seq_dir / "OS_transcripts.fa", {"OS_t1": "ATCGATCG"})

        store = SequenceStore(str(seq_dir))

        assert store.get_rna_seq("OS", "OS_t1") == "ATCGATCG"

    def test_unknown_gene_returns_empty(self, seq_dir: Path) -> None:
        """A gene ID not present in the FASTA file returns an empty string."""
        write_fasta(seq_dir / "AT.protein.fas", {"AT_gene1": "MSEQ"})

        store = SequenceStore(str(seq_dir))

        assert store.get_protein_seq("AT", "nonexistent_gene") == ""

    def test_unknown_species_returns_empty(self, seq_dir: Path) -> None:
        """A species code with no indexed file returns an empty string."""
        write_fasta(seq_dir / "AT.protein.fas", {"AT_gene1": "MSEQ"})

        store = SequenceStore(str(seq_dir))

        assert store.get_protein_seq("XY", "AT_gene1") == ""

    def test_missing_type_returns_empty(self, seq_dir: Path) -> None:
        """If only the protein file exists, get_rna_seq returns empty without error."""
        write_fasta(seq_dir / "AT.protein.fas", {"AT_gene1": "MSEQ"})

        store = SequenceStore(str(seq_dir))

        assert store.get_rna_seq("AT", "AT_gene1") == ""

    def test_cache_is_populated_after_first_call(self, seq_dir: Path) -> None:
        """The in-memory cache key is set after the first retrieval call."""
        write_fasta(seq_dir / "AT.protein.fas", {"AT_gene1": "MSEQ"})

        store = SequenceStore(str(seq_dir))
        store.get_protein_seq("AT", "AT_gene1")

        assert "AT_protein" in store._cache

    def test_multiline_fasta_parsed_correctly(self, seq_dir: Path) -> None:
        """FASTA sequences split across multiple lines are concatenated correctly."""
        fasta_content = textwrap.dedent("""\
            >gene1
            MSTARV
            KQWERT
            """)
        (seq_dir / "AT.protein.fas").write_text(fasta_content)

        store = SequenceStore(str(seq_dir))

        assert store.get_protein_seq("AT", "gene1") == "MSTARVKQWERT"

    def test_fasta_header_extra_tokens_ignored(self, seq_dir: Path) -> None:
        """Only the first token after '>' is used as the sequence ID."""
        fasta_content = ">gene1 some extra description\nMSEQ\n"
        (seq_dir / "AT.protein.fas").write_text(fasta_content)

        store = SequenceStore(str(seq_dir))

        assert store.get_protein_seq("AT", "gene1") == "MSEQ"
        assert store.get_protein_seq("AT", "gene1 some extra description") == ""


# ---------------------------------------------------------------------------
# Keyword coverage
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,expected_type", [
    ("SP.protein.fas",     "protein"),
    ("SP.proteins.fas",    "protein"),
    ("SP.prot.fas",        "protein"),
    ("SP.pep.faa",         "protein"),
    ("SP.aa.faa",          "protein"),
    ("SP.RNA.fas",         "RNA"),
    ("SP.rna.fas",         "RNA"),
    ("SP.transcript.fa",   "RNA"),
    ("SP.transcripts.fa",  "RNA"),
    ("SP.mrna.fa",         "RNA"),
    ("SP.cdna.fa",         "RNA"),
    ("SP.cds.fa",          "RNA"),
    ("SP.nucl.fas",        "RNA"),
    ("SP_proteins.faa",    "protein"),
    ("SP_transcripts.fa",  "RNA"),
])
def test_keyword_variants(tmp_path: Path, filename: str, expected_type: str) -> None:
    """All recognised keyword variants are mapped to the correct sequence type."""
    write_fasta(tmp_path / filename, {"SP_g1": "SEQ"})

    store = SequenceStore(str(tmp_path))

    assert "SP" in store._index, f"Species code not indexed for filename: {filename}"
    assert expected_type in store._index["SP"], (
        f"Type '{expected_type}' not indexed for filename: {filename}"
    )
