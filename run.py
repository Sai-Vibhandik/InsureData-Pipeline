"""CLI:  python run.py [--input data/raw] [--output outputs] [--parallel] [--no-parquet]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from insuredata.ingestion import IngestionError  # noqa: E402
from insuredata.pipeline import run_pipeline  # noqa: E402
from insuredata.utils import load_config, setup_logging  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the InsureData ETL pipeline")
    ap.add_argument("--input", type=Path, default=ROOT / "data" / "raw")
    ap.add_argument("--output", type=Path, default=ROOT / "outputs")
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--parallel", action="store_true", help="read claim files with a bounded thread pool")
    ap.add_argument("--no-parquet", action="store_true")
    a = ap.parse_args()
    setup_logging(log_file=ROOT / "logs" / "pipeline.log")
    try:
        res = run_pipeline(a.input, a.output, load_config(a.config), a.parallel, not a.no_parquet)
    except IngestionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"\nRun {res.run_id} OK in {res.elapsed_seconds}s (rerun of identical input: {res.repeat_of_same_input})")
    for ent, e in res.quality["entities"].items():
        print(f"  {ent:<10} in={e['input']:>5} curated={e['curated']:>5} rejected={e['rejected']:>4} ({e['rejected_pct']}%)")
    print(json.dumps(res.kpis, indent=2))
    print(f"Outputs: {a.output}/ (staging, curated, rejected, reporting)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
