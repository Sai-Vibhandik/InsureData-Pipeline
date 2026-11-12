"""Tiny in-memory raw tables (all text, like real ingestion output)."""
import pandas as pd

import _path  # noqa: F401
from insuredata.utils import load_config

CFG = load_config()


def customers(rows=None):
    base = [dict(customer_id="CUST-1", full_name="ann lee", date_of_birth="1985-03-01", region="north",
                 segment="Retail", signup_date="2020-01-01", updated_at="2024-01-01", source_file="c.csv")]
    return pd.DataFrame(rows if rows is not None else base, dtype="object")


def policies(rows=None):
    base = [dict(policy_id="POL-1", customer_id="CUST-1", policy_type="Motor", start_date="2024-01-01",
                 end_date="2024-12-31", annual_premium="$1,000.00", coverage_limit="10000", status="Active",
                 source_file="p.json")]
    return pd.DataFrame(rows if rows is not None else base, dtype="object")


def claims(rows=None):
    base = [dict(claim_id="CLM-1", policy_id="POL-1", claim_date="2024-06-01", claim_amount="2500",
                 claim_status="paid", claim_type="collision", source_file="k.csv")]
    return pd.DataFrame(rows if rows is not None else base, dtype="object")


def with_(df, idx=0, **chg):
    d = df.copy()
    for k, v in chg.items():
        d.loc[d.index[idx], k] = v
    return d


def dup(df, idx=0, **chg):
    row = df.iloc[[idx]].copy()
    for k, v in chg.items():
        row[k] = v
    return pd.concat([df, row], ignore_index=True)
