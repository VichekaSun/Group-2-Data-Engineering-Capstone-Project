# Real screenshots for the deck

Save a screenshot here with the exact file name below and the deck shows it
in place of the drawn table or diagram, on any computer. You can also click the
dashed "Real screenshot" box on a slide to insert one (kept in that browser only).

| File | Slide | What to capture |
|---|---|---|
| cd-raw-attendance.png | HR numbers nobody can trust (Chea Dalin) | data/source/attendance.csv opened in Excel, bad rows visible |
| cd-cleaning-run.png | Cleaning results (Chea Dalin) | Cleaning run output: terminal / Airflow task log, or data/logs/*_cleaning_log.json |
| cd-quality-report.png | 20 automated quality checks (Chea Dalin) | quality_checks task log in Airflow, or data/logs/quality_report.json |
| cd-airflow-graph.png | The Airflow DAG (Chea Dalin) | Airflow UI, Graph view of hr_pipeline_extract_clean after a green run |
| lv-docker-running.png | Docker Compose (Lim Viboth) | Docker Desktop or `docker compose ps` with mysql + airflow running |
| lv-snowflake-connection.png | Configuration (Lim Viboth) | Snowflake: HR_DB, schema ANALYTICS, warehouse COMPUTE_WH. Hide passwords and the account URL |
| lv-snowflake-schema.png | Star schema (Lim Viboth) | Snowflake: HR_DB.ANALYTICS tables in the object browser, or an ER diagram |
| sv-github-prs.png | Git workflow (Sun Vicheka) | GitHub: the repo's closed pull requests list |
| lv-fact-counts.png | Fact tables (Lim Viboth) | Snowflake worksheet: SELECT COUNT(*) on fact_attendance (12,917) and fact_performance (372) |
