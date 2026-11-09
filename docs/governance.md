# Data Governance (draft)

Status: draft, 9 Nov 2026. Owners are listed as Member A, B and C until the README names them.

Every policy line carries a tag:

- **Enforced**: the code or the configuration already does this.
- **Proposed**: the team must agree to it before it applies.

## 1. Ownership

| Asset | Owner | Responsibility |
| --- | --- | --- |
| `data/source/`, `src/generate_data.py` | Member A | Synthetic data and injected errors |
| `data/raw/`, `data/clean/`, `data/rejects/`, `data/logs/` | Member A | Ingest, cleaning, quality checks |
| `data/reference/departments.csv` | Member A | The official department and division list. It changes only through a PR, and the `Unknown,Unknown` row must stay, or employees with a blank department are rejected. **Proposed** |
| Warehouse schema, load code, `docker-compose.yml` | Member B | The `ANALYTICS` star schema and the infrastructure |
| Airflow DAG | Member A (extract, clean, checks), Member B (load tasks) | Runs the pipeline |
| Report views, Power BI | Member C | The dashboard and its measures |
| `docs/governance.md`, `docs/data_dictionary.md` | Member C | Keeping the documents in line with the code |

## 2. Data lineage

`data/source` → `data/raw/<dataset>/<run date>` → `data/clean` | `data/rejects` | `data/logs` → `data/logs/quality_report.json` → warehouse (`ANALYTICS`) → Power BI

Columns and types are listed in [data_dictionary.md](data_dictionary.md).

## 3. Data quality rules

### 3a. Cleaning rules (`src/extract_clean.py`), **Enforced**

| Dataset | Rule | Action | Reject reason |
| --- | --- | --- | --- |
| all | Exact duplicate rows | Drop the copy and count it | None |
| employees | Same `employee_id` with different values | Reject the later rows | `duplicate employee_id, conflicting values` |
| employees | Missing `department` or `job_title` | Fill in `Unknown` | None |
| employees | Department not in the reference list after alias mapping | Reject | `department not in the official list` |
| employees | Job title with inconsistent casing | Fix | None |
| employees | `hire_date` in the future or unreadable | Blank the date, keep the row | None |
| attendance | Impossible `attendance_date` | Reject | `attendance_date is not a valid date` |
| attendance | Status not Present, Late, Absent or Leave after typo fixes | Reject | `invalid status` |
| attendance | `hours_worked` outside 0–24 | Reject | `hours outside 0-24` |
| attendance | `check_out` earlier than `check_in` | Reject | `check_out before check_in` |
| attendance | Missing `check_in` on a Present or Late row | Keep the row and count it | None |
| attendance, performance | `employee_id` not in the raw employees file | Reject | `employee_id not in employees` |
| performance | Missing `score` | Reject | `missing score` |
| performance | `score` not a number from 1 to 5 | Reject | `score outside 1-5` |
| performance | `reviewer_status` not Approved, Draft or Pending after case fixes | Reject | `invalid reviewer_status` |

Rejected rows go to `data/rejects/<dataset>_rejected.csv` with a `reject_reason` column. No row is dropped silently.

### 3b. Quality checks (`src/quality_checks.py`), **Enforced**

| Dataset | Rule | Level |
| --- | --- | --- |
| employees | employee_id is filled in | FAIL |
| employees | employee_id is unique | FAIL |
| employees | department is in the official list | FAIL |
| employees | division is filled in | FAIL |
| employees | hire_date is a valid YYYY-MM-DD date (blank is allowed) | FAIL |
| employees | hire_date is not in the future | FAIL |
| attendance | attendance_id is unique | FAIL |
| attendance | employee_id exists in employees | FAIL |
| attendance | attendance_date is a valid YYYY-MM-DD date | FAIL |
| attendance | status is Present, Absent, Late or Leave | FAIL |
| attendance | hours_worked is a number between 0 and 24 | FAIL |
| attendance | check_out is not before check_in | FAIL |
| attendance | Present/Late rows have a check_in | WARN |
| attendance | one row per employee per day | WARN |
| performance | employee_id exists in employees | FAIL |
| performance | score is filled in | FAIL |
| performance | reviewer_status is Approved, Draft or Pending | FAIL |
| performance | review_date is a valid YYYY-MM-DD date | FAIL |
| performance | score is a number between 1 and 5 | WARN |
| performance | one review per employee per review_period | WARN |

### 3c. Thresholds

- Any FAIL fails the Airflow `quality_checks` task, so the load does not run. Run on its own, the script exits with code 1. **Enforced**
- The data owner reviews each WARN before the dashboard is refreshed. **Proposed**
- Rejected rows are never fixed by hand in `data/clean/`. Fix the source, then run the pipeline again. **Proposed**
- Latest result (`data/logs/quality_report.json`): 19 PASS, 1 WARN, 0 FAIL.

## 4. Access roles, **Proposed**

| Role | Who | Access | Example warehouse role |
| --- | --- | --- | --- |
| `pipeline_service` | The Airflow container | Reads `data/*`. Writes clean, rejects and logs. Writes the warehouse tables. | A dedicated loader role. `dag/hr_pipeline.py` defaults to `SYSADMIN`, which has more rights than the pipeline needs. |
| `data_engineer` | Members A and B | Read and write on the repo and the warehouse, including raw and rejects | Developer role |
| `analyst` | Member C | Read-only on the `ANALYTICS` report views. No access to raw files or rejects. | Read-only reporting role |
| `hr_viewer` | Managers | The Power BI dashboard only. Performance data is limited to Approved rows. | None (Power BI sharing) |

## 5. Retention

| Location | What is kept | Rule |
| --- | --- | --- |
| `data/raw/<dataset>/<date>/` | An untouched copy of each run's source files | Never overwritten. **Enforced** by `ingest_to_raw`. Keep them until 90 days after the 18 Nov 2026 submission, then delete. **Proposed** |
| `data/clean/`, `data/rejects/`, `data/logs/` | The latest run only | Overwritten on every run, so there is no history and only the latest run can be audited. **Enforced** |
| Warehouse | The loaded star schema | Rebuilt from `data/clean/` on each load. **Proposed** |
| `.env` (secrets) | Database and Snowflake credentials | Kept out of git. **Enforced** by `.gitignore`. Never posted in chat or committed. **Proposed** |

## 6. Privacy

- The data is synthetic. **Enforced** by `src/generate_data.py`.
- No columns hold names, phones, emails or addresses. **Enforced** by the schema and the data dictionary.
- Reports go no deeper than `employee_id`. **Enforced** by the star schema.
- MySQL and Airflow accept connections only from the local machine (`127.0.0.1`). **Enforced** in `docker-compose.yml`.
- `score`, `salary_band` and `employment_status` are sensitive. Only `data_engineer` sees them at row level; the dashboard shows them as totals. **Proposed**
- The dashboard hides any group with fewer than 5 employees. **Proposed**
- The same rules apply if real data ever replaces the synthetic data. **Proposed**

## 7. Change management and incidents

- Branch from `dev`, open a PR into `dev`, get a review from another member, and merge. Merge `dev` into `main` by PR. **Enforced** by the team workflow in the README.
- A schema change, a new rule or a change to the reference data must update `docs/data_dictionary.md` and this document in the same PR. **Proposed**
- A FAIL in Airflow is fixed by the owner of that dataset on the same day. **Proposed**
- Anyone stuck for more than half a day tells the group chat. **Enforced** by the team workflow in the README.

## Open decisions

- The warehouse engine: MySQL, Snowflake or PostgreSQL.
- The pipeline's warehouse role, to replace the `SYSADMIN` default.
- Whether to keep clean, rejects and log files for each run date.
- How long to keep data after submission (90 days is proposed).
- The smallest group the dashboard may show (5 is proposed).
