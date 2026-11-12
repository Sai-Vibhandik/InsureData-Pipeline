import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import _path  # noqa: F401
from insuredata.ingestion import IngestionError
from insuredata.pipeline import run_pipeline
from insuredata.storage import read_run_log

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
DETERMINISTIC = ("curated", "rejected", "reporting")


def snapshot(out: Path) -> dict:
    snap = {}
    for zone in DETERMINISTIC:
        for p in sorted((out / zone).glob("*")):
            if p.name in ("pipeline_summary.json", "pipeline_runs.jsonl") or p.suffix == ".parquet":
                continue                      # contain timestamps/timings by design
            snap[f"{zone}/{p.name}"] = hashlib.sha256(p.read_bytes()).hexdigest()
    return snap


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())

    def test_end_to_end_zones_schema_and_row_conservation(self):
        res = run_pipeline(RAW, self.out, write_parquet=False)
        for zone in ("staging", "curated", "rejected", "reporting"):
            self.assertTrue((self.out / zone).is_dir(), zone)
        for ent, e in res.quality["entities"].items():
            self.assertEqual(e["input"], e["curated"] + e["rejected"], ent)
        fc = pd.read_csv(self.out / "curated" / "fact_claims.csv")
        self.assertEqual(list(fc.columns[:4]), ["claim_id", "policy_id", "customer_id", "policy_type"])
        self.assertTrue(fc.claim_id.is_unique)
        dp = pd.read_csv(self.out / "curated" / "dim_policy.csv")
        self.assertTrue(dp.policy_id.is_unique)
        self.assertTrue(set(fc.policy_id) <= set(dp.policy_id))                     # referential integrity holds
        self.assertTrue(set(dp.customer_id) <= set(pd.read_csv(self.out / "curated" / "dim_customer.csv").customer_id))
        rej = pd.read_csv(self.out / "rejected" / "claims_rejected.csv")
        self.assertTrue(rej.reject_reasons.notna().all())
        self.assertIn("orphan_policy_ref", set(rej.reject_reasons.str.split(";").explode()))
        kpis = json.loads((self.out / "reporting" / "kpis.json").read_text())
        self.assertEqual(kpis["claims"], len(fc))
        self.assertEqual([s["stage"] for s in res.stages], ["ingestion", "validation", "transformation", "loading"])

    def test_rerun_is_idempotent_and_does_not_multiply_records(self):
        run_pipeline(RAW, self.out, write_parquet=False)
        first = snapshot(self.out)
        n_claims = len(pd.read_csv(self.out / "curated" / "fact_claims.csv"))
        res2 = run_pipeline(RAW, self.out, write_parquet=False)
        self.assertEqual(first, snapshot(self.out))
        self.assertEqual(n_claims, len(pd.read_csv(self.out / "curated" / "fact_claims.csv")))
        self.assertTrue(res2.repeat_of_same_input)
        self.assertEqual(len(read_run_log(self.out)), 2)                             # history appends, data does not

    def test_parallel_matches_serial(self):
        o2 = Path(tempfile.mkdtemp())
        run_pipeline(RAW, self.out, write_parquet=False)
        run_pipeline(RAW, o2, parallel=True, write_parquet=False)
        self.assertEqual(snapshot(self.out), snapshot(o2))

    def test_missing_input_and_missing_column_fail_clearly(self):
        empty = Path(tempfile.mkdtemp())
        with self.assertRaises(IngestionError):
            run_pipeline(empty, self.out)
        broken = Path(tempfile.mkdtemp())
        for f in RAW.iterdir():
            shutil.copy(f, broken / f.name)
        df = pd.read_csv(broken / "claims_2024.csv", dtype=str).drop(columns=["claim_amount"])
        df.to_csv(broken / "claims_2024.csv", index=False)
        with self.assertRaises(IngestionError) as cm:
            run_pipeline(broken, self.out)
        self.assertIn("claim_amount", str(cm.exception))

    def test_changed_input_changes_run_id(self):
        a = run_pipeline(RAW, self.out, write_parquet=False).run_id
        alt = Path(tempfile.mkdtemp())
        for f in RAW.iterdir():
            shutil.copy(f, alt / f.name)
        with (alt / "claims_2024.csv").open("a") as fh:
            fh.write("CLM-999999,POL-00001,2024-02-01,10,paid,Glass\n")
        self.assertNotEqual(a, run_pipeline(alt, Path(tempfile.mkdtemp()), write_parquet=False).run_id)


if __name__ == "__main__":
    unittest.main()
