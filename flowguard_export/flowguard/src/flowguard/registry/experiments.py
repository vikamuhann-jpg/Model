"""Experiment registry (plan v3 Phase 17).

Every run writes a self-contained JSON record plus a row in a flat CSV index.
The record must carry enough provenance to answer "what produced this number?"
without reference to anyone's memory.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "experiments"


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parent,
        )
        return out.stdout.strip()
    except Exception:
        return None


def _library_versions() -> dict[str, str]:
    from importlib.metadata import PackageNotFoundError, version

    out = {}
    for name in ("snapml", "xgboost", "scikit-learn", "pandas", "numpy"):
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            continue
    return out


@dataclass
class ExperimentRecord:
    """One experiment. ``experiment_id`` follows the E0…E7 scheme only."""

    experiment_id: str
    description: str
    dataset: dict[str, Any] = field(default_factory=dict)
    split: dict[str, Any] = field(default_factory=dict)
    features: dict[str, Any] = field(default_factory=dict)
    model: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    cost: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    #: Set when extraction and training ran on different platforms (e.g.
    #: GFP extracted in WSL, trained on Windows). ``None`` for tabular-only
    #: experiments where a single machine did everything.
    extraction_platform: str | None = None

    def to_metadata(self) -> dict:
        provenance: dict[str, Any] = {
            "git_commit": _git_commit(),
            "python": sys.version.split()[0],
            "training_platform": platform.platform(),
            "libraries": _library_versions(),
        }
        if self.extraction_platform is not None:
            provenance["extraction_platform"] = self.extraction_platform
        return {
            "experiment_id": self.experiment_id,
            "description": self.description,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "dataset": self.dataset,
            "split": self.split,
            "features": self.features,
            "model": self.model,
            "metrics": self.metrics,
            "cost": self.cost,
            "notes": self.notes,
            "provenance": provenance,
        }


class Registry:
    """Filesystem-backed experiment log."""

    def __init__(self, root: Path | str = DEFAULT_ROOT) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "results.csv"

    def log(self, record: ExperimentRecord) -> Path:
        """Write the full record and append a summary row to the index."""
        target = self.root / record.experiment_id
        target.mkdir(parents=True, exist_ok=True)
        path = target / "record.json"
        path.write_text(json.dumps(record.to_metadata(), indent=2), encoding="utf-8")
        self._append_index(record)
        return path

    def _append_index(self, record: ExperimentRecord) -> None:
        import csv

        test = record.metrics.get("test", {})
        budget_1pct = next(
            (b for b in test.get("budgets", []) if b.get("budget") == 0.01), {}
        )
        row = {
            "experiment_id": record.experiment_id,
            "description": record.description,
            "features": record.features.get("family", ""),
            "n_features": record.features.get("count", ""),
            "test_pr_auc": test.get("pr_auc", ""),
            "test_roc_auc": test.get("roc_auc", ""),
            "lift": test.get("lift_over_base_rate", ""),
            "recall_at_1pct": budget_1pct.get("recall", ""),
            "precision_at_1pct": budget_1pct.get("precision", ""),
            "train_seconds": record.cost.get("train_seconds", ""),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        write_header = not self.index_path.exists()
        with self.index_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    def load(self, experiment_id: str) -> dict:
        path = self.root / experiment_id / "record.json"
        if not path.exists():
            raise FileNotFoundError(f"no record for {experiment_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def experiment_ids(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if (p / "record.json").exists())
