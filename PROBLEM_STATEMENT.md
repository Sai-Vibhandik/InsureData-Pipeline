# Problem Statement - InsureData Pipeline

## Business context
An insurance analytics team receives customer master data, policy records and claims from different systems. Reporting on portfolio performance requires trusted, joined datasets.

## Problem definition
Build a repeatable pipeline that ingests the raw files, standardizes and validates them against documented rules (including referential integrity and business rules), keeps every rejected record with reasons, produces curated analytical tables, computes defined metrics, and exposes results to analysts.

## Target users
Insurance data/analytics engineers, portfolio analysts, data stewards fixing source data, and interviewers evaluating ETL fundamentals.

## Existing pain points
One-off scripts that drop nulls silently; duplicate keys multiplying joined rows; orphaned claims; inconsistent categories; undocumented metric formulas; reruns that append duplicate data.

## Functional requirements
FR1 ingest CSV/JSON (+Excel/Parquet). FR2 explicit ingestion/validation/transformation/loading stages. FR3 separate raw, staging, curated, rejected and reporting outputs. FR4 standardize dates, categories, identifiers, numbers. FR5 documented handling of missing values, duplicates, malformed records, invalid types. FR6 referential integrity (claims->policies->customers). FR7 defined insurance metrics. FR8 documented join keys and duplicate/unmatched handling. FR9 aggregations, pivot, crosstab, time summaries. FR10 CLI entry point. FR11 execution summary, DQ report, rejected files. FR12 CSV/Parquet export. FR13 dashboard with filters/KPIs/trends/drill-down. FR14 optional concurrent ingestion. FR15 scheduling design (documented). FR16 idempotent reruns. FR17 scaling notes.

## Non-functional requirements
Deterministic outputs; atomic writes; no network; clear errors; tests offline; documented limits.

## Scope
In: local pipeline + dashboard on synthetic data. **Out:** real policy admin integration, actuarial reserving, earned-premium/exposure modelling, PII governance, orchestrated production deployment.

## Acceptance criteria
1. `python run.py` completes and writes all four zones. 2. For each entity, input = curated + rejected. 3. Every curated claim references a curated policy; every curated policy a curated customer. 4. Reruns on identical input produce identical data files. 5. Metrics match documented formulas (tested on tiny fixtures). 6. Tests pass offline.

## Business value (qualitative)
Trusted, explainable datasets and a visible list of data defects for upstream owners. No quantitative benefit is claimed.

## Assumptions
Policy term is one year in the sample; the as-of date is 2024-12-31; `updated_at` identifies the most recent customer record; premium is annual written premium; thresholds and mappings are illustrative.
