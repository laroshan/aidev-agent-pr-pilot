"""Run the whole pilot in order: download, schema, sample, analysis, figure.

Usage:
    python scripts/run_all.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = ["01_download_data.py", "02_inspect_schema.py", "03_build_sample.py",
         "04_analyze.py", "05_make_figure.py", "06_concept_figures.py"]

for step in STEPS:
    print("\n=== %s ===" % step, flush=True)
    subprocess.run([sys.executable, os.path.join(HERE, step)], check=True)
