"""
Quality checks for the HR pipeline (Chea Dalin).

Reads the clean files made by extract_clean.py and checks them against the
data quality rules. Prints a PASS / FAIL / WARN line for each rule and saves
the same report to data/logs/quality_report.json.

  FAIL = a real problem; the script stops with an error (so Airflow can show it)
  WARN = worth a look, but it does not stop the pipeline

Run it after extract_clean.py:  python src/quality_checks.py
"""
import json
import sys
from datetime import datetime

import pandas as pd

from extract_clean import (CLEAN_DIR, LOGS_DIR, READ_OPTIONS, parse_times,
                           read_departments)

VALID_ATTENDANCE_STATUS = {"Present", "Absent", "Late", "Leave"}
VALID_REVIEW_STATUS = {"Approved", "Draft", "Pending"}


def read_clean(name):
    """Read one clean file as text (same way extract_clean.py reads files)."""
    return pd.read_csv(CLEAN_DIR / f"{name}_clean.csv", **READ_OPTIONS)


def add(results, dataset, rule, failed, total, level="error"):
    """Save the result of one rule. `failed` is the number of rows that break it."""
    failed = int(failed)
    status = "PASS" if failed == 0 else ("FAIL" if level == "error" else "WARN")
    results.append({
        "dataset": dataset, "rule": rule, "rows_checked": int(total),
        "rows_failed": failed, "status": status,
    })


def bad_dates(series):
    """Rows where a date is filled in but is not a real YYYY-MM-DD date."""
    parsed = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    return parsed.isna() & series.notna(), parsed


# ------------------------------------------------------------- employees
def check_employees(emp, results):
    n = len(emp)
    official = set(read_departments()["department"])

    add(results, "employees", "employee_id is filled in", emp["employee_id"].isna().sum(), n)
    add(results, "employees", "employee_id is unique",
        emp["employee_id"].duplicated().sum(), n)
    add(results, "employees", "department is in the official list",
        (~emp["department"].isin(official)).sum(), n)
    add(results, "employees", "division is filled in", emp["division"].isna().sum(), n)

    invalid, parsed = bad_dates(emp["hire_date"])
    add(results, "employees", "hire_date is a valid YYYY-MM-DD date (blank is allowed)",
        invalid.sum(), n)
    add(results, "employees", "hire_date is not in the future",
        (parsed > pd.Timestamp.today().normalize()).sum(), n)


# ------------------------------------------------------------ attendance
def check_attendance(att, emp, results):
    n = len(att)

    add(results, "attendance", "attendance_id is unique",
        att["attendance_id"].duplicated().sum(), n)
    add(results, "attendance", "employee_id exists in employees",
        (~att["employee_id"].isin(emp["employee_id"])).sum(), n)

    invalid, _ = bad_dates(att["attendance_date"])
    add(results, "attendance", "attendance_date is a valid YYYY-MM-DD date",
        (invalid | att["attendance_date"].isna()).sum(), n)
    add(results, "attendance", "status is Present, Absent, Late or Leave",
        (~att["status"].isin(VALID_ATTENDANCE_STATUS)).sum(), n)

    hours = pd.to_numeric(att["hours_worked"], errors="coerce")
    wrong_hours = att["hours_worked"].notna() & (hours.isna() | (hours < 0) | (hours > 24))
    add(results, "attendance", "hours_worked is a number between 0 and 24",
        wrong_hours.sum(), n)

    t_in = parse_times(att["check_in"])
    t_out = parse_times(att["check_out"])
    add(results, "attendance", "check_out is not before check_in",
        (t_out < t_in).sum(), n)

    # Warnings: not always wrong, but worth a look
    worked = att["status"].isin(["Present", "Late"])
    add(results, "attendance", "Present/Late rows have a check_in",
        (att["check_in"].isna() & worked).sum(), n, level="warn")
    add(results, "attendance", "one row per employee per day",
        att.duplicated(["employee_id", "attendance_date"]).sum(), n, level="warn")


# ----------------------------------------------------------- performance
def check_performance(perf, emp, results):
    n = len(perf)

    add(results, "performance", "employee_id exists in employees",
        (~perf["employee_id"].isin(emp["employee_id"])).sum(), n)
    add(results, "performance", "score is filled in", perf["score"].isna().sum(), n)
    add(results, "performance", "reviewer_status is Approved, Draft or Pending",
        (~perf["reviewer_status"].isin(VALID_REVIEW_STATUS)).sum(), n)

    invalid, _ = bad_dates(perf["review_date"])
    add(results, "performance", "review_date is a valid YYYY-MM-DD date",
        (invalid | perf["review_date"].isna()).sum(), n)

    # Warnings
    score = pd.to_numeric(perf["score"], errors="coerce")
    add(results, "performance", "score is a number between 1 and 5",
        (perf["score"].notna() & (score.isna() | (score < 1) | (score > 5))).sum(),
        n, level="warn")
    add(results, "performance", "one review per employee per review_period",
        perf.duplicated(["employee_id", "review_period"]).sum(), n, level="warn")


# ------------------------------------------------------------------ main
def run_quality_checks():
    """Run every check, print and save the report, and return the results."""
    emp = read_clean("employees")
    att = read_clean("attendance")
    perf = read_clean("performance")

    results = []
    check_employees(emp, results)
    check_attendance(att, emp, results)
    check_performance(perf, emp, results)

    for r in results:
        print(f"[{r['status']}] {r['dataset']:<11} {r['rule']}  "
              f"({r['rows_failed']} of {r['rows_checked']} rows)")

    counts = {s: sum(r["status"] == s for r in results) for s in ("PASS", "WARN", "FAIL")}
    print(f"\nSummary: {counts['PASS']} passed, {counts['WARN']} warnings, "
          f"{counts['FAIL']} failed")

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    report = {"run_at": datetime.now().isoformat(timespec="seconds"),
              "summary": counts, "checks": results}
    (LOGS_DIR / "quality_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print("[saved] data/logs/quality_report.json")
    return results


if __name__ == "__main__":
    outcome = run_quality_checks()
    if any(r["status"] == "FAIL" for r in outcome):
        sys.exit(1)