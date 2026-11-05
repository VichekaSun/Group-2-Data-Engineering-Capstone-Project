"""
Synthetic HR data generator - Group 2, Data Engineering final project (Option 2).

Creates related, fully synthetic HR files (no real employee data):
  employees.xlsx   - one row per employee, Excel format (plus injected errors)
  attendance.csv   - daily attendance per employee, with hours_worked
  performance.csv  - half-year performance reviews (score 1-5)
  departments.csv  - clean reference list: department -> division

"""
import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
N_EMPLOYEES = 200
ATT_START = date(2026, 8, 3)    # a Monday
ATT_END = date(2026, 10, 30)    # a Friday

DEPARTMENTS = {
    "Human Resources": ["HR Officer", "HR Manager", "Recruiter"],
    "Finance": ["Accountant", "Finance Analyst", "Finance Manager"],
    "IT": ["Software Engineer", "Data Analyst", "IT Support", "IT Manager"],
    "Marketing": ["Marketing Executive", "Content Creator", "Marketing Manager"],
    "Operations": ["Operations Officer", "Operations Manager", "Logistics Coordinator"],
    "Sales": ["Sales Executive", "Sales Manager", "Account Officer"],
    "Customer Service": ["Customer Service Agent", "Team Leader", "Support Specialist"],
}
DEPT_DIRTY = {
    "Human Resources": ["HR", "human resources", "Human Resource", "H.R."],
    "Finance": ["finance", "FINANCE", "Finance Dept"],
    "IT": ["I.T", "it", "Information Technology", "IT "],
    "Marketing": ["marketing", "Mktg"],
    "Operations": ["operations", "Ops"],
    "Sales": ["sales", "SALES"],
    "Customer Service": ["customer service", "Cust. Service", "CS"],
}


def pick(rng, pool, k, used):
    """Choose k distinct row indexes from pool that were not used by another error."""
    avail = [i for i in pool if i not in used]
    chosen = rng.sample(avail, k)
    used.update(chosen)
    return chosen


def dmy(iso_text):
    """2026-03-05 -> 05/03/2026 (a different date format on purpose)."""
    y, m, d = iso_text.split("-")
    return f"{d}/{m}/{y}"


def workdays(start, end):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


# ---------------------------------------------------------------- employees
def make_employees(rng, log):
    depts = list(DEPARTMENTS)
    weights = [8, 10, 25, 12, 15, 18, 12]
    span = (date(2026, 7, 31) - date(2018, 1, 1)).days
    clean = []
    for i in range(1, N_EMPLOYEES + 1):
        dept = rng.choices(depts, weights)[0]
        clean.append({
            "employee_id": f"E{i:04d}",
            "department": dept,
            "job_title": rng.choice(DEPARTMENTS[dept]),
            "hire_date": (date(2018, 1, 1) + timedelta(days=rng.randint(0, span))).isoformat(),
            "employment_status": rng.choices(["Active", "On Leave", "Resigned"], [88, 4, 8])[0],
            "salary_band": rng.choice(["B1", "B2", "B3", "B4"]),
        })

    rows = [dict(r) for r in clean]
    used = set()
    pool = list(range(len(rows)))

    for i in pick(rng, pool, 24, used):            # inconsistent department labels
        rows[i]["department"] = rng.choice(DEPT_DIRTY[clean[i]["department"]])
    for i in pick(rng, pool, 5, used):             # missing department
        rows[i]["department"] = ""
    for i in pick(rng, pool, 4, used):             # missing job title
        rows[i]["job_title"] = ""
    for i in pick(rng, pool, 8, used):             # job title casing
        rows[i]["job_title"] = rng.choice([rows[i]["job_title"].lower(), rows[i]["job_title"].upper()])
    for i in pick(rng, pool, 3, used):             # hire date in the future (invalid)
        rows[i]["hire_date"] = (date(2027, 1, 1) + timedelta(days=rng.randint(0, 300))).isoformat()
    for i in pick(rng, pool, 10, used):            # different date format
        rows[i]["hire_date"] = dmy(rows[i]["hire_date"])

    # duplicate employee IDs: 3 exact copies + 3 conflicting copies (different job title)
    for n in range(6):
        src = dict(rows[rng.randrange(len(rows))])
        if n >= 3:
            src["job_title"] = rng.choice(DEPARTMENTS[clean[int(src["employee_id"][1:]) - 1]["department"]])
        rows.insert(rng.randint(0, len(rows)), src)

    log["employees"] = {
        "total_rows_written": len(rows),
        "inconsistent_department_labels": 24,
        "missing_department": 5,
        "missing_job_title": 4,
        "job_title_casing_issues": 8,
        "future_hire_date": 3,
        "non_iso_hire_date_format": 10,
        "duplicate_employee_id_rows": 6,
    }
    return clean, rows


# --------------------------------------------------------------- attendance
def make_attendance(rng, clean_emps, log):
    rows = []
    n = 0
    for emp in clean_emps:
        hired = date.fromisoformat(emp["hire_date"])
        for d in workdays(ATT_START, ATT_END):
            if d < hired:
                continue
            n += 1
            status = rng.choices(["Present", "Late", "Absent", "Leave"], [85, 7, 5, 3])[0]
            check_in = check_out = ""
            if status == "Present":
                check_in = f"{rng.randint(7, 7)}:{rng.randint(30, 59):02d}".zfill(5)
                check_out = f"{rng.randint(17, 17)}:{rng.randint(0, 45):02d}"
            elif status == "Late":
                check_in = f"{rng.randint(8, 9)}:{rng.randint(16, 59):02d}".zfill(5)
                check_out = f"{rng.randint(17, 18)}:{rng.randint(0, 45):02d}"
            hours = 0.0
            if check_in and check_out:
                h1, m1 = map(int, check_in.split(":"))
                h2, m2 = map(int, check_out.split(":"))
                hours = round((h2 * 60 + m2 - h1 * 60 - m1) / 60, 2)
            rows.append({
                "attendance_id": f"A{n:06d}",
                "employee_id": emp["employee_id"],
                "attendance_date": d.isoformat(),
                "status": status,
                "check_in": check_in,
                "check_out": check_out,
                "hours_worked": hours,
            })

    used = set()
    all_idx = list(range(len(rows)))
    timed = [i for i, r in enumerate(rows) if r["status"] in ("Present", "Late")]

    for i in pick(rng, all_idx, 40, used):         # misspelled / invalid status
        rows[i]["status"] = rng.choice(["Prsent", "present", "ABSENT", "N/A", "Pressent", "Lte"])
    for i in pick(rng, all_idx, 30, used):         # orphan employee ids (not in employees)
        rows[i]["employee_id"] = f"E{rng.randint(9001, 9099)}"
    for i in pick(rng, timed, 25, used):           # check_out earlier than check_in
        rows[i]["check_in"], rows[i]["check_out"] = rows[i]["check_out"], rows[i]["check_in"]
    for i in pick(rng, timed, 30, used):           # missing check_in on a worked day
        rows[i]["check_in"] = ""
    for i in pick(rng, all_idx, 10, used):         # impossible dates
        rows[i]["attendance_date"] = rng.choice(["2026-13-45", "31/02/2026", "2026-00-10", "not_a_date"])
    for i in pick(rng, all_idx, 50, used):         # different date format
        rows[i]["attendance_date"] = dmy(rows[i]["attendance_date"])
    for i in pick(rng, all_idx, 12, used):         # hours_worked outside 0-24
        rows[i]["hours_worked"] = rng.choice([30, 25, 48, -3, 99])

    for _ in range(40):                            # exact duplicate rows
        src = dict(rows[rng.randrange(len(rows))])
        rows.insert(rng.randint(0, len(rows)), src)

    log["attendance"] = {
        "total_rows_written": len(rows),
        "invalid_status_values": 40,
        "orphan_employee_ids": 30,
        "check_out_before_check_in": 25,
        "missing_check_in_on_worked_day": 30,
        "impossible_dates": 10,
        "non_iso_date_format": 50,
        "hours_worked_out_of_range": 12,
        "exact_duplicate_rows": 40,
    }
    return rows


# -------------------------------------------------------------- performance
def make_performance(rng, clean_emps, log):
    rows = []
    for emp in clean_emps:
        for period in ("2025-H2", "2026-H1"):
            base = date(2025, 12, 1) if period == "2025-H2" else date(2026, 6, 1)
            rows.append({
                "employee_id": emp["employee_id"],
                "review_period": period,
                "review_date": (base + timedelta(days=rng.randint(0, 28))).isoformat(),
                "score": rng.choices([1, 2, 3, 4, 5], [3, 10, 40, 35, 12])[0],
                "reviewer_status": rng.choices(["Approved", "Draft", "Pending"], [80, 12, 8])[0],
            })

    used = set()
    idx = list(range(len(rows)))
    for i in pick(rng, idx, 12, used):             # score out of the 1-5 range
        rows[i]["score"] = rng.choice([0, 6, 7, -1, 10])
    for i in pick(rng, idx, 8, used):              # missing score
        rows[i]["score"] = ""
    for i in pick(rng, idx, 8, used):              # orphan employee ids
        rows[i]["employee_id"] = f"E{rng.randint(9001, 9099)}"
    for i in pick(rng, idx, 15, used):             # inconsistent status casing
        rows[i]["reviewer_status"] = rng.choice(["approved", "APPROVED", "Approved "])
    for _ in range(10):                            # exact duplicates
        src = dict(rows[rng.randrange(len(rows))])
        rows.insert(rng.randint(0, len(rows)), src)

    log["performance"] = {
        "total_rows_written": len(rows),
        "score_out_of_range": 12,
        "missing_score": 8,
        "orphan_employee_ids": 8,
        "inconsistent_status_casing": 15,
        "exact_duplicate_rows": 10,
    }
    return rows


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


DIVISIONS = {
    "Human Resources": "Corporate Services",
    "Finance": "Corporate Services",
    "IT": "Technology",
    "Marketing": "Commercial",
    "Sales": "Commercial",
    "Operations": "Operations",
    "Customer Service": "Operations",
}


def write_employees(out, rows):
    """Excel file (roadmap says CSV + Excel). Falls back to CSV without openpyxl."""
    try:
        from openpyxl import Workbook
    except ImportError:
        write_csv(out / "employees.csv", rows)
        return "employees.csv (openpyxl missing -> CSV written; run: pip install openpyxl)"
    wb = Workbook()
    ws = wb.active
    ws.title = "employees"
    cols = list(rows[0].keys())
    ws.append(cols)
    for r in rows:
        ws.append([r[c] for c in cols])
    wb.save(out / "employees.xlsx")
    return "employees.xlsx"


def write_departments(out):
    """Clean reference list used by quality rule 6 and by DimDepartment (division)."""
    write_csv(out / "departments.csv",
              [{"department": d, "division": DIVISIONS[d]} for d in DEPARTMENTS])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/source", help="output folder")
    args = ap.parse_args()

    rng = random.Random(SEED)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = {"seed": SEED, "note": "All data is synthetic. Counts are errors deliberately injected."}

    clean_emps, emp_rows = make_employees(rng, log)
    att_rows = make_attendance(rng, clean_emps, log)
    perf_rows = make_performance(rng, clean_emps, log)

    emp_file = write_employees(out, emp_rows)
    write_departments(out)
    write_csv(out / "attendance.csv", att_rows)
    write_csv(out / "performance.csv", perf_rows)
    with open(out / "injected_errors.json", "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

    print(f"Done. Files written to: {out.resolve()}")
    print(f"  {emp_file}: {log['employees']['total_rows_written']} rows")
    print(f"  attendance.csv: {log['attendance']['total_rows_written']} rows")
    print(f"  performance.csv: {log['performance']['total_rows_written']} rows")
    print("  departments.csv: clean reference list (department, division)")
    print("  injected_errors.json: error counts for your slides")


if __name__ == "__main__":
    main()