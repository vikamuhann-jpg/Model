"""Platform-aware path resolver for FlowGuard (plan v3 split-platform arch).

Resolution order for every path, highest priority first:

1. Environment variable (FLOWGUARD_PROCESSED_DIR, FLOWGUARD_RAW_DIR,
   FLOWGUARD_GFP_CACHE)
2. Platform-specific entry in configs/paths.yaml  (linux / win32 key)
3. A "default" key in paths.yaml if no platform-specific entry exists
4. Hard-coded fallback (identical to the old /mnt/... defaults — safe on WSL)

Import::

    from flowguard.config import PROCESSED_DIR, RAW_DIR, GFP_CACHE

or, for dynamic resolution after env vars are changed in-process::

    from flowguard.config import resolve
    p = resolve("processed_dir")
"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

# configs/paths.yaml sits at the project root:
#   .../flowguard/src/flowguard/config.py  ->  .../flowguard/configs/paths.yaml
# parents[0]=src/flowguard, [1]=src, [2]=project root. Using [3] climbs one
# level too far, and because _load_yaml() swallows every exception the file
# would simply never load while the fallbacks silently took over.
_YAML_PATH = Path(__file__).resolve().parents[2] / "configs" / "paths.yaml"

_PLATFORM = "win32" if sys.platform == "win32" else "linux"

# Hard-coded last-resort defaults, resolved per platform.
# These mirror paths.yaml but require no file I/O, so the module always loads.
_WIN = sys.platform == "win32"
_FALLBACKS: dict[str, str] = {
    "processed_dir": (
        r"C:/Users/vikam/flowguard_data/processed" if _WIN
        else "/mnt/c/Users/vikam/flowguard_data/processed"
    ),
    "raw_dir": (
        r"C:/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/Dataset_/IBM_Dataset" if _WIN
        else "/mnt/c/Users/vikam/OneDrive/Desktop/Hackathon_project/datathon_research/Dataset_/IBM_Dataset"
    ),
    "gfp_cache": (
        r"C:/Users/vikam/flowguard_data/gfp_cache/HI-Small_2d.parquet" if _WIN
        else "/mnt/c/Users/vikam/flowguard_data/gfp_cache/HI-Small_2d.parquet"
    ),
}

_ENV_VARS: dict[str, str] = {
    "processed_dir": "FLOWGUARD_PROCESSED_DIR",
    "raw_dir":       "FLOWGUARD_RAW_DIR",
    "gfp_cache":     "FLOWGUARD_GFP_CACHE",
}


def _load_yaml() -> dict:
    """Parse paths.yaml without introducing a hard yaml dependency.

    A missing file is fine -- the fallbacks cover it. A file that exists but
    cannot be parsed is not: it means the operator edited the single source of
    truth and it is being ignored, which is exactly the failure this function
    used to hide behind a blanket except.
    """
    if not _YAML_PATH.exists():
        return {}
    try:
        import yaml  # PyYAML
    except ImportError:
        warnings.warn(
            f"{_YAML_PATH} exists but PyYAML is not installed; falling back to "
            "built-in defaults. Paths in that file are being ignored.",
            stacklevel=2,
        )
        return {}
    try:
        with _YAML_PATH.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception as exc:
        warnings.warn(
            f"could not parse {_YAML_PATH} ({exc}); falling back to built-in "
            "defaults. Paths in that file are being ignored.",
            stacklevel=2,
        )
        return {}


_yaml_cache: dict | None = None


def resolve(key: str) -> Path:
    """Return the resolved Path for *key* (e.g. ``"processed_dir"``).

    Follows the priority order documented at the module level.
    """
    global _yaml_cache

    # 1. Environment variable
    env_key = _ENV_VARS.get(key)
    if env_key and os.environ.get(env_key):
        return Path(os.environ[env_key])

    # 2 + 3. paths.yaml
    if _yaml_cache is None:
        _yaml_cache = _load_yaml()
    entry = _yaml_cache.get(key, {})
    if isinstance(entry, dict):
        raw = entry.get(_PLATFORM) or entry.get("default")
    else:
        raw = entry  # scalar — used on both platforms
    if raw:
        return Path(raw)

    # 4. Hard-coded fallback
    return Path(_FALLBACKS.get(key, "."))


# Module-level constants — the usual import target.
PROCESSED_DIR: Path = resolve("processed_dir")
RAW_DIR:       Path = resolve("raw_dir")
GFP_CACHE:     Path = resolve("gfp_cache")
