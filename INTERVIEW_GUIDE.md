# Interview Guide - InsureData Pipeline

> **Make it yours.** These projects are teaching scaffolds. Before you put one on your CV, read every module, run it, break it on purpose, change something meaningful (a rule, a metric, a chart), and be able to explain each design choice in your own words. In interviews, be transparent about what you built, what was provided in the course, and what is simulated or future work. Never claim production use, users, or performance numbers you did not measure.

## 30-second pitch
InsureData is a reproducible ETL pipeline that turns messy synthetic customer, policy and claims files into trusted curated tables. It enforces referential integrity, keeps every rejected record with reasons, computes precisely defined metrics like loss ratio and claim frequency, and presents them in a Streamlit analytics workbench. Reruns are idempotent.

## Two-minute technical explanation
Four explicit stages. Ingestion reads customers.csv, policies.json and two claims CSVs as text with source-file lineage (optionally reading claim files in parallel) and checks required columns per file. Validation standardizes dates, IDs, categories and numbers, then applies documented rules in dependency order so policies must reference curated customers and claims must reference curated policies and fall inside the policy period; failures go to rejected tables with all reasons. Transformation builds `dim_policy` and `fact_claims` via validated many-to-one joins and derives bands, months and incurred amounts with NumPy. Loading writes staging, curated, rejected and reporting zones atomically, plus KPIs, pivots, a crosstab, a data-quality report and a run log. The dashboard reads those outputs.

## What each module does
| Module | Responsibility |
|---|---|
| `ingestion.py` | Read CSV/JSON/Excel/Parquet as text; bounded parallel reads; column checks. |
| `validation.py` | Per-entity rules, standardization, referential integrity. |
| `transformations.py` | Curated `dim_policy` and `fact_claims` with derived fields. |
| `analytics.py` | Metric formulas, pivot, crosstab, DQ report. |
| `storage.py` | Atomic zone writers, run log. |
| `pipeline.py` | Stage orchestration and run id. |
| `app.py` | Streamlit workbench (reads outputs). |

## Architecture in an interview (how to say it)
Say: 'It's a classic landing -> staging -> curated architecture on local files. Each stage has a clear input/output contract, and everything rejected is kept. The same design maps onto Spark/dbt and an orchestrator later.'

## Data flow in one breath
raw CSV/JSON -> text DataFrames (+source_file) -> staging copy -> validate customers -> validate policies -> validate claims -> rejected tables -> dim_policy / fact_claims -> metrics, pivot, crosstab, DQ report -> CSV/Parquet zones -> dashboard.

## Why these tools
Pandas for relational joins, groupby, pivot_table and crosstab; NumPy for vectorized conditionals; `concurrent.futures` for optional parallel reads; pathlib/json for config and paths; PyArrow for Parquet; Streamlit/Plotly for the workbench; openpyxl for Excel input support.

## Five important technical decisions
1. **Validate in dependency order** - parent tables first so orphan references are caught and cascades are explainable.
2. **Reject with reasons, assert row conservation** - no silent loss; auditable data quality.
3. **Capped incurred amount with a flag** - a defined business rule that keeps outliers visible but not distorting.
4. **Atomic, fixed-name outputs + input-hash run id** - idempotent reruns without duplicated or half-written data.
5. **Config-driven mappings and as-of date** - behavior and reproducibility controlled outside code.

## Ten likely questions (with model answers)
**Q1. Why validate customers, then policies, then claims?**

Referential integrity is checked against the already-validated parent table: a policy needs a *curated* customer, a claim needs a *curated* policy. Doing it in the opposite order would let claims reference policies that are later rejected. The cascade is intentional: 45 claims are rejected as `orphan_policy_ref`, some because their policy was itself rejected.

**Q2. How do you handle duplicate keys?**

Customers: the latest `updated_at` wins; older copies go to `customers_rejected` as `superseded_duplicate`. Policies and claims: first occurrence in deterministic file order wins; later copies are rejected as `duplicate_policy_id` / `duplicate_claim_id`. The joins use pandas `validate='many_to_one'`, so any remaining duplicate key would raise instead of silently multiplying rows.

**Q3. Define loss ratio and its limits.**

loss_ratio = incurred_amount / written annual premium. Incurred excludes Rejected claims and is capped at the policy coverage limit. Limits: written premium is not earned premium (no time-on-risk adjustment), and the sample is synthetic, so values carry no industry meaning.

**Q4. Why cap incurred at the coverage limit?**

A claim larger than the limit cannot be paid above it. Without the cap, 8 injected 900k+ claims dominated the portfolio (loss ratio 4.1 -> 0.81). The raw amount is retained and flagged in `exceeds_coverage_limit`, so nothing is hidden.

**Q5. How do reruns avoid corrupting or multiplying data?**

Output filenames are fixed and written atomically (temp file + `os.replace`), so a rerun overwrites rather than appends. The run id is a hash of inputs + config; the run log (`pipeline_runs.jsonl`) is the only append-only file and records `repeat_of_same_input`. A test compares file hashes across reruns.

**Q6. Why preserve rejected records?**

Data stewards need to fix upstream data. Each rejected row keeps `source_file`, `source_row` and *all* failed rules (`reject_reasons`, semicolon-joined). A pipeline assertion checks `input == curated + rejected` per entity, so rows cannot vanish.

**Q7. Where do you use NumPy and why?**

`np.select` builds age bands, `np.where`/`np.minimum` implement the coverage cap and flags, and `np.inf` marks 'no cap'. These are vectorized, avoiding Python loops over rows. Pandas handles the joins, groupbys, pivot tables and crosstabs.

**Q8. Is concurrent ingestion worthwhile here?**

Honestly, for two small CSVs the benefit is negligible; `--parallel` demonstrates a bounded `ThreadPoolExecutor` reading files concurrently and, because `pool.map` preserves order, produces identical output (tested). It becomes useful with many or large files or slow storage.

**Q9. Why is `as_of_date` in the config?**

Age and 'future DOB' checks depend on 'today'. Using the wall clock would change outputs between runs; a configured as-of date keeps results reproducible.

**Q10. What do staging, curated, rejected and reporting mean?**

Staging: raw rows as text with lineage (a landing copy). Curated: validated, typed, joined analytical tables (`dim_customer`, `dim_policy`, `fact_claims`). Rejected: failed records with reasons. Reporting: aggregates, pivots, KPIs and the quality report.

More questions: [docs/interview_questions.md](docs/interview_questions.md).

## Five realistic failure scenarios
1. **Missing input file or column** -> `IngestionError` naming the file/columns; exit code 2 from the CLI.
2. **Claim references nonexistent policy** -> rejected `orphan_policy_ref`, preserved.
3. **Claim date outside policy period** -> rejected `claim_outside_policy_period`.
4. **Duplicate IDs** -> customers: latest wins; policies/claims: first wins; others preserved as rejected.
5. **Rerun after partial/interrupted write** -> atomic replace means no half-written files; rerunning rewrites the same names.

## Three realistic improvements for a future version
1. Incremental loads keyed on `updated_at` and partitioned Parquet output.
2. Add earned-premium exposure calculations and a proper claim-development view.
3. Orchestrate with Airflow/Prefect and add Great-Expectations-style checks and alerts.

## What must change before production
A real warehouse or lakehouse, orchestration with retries and alerting, secrets and access control, PII handling and data-retention review, schema contracts with the source systems, data lineage/catalog, performance testing on real volumes, and actuarial/business review of every metric definition.

## Skills this project demonstrates
ETL stage design, Relational data quality and referential integrity, Pandas joins/groupby/pivot_table/crosstab, NumPy vectorization, CSV/JSON/Excel/Parquet I/O, Idempotent, atomic file loading, Concurrent file reads (bounded), Metric definition and documentation, Streamlit/Plotly analytics UI, Testing data pipelines

## Suggested GitHub repository description
> Reproducible insurance ETL on synthetic data: ingestion, validation, referential integrity, rejected-record tracking, curated tables, metrics and a Streamlit workbench.

**Topics:** python, pandas, numpy, etl, data-engineering, data-quality, insurance-analytics, parquet, streamlit, portfolio-project

## Checklist before publishing
- [ ] Replace `<YOUR NAME>` in `LICENSE` and `pyproject.toml`; read the license terms.
- [ ] Run the app and tests on your own machine; paste *your* real test output in the README.
- [ ] Capture screenshots into `docs/screenshots/` and link them in the README (none are shipped - none could be generated here).
- [ ] Change at least one rule/metric/page and document it in the README "What I changed" section.
- [ ] Keep the "synthetic data / simulated" labels. Do not remove limitations.
- [ ] Confirm no `.env`, logs or database files are committed (`git status`).
- [ ] Be ready to explain every file. If you cannot, simplify it until you can.
