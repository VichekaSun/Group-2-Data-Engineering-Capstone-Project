-- HR star schema (Snowflake) - loads into the ANALYTICS schema.
--
--   dim_date ───────────┐
--   dim_employee ───────┼── fact_attendance ── dim_attendance_status
--   dim_employee ───────┼── fact_performance ── dim_review_period
--   dim_date ───────────┘

CREATE SCHEMA IF NOT EXISTS ANALYTICS;
USE SCHEMA ANALYTICS;

-- Dimensions ------------------------------------------------------------

CREATE OR REPLACE TABLE dim_date (
    date_key     INT PRIMARY KEY,      -- YYYYMMDD
    full_date    DATE        NOT NULL,
    day_name     VARCHAR(9)  NOT NULL,
    week_of_year TINYINT     NOT NULL,
    month_number TINYINT     NOT NULL,
    month_name   VARCHAR(9)  NOT NULL,
    quarter      TINYINT     NOT NULL,
    half_year    VARCHAR(7)  NOT NULL, -- e.g. 2026-H1 (matches review_period)
    year         SMALLINT    NOT NULL,
    is_weekend   BOOLEAN     NOT NULL
);

-- Source: employees.xlsx + departments.csv (department -> division)
CREATE OR REPLACE TABLE dim_employee (
    employee_key      INT AUTOINCREMENT PRIMARY KEY,
    employee_id       VARCHAR(10) NOT NULL UNIQUE,   -- e.g. E0001
    department        VARCHAR(50),
    division          VARCHAR(50),
    job_title         VARCHAR(60),
    salary_band       VARCHAR(2),                    -- B1 - B4
    employment_status VARCHAR(10),                   -- Active / On Leave / Resigned
    hire_date         DATE
);

CREATE OR REPLACE TABLE dim_attendance_status (
    attendance_status_key TINYINT PRIMARY KEY,
    status_name           VARCHAR(10) NOT NULL,
    is_worked_day         BOOLEAN     NOT NULL
);

INSERT INTO dim_attendance_status VALUES
    (1, 'Present', TRUE),
    (2, 'Late',    TRUE),
    (3, 'Absent',  FALSE),
    (4, 'Leave',   FALSE);

CREATE OR REPLACE TABLE dim_review_period (
    review_period_key TINYINT PRIMARY KEY,
    review_period     VARCHAR(7) NOT NULL,   -- 2025-H2 / 2026-H1
    year              SMALLINT   NOT NULL,
    half              TINYINT    NOT NULL    -- 1 or 2
);

INSERT INTO dim_review_period VALUES
    (1, '2025-H2', 2025, 2),
    (2, '2026-H1', 2026, 1);

-- Facts -----------------------------------------------------------------

-- One row per employee per working day (source: attendance.csv)
CREATE OR REPLACE TABLE fact_attendance (
    attendance_id         VARCHAR(10) PRIMARY KEY,
    date_key              INT         NOT NULL REFERENCES dim_date (date_key),
    employee_key          INT         NOT NULL REFERENCES dim_employee (employee_key),
    attendance_status_key TINYINT     NOT NULL REFERENCES dim_attendance_status (attendance_status_key),
    check_in              TIME,
    check_out             TIME,
    hours_worked          NUMBER(4,2) NOT NULL
);

-- One row per employee per review period (source: performance.csv)
CREATE OR REPLACE TABLE fact_performance (
    employee_key      INT         NOT NULL REFERENCES dim_employee (employee_key),
    review_period_key TINYINT     NOT NULL REFERENCES dim_review_period (review_period_key),
    review_date_key   INT         NOT NULL REFERENCES dim_date (date_key),
    score             TINYINT,                -- 1 - 5
    reviewer_status   VARCHAR(10) NOT NULL,   -- Approved / Draft / Pending
    PRIMARY KEY (employee_key, review_period_key)
);
