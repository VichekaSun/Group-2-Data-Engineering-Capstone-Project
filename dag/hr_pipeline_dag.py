"""
HR pipeline DAG - extract and clean step (Member A).

ingest_to_raw  ->  clean_employees   \
                   clean_attendance   >  quality_checks  ->  (load is added later)
                   clean_performance /

The cleaning code lives in src/extract_clean.py and the checks in
src/quality_checks.py. This file only calls them.
"""
import sys
from datetime import datetime
from pathlib import Path

from airflow import DAG

try:  # Airflow 3
    from airflow.providers.standard.operators.python import PythonOperator
except ImportError:  # Airflow 2
    from airflow.operators.python import PythonOperator

# This file lives in dag/, so the project folder is one level up.
#   Locally:    <repo folder>/
#   In Docker:  /opt/airflow/   (./dag, ./data and ./src are mounted there)
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

import extract_clean  # noqa: E402  (needs the sys.path line above)
import quality_checks  # noqa: E402


def ingest(run_date):
    extract_clean.ingest_to_raw(run_date)


def clean(dataset, run_date):
    return extract_clean.run_clean(dataset, run_date)


def check_quality():
    """Run the quality checks. Any FAIL makes the task fail (a red box in Airflow)."""
    results = quality_checks.run_quality_checks()
    failed = [r for r in results if r["status"] == "FAIL"]
    if failed:
        names = "; ".join(f"{r['dataset']}: {r['rule']}" for r in failed)
        raise ValueError(f"{len(failed)} quality check(s) failed: {names}")
    return {s: sum(r["status"] == s for r in results) for s in ("PASS", "WARN", "FAIL")}


with DAG(
    dag_id="hr_pipeline_extract_clean",
    description="Copy source files into the data lake, then clean each dataset",
    start_date=datetime(2026, 11, 1),
    schedule=None,  # run it by hand from the Airflow page for now
    catchup=False,
    tags=["hr", "member-a"],
) as dag:

    ingest_to_raw = PythonOperator(
        task_id="ingest_to_raw",
        python_callable=ingest,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    clean_tasks = [
        PythonOperator(
            task_id=f"clean_{dataset}",
            python_callable=clean,
            op_kwargs={"dataset": dataset, "run_date": "{{ ds }}"},
        )
        for dataset in ("employees", "attendance", "performance")
    ]

    quality_task = PythonOperator(
        task_id="quality_checks",
        python_callable=check_quality,
    )

    ingest_to_raw >> clean_tasks >> quality_task