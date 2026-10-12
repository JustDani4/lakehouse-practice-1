#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
"${PYTHON_EXEC:-python3}" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python setup.py
.venv/bin/python pipeline.py bronze
.venv/bin/python bench_codecs.py --repeats 3
.venv/bin/python verify_files.py
.venv/bin/python pipeline.py silver-gold
.venv/bin/python pipeline.py demo
.venv/bin/python run_spark.py
.venv/bin/python record_environment.py
.venv/bin/python build_report.py
