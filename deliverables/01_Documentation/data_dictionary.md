# Data Dictionary (draft)

Status: draft, 9 Nov 2026. Clean-layer facts are taken from `src/extract_clean.py` and the run on 8–9 Nov 2026. Warehouse types are taken from `sql/create_star_schema.sql`, which uses Snowflake syntax; they may change once the warehouse engine is chosen.

All data is synthetic. No dataset holds names, phones, emails or addresses.

## 1. Clean layer (`data/clean/`)

All files are CSV with UTF-8 text. Dates use `YYYY-MM-DD`, and times use `HH:MM`.

### employees_clean.csv (200 rows, one row per employee)

| Column | Type | Nulls | Allowed values / rule | Cleaning applied |
| --- | --- | --- | --- | --- |
| `employee_id` | text, `E` + 4 digits | No | Unique | Exact duplicates are dropped. For a repeated ID with conflicting values, the first row is kept and the rest are rejected. |
| `department` | text | No | Must be in `data/reference/departments.csv` | Spelling variants are mapped to the official name (for example `HR` → Human Resources). A missing value becomes `Unknown`, and an unmatched value is rejected. |
| `division` | text | No | Corporate Services, Technology, Commercial, Operations, Unknown | Looked up from `department` |
| `job_title` | text | No | 23 titles | Casing is standardized. A missing value becomes `Unknown`. |
| `hire_date` | date | Yes (3) | Not in the future | `dd/mm/yyyy` is converted. A future or unreadable date is blanked, and the row is kept. |
| `employment_status` | text | No | Active, On Leave, Resigned | None |
| `salary_band` | text | No | B1, B2, B3, B4 | None |

### attendance_clean.csv (12,917 rows, one row per attendance record)

Date range: 2026-08-03 to 2026-10-30, weekdays only.

| Column | Type | Nulls | Allowed values / rule | Cleaning applied |
| --- | --- | --- | --- | --- |
| `attendance_id` | text, `A` + 6 digits | No | Unique | Exact duplicates are dropped. |
| `employee_id` | text | No | Must exist in employees | A row for an unknown ID is rejected. |
| `attendance_date` | date | No | A valid date | `dd/mm/yyyy` is converted. An impossible date is rejected. |
| `status` | text | No | Present, Late, Absent, Leave | Typos are fixed (`prsent`, `lte`). Any other value is rejected. |
| `check_in` | time | Yes | None | A missing value on a Present or Late row is kept and counted as a WARN. |
| `check_out` | time | Yes | Not earlier than `check_in` | A row where `check_out` is earlier is rejected. |
| `hours_worked` | decimal | No | 0–24 | A value outside the range is rejected. |

### performance_clean.csv (372 rows, one row per employee per review period)

| Column | Type | Nulls | Allowed values / rule | Cleaning applied |
| --- | --- | --- | --- | --- |
| `employee_id` | text | No | Must exist in employees | A row for an unknown ID is rejected. |
| `review_period` | text | No | 2025-H2, 2026-H1 | None |
| `review_date` | date | No | A valid date | None |
| `score` | integer | No | 1–5 | A missing or out-of-range score is rejected. |
| `reviewer_status` | text | No | Approved, Draft, Pending | Casing and spaces are fixed. Any other value is rejected. |

The dashboard reads only `Approved` rows. Draft and Pending rows are kept.

## 2. Reference and side outputs

| File | Content |
| --- | --- |
| `data/reference/departments.csv` | `department`, `division`: the 7 official departments plus `Unknown` |
| `data/rejects/<dataset>_rejected.csv` | The original columns plus `reject_reason` |
| `data/logs/<dataset>_cleaning_log.json` | Row counts per cleaning rule |
| `data/logs/quality_report.json` | PASS, WARN or FAIL for each quality rule |
| `data/source/injected_errors.json` | The errors the generator injected on purpose |

## 3. Warehouse (`ANALYTICS` schema)

### dim_employee

| Column | Type | Source |
| --- | --- | --- |
| `employee_key` | INT, autoincrement, PK | Surrogate key |
| `employee_id` | VARCHAR(10), unique | `employees_clean.employee_id` |
| `department` | VARCHAR(50) | `employees_clean` |
| `division` | VARCHAR(50) | `employees_clean` |
| `job_title` | VARCHAR(60) | `employees_clean` |
| `salary_band` | VARCHAR(2) | `employees_clean` |
| `employment_status` | VARCHAR(10) | `employees_clean` |
| `hire_date` | DATE | `employees_clean` |

### dim_date

| Column | Type | Note |
| --- | --- | --- |
| `date_key` | INT, PK | `YYYYMMDD` |
| `full_date` | DATE | None |
| `day_name`, `month_name` | VARCHAR(9) | None |
| `week_of_year`, `month_number`, `quarter` | TINYINT | None |
| `half_year` | VARCHAR(7) | For example `2026-H1` |
| `year` | SMALLINT | None |
| `is_weekend` | BOOLEAN | None |

### dim_attendance_status (seeded)

| `attendance_status_key` | `status_name` | `is_worked_day` |
| --- | --- | --- |
| 1 | Present | TRUE |
| 2 | Late | TRUE |
| 3 | Absent | FALSE |
| 4 | Leave | FALSE |

### dim_review_period (seeded)

| `review_period_key` | `review_period` | `year` | `half` |
| --- | --- | --- | --- |
| 1 | 2025-H2 | 2025 | 2 |
| 2 | 2026-H1 | 2026 | 1 |

### fact_attendance (grain: one employee, one day)

| Column | Type | Source |
| --- | --- | --- |
| `attendance_id` | VARCHAR(10), PK | `attendance_clean.attendance_id` |
| `date_key` | INT, FK → dim_date | `attendance_date` |
| `employee_key` | INT, FK → dim_employee | Looked up by `employee_id` |
| `attendance_status_key` | TINYINT, FK → dim_attendance_status | `status` |
| `check_in`, `check_out` | TIME | Same column names in `attendance_clean` |
| `hours_worked` | NUMBER(4,2), not null | `hours_worked` |

### fact_performance (grain: one employee, one review period)

| Column | Type | Source |
| --- | --- | --- |
| `employee_key` | INT, FK → dim_employee | Looked up by `employee_id` |
| `review_period_key` | TINYINT, FK → dim_review_period | `review_period` |
| `review_date_key` | INT, FK → dim_date | `review_date` |
| `score` | TINYINT | `score` |
| `reviewer_status` | VARCHAR(10), not null | `reviewer_status` |

Primary key: (`employee_key`, `review_period_key`).

## 4. Report definitions

- **Headcount**: employees whose `employment_status` is Active or On Leave.
- **Attendance rate**: (Present + Late) / all attendance rows.

## Open items

- The warehouse engine is not decided (MySQL, Snowflake or PostgreSQL), so the types above may change.
- No department dimension yet.
- `dim_date` must cover hire dates back to 2018 if `hire_date` is ever keyed. Today it is stored as a plain DATE.
