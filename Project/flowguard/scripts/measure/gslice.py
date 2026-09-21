"""Read only the graph-feature rows one split needs, one part file at a time.

read_varying_chunks materialises the whole block before any slice is taken, so
peak memory is the full corpus block plus the slice -- which is what OOM-killed
the first P3 attempt at 5.6 GB. Filtering during the read keeps peak at one part
file plus the accumulating slice.
"""
from pathlib import Path

import pandas as pd

from flowguard.features.gfp import varying_columns
from _paths import DATA, REPO  # noqa: E402  (FLOWGUARD_DATA overrides)


def _parts(parts_dir):
    found = sorted(Path(parts_dir).glob("part_*.parquet"))
    if not found:
        raise FileNotFoundError(f"no part files under {parts_dir}")
    return found


def keep_columns(parts_dir):
    parts = _parts(parts_dir)
    keep, total = varying_columns(parts)
    return keep, total


def covered_index(parts_dir):
    rows = []
    for path in _parts(parts_dir):
        rows.append(pd.read_parquet(path, columns=["_row"])["_row"])
    return pd.Index(pd.concat(rows, ignore_index=True))


def graph_slice(parts_dir, index, keep):
    want = pd.Index(index)
    frames = []
    for path in _parts(parts_dir):
        frame = pd.read_parquet(path, columns=["_row"] + keep).set_index("_row")
        hit = frame.index.intersection(want)
        if len(hit):
            frames.append(frame.loc[hit].astype("float32"))
        del frame
    out = pd.concat(frames).sort_index().reset_index(drop=True)
    del frames
    return out
