"""Config – YAML configuration loader and schema validation.

Reads a user-provided ``config.yml``, validates its structure, resolves paths
relative to the config file location, and returns a typed dataclass tree.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from genxprep.reporter import Reporter, ValidationResult

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MatrixPaths:
    raw: Path | None = None
    tpm: Path | None = None
    tmm: Path | None = None
    getmm: Path | None = None
    vst: Path | None = None

    @property
    def available(self) -> dict[str, Path]:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @property
    def any_present(self) -> bool:
        return bool(self.available)

    @property
    def primary(self) -> tuple[str, Path]:
        """Return the first available matrix (prefer raw)."""
        for key in ("raw", "tpm", "tmm", "getmm", "vst"):
            p = getattr(self, key)
            if p is not None:
                return key, p
        raise ValueError("No matrix available")  # should not happen after validation


@dataclass
class SequencePaths:
    protein: Path | None = None
    rna: Path | None = None


@dataclass
class MetadataPaths:
    uniprot: Path | None = None
    interpro: Path | None = None
    pfam: Path | None = None
    tf: Path | None = None


@dataclass
class SpeciesConfig:
    code: str
    name: str
    matrix: MatrixPaths
    sample_mapping: Path | None = None
    metrics: Path | None = None
    metadata: MetadataPaths = field(default_factory=MetadataPaths)
    sequences: SequencePaths = field(default_factory=SequencePaths)


@dataclass
class GlobalMetadata:
    orthogroups: Path | None = None
    gene_trees: Path | None = None
    species_mapping: Path | None = None


@dataclass
class ProjectConfig:
    name: str
    output_dir: Path
    global_metadata: GlobalMetadata
    species: dict[str, SpeciesConfig]
    config_dir: Path  # directory containing the config file (for relative paths)


# ---------------------------------------------------------------------------
# Code pattern
# ---------------------------------------------------------------------------

SPECIES_CODE_RE = re.compile(r"^[A-Z]{2,10}$")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve(base: Path, raw: Any) -> Path | None:
    """Resolve a path string relative to *base*, or return None.

    Supports:
    - Absolute paths: ``/home/user/data/file.tsv``
    - Home-relative paths: ``~/data/file.tsv``
    - Relative paths: ``Matrices/file.tsv`` (resolved against *base*)
    """
    if raw is None or raw == "":
        return None
    s = str(raw).strip()
    # Expand ~ and ~user
    p = Path(os.path.expanduser(s))
    if not p.is_absolute():
        p = base / p
    return p.resolve()


def _check_file(path: Path | None, label: str, vr: ValidationResult, *, required: bool = False) -> bool:
    """Add error/warning if *path* does not exist.  Returns True if ok."""
    if path is None:
        if required:
            vr.error(f"Required path for '{label}' is not set in config.")
        return path is not None
    if not path.exists():
        if required:
            vr.error(
                f"File not found: {path}",
                suggestion=f"Check the path for '{label}' in your config.yml.",
            )
        else:
            vr.warn(
                f"Optional file not found: {path}",
                suggestion=f"Remove or correct the '{label}' entry if you don't have this file.",
            )
        return False
    return True


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(config_path: Path, reporter: Reporter) -> ProjectConfig | None:
    """Load and validate a config YAML.  Returns *None* on fatal errors."""

    vr = reporter.new("Configuration")
    config_path = config_path.resolve()
    config_dir = config_path.parent

    # --- read YAML --------------------------------------------------------
    if not config_path.exists():
        vr.error(
            f"Config file not found: {config_path}",
            suggestion="Run 'genxprep init' to generate a template config.yml.",
        )
        return None

    try:
        with open(config_path) as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        vr.error(
            f"Invalid YAML syntax: {exc}",
            suggestion="Check for indentation or quoting errors in your config.yml.",
        )
        return None

    if not isinstance(raw, dict):
        vr.error("Config file must be a YAML mapping (key: value pairs).")
        return None

    # --- project ----------------------------------------------------------
    project_raw = raw.get("project")
    if not isinstance(project_raw, dict):
        vr.error("Missing 'project' section in config.", suggestion="Add:\n  project:\n    name: \"My Project\"\n    output_dir: ./data")
        return None

    proj_name = project_raw.get("name")
    if not proj_name:
        vr.error("Missing 'project.name'.", suggestion="Add:  name: \"My Project\"")

    # --- root_dir (base for relative paths) --------------------------------
    root_dir_raw = project_raw.get("root_dir")
    if root_dir_raw:
        base = Path(os.path.expanduser(str(root_dir_raw).strip()))
        if not base.is_absolute():
            base = (config_dir / base).resolve()
        else:
            base = base.resolve()
        if not base.is_dir():
            vr.error(
                f"root_dir does not exist or is not a directory: {base}",
                suggestion="Set root_dir to the folder that contains your input data.",
            )
            return None
        vr.info(f"Using root_dir: {base}")
    else:
        base = config_dir  # default: config file's own directory

    output_dir_raw = project_raw.get("output_dir")
    if not output_dir_raw:
        vr.error("Missing 'project.output_dir'.", suggestion="Add:  output_dir: ./data")
        return None

    output_dir = _resolve(config_dir, output_dir_raw)
    assert output_dir is not None

    # --- global metadata --------------------------------------------------
    gm_raw = raw.get("global_metadata", {}) or {}
    global_meta = GlobalMetadata(
        orthogroups=_resolve(base, gm_raw.get("orthogroups")),
        gene_trees=_resolve(base, gm_raw.get("gene_trees")),
        species_mapping=_resolve(base, gm_raw.get("species_mapping")),
    )
    # check optional global files
    for attr in ("orthogroups", "gene_trees", "species_mapping"):
        p = getattr(global_meta, attr)
        if p is not None:
            _check_file(p, f"global_metadata.{attr}", vr)

    # --- species ----------------------------------------------------------
    species_raw = raw.get("species")
    if not isinstance(species_raw, dict) or len(species_raw) == 0:
        vr.error(
            "No species defined.",
            suggestion="Add at least one species under 'species:' in your config.",
        )
        return None

    species: dict[str, SpeciesConfig] = {}

    for code, sp_raw in species_raw.items():
        code = str(code).strip()
        sp_vr = reporter.new(f"Config → species '{code}'")

        # code pattern
        if not SPECIES_CODE_RE.match(code):
            sp_vr.error(
                f"Species code '{code}' is invalid.",
                suggestion="Use 2-10 uppercase letters, e.g. 'AC', 'PS', 'TT'.",
            )

        if not isinstance(sp_raw, dict):
            sp_vr.error(f"Species '{code}' must be a mapping with 'name' and 'matrix'.")
            continue

        sp_name = sp_raw.get("name")
        if not sp_name:
            sp_vr.error("Missing 'name' (full species name).", suggestion=f"Add:  name: \"Genus species\"")

        # matrices
        mat_raw = sp_raw.get("matrix", {}) or {}
        if not isinstance(mat_raw, dict):
            sp_vr.error("'matrix' must be a mapping with keys like 'raw', 'tpm', 'tmm', 'getmm', 'vst'.")
            continue

        mat = MatrixPaths(
            raw=_resolve(base, mat_raw.get("raw")),
            tpm=_resolve(base, mat_raw.get("tpm")),
            tmm=_resolve(base, mat_raw.get("tmm")),
            getmm=_resolve(base, mat_raw.get("getmm")),
            vst=_resolve(base, mat_raw.get("vst")),
        )
        if not mat.any_present:
            sp_vr.error(
                "No expression matrix specified.",
                suggestion="Provide at least one matrix path, e.g.:\n  matrix:\n    raw: path/to/counts.tsv",
            )
            continue

        # check matrix files exist
        for mkey, mpath in mat.available.items():
            _check_file(mpath, f"matrix.{mkey}", sp_vr, required=True)

        # sample mapping & metrics
        sample_mapping = _resolve(base, sp_raw.get("sample_mapping"))
        if sample_mapping:
            _check_file(sample_mapping, "sample_mapping", sp_vr)

        metrics = _resolve(base, sp_raw.get("metrics"))
        if metrics:
            _check_file(metrics, "metrics", sp_vr)

        # per-species metadata
        md_raw = sp_raw.get("metadata", {}) or {}
        md = MetadataPaths(
            uniprot=_resolve(base, md_raw.get("uniprot")),
            interpro=_resolve(base, md_raw.get("interpro")),
            pfam=_resolve(base, md_raw.get("pfam")),
            tf=_resolve(base, md_raw.get("tf")),
        )
        for attr in ("uniprot", "interpro", "pfam", "tf"):
            p = getattr(md, attr)
            if p is not None:
                _check_file(p, f"metadata.{attr}", sp_vr)

        # sequences
        seq_raw = sp_raw.get("sequences", {}) or {}
        seq = SequencePaths(
            protein=_resolve(base, seq_raw.get("protein")),
            rna=_resolve(base, seq_raw.get("rna")),
        )
        for attr in ("protein", "rna"):
            p = getattr(seq, attr)
            if p is not None:
                _check_file(p, f"sequences.{attr}", sp_vr)

        species[code] = SpeciesConfig(
            code=code,
            name=sp_name or code,
            matrix=mat,
            sample_mapping=sample_mapping,
            metrics=metrics,
            metadata=md,
            sequences=seq,
        )

    if not species:
        vr.error("No valid species definitions found.")
        return None

    vr.success(f"Config loaded: project '{proj_name}' with {len(species)} species.")

    return ProjectConfig(
        name=proj_name or "Unnamed",
        output_dir=output_dir,
        global_metadata=global_meta,
        species=species,
        config_dir=base,
    )
