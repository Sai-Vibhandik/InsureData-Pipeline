# InsureData Pipeline - Interview Questions and Model Answers

### 1. Why validate customers, then policies, then claims?

Referential integrity is checked against the already-validated parent table: a policy needs a *curated* customer, a claim needs a *curated* policy. Doing it in the opposite order would let claims reference policies that are later rejected. The cascade is intentional: 45 claims are rejected as `orphan_policy_ref`, some because their policy was itself rejected.

### 2. How do you handle duplicate keys?

Customers: the latest `updated_at` wins; older copies go to `customers_rejected` as `superseded_duplicate`. Policies and claims: first occurrence in deterministic file order wins; later copies are rejected as `duplicate_policy_id` / `duplicate_claim_id`. The joins use pandas `validate='many_to_one'`, so any remaining duplicate key would raise instead of silently multiplying rows.

### 3. Define loss ratio and its limits.

loss_ratio = incurred_amount / written annual premium. Incurred excludes Rejected claims and is capped at the policy coverage limit. Limits: written premium is not earned premium (no time-on-risk adjustment), and the sample is synthetic, so values carry no industry meaning.

### 4. Why cap incurred at the coverage limit?

A claim larger than the limit cannot be paid above it. Without the cap, 8 injected 900k+ claims dominated the portfolio (loss ratio 4.1 -> 0.81). The raw amount is retained and flagged in `exceeds_coverage_limit`, so nothing is hidden.

### 5. How do reruns avoid corrupting or multiplying data?

Output filenames are fixed and written atomically (temp file + `os.replace`), so a rerun overwrites rather than appends. The run id is a hash of inputs + config; the run log (`pipeline_runs.jsonl`) is the only append-only file and records `repeat_of_same_input`. A test compares file hashes across reruns.

### 6. Why preserve rejected records?

Data stewards need to fix upstream data. Each rejected row keeps `source_file`, `source_row` and *all* failed rules (`reject_reasons`, semicolon-joined). A pipeline assertion checks `input == curated + rejected` per entity, so rows cannot vanish.

### 7. Where do you use NumPy and why?

`np.select` builds age bands, `np.where`/`np.minimum` implement the coverage cap and flags, and `np.inf` marks 'no cap'. These are vectorized, avoiding Python loops over rows. Pandas handles the joins, groupbys, pivot tables and crosstabs.

### 8. Is concurrent ingestion worthwhile here?

Honestly, for two small CSVs the benefit is negligible; `--parallel` demonstrates a bounded `ThreadPoolExecutor` reading files concurrently and, because `pool.map` preserves order, produces identical output (tested). It becomes useful with many or large files or slow storage.

### 9. Why is `as_of_date` in the config?

Age and 'future DOB' checks depend on 'today'. Using the wall clock would change outputs between runs; a configured as-of date keeps results reproducible.

### 10. What do staging, curated, rejected and reporting mean?

Staging: raw rows as text with lineage (a landing copy). Curated: validated, typed, joined analytical tables (`dim_customer`, `dim_policy`, `fact_claims`). Rejected: failed records with reasons. Reporting: aggregates, pivots, KPIs and the quality report.

### 11. Why check required columns per file?

If one claims file lacked `claim_amount`, concatenation would fill NaN and every row from that file would be rejected as an amount problem, hiding a schema break. Checking each file before concatenation gives a clear `IngestionError` naming the file.

### 12. How would this scale to the cloud?

Land raw files in object storage, run the same stages as Spark/dbt/SQL jobs writing partitioned Parquet or Delta tables, keep the rejected zone and quality report, and orchestrate with Airflow or a managed scheduler. The stage boundaries and table contracts already map onto that. This is a design note, not an implemented feature.

### 13. How would you schedule it without Airflow?

A cron or Windows Task Scheduler entry running `python run.py`; see `docs/scheduling.md` for an example and an Airflow DAG sketch (not executed here).

### 14. How is the pipeline tested?

25 tests: ingestion (CSV/JSON/Excel, errors, parallel = serial), each validation rule, join cardinality, metric formulas on tiny fixtures, no-claims edge case, end-to-end zones/schemas/row conservation, idempotent reruns, missing input/column errors, changed input => new run id.

### 15. What are the claim frequency limitations?

claims / policies ignores exposure (policies in force for different lengths of time) and lapsed policies. A production metric would use earned exposure years.

### 16. What breaks if source data is huge?

Everything is loaded in memory (100 MB guard). I would switch to chunked/partitioned processing, a columnar engine and incremental loads keyed on `updated_at`.
