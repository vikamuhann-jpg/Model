"""Where the measurement scripts find their inputs.

DATA is the external data folder (processed parquet, graph-feature parts, logs).
It defaults to the build machine's location; set FLOWGUARD_DATA to point elsewhere.
REPO is this repository's root, found from this file's own location.
"""
import os
from pathlib import Path

DATA = Path(os.environ.get("FLOWGUARD_DATA", "/mnt/c/Users/vikam/flowguard_data"))
# _paths.py -> measure -> scripts -> flowguard -> Project -> repository root
REPO = Path(__file__).resolve().parents[4]
