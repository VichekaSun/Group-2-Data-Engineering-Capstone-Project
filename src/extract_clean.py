"""
Extract and clean step for the HR pipeline (Member A).

Runs locally and inside Airflow: every path is built from this file's location,
so nothing is hard-coded to one computer.
"""
import json
import shutil
from datetime import date
from pathlib import Path

import pandas as pd

# This file lives in src/, so the project folder is one level up.
#   Locally:    <repo folder>/
#   In Docker:  /opt/airflow/   (see the volume mounts in docker-compose.yml)
BASE_DIR = Path(__file__).resolve().parent.parent

SOURCE_DIR = BASE_DIR / "data" / "source"
RAW_DIR = BASE_DIR / "data" / "raw"
REFERENCE_DIR = BASE_DIR / "data" / "reference"
CLEAN_DIR = BASE_DIR / "data" / "clean"
REJECTS_DIR = BASE_DIR / "data" / "rejects"
LOGS_DIR = BASE_DIR / "data" / "logs"

# dataset name -> file name in data/source/
DATASETS = {
    "employees": "employees.xlsx",
    "attendance": "attendance.csv",
    "performance": "performance.csv",
}

# Read everything as TEXT so nothing is converted or hidden. Only truly empty
# cells count as missing, so a value like "N/A" stays visible as text.
READ_OPTIONS = dict(dtype=str, keep_default_na=False, na_values=[""])


# ---------------------------------------------------------------- ingest
def ingest_to_raw(run_date=None):
    """Copy each source file into data/raw/<dataset>/<run_date>/ without changing it.

    A file that is already in the data lake is never overwritten,
    so running this twice with the same date is safe.
    """
    run_date = run_date or date.today().isoformat()
    copied = []
    for dataset, filename in DATASETS.items():
        src = SOURCE_DIR / filename
        dest_dir = RAW_DIR / dataset / run_date
        dest = dest_dir / filename

        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {src}")
        if dest.exists():
            print(f"[skip]   already in the data lake: {dest.relative_to(BASE_DIR)}")
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"[ingest] {src.relative_to(BASE_DIR)} -> {dest.relative_to(BASE_DIR)}")
        copied.append(dest)
    return copied


# ------------------------------------------------------------------ read
def read_raw(dataset, run_date=None):
    """Read one dataset from the data lake (never from data/source/)."""
    run_date = run_date or date.today().isoformat()
    path = RAW_DIR / dataset / run_date / DATASETS[dataset]
    if not path.exists():
        raise FileNotFoundError(f"Raw file not found: {path}")
    if path.suffix == ".xlsx":
        return pd.read_excel(path, **READ_OPTIONS)
    return pd.read_csv(path, **READ_OPTIONS)


# ------------------------------------------------------------ reference
def read_departments():
    """Official department list (columns: department, division)."""
    return pd.read_csv(REFERENCE_DIR / "departments.csv", **READ_OPTIONS)


# Spelling variants found while profiling -> official department name.
# Keys are lowercase, without dots and extra spaces.
DEPARTMENT_ALIASES = {
    "hr": "Human Resources",
    "human resource": "Human Resources",
    "finance dept": "Finance",
    "it": "IT",
    "information technology": "IT",
    "mktg": "Marketing",
    "ops": "Operations",
    "cust service": "Customer Service",
    "cs": "Customer Service",
}

# Job titles that only appear in a damaged spelling in the file, so the correct
# spelling cannot be learned from the data. Found while profiling.
JOB_TITLE_ALIASES = {
    "hr manager": "HR Manager",
}

# Column order of the clean employees file (matches dim_employee in Snowflake)
EMPLOYEE_COLUMNS = [
    "employee_id", "department", "division", "job_title",
    "hire_date", "employment_status", "salary_band",
]

# Column names used by the attendance and performance rules.
# If your file uses a different name, change it here only.
ATT_STATUS = "status"
PERF_SCORE = "score"
PERF_STATUS = "reviewer_status"

# Attendance status typos -> official value (keys are lowercase)
STATUS_MAP = {
    "present": "Present", "prsent": "Present", "pressent": "Present",
    "absent": "Absent",
    "late": "Late", "lte": "Late",
    "leave": "Leave",
}

# Performance review status spellings -> official value (keys are lowercase)
REVIEW_STATUS_MAP = {
    "approved": "Approved",
    "draft": "Draft",
    "pending": "Pending",
}


# ------------------------------------------------------------ shared helpers
def reject_rows(df, mask, reason, rejects):
    """Move the rows selected by mask into the rejects list.

    Returns the remaining rows and the number of rejected rows.
    """
    rejected = df[mask].copy()
    rejected["reject_reason"] = reason
    rejects.append(rejected)
    return df[~mask].copy(), len(rejected)


def parse_dates(series):
    """Read dates written as YYYY-MM-DD or dd/mm/yyyy.

    Returns the parsed dates (empty where a date cannot be read) and how many
    dates used the dd/mm/yyyy format. We assume day first, because profiling
    showed days above 12 (for example 17/02/2018), so it cannot be month first.
    """
    iso = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    dmy = pd.to_datetime(series, format="%d/%m/%Y", errors="coerce")
    return iso.fillna(dmy), int((iso.isna() & dmy.notna()).sum())


def parse_times(series):
    """Read times written as HH:MM or HH:MM:SS (empty where unreadable)."""
    short = pd.to_datetime(series, format="%H:%M", errors="coerce")
    full = pd.to_datetime(series, format="%H:%M:%S", errors="coerce")
    return short.fillna(full)


def combine_rejects(rejects):
    """Join the rejected rows of every rule (an empty table if nothing was rejected)."""
    if not rejects:
        return pd.DataFrame()
    return pd.concat(rejects, ignore_index=True)


# ------------------------------------------------------------- employees
def clean_employees(df):
    """Apply the employees cleaning rules, one rule at a time.

    Returns the cleaned table, the rejected rows (with a reject_reason column),
    and a log of how many rows each rule changed.
    """
    log = {"rows_in": len(df)}
    rejects = []

    # Rule 1: identical duplicate rows -> drop one copy
    before = len(df)
    df = df.drop_duplicates()
    log["identical_duplicates_dropped"] = before - len(df)

    # Rule 2: same employee_id but different values -> keep the first row,
    # reject the later ones (they go to data/rejects/ with a reason)
    df, log["conflicting_id_rows_rejected"] = reject_rows(
        df, df.duplicated("employee_id", keep="first"),
        "duplicate employee_id, conflicting values", rejects)

    # Rule 3: missing department or job title -> fill with "Unknown"
    # (the employee stays in the data, and the gap stays visible)
    for col in ["department", "job_title"]:
        log[f"missing_{col}_filled"] = int(df[col].isna().sum())
        df[col] = df[col].fillna("Unknown")

    # Rule 4: department spelling -> official name from departments.csv.
    # A department that cannot be matched is rejected (quality rule 6).
    official = read_departments()
    lookup = {name.lower(): name for name in official["department"]}
    lookup.update(DEPARTMENT_ALIASES)
    key = (df["department"].str.lower()
           .str.replace(".", "", regex=False)
           .str.replace(r"\s+", " ", regex=True)
           .str.strip())
    fixed = key.map(lookup)
    log["department_labels_fixed"] = int((fixed.notna() & (fixed != df["department"])).sum())
    unmatched = fixed.isna()
    df, log["unmatched_department_rows_rejected"] = reject_rows(
        df, unmatched, "department not in the official list", rejects)
    df["department"] = fixed[~unmatched]

    # Rule 5: job title casing -> one spelling per title.
    # The correct spelling is the one that is NOT all lowercase and NOT all
    # UPPERCASE (for example "HR Manager", not "hr manager" or "HR MANAGER").
    title = df["job_title"]
    title_key = title.str.lower().str.strip()
    mixed_case = (title != title.str.lower()) & (title != title.str.upper())
    best_spelling = title[mixed_case].groupby(title_key[mixed_case]).agg(
        lambda s: s.value_counts().idxmax())
    standard_title = (title_key.map(best_spelling)
                      .fillna(title_key.map(JOB_TITLE_ALIASES))
                      .fillna(title))
    log["job_title_casing_fixed"] = int((standard_title != title).sum())
    df["job_title"] = standard_title
    still_wrong = ((standard_title == standard_title.str.lower())
                   | (standard_title == standard_title.str.upper()))
    log["job_title_casing_unresolved"] = int(still_wrong.sum())

    # Rule 6: hire date -> YYYY-MM-DD. A date in the future (or one that cannot
    # be read) is blanked, but the employee is kept: their attendance shows they
    # work here, so rejecting them would also remove their attendance rows.
    parsed, log["hire_date_format_fixed"] = parse_dates(df["hire_date"])
    unreadable = parsed.isna() & df["hire_date"].notna()
    future = parsed > pd.Timestamp.today().normalize()
    log["unreadable_hire_date_blanked"] = int(unreadable.sum())
    log["future_hire_date_blanked"] = int(future.sum())
    df["hire_date"] = parsed.mask(future).dt.strftime("%Y-%m-%d")

    # Last step: add the division for each department (dim_employee needs it)
    # and put the columns in the same order as the Snowflake table.
    df = df.merge(official[["department", "division"]], on="department", how="left")
    df = df[EMPLOYEE_COLUMNS]

    log["rows_out"] = len(df)
    return df, combine_rejects(rejects), log


# ------------------------------------------------------------ attendance
def clean_attendance(df):
    """Apply the attendance cleaning rules, one rule at a time."""
    log = {"rows_in": len(df)}
    rejects = []

    # Rule 1: identical duplicate rows -> drop one copy
    before = len(df)
    df = df.drop_duplicates()
    log["identical_duplicates_dropped"] = before - len(df)

    # Rule 2: attendance date -> YYYY-MM-DD. A date that cannot exist
    # (for example 2026-13-45) is rejected, because we cannot know the real date.
    parsed, log["date_format_fixed"] = parse_dates(df["attendance_date"])
    df, log["impossible_date_rows_rejected"] = reject_rows(
        df, parsed.isna(), "attendance_date is not a valid date", rejects)
    df["attendance_date"] = parsed[df.index].dt.strftime("%Y-%m-%d")

    # Rule 3: status typos -> Present / Absent / Late. Anything else
    # (for example "N/A") cannot be fixed, so the row is rejected.
    fixed = df[ATT_STATUS].str.strip().str.lower().map(STATUS_MAP)
    log["status_labels_fixed"] = int((fixed.notna() & (fixed != df[ATT_STATUS])).sum())
    invalid = fixed.isna()
    df, log["invalid_status_rows_rejected"] = reject_rows(
        df, invalid, "invalid status", rejects)
    df[ATT_STATUS] = fixed[~invalid]

    # Rule 4: hours_worked must be between 0 and 24 (reject, do not recalculate)
    hours = pd.to_numeric(df["hours_worked"], errors="coerce")
    df, log["hours_outside_0_24_rejected"] = reject_rows(
        df, (hours < 0) | (hours > 24), "hours outside 0-24", rejects)

    # Rule 5: check_out earlier than check_in -> reject (do not swap the times)
    t_in = parse_times(df["check_in"])
    t_out = parse_times(df["check_out"])
    df, log["check_out_before_check_in_rejected"] = reject_rows(
        df, t_out < t_in, "check_out before check_in", rejects)

    # Rule 6: missing check_in on a worked day -> keep the row, only count it
    worked = df[ATT_STATUS].isin(["Present", "Late"])
    log["missing_check_in_kept"] = int((df["check_in"].isna() & worked).sum())

    log["rows_out"] = len(df)
    return df, combine_rejects(rejects), log


# ----------------------------------------------------------- performance
def clean_performance(df):
    """Apply the performance cleaning rules."""
    log = {"rows_in": len(df)}
    rejects = []

    # Rule 1: a review without a score is rejected
    df, log["missing_score_rows_rejected"] = reject_rows(
        df, df[PERF_SCORE].isna(), "missing score", rejects)

    # Rule 2: status spelling -> Approved / Draft / Pending (for example
    # "approved", "APPROVED" and "Approved " all become "Approved"), so the
    # dashboard filter on Approved does not miss any rows.
    fixed = df[PERF_STATUS].str.strip().str.lower().map(REVIEW_STATUS_MAP)
    log["status_labels_fixed"] = int((fixed.notna() & (fixed != df[PERF_STATUS])).sum())
    unknown = fixed.isna()
    df, log["invalid_status_rows_rejected"] = reject_rows(
        df, unknown, "invalid reviewer_status", rejects)
    df[PERF_STATUS] = fixed[~unknown]

    # Rule 3: keep Approved, Draft and Pending. The dashboard filters on status
    # later, so here we only count how many rows each status has.
    log["rows_by_status"] = {k: int(v) for k, v in df[PERF_STATUS].value_counts().items()}

    log["rows_out"] = len(df)
    return df, combine_rejects(rejects), log


# ------------------------------------------------------------------ save
def save_outputs(name, clean_df, rejects_df, log):
    """Write the cleaned rows, the rejected rows and the cleaning log to disk.

    The files are rewritten on every run. This is safe because they are always
    rebuilt from the untouched files in data/raw/.
    """
    for folder in (CLEAN_DIR, REJECTS_DIR, LOGS_DIR):
        folder.mkdir(parents=True, exist_ok=True)

    clean_path = CLEAN_DIR / f"{name}_clean.csv"
    rejects_path = REJECTS_DIR / f"{name}_rejected.csv"
    log_path = LOGS_DIR / f"{name}_cleaning_log.json"

    clean_df.to_csv(clean_path, index=False)
    rejects_df.to_csv(rejects_path, index=False)
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")

    print(f"[saved] {clean_path.relative_to(BASE_DIR)}  ({len(clean_df)} rows)")
    print(f"[saved] {rejects_path.relative_to(BASE_DIR)}  ({len(rejects_df)} rows)")
    print(f"[saved] {log_path.relative_to(BASE_DIR)}")


# --------------------------------------------------------- airflow helpers
CLEANERS = {
    "employees": clean_employees,
    "attendance": clean_attendance,
    "performance": clean_performance,
}


def run_clean(dataset, run_date=None):
    """Read one dataset from the data lake, clean it and save the outputs.

    This is the one function an Airflow task calls per dataset.
    Returns the cleaning log (small and JSON-friendly, so Airflow can store it).
    """
    clean_df, rejects_df, log = CLEANERS[dataset](read_raw(dataset, run_date))
    save_outputs(dataset, clean_df, rejects_df, log)
    return log


if __name__ == "__main__":
    ingest_to_raw()

    employees = read_raw("employees")
    emp_clean, emp_rejects, emp_log = clean_employees(employees)
    save_outputs("employees", emp_clean, emp_rejects, emp_log)
    print("\nEmployees cleaning log:", emp_log)

    attendance = read_raw("attendance")
    att_clean, att_rejects, att_log = clean_attendance(attendance)
    save_outputs("attendance", att_clean, att_rejects, att_log)
    print("\nAttendance cleaning log:", att_log)
    print("\nAttendance rejected rows by reason:")
    print(att_rejects["reject_reason"].value_counts().to_string())

    performance = read_raw("performance")
    perf_clean, perf_rejects, perf_log = clean_performance(performance)
    save_outputs("performance", perf_clean, perf_rejects, perf_log)
    print("\nPerformance cleaning log:", perf_log)