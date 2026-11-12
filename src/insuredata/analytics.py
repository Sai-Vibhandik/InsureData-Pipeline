"""Metric definitions (documented in docs/data_dictionary.md). Pure functions over curated tables.

claim_frequency = valid claims / policies                (per group, no exposure-time adjustment)
incurred_amount = sum(claim_amount) for claims whose status is not Rejected
loss_ratio      = incurred_amount / sum(annual_premium)  (written premium, NOT earned premium)
approval_rate   = (Approved + Paid) / (Approved + Paid + Rejected)   (Open claims excluded)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _group_metrics(dim_policy: pd.DataFrame, fact: pd.DataFrame, by: str) -> pd.DataFrame:
    p = dim_policy.groupby(by).agg(policies=("policy_id", "count"), written_premium=("annual_premium", "sum"))
    c = fact.groupby(by).agg(claims=("claim_id", "count"), incurred_amount=("incurred_amount", "sum"),
                             avg_claim_amount=("claim_amount", "mean"))
    out = p.join(c).fillna({"claims": 0, "incurred_amount": 0.0, "avg_claim_amount": 0.0})
    out["claim_frequency"] = out["claims"] / out["policies"]
    out["loss_ratio"] = out["incurred_amount"] / out["written_premium"].replace(0, np.nan)
    return out.round(4).reset_index()


def by_policy_type(dim_policy, fact):
    return _group_metrics(dim_policy, fact, "policy_type")


def by_region(dim_policy, fact):
    return _group_metrics(dim_policy, fact, "region")


def monthly_claims(fact: pd.DataFrame) -> pd.DataFrame:
    g = fact.groupby("claim_month").agg(claims=("claim_id", "count"), incurred_amount=("incurred_amount", "sum"))
    return g.round(2).reset_index()


def pivot_incurred(fact: pd.DataFrame) -> pd.DataFrame:
    return fact.pivot_table(index="policy_type", columns="region", values="incurred_amount",
                            aggfunc="sum", fill_value=0.0, margins=True, margins_name="Total").round(2).reset_index()


def crosstab_status(fact: pd.DataFrame) -> pd.DataFrame:
    return pd.crosstab(fact["policy_type"], fact["claim_status"], margins=True, margins_name="Total").reset_index()


def portfolio_kpis(dim_policy: pd.DataFrame, fact: pd.DataFrame) -> dict:
    prem = float(dim_policy["annual_premium"].sum())
    inc = float(fact["incurred_amount"].sum())
    st = fact["claim_status"].value_counts()
    decided = st.get("Approved", 0) + st.get("Paid", 0) + st.get("Rejected", 0)
    return {
        "policies": int(len(dim_policy)), "customers_with_policies": int(dim_policy["customer_id"].nunique()),
        "claims": int(len(fact)), "written_premium": round(prem, 2), "incurred_amount": round(inc, 2),
        "loss_ratio": round(inc / prem, 4) if prem else None,
        "claim_frequency": round(len(fact) / len(dim_policy), 4) if len(dim_policy) else None,
        "avg_claim_amount": round(float(fact["claim_amount"].mean()), 2) if len(fact) else None,
        "approval_rate": round(float((st.get("Approved", 0) + st.get("Paid", 0)) / decided), 4) if decided else None,
        "claims_exceeding_coverage": int(fact["exceeds_coverage_limit"].sum()) if len(fact) else 0,
        "avg_days_to_claim": round(float(fact["days_since_policy_start"].mean()), 2) if len(fact) else None,
    }


def data_quality_report(counts: dict, rejects: dict[str, pd.DataFrame], warnings: list[dict]) -> dict:
    rep = {"entities": {}, "warnings": warnings}
    for ent, rej in rejects.items():
        reasons = (rej["reject_reasons"].str.split(";").explode().value_counts().to_dict() if len(rej) else {})
        n_in = counts[ent]["input"]
        rep["entities"][ent] = {**counts[ent], "rejected_pct": round(100 * counts[ent]["rejected"] / max(n_in, 1), 2),
                                "reject_reason_counts": {k: int(v) for k, v in reasons.items()}}
    return rep
