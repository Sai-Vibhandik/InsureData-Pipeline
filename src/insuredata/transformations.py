"""Stage 3 - Transformation: build curated, analysis-ready tables (vectorized NumPy/Pandas)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def build_dim_policy(policies: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    """Policy dimension enriched with customer attributes. Join key: policies.customer_id -> customers.customer_id
    (customers are unique after validation, so the join cannot multiply policy rows)."""
    cust = customers[["customer_id", "full_name", "region", "segment", "age"]]
    out = policies.merge(cust, on="customer_id", how="left", validate="many_to_one")
    out["term_days"] = (out["end_date"] - out["start_date"]).dt.days
    age = out["age"].astype("float64")            # NaN-safe boolean comparisons (nullable Int64 yields NA masks)
    out["age_band"] = np.select([age.isna(), age < 30, age < 50, age < 65],
                                ["Unknown", "<30", "30-49", "50-64"], default="65+")
    out["premium_band"] = pd.cut(out["annual_premium"], [0, 500, 1500, 3000, np.inf],
                                 labels=["Low", "Medium", "High", "Premium"]).astype(str)
    cols = ["policy_id", "customer_id", "full_name", "region", "segment", "age", "age_band", "policy_type",
            "start_date", "end_date", "term_days", "annual_premium", "premium_band", "coverage_limit", "status",
            "source_file"]
    return out[cols].sort_values("policy_id").reset_index(drop=True)


def build_fact_claims(claims: pd.DataFrame, dim_policy: pd.DataFrame) -> pd.DataFrame:
    """Claims fact with policy context. Join key: claims.policy_id -> dim_policy.policy_id (unique)."""
    pol = dim_policy[["policy_id", "customer_id", "policy_type", "region", "segment", "start_date", "annual_premium", "coverage_limit"]]
    out = claims.merge(pol, on="policy_id", how="left", validate="many_to_one")
    out["claim_month"] = out["claim_date"].dt.to_period("M").astype(str)
    out["days_since_policy_start"] = (out["claim_date"] - out["start_date"]).dt.days
    out["is_incurred"] = out["claim_status"] != "Rejected"
    # Incurred is capped at the policy coverage limit (a limit of 0 means "unknown", so no cap is applied).
    cap = np.where(out["coverage_limit"] > 0, out["coverage_limit"], np.inf)
    out["incurred_amount"] = np.where(out["is_incurred"], np.minimum(out["claim_amount"], cap), 0.0)
    cols = ["claim_id", "policy_id", "customer_id", "policy_type", "region", "segment", "claim_date", "claim_month",
            "claim_type", "claim_status", "claim_amount", "incurred_amount", "is_incurred",
            "days_since_policy_start", "exceeds_coverage_limit", "source_file"]
    return out[cols].sort_values("claim_id").reset_index(drop=True)
