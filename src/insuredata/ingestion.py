"""Stage 1 - Ingestion: read raw files (CSV/JSON/Excel/Parquet) as text; optional concurrent reads."""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)


class IngestionError(Exception):
    pass


def read_any(path: Path, max_mb: float = 100) -> pd.DataFrame:
    """Read one file into an all-text DataFrame with a `source_file` lineage column."""
    path = Path(path)
    if not path.is_file():
        raise IngestionError(f"Input file not found: {path}")
    if path.stat().st_size / 1_048_576 > max_mb:
        raise IngestionError(f"{path.name} exceeds {max_mb} MB limit (loaded fully in memory)")
    ext = path.suffix.lower()
    try:
        if ext == ".csv":
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        elif ext == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            recs = payload.get("records", payload) if isinstance(payload, dict) else payload
            if not isinstance(recs, list):
                raise IngestionError(f"{path.name}: expected a list of records")
            df = pd.DataFrame(recs).astype(object)
            df = df.where(df.notna(), "").astype(str)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(path, dtype=str, keep_default_na=False)       # needs openpyxl
        elif ext == ".parquet":
            df = pd.read_parquet(path).astype(str)                           # needs pyarrow
        else:
            raise IngestionError(f"Unsupported file type: {ext}")
    except (json.JSONDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError, ImportError) as exc:
        raise IngestionError(f"{path.name}: cannot read ({type(exc).__name__}: {exc})") from exc
    df = df.replace(r"^\s*$", pd.NA, regex=True)
    df.columns = [str(c).strip().lower() for c in df.columns]
    df["source_file"] = path.name
    return df


def read_many(paths: list[Path], parallel: bool = False, max_workers: int = 4, max_mb: float = 100,
              required: list[str] | None = None) -> pd.DataFrame:
    """Read several files with the same layout and concatenate in sorted-name order (deterministic).

    parallel=True uses a bounded thread pool; reading is I/O-bound so threads help for many/large files.
    """
    paths = sorted(Path(p) for p in paths)
    if not paths:
        raise IngestionError("No input files given")
    if parallel and len(paths) > 1:
        with ThreadPoolExecutor(max_workers=min(max_workers, 8, len(paths))) as pool:
            frames = list(pool.map(lambda p: read_any(p, max_mb), paths))   # map preserves input order
    else:
        frames = [read_any(p, max_mb) for p in paths]
    if required:                      # check EACH file: a column missing from one file must not silently become nulls
        for p, f in zip(paths, frames):
            check_columns(f, required, p.name)
    return pd.concat(frames, ignore_index=True)


def check_columns(df: pd.DataFrame, required: list[str], label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise IngestionError(f"{label}: missing required columns {missing}")
