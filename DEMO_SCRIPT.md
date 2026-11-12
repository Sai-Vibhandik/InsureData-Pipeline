# Five-Minute Demo Script - InsureData Pipeline

**Before:** activate the venv; run `python run.py --parallel` once; start `streamlit run app.py`.

| Time | Do | Say |
|---|---|---|
| 0:00 | Terminal: `python run.py --parallel` | "Four stages: ingestion, validation, transformation, loading. Synthetic data from three systems, with problems injected on purpose." |
| 0:45 | Point at per-entity counts | "Input equals curated plus rejected for every entity. Nothing disappears silently." |
| 1:15 | Dashboard -> **Portfolio Overview** | "Loss ratio is incurred over written premium, capped at coverage limits. Definitions are in the data dictionary; I don't claim any real benchmarks." |
| 2:00 | **Claims Analytics**: monthly trend, pivot, crosstab; filter Policy type = Auto | "Pivot of incurred by type and region; crosstab of status counts. Filters apply across pages." |
| 2:45 | **Data Quality** page | "45 claims reference missing policies; some because their policy was rejected first. That's the dependency order at work." |
| 3:30 | Inspect `claims_rejected` | "Each rejected record carries all failed rules and its source file and row." |
| 4:00 | Terminal: run `python run.py` again | "Same input hash, `repeat_of_same_input: True`, identical files: reruns don't multiply records." |
| 4:30 | **Failure scenario:** rename `data/raw/claims_2024.csv` temporarily (or delete a column) and rerun | "Clear error naming the missing file/column and exit code 2; no partial outputs because writes are atomic." Restore the file. |
| 4:50 | Close | "Next: incremental loads, exposure-based metrics, orchestration. The zones map directly to a cloud lakehouse." |
