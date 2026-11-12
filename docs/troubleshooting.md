# Troubleshooting

## Installation
- **`python` not found (Windows):** install Python 3.11+ from python.org and tick "Add python.exe to PATH", or use `py -3.11 -m venv .venv`.
- **`pip install` fails with build errors:** upgrade pip first: `python -m pip install --upgrade pip`. Use Python 3.11-3.13; very new or very old interpreters may lack wheels for pandas/pyarrow.
- **`ModuleNotFoundError: pandas` / `streamlit`:** the virtual environment is not active (prompt should show `(.venv)`), or dependencies were installed into a different Python. Run `python -m pip install -r requirements-dev.txt` using the same `python` you run the app with.
- **PowerShell cannot run `Activate.ps1`:** `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again. Or use `cmd` and `activate.bat`.
- **PyArrow missing or fails to install:** Parquet output is skipped automatically with a log warning; CSV/JSON still work. Fix with `pip install pyarrow`, or use a supported Python version.
- **pandas/PyArrow version conflicts:** create a fresh venv and install only from `requirements.txt`; the code was verified on pandas 3.0.2 (older pandas 2.x is untested).

## Running
- **`ModuleNotFoundError: <package>` when running a script:** run commands from the project folder (the one containing `run.py`). `run.py`/`app.py` add `src/` to the path themselves; for tests use `python -m pytest` from the project folder.
- **File path errors / `FileNotFoundError`:** all paths are relative to the project folder via `pathlib`. Do not move `data/` or `config/`. Regenerate samples with `python scripts/generate_sample_data.py`.
- **Port already in use:** `streamlit run app.py --server.port 8502`. Stop old instances with `Ctrl+C`; on Windows check `netstat -ano | findstr 8501`.
- **Browser does not open:** open the URL printed in the terminal (usually http://localhost:8501) manually.
- **Streamlit asks for an email on first launch:** press Enter to skip.
- **Blank page / old data after changing code:** press `R` in the browser or use the menu -> "Rerun"; use "Clear cache" if results look stale.
- **Corporate proxy / no internet:** installing packages needs internet once; running the demo does not.

## Data and CSV problems
- **`UnicodeDecodeError` / odd characters:** save CSV as UTF-8. Where supported the loader retries as latin-1 and logs a warning.
- **Missing columns error:** the message lists the required columns; see `docs/data_dictionary.md`.
- **Dates read incorrectly:** supported formats are listed in the config (`date_formats`); slash dates are read as MM/DD/YYYY.
- **Large files:** files are loaded fully into memory and a size limit is enforced (see config).

## InsureData-specific
- **"Required input file missing":** the five expected files are listed in `config/pipeline.json` (`claims_files`) plus `customers.csv` and `policies.json` in `data/raw`. Regenerate with `python scripts/generate_sample_data.py`.
- **Dashboard says "No curated data yet":** click *Run pipeline now* or run `python run.py` from the project folder.
- **Excel input:** needs `openpyxl` (`pip install openpyxl`). Parquet input/output needs `pyarrow`.
- **Different outputs after editing config:** the run id changes because it hashes the config; that is expected.
- **Why are some policies/claims rejected after I fixed one rule?** Rejections cascade: a policy rejected because of its customer causes its claims to fail `orphan_policy_ref`.
