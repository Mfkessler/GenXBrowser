"""Gene trees validator – validates Newick tree files.

Expected format: one line per tree ``OG_ID:newick_string``.
"""

from __future__ import annotations

from pathlib import Path

from genxprep.reporter import ValidationResult


def validate_gene_trees(
    path: Path,
    orthogroup_ids: set[str] | None,
    vr: ValidationResult,
) -> dict[str, str] | None:
    """Validate a gene trees file.

    Returns a mapping of ``orthogroup_id → newick_string``, or *None* on error.
    """
    if not path.exists():
        vr.error(f"Gene trees file not found: {path}")
        return None

    trees: dict[str, str] = {}
    n_bad = 0

    try:
        with open(path, errors="replace") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                if ":" not in line:
                    # First colon separates OG_ID from newick
                    n_bad += 1
                    continue
                og_id, newick = line.split(":", 1)
                og_id = og_id.strip()
                newick = newick.strip()
                if not og_id or not newick:
                    n_bad += 1
                    continue
                # Basic bracket balance check
                if newick.count("(") != newick.count(")"):
                    vr.warn(
                        f"Line {lineno}: Unbalanced parentheses in tree for '{og_id}'.",
                    )
                trees[og_id] = newick
    except Exception as exc:
        vr.error(f"Could not read gene trees file: {exc}")
        return None

    if not trees and n_bad == 0:
        vr.warn("Gene trees file is empty. Phylogenetic trees will not be available.")
        return {}

    if n_bad > 0:
        vr.warn(f"{n_bad} line(s) in gene trees file could not be parsed (expected OG_ID:newick).")

    # Cross-check with orthogroups
    if orthogroup_ids is not None and trees:
        matched = set(trees.keys()) & orthogroup_ids
        orphaned = set(trees.keys()) - orthogroup_ids
        pct = len(matched) / len(trees) * 100 if trees else 0
        vr.info(f"Gene trees: {len(matched)}/{len(trees)} trees match known orthogroups ({pct:.0f}%).")
        if orphaned and len(orphaned) <= 5:
            vr.info(f"Orphan tree OGs: {', '.join(sorted(orphaned))}")

    vr.success(f"Gene trees: {len(trees):,} trees loaded.")
    return trees
