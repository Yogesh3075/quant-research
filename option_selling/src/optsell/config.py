"""Project paths and the config loader.

Paths inside configs/config.yaml (data/, results/) are relative to the project root, so
`load_config` works from there. The file is kept byte-identical: its SHA-256 is recorded when a
rule is frozen (Phases 3 and 4).
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "config.yaml"
# NIFTY 50 TRI, downloaded by the factor_regime_rotation project
DEFAULT_TRI_PATH = (
    PROJECT_ROOT.parent / "factor_regime_rotation" / "data" / "processed" / "tri_daily.csv"
)


def load_config() -> dict:
    """Read configs/config.yaml and work from the project root."""
    os.chdir(PROJECT_ROOT)
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def tri_path(cfg: dict) -> Path:
    """NIFTY 50 TRI file: $OPTSELL_TRI_PATH, else the config's path, else the sibling project."""
    for candidate in (os.environ.get("OPTSELL_TRI_PATH"), cfg.get("tri_path")):
        if candidate and Path(candidate).exists():
            return Path(candidate)
    if DEFAULT_TRI_PATH.exists():
        return DEFAULT_TRI_PATH
    raise FileNotFoundError(
        "NIFTY 50 TRI not found: run factor_regime_rotation's download or set OPTSELL_TRI_PATH"
    )
