"""Ingestion and the immutable raw layer (plan v3 Phase 1).

Reads a raw IBM AML variant, attaches pattern annotations, validates it, and
writes a canonical Parquet plus a ``dataset_summary.json`` whose counts are
**derived here**, not copied from the planning documents -- those figures are
flagged unverified in the plans themselves.

Usage::

    python -m flowguard.pipeline.ingest --variant HI-Small
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from flowguard.data import schema as S
from flowguard.data.loader import (
    DEFAULT_AMOUNT_SIDE,
    AmountSide,
    load_accounts,
    load_transactions,
)
from flowguard.data.patterns import attach_patterns, parse_patterns
from flowguard.data.windowing import daily_profile, trim_sparse_tail
from flowguard.data.validator import validate_transactions

CHUNK = 1 << 22  # 4 MiB


def sha256(path: Path) -> str:
    """Checksum a file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
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

    names = ["snapml", "xgboost", "scikit-learn", "pandas", "numpy", "pyarrow"]
    out = {}
    for name in names:
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            continue
    return out


@dataclass(frozen=True)
class IngestPaths:
    transactions: Path
    patterns: Path
    accounts: Path

    @classmethod
    def for_variant(cls, raw_dir: Path, variant: str) -> IngestPaths:
        return cls(
            transactions=raw_dir / f"{variant}_Trans.csv",
            patterns=raw_dir / f"{variant}_Patterns.txt",
            accounts=raw_dir / f"{variant}_accounts.csv",
        )

    def missing(self) -> list[Path]:
        return [p for p in (self.transactions, self.patterns, self.accounts) if not p.exists()]


def ingest(
    variant: str,
    raw_dir: Path,
    out_dir: Path,
    *,
    amount_side: AmountSide = DEFAULT_AMOUNT_SIDE,
    nrows: int | None = None,
    checksum: bool = True,
    min_density: float = 0.05,
) -> dict:
    """Ingest one variant end to end. Returns the summary metadata."""
    paths = IngestPaths.for_variant(raw_dir, variant)
    if missing := paths.missing():
        raise FileNotFoundError(f"missing raw file(s): {[str(p) for p in missing]}")

    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    print(f"[1/5] loading {paths.transactions.name}")
    tx, load_report = load_transactions(
        paths.transactions, amount_side=amount_side, nrows=nrows
    )
    print(f"      {len(tx):,} transactions")

    print(f"[2/5] parsing {paths.patterns.name}")
    patterns = parse_patterns(paths.patterns)
    tx, attach_report = attach_patterns(tx, patterns)
    print(
        f"      {attach_report.patterns} patterns, "
        f"{attach_report.matched_transactions:,} transactions labelled"
    )

    print(f"[3/5] loading {paths.accounts.name}")
    accounts = load_accounts(paths.accounts)
    print(f"      {len(accounts):,} accounts")

    print("[4/5] trimming the generator's sparse tail")
    tx, window_report = trim_sparse_tail(tx, min_density=min_density)
    if window_report.applied:
        print(
            f"      dropped {window_report.rows_dropped:,} rows "
            f"({window_report.positives_dropped:,} positives) across "
            f"{len(window_report.days_dropped)} trailing days"
        )
    else:
        print("      no sparse tail detected")

    print("[5/6] validating")
    validation = validate_transactions(tx)
    print(validation.summary())

    print("[6/6] writing canonical parquet")
    tx_path = out_dir / f"{variant}_transactions.parquet"
    acct_path = out_dir / f"{variant}_accounts.parquet"
    tx.to_parquet(tx_path, index=False)
    accounts.to_parquet(acct_path, index=False)

    summary = S.summarise(tx)
    # Orphan check: every transaction endpoint should resolve in the accounts
    # reference table. A non-zero count means the composite key is wrong.
    known = set(accounts["account_id"])
    endpoints = set(tx[S.SOURCE_ACCOUNT]) | set(tx[S.DESTINATION_ACCOUNT])
    orphans = len(endpoints - known)

    metadata = {
        "variant": variant,
        "ingested_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "raw_files": {
            p.name: {
                "bytes": p.stat().st_size,
                "sha256": sha256(p) if checksum else None,
            }
            for p in (paths.transactions, paths.patterns, paths.accounts)
        },
        "derived_counts": summary.to_metadata(),
        "load": load_report.to_metadata(),
        "patterns": attach_report.to_metadata(),
        "accounts": {
            "rows": len(accounts),
            "entities": int(accounts["entity_id"].nunique()),
            "banks": int(accounts["bank_id"].nunique()),
            "transaction_endpoints": len(endpoints),
            "orphan_endpoints": orphans,
        },
        "window_trim": window_report.to_metadata(),
        "daily_profile": {
            str(day): {"rows": int(r["rows"]), "positives": int(r["positives"]),
                       "rate": float(r["rate"])}
            for day, r in daily_profile(tx).iterrows()
        },
        "validation": validation.to_metadata(),
        "outputs": {
            "transactions": str(tx_path),
            "accounts": str(acct_path),
        },
        "provenance": {
            "git_commit": _git_commit(),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "libraries": _library_versions(),
            "nrows_limit": nrows,
        },
        "elapsed_seconds": round(time.perf_counter() - started, 1),
    }

    summary_path = out_dir / f"{variant}_dataset_summary.json"
    summary_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"\nwrote {summary_path}")
    return metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="HI-Small")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("/mnt/c/Users/vikam/OneDrive/Desktop/Hackathon_project/"
                     "datathon_research/Dataset_/IBM_Dataset"),
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("/mnt/c/Users/vikam/flowguard_data/processed")
    )
    parser.add_argument("--amount-side", choices=["paid", "received"], default="paid")
    parser.add_argument("--nrows", type=int, default=None)
    parser.add_argument("--min-density", type=float, default=0.05)
    parser.add_argument(
        "--no-checksum", action="store_true", help="skip SHA-256 (faster for smoke runs)"
    )
    args = parser.parse_args(argv)

    ingest(
        args.variant,
        args.raw_dir,
        args.out_dir,
        amount_side=args.amount_side,  # type: ignore[arg-type]
        nrows=args.nrows,
        checksum=not args.no_checksum,
        min_density=args.min_density,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
