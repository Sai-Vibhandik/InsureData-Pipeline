"""Regenerate sample data, run the pipeline twice (shows idempotent reruns):  python scripts/run_demo.py"""
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(ROOT / "scripts/generate_sample_data.py")], check=True, cwd=ROOT)
for _ in range(2):
    subprocess.run([sys.executable, str(ROOT / "run.py"), "--parallel"], check=True, cwd=ROOT)
