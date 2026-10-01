"""I/O abstraction for tables and matrices.

Falls back to CSV and HDF5 if parquet is not available in the environment.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pandas as pd

# Check if parquet is available
_HAS_PARQUET = True
try:
    import pyarrow.parquet  # noqa: F401
except ImportError:
    try:
        import fastparquet  # noqa: F401
    except ImportError:
        _HAS_PARQUET = False


def _is_numeric(df: pd.DataFrame) -> bool:
    """True if all columns are numeric (float/int), used to choose HDF5 vs CSV."""
    from pandas.api.types import is_numeric_dtype
    for col in df.columns:
        if col == "_row" or col == "transaction_id":
            continue
        if not is_numeric_dtype(df[col]):
            return False
    return True


def write_table(df: pd.DataFrame, path: Path | str, index: bool = False) -> None:
    """Write DataFrame to disk, using parquet if possible, falling back to CSV/HDF5."""
    path = Path(path)
    if _HAS_PARQUET:
        if path.suffix != ".parquet":
            path = path.with_suffix(".parquet")
        df.to_parquet(path, index=index)
        return

    # Fallback mode
    if _is_numeric(df):
        # Float blocks (e.g. GFP features) go to HDF5
        path = path.with_suffix(".h5")
        import h5py
        with h5py.File(path, "w") as f:
            if index:
                f.create_dataset("_index", data=df.index.to_numpy())
            for col in df.columns:
                f.create_dataset(str(col), data=df[col].to_numpy())
    else:
        # Row data (e.g. transactions) goes to CSV
        path = path.with_suffix(".csv")
        df.to_csv(path, index=index)


def read_table(path: Path | str, columns: list[str] | None = None) -> pd.DataFrame:
    """Read DataFrame from disk, automatically resolving the fallback extension."""
    path = Path(path)
    
    # Resolve actual extension
    if not path.exists():
        if path.with_suffix(".parquet").exists():
            path = path.with_suffix(".parquet")
        elif path.with_suffix(".h5").exists():
            path = path.with_suffix(".h5")
        elif path.with_suffix(".csv").exists():
            path = path.with_suffix(".csv")
            
    if path.suffix == ".parquet":
        return pd.read_parquet(path, columns=columns)
        
    if path.suffix == ".h5":
        import h5py
        import numpy as np
        data = {}
        with h5py.File(path, "r") as f:
            read_cols = columns if columns is not None else [k for k in f.keys() if k != "_index"]
            for col in read_cols:
                data[col] = f[col][:]
            
            df = pd.DataFrame(data)
            if "_index" in f:
                df.index = f["_index"][:]
        return df
        
    if path.suffix == ".csv":
        return pd.read_csv(path, usecols=columns)
        
    raise FileNotFoundError(f"Could not find table {path} (checked .parquet, .h5, .csv)")
