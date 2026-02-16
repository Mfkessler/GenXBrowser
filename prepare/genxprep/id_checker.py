"""ID Checker – Cross-file gene ID consistency validation.

Collects canonical gene IDs from the primary expression matrix and checks
every other input file for matching IDs.
"""

from __future__ import annotations

from pathlib import Path

from genxprep.reporter import ValidationResult


def check_id_overlap(
    canonical_ids: set[str],
    other_ids: set[str],
    file_label: str,
    vr: ValidationResult,
    *,
    id_column_name: str = "ID",
) -> float:
    """Compare *other_ids* against *canonical_ids*.

    Adds errors/warnings/success to *vr*.  Returns overlap fraction (0.0–1.0).
    """
    if not other_ids:
        vr.warn(f"No IDs found in {file_label}.")
        return 0.0

    overlap = canonical_ids & other_ids
    frac = len(overlap) / len(other_ids) if other_ids else 0.0

    # Grab example IDs for diagnostic messages
    canon_examples = sorted(list(canonical_ids))[:3]
    other_examples = sorted(list(other_ids - canonical_ids))[:3]

    if len(overlap) == 0:
        vr.error(
            f"No IDs from '{file_label}' match your expression matrix (0% overlap).",
            suggestion=(
                f"Your matrix uses IDs like: {', '.join(canon_examples)}\n"
                f"      But '{file_label}' uses IDs like: {', '.join(other_examples)}\n"
                f"      All input files must use the same gene/transcript ID system.\n"
                f"      Make sure '{id_column_name}' in '{file_label}' matches the row IDs of your count matrix."
            ),
        )
    elif frac < 0.5:
        n_miss = len(other_ids) - len(overlap)
        vr.warn(
            f"Only {frac:.0%} of IDs in '{file_label}' match your matrix "
            f"({len(overlap)} matched, {n_miss} unmatched).",
            suggestion=(
                f"Unmatched IDs look like: {', '.join(other_examples)}\n"
                f"      Matrix IDs look like: {', '.join(canon_examples)}\n"
                f"      Unmatched entries will be ignored."
            ),
        )
    else:
        n_miss = len(other_ids) - len(overlap)
        if n_miss > 0:
            vr.info(
                f"{file_label}: {len(overlap)}/{len(other_ids)} IDs match "
                f"({frac:.0%}). {n_miss} entries have no match in the matrix and will be skipped."
            )
        else:
            vr.success(f"{file_label}: all {len(overlap)} IDs match the expression matrix.")

    return frac
