# Technical Decisions - InsureData Pipeline

| Decision | Why | Alternatives | Trade-off |
|---|---|---|---|
| Pandas + NumPy | Course stack; right size for thousands of rows | Polars, DuckDB, Spark | In-memory only |
| Stage functions in one orchestrator | Clear contracts, easy timing/logging | Class hierarchy, framework | Less pluggable |
| Validate in dependency order | Correct referential integrity | Validate independently then join | Cascading rejects (explained in output) |
| Reasons as semicolon-joined text | Simple to read in CSV and filter | One row per reason | Exploding needed for counts (done in report) |
| Cap incurred at coverage limit | Realistic payable ceiling, keeps outliers visible | Drop or ignore outliers | Cap is an assumption to confirm with business |
| `as_of_date` in config | Deterministic age checks | `date.today()` | Must be updated for new data |
| Fixed output names + atomic replace | Idempotent reruns | Timestamped folders | History not kept (run log only) |
| Optional `--parallel` | Demonstrates bounded threads | Always serial | Little benefit at this size (documented) |
| Streamlit reads output files | UI independent of pipeline internals | UI calls pipeline functions directly | Needs a run first (button provided) |

## Known limitations
Metrics ignore exposure; synthetic distributions; Parquet and UI unverified in the build environment; first-wins duplicate rule for policies/claims is a documented simplification.
