"""Pipeline orchestrator: ingestion -> validation -> transformation -> loading (+ reporting)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from . import analytics, ingestion, storage, transformations, validation
from .utils import PROJECT_ROOT, input_fingerprint, load_config

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    run_id: str
    stages: list[dict] = field(default_factory=list)
    customers: pd.DataFrame | None = None
    dim_policy: pd.DataFrame | None = None
    fact_claims: pd.DataFrame | None = None
    rejected: dict[str, pd.DataFrame] = field(default_factory=dict)
    kpis: dict = field(default_factory=dict)
    quality: dict = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    repeat_of_same_input: bool = False


def _stage(result: PipelineResult, name: str, fn):
    t0 = time.perf_counter()
    out = fn()
    result.stages.append({"stage": name, "status": "ok", "seconds": round(time.perf_counter() - t0, 3)})
    log.info("stage %-14s ok (%.2fs)", name, time.perf_counter() - t0)
    return out


def run_pipeline(input_dir: Path | None = None, output_dir: Path | None = None, cfg: dict[str, Any] | None = None,
                 parallel: bool = False, write_parquet: bool = True) -> PipelineResult:
    """Run the whole ETL. Re-running on identical input rewrites identical curated/rejected/reporting files."""
    t_start = time.perf_counter()
    cfg = cfg or load_config()
    input_dir = Path(input_dir or PROJECT_ROOT / "data" / "raw")
    output_dir = Path(output_dir or PROJECT_ROOT / "outputs")
    max_mb = cfg["max_input_mb"]

    claim_paths = [input_dir / f for f in cfg["claims_files"]]
    paths = [input_dir / "customers.csv", input_dir / "policies.json", *claim_paths]
    for p in paths:
        if not p.is_file():
            raise ingestion.IngestionError(f"Required input file missing: {p}")
    run_id = input_fingerprint(paths, cfg)
    prior = storage.read_run_log(output_dir)
    res = PipelineResult(run_id=run_id, repeat_of_same_input=any(r.get("run_id") == run_id for r in prior))

    # 1) INGESTION ---------------------------------------------------------------
    def ingest():
        cust = ingestion.read_any(paths[0], max_mb)
        pol = ingestion.read_any(paths[1], max_mb)
        clm = ingestion.read_many(claim_paths, parallel=parallel, max_mb=max_mb, required=validation.CLAIM_COLS)
        ingestion.check_columns(cust, validation.CUSTOMER_COLS, "customers")
        ingestion.check_columns(pol, validation.POLICY_COLS, "policies")
        ingestion.check_columns(clm, validation.CLAIM_COLS, "claims")
        return cust, pol, clm
    raw_c, raw_p, raw_k = _stage(res, "ingestion", ingest)
    counts = {"customers": {"input": len(raw_c)}, "policies": {"input": len(raw_p)}, "claims": {"input": len(raw_k)}}

    # 2) VALIDATION (order enforces referential integrity) --------------------------
    def validate():
        c, cr, cw = validation.validate_customers(raw_c, cfg)
        p, pr, pw = validation.validate_policies(raw_p, c, cfg)
        k, kr, kw = validation.validate_claims(raw_k, p, cfg)
        return (c, p, k), {"customers": cr, "policies": pr, "claims": kr}, cw + pw + kw
    (cust, pol, clm), res.rejected, warnings = _stage(res, "validation", validate)
    for ent, df in (("customers", cust), ("policies", pol), ("claims", clm)):
        counts[ent].update(curated=len(df), rejected=len(res.rejected[ent]))
        assert counts[ent]["input"] == counts[ent]["curated"] + counts[ent]["rejected"], f"row loss in {ent}"

    # 3) TRANSFORMATION ------------------------------------------------------------
    def transform():
        dp = transformations.build_dim_policy(pol, cust)
        return dp, transformations.build_fact_claims(clm, dp)
    res.dim_policy, res.fact_claims = _stage(res, "transformation", transform)
    res.customers = cust.sort_values("customer_id").reset_index(drop=True)
    res.kpis = analytics.portfolio_kpis(res.dim_policy, res.fact_claims)
    res.quality = analytics.data_quality_report(counts, res.rejected, warnings)

    # 4) LOADING -------------------------------------------------------------------
    def load():
        pq = write_parquet
        for name, df in (("customers", raw_c), ("policies", raw_p), ("claims", raw_k)):
            storage.write_frame(df, output_dir, "staging", f"{name}_raw", pq)
        storage.write_frame(res.customers, output_dir, "curated", "dim_customer", pq)
        storage.write_frame(res.dim_policy, output_dir, "curated", "dim_policy", pq)
        storage.write_frame(res.fact_claims, output_dir, "curated", "fact_claims", pq)
        for ent, df in res.rejected.items():
            storage.write_frame(df, output_dir, "rejected", f"{ent}_rejected", pq)
        rp = lambda n, df: storage.write_frame(df, output_dir, "reporting", n, pq)
        rp("metrics_by_policy_type", analytics.by_policy_type(res.dim_policy, res.fact_claims))
        rp("metrics_by_region", analytics.by_region(res.dim_policy, res.fact_claims))
        rp("monthly_claims", analytics.monthly_claims(res.fact_claims))
        rp("pivot_incurred_type_by_region", analytics.pivot_incurred(res.fact_claims))
        rp("crosstab_type_by_status", analytics.crosstab_status(res.fact_claims))
        storage.write_json(res.kpis, output_dir, "reporting", "kpis.json")
        storage.write_json(res.quality, output_dir, "reporting", "data_quality_report.json")
    _stage(res, "loading", load)

    res.elapsed_seconds = round(time.perf_counter() - t_start, 3)
    summary = {"run_id": run_id, "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "elapsed_seconds": res.elapsed_seconds, "parallel_ingestion": parallel,
               "repeat_of_same_input": res.repeat_of_same_input, "stages": res.stages, "row_counts": counts}
    storage.write_json(summary, output_dir, "reporting", "pipeline_summary.json")
    storage.append_run_log({k: summary[k] for k in ("run_id", "finished_at", "elapsed_seconds", "parallel_ingestion",
                                                    "repeat_of_same_input")} | {"curated_claims": counts["claims"]["curated"],
                                                                                 "rejected_total": sum(c["rejected"] for c in counts.values())},
                           output_dir)
    return res
