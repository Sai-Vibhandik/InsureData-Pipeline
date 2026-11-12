# Scheduling and Scaling Notes (design only)

The core pipeline needs no scheduler: `python run.py`.

## Option 1 - cron (Linux/macOS), daily at 02:00
```
0 2 * * * cd /path/to/project_3_insuredatapipeline && .venv/bin/python run.py >> logs/cron.log 2>&1
```
Windows: Task Scheduler -> action `...\.venv\Scripts\python.exe` with argument `run.py` and "Start in" set to the project folder.

## Option 2 - Airflow sketch (**not part of this project; untested**)
```python
from datetime import datetime
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG("insuredata_daily", start_date=datetime(2025, 1, 1), schedule="@daily", catchup=False) as dag:
    BashOperator(task_id="run_pipeline",
                 bash_command="cd /opt/insuredata && python run.py --parallel")
```
To use stages as separate tasks, split `ingest`, `validate`, `transform`, `load` in `pipeline.py` into callables that exchange data through the staging zone.

## Scaling path
1. Partition curated Parquet by `claim_month`. 2. Replace CSV landing with object storage. 3. Move heavy joins to SQL/Spark. 4. Load curated tables into a warehouse with FK constraints. 5. Track data-quality metrics over time and alert on thresholds. These are suggestions; none are implemented.
