"""
HR pipeline DAG - extract and clean step (Member A).

ingest_to_raw  ->  clean_employees   \
                   clean_attendance   >  (quality checks and load are added later)
                   clean_performance /

The cleaning code lives in src/extract_clean.py. This file only calls it.
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


def ingest(run_date):
    extract_clean.ingest_to_raw(run_date)


def clean(dataset, run_date):
    return extract_clean.run_clean(dataset, run_date)


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

    ingest_to_raw >> clean_tasks