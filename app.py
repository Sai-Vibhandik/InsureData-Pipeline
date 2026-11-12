"""InsureData analytics workbench.  Launch:  streamlit run app.py
Reads the pipeline's curated outputs (run `python run.py` first, or use the sidebar button)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from insuredata import analytics  # noqa: E402
from insuredata.ingestion import IngestionError  # noqa: E402
from insuredata.pipeline import run_pipeline  # noqa: E402
from insuredata.storage import read_run_log  # noqa: E402

OUT = ROOT / "outputs"
st.set_page_config(page_title="InsureData Workbench", page_icon="📊", layout="wide")
PLUM, SAND, TEAL, ROSE = "#3B1F5C", "#F4EFE6", "#0E7C7B", "#C8553D"
st.markdown(f"""<style>
.block-container {{padding-top:1.2rem; max-width:1300px}}
.k {{background:{SAND};border-radius:10px;padding:12px 16px;border-bottom:4px solid {PLUM}}}
.k .l {{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:#6B5B7B}}
.k .v {{font-size:1.5rem;font-weight:700;color:{PLUM}}}
h1,h2,h3 {{color:{PLUM}}}
</style>""", unsafe_allow_html=True)


def kpi(col, label, value):
    col.markdown(f'<div class="k"><div class="l">{label}</div><div class="v">{value}</div></div>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load(mtime: float):
    z = lambda zone, n: pd.read_csv(OUT / zone / f"{n}.csv")
    pol, clm, cus = z("curated", "dim_policy"), z("curated", "fact_claims"), z("curated", "dim_customer")
    clm["claim_date"] = pd.to_datetime(clm["claim_date"])
    rej = {e: z("rejected", f"{e}_rejected") for e in ("customers", "policies", "claims")}
    return pol, clm, cus, rej


st.sidebar.markdown("## 📊 InsureData\nInsurance analytics workbench")
if st.sidebar.button("▶ Run pipeline now"):
    try:
        with st.spinner("Running ingestion → validation → transformation → loading..."):
            r = run_pipeline(parallel=True)
        st.sidebar.success(f"Run {r.run_id} finished in {r.elapsed_seconds}s")
    except IngestionError as exc:
        st.sidebar.error(f"Pipeline failed: {exc}")
marker = OUT / "reporting" / "kpis.json"
if not marker.exists():
    st.info("No curated data yet. Click **Run pipeline now** in the sidebar (or run `python run.py`).")
    st.stop()
pol, clm, cus, rej = load(marker.stat().st_mtime)

page = st.sidebar.radio("Workspace", ["Portfolio Overview", "Claims Analytics", "Policy Explorer", "Data Quality",
                                      "Pipeline Runs", "Data Exports"])
st.sidebar.caption("Synthetic data. Metrics are defined in docs/data_dictionary.md.")
types = st.sidebar.multiselect("Policy type", sorted(pol.policy_type.unique()))
regions = st.sidebar.multiselect("Region", sorted(pol.region.unique()))
fp = pol
if types:
    fp = fp[fp.policy_type.isin(types)]
if regions:
    fp = fp[fp.region.isin(regions)]
fc = clm[clm.policy_id.isin(fp.policy_id)]

if page == "Portfolio Overview":
    st.title("Portfolio Overview")
    if fp.empty:
        st.warning("No policies match the filters.")
        st.stop()
    k = analytics.portfolio_kpis(fp, fc)
    c = st.columns(6)
    kpi(c[0], "Policies", f"{k['policies']:,}"); kpi(c[1], "Written premium", f"${k['written_premium']:,.0f}")
    kpi(c[2], "Incurred claims", f"${k['incurred_amount']:,.0f}")
    kpi(c[3], "Loss ratio", f"{(k['loss_ratio'] or 0):.1%}"); kpi(c[4], "Claim frequency", f"{(k['claim_frequency'] or 0):.2f}")
    kpi(c[5],"Avg days to claim",f"{k['avg_days_to_claim']:,.1f}" if k["avg_days_to_claim"] is not None else "N/A") #updated
    st.caption("Loss ratio = incurred ÷ written premium (not earned premium). Frequency = claims ÷ policies.")
    a, b = st.columns(2)
    m = analytics.by_policy_type(fp, fc)
    a.plotly_chart(px.bar(m, x="policy_type", y="loss_ratio", title="Loss ratio by policy type", color_discrete_sequence=[TEAL]), use_container_width=True)
    b.plotly_chart(px.bar(analytics.by_region(fp, fc), x="region", y="claim_frequency", title="Claim frequency by region",
                          color_discrete_sequence=[PLUM]), use_container_width=True)
    
    # Average days between policy start and claim date by policy type         #Updated
    avg_days = (fc.groupby("policy_type", as_index=False)["days_since_policy_start"].mean())

    st.plotly_chart(
        px.bar(
            avg_days,
            x="policy_type",
            y="days_since_policy_start",
            title="Average Days to Claim by Policy Type",
            labels={
                "policy_type": "Policy Type",
                "days_since_policy_start": "Average Days"
            },
            color_discrete_sequence=[TEAL]
        ),
        use_container_width=True
    )
    
    st.subheader("Metrics by policy type")
    st.dataframe(m, hide_index=True, use_container_width=True)

elif page == "Claims Analytics":
    st.title("Claims Analytics")
    status = st.multiselect("Claim status", sorted(fc.claim_status.unique()), default=sorted(fc.claim_status.unique()))
    v = fc[fc.claim_status.isin(status)]
    if v.empty:
        st.warning("No claims match the filters."); st.stop()
    st.plotly_chart(px.bar(analytics.monthly_claims(v), x="claim_month", y="incurred_amount", title="Incurred amount by month",
                           color_discrete_sequence=[ROSE]), use_container_width=True)
    a, b = st.columns(2)
    a.subheader("Incurred: policy type × region (pivot)"); a.dataframe(analytics.pivot_incurred(v), hide_index=True)
    b.subheader("Policy type × status (crosstab)"); b.dataframe(analytics.crosstab_status(v), hide_index=True)
    st.subheader("Claims above coverage limit (flagged, incurred capped)")
    st.dataframe(v[v.exceeds_coverage_limit], hide_index=True, use_container_width=True)
    st.subheader("Claim records")
    st.dataframe(v.sort_values("claim_amount", ascending=False), hide_index=True, use_container_width=True)

elif page == "Policy Explorer":
    st.title("Policy Explorer")
    q = st.text_input("Search policy or customer ID / name")
    v = fp[fp.apply(lambda r: q.lower() in f"{r.policy_id} {r.customer_id} {r.full_name}".lower(), axis=1)] if q else fp
    st.caption(f"{len(v):,} policies")
    st.dataframe(v, hide_index=True, use_container_width=True)
    if len(v):
        pick = st.selectbox("Drill into policy", v.policy_id.tolist())
        st.json(v[v.policy_id == pick].iloc[0].astype(str).to_dict())
        pc = clm[clm.policy_id == pick]
        st.write(f"**{len(pc)} claim(s)**" if len(pc) else "No claims for this policy.")
        if len(pc): st.dataframe(pc, hide_index=True, use_container_width=True)

elif page == "Data Quality":
    st.title("Data Quality")
    rep = pd.read_json(OUT / "reporting" / "data_quality_report.json", typ="series")
    ent = rep["entities"]
    cols = st.columns(3)
    for col, (name, e) in zip(cols, ent.items()):
        kpi(col, f"{name}: rejected", f"{e['rejected']} / {e['input']} ({e['rejected_pct']}%)")
    rows = [{"entity": n, "reason": r, "records": c} for n, e in ent.items() for r, c in e["reject_reason_counts"].items()]
    if rows:
        st.plotly_chart(px.bar(pd.DataFrame(rows), x="records", y="reason", color="entity", orientation="h",
                               title="Rejected records by rule"), use_container_width=True)
    st.subheader("Non-blocking warnings"); st.dataframe(pd.DataFrame(rep["warnings"]), hide_index=True)
    which = st.selectbox("Inspect rejected records", list(rej))
    st.dataframe(rej[which], hide_index=True, use_container_width=True)

elif page == "Pipeline Runs":
    st.title("Pipeline Runs")
    runs = pd.DataFrame(read_run_log(OUT))
    summary = pd.read_json(OUT / "reporting" / "pipeline_summary.json", typ="series")
    st.subheader("Last run stages")
    st.dataframe(pd.DataFrame(summary["stages"]), hide_index=True)
    st.caption("Re-running on identical input rewrites identical curated files (see `repeat_of_same_input`).")
    st.dataframe(runs, hide_index=True, use_container_width=True)

else:
    st.title("Data Exports")
    for name, df in {"dim_policy": fp, "fact_claims": fc, "dim_customer": cus, **{f"{k}_rejected": v for k, v in rej.items()}}.items():
        a, b = st.columns([4, 1])
        a.write(f"**{name}** · {len(df):,} rows")
        b.download_button("CSV", df.to_csv(index=False).encode(), f"{name}.csv", "text/csv", key=name)
    st.caption("Full curated CSV/Parquet files are in outputs/curated/ and outputs/reporting/.")
