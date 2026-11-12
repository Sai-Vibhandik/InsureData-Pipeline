"""Stage 4 - Loading: atomic, idempotent writes into staging/curated/rejected/reporting zones."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)
ZONES = ("staging", "curated", "rejected", "reporting")


def _printable(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
    return out


def _atomic(path: Path, writer) -> None:
    tmp = path.with_name(path.name + ".tmp")
    writer(tmp)
    os.replace(tmp, path)


def write_frame(df: pd.DataFrame, out_dir: Path, zone: str, name: str, parquet: bool = True) -> list[Path]:
    if zone not in ZONES:
        raise ValueError(f"unknown zone {zone}")
    target = Path(out_dir) / zone
    target.mkdir(parents=True, exist_ok=True)
    flat, paths = _printable(df), []
    csv = target / f"{name}.csv"
    _atomic(csv, lambda p: flat.to_csv(p, index=False)); paths.append(csv)
    if parquet:
        try:
            import pyarrow  # noqa: F401
            pq = target / f"{name}.parquet"
            _atomic(pq, lambda p: flat.to_parquet(p, index=False)); paths.append(pq)
        except ImportError:
            log.warning("pyarrow missing: skipped parquet for %s/%s", zone, name)
    return paths


def write_json(obj, out_dir: Path, zone: str, name: str) -> Path:
    target = Path(out_dir) / zone
    target.mkdir(parents=True, exist_ok=True)
    path = target / name
    _atomic(path, lambda p: p.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str), encoding="utf-8"))
    return path


def append_run_log(entry: dict, out_dir: Path) -> None:
    path = Path(out_dir) / "reporting" / "pipeline_runs.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True, default=str) + "\n")


def read_run_log(out_dir: Path) -> list[dict]:
    path = Path(out_dir) / "reporting" / "pipeline_runs.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
