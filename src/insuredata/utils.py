"""Configuration, logging, hashing and small parsing helpers."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else PROJECT_ROOT / "config" / "pipeline.json"
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def setup_logging(level: int = logging.INFO, log_file: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=level, handlers=handlers, force=True,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def input_fingerprint(files: list[Path], cfg: dict[str, Any]) -> str:
    h = hashlib.sha256()
    for f in sorted(files):
        h.update(f.name.encode()); h.update(f.read_bytes())
    h.update(json.dumps(cfg, sort_keys=True).encode())
    return h.hexdigest()[:12]


def parse_dates(series: pd.Series, formats: list[str]) -> pd.Series:
    s = series.astype("object").where(series.notna(), None)
    out = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    for fmt in formats:
        todo = out.isna() & s.notna()
        if not todo.any():
            break
        out.loc[todo] = pd.to_datetime(s[todo].astype(str).str.strip(), format=fmt, errors="coerce")
    return out


def parse_money(series: pd.Series) -> pd.Series:
    txt = series.astype("string").str.replace(r"[$,\s]", "", regex=True)
    return pd.to_numeric(txt, errors="coerce")


def norm_id(series: pd.Series) -> pd.Series:
    s = series.astype("string").str.strip().str.upper()
    return s.where(s != "")
