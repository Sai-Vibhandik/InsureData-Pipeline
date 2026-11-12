"""Stage 2 - Validation & standardization with explicit, documented rules.

Every rejected record keeps ALL failed rules in `reject_reasons` plus its `source_file` and `source_row`.
Order matters for referential integrity: customers -> policies -> claims.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .utils import norm_id, parse_dates, parse_money

CUSTOMER_COLS = ["customer_id", "full_name", "date_of_birth", "region", "segment", "signup_date", "updated_at"]
POLICY_COLS = ["policy_id", "customer_id", "policy_type", "start_date", "end_date", "annual_premium",
               "coverage_limit", "status"]
CLAIM_COLS = ["claim_id", "policy_id", "claim_date", "claim_amount", "claim_status", "claim_type"]


def _reasons(df: pd.DataFrame, rules: dict[str, pd.Series]) -> pd.Series:
    """Join names of all failed rules per row (vectorized: one boolean column per rule)."""
    out = pd.Series("", index=df.index, dtype="object")
    for name, mask in rules.items():
        m = mask.fillna(False).astype(bool)
        out = out.where(~m, out + np.where(out.eq("") , "", ";") + name)
    return out


def _split(df: pd.DataFrame, reasons: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    bad = reasons != ""
    rej = df[bad].copy()
    rej["reject_reasons"] = reasons[bad]
    return df[~bad].copy(), rej


def validate_customers(raw: pd.DataFrame, cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    df = raw.copy()
    df["source_row"] = range(1, len(df) + 1)
    df["customer_id"] = norm_id(df["customer_id"])
    df["updated_at"] = parse_dates(df["updated_at"], cfg["date_formats"])
    df["signup_date"] = parse_dates(df["signup_date"], cfg["date_formats"])
    dob = parse_dates(df["date_of_birth"], cfg["date_formats"])
    as_of = pd.Timestamp(cfg["as_of_date"])
    age = (as_of - dob).dt.days / 365.25
    bad_dob = dob.isna() | (age < 0) | (age > cfg["max_age_years"])
    warnings = [{"entity": "customers", "rule": "invalid_dob_set_null", "records": int(bad_dob.sum())}]
    df["date_of_birth"] = dob.where(~bad_dob)
    region = df["region"].astype("string").str.strip().str.title()
    df["region"] = region.where(region.isin(cfg["regions"]), "Unknown").astype("object")
    df["full_name"] = df["full_name"].astype("string").str.strip().str.title()
    # latest record wins per customer_id (ties -> later row); older copies are kept as rejected
    ranked = df.sort_values(["customer_id", "updated_at", "source_row"], na_position="first")
    superseded = ranked.duplicated("customer_id", keep="last").reindex(df.index)
    clean, rej = _split(df, _reasons(df, {"missing_customer_id": df["customer_id"].isna(),
                                          "superseded_duplicate": superseded & df["customer_id"].notna()}))
    clean["age"] = ((as_of - clean["date_of_birth"]).dt.days // 365.25).astype("Int64")
    return clean.reset_index(drop=True), rej.reset_index(drop=True), warnings


def validate_policies(raw: pd.DataFrame, customers: pd.DataFrame, cfg: dict[str, Any]):
    df = raw.copy()
    df["source_row"] = range(1, len(df) + 1)
    df["policy_id"], df["customer_id"] = norm_id(df["policy_id"]), norm_id(df["customer_id"])
    key = df["policy_type"].astype("string").str.strip().str.lower()
    df["policy_type"] = key.map(cfg["policy_type_map"]).astype("object")
    df["start_date"] = parse_dates(df["start_date"], cfg["date_formats"])
    df["end_date"] = parse_dates(df["end_date"], cfg["date_formats"])
    df["annual_premium"] = parse_money(df["annual_premium"])
    df["coverage_limit"] = parse_money(df["coverage_limit"])
    df["status"] = df["status"].astype("string").str.strip().str.title()
    dup_later = df.sort_values("source_row").duplicated("policy_id", keep="first").reindex(df.index) & df["policy_id"].notna()
    rules = {
        "missing_policy_id": df["policy_id"].isna(),
        "duplicate_policy_id": dup_later,
        "unknown_policy_type": df["policy_type"].isna(),
        "invalid_premium": df["annual_premium"].isna() | (df["annual_premium"] <= 0),
        "invalid_dates": df["start_date"].isna() | df["end_date"].isna(),
        "end_not_after_start": df["end_date"] <= df["start_date"],
        "policy_term_exceeds_limit": (df["end_date"] >df["start_date"] + pd.DateOffset(years=cfg["max_policy_term_years"])),
        "orphan_customer_ref": ~df["customer_id"].isin(set(customers["customer_id"])),
    }
    clean, rej = _split(df, _reasons(df, rules))
    clean["coverage_limit"] = clean["coverage_limit"].fillna(0.0)
    return clean.reset_index(drop=True), rej.reset_index(drop=True), []


def validate_claims(raw: pd.DataFrame, policies: pd.DataFrame, cfg: dict[str, Any]):
    df = raw.copy()
    df["source_row"] = df.groupby("source_file").cumcount() + 1
    df["claim_id"], df["policy_id"] = norm_id(df["claim_id"]), norm_id(df["policy_id"])
    df["claim_date"] = parse_dates(df["claim_date"], cfg["date_formats"])
    df["claim_amount"] = parse_money(df["claim_amount"])
    key = df["claim_status"].astype("string").str.strip().str.lower()
    df["claim_status"] = key.map(cfg["claim_status_map"]).astype("object")
    df["claim_type"] = df["claim_type"].astype("string").str.strip().str.title()
    dup_later = df.duplicated("claim_id", keep="first") & df["claim_id"].notna()    # concat order is deterministic
    pol = policies.set_index("policy_id")[["start_date", "end_date", "coverage_limit"]]
    j = df[["policy_id"]].join(pol, on="policy_id")
    outside = df["claim_date"].notna() & j["start_date"].notna() & (
        (df["claim_date"] < j["start_date"]) | (df["claim_date"] > j["end_date"]))
    rules = {
        "missing_claim_id": df["claim_id"].isna(),
        "duplicate_claim_id": dup_later,
        "invalid_claim_date": df["claim_date"].isna(),
        "invalid_amount": df["claim_amount"].isna() | (df["claim_amount"] <= 0),
        "unknown_claim_status": df["claim_status"].isna(),
        "orphan_policy_ref": ~df["policy_id"].isin(set(policies["policy_id"])),
        "claim_outside_policy_period": outside,
    }
    clean, rej = _split(df, _reasons(df, rules))
    lim = clean[["policy_id"]].join(pol[["coverage_limit"]], on="policy_id")["coverage_limit"]
    clean["exceeds_coverage_limit"] = np.where(lim > 0, clean["claim_amount"] > lim, False)
    warnings = [{"entity": "claims", "rule": "exceeds_coverage_limit_flagged", "records": int(clean["exceeds_coverage_limit"].sum())}]
    return clean.reset_index(drop=True), rej.reset_index(drop=True), warnings
