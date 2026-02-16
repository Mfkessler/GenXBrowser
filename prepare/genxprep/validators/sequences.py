"""Sequences validator – validates FASTA files.

Checks that FASTA files are well-formed and that sequence IDs match the
gene IDs in the expression matrix.
"""

from __future__ import annotations

from pathlib import Path

from genxprep.id_checker import check_id_overlap
from genxprep.reporter import ValidationResult


def validate_fasta(
    path: Path,
    gene_ids: set[str],
    label: str,
    vr: ValidationResult,
) -> set[str] | None:
    """Validate a FASTA file.

    Returns the set of sequence IDs found, or *None* on fatal error.
    """
    if not path.exists():
        vr.error(f"{label} FASTA file not found: {path}")
        return None

    seq_ids: set[str] = set()
    n_seqs = 0
    n_lines = 0

    try:
        with open(path, errors="replace") as fh:
            for line in fh:
                n_lines += 1
                line = line.strip()
                if not line:
                    continue
                if line.startswith(">"):
                    n_seqs += 1
                    # Sequence ID = first word after >
                    sid = line[1:].split()[0].strip()
                    if sid:
                        seq_ids.add(sid)
    except Exception as exc:
        vr.error(f"Could not read {label} FASTA: {exc}")
        return None

    if n_seqs == 0:
        vr.error(
            f"{label}: No sequences found (0 '>' headers).",
            suggestion="Ensure the file is in FASTA format: >ID\\nSEQUENCE...",
        )
        return None

    # ID overlap
    check_id_overlap(gene_ids, seq_ids, f"{label} sequences", vr, id_column_name="sequence ID")

    vr.success(f"{label}: {n_seqs:,} sequences found.")
    return seq_ids
