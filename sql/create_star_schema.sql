CREATE SCHEMA IF NOT EXISTS ANALYTICS;
USE SCHEMA ANALYTICS;

-- 1. DIMENSION TABLES

-- Date Dimension
CREATE OR REPLACE TABLE dim_date (
    date_key        INT PRIMARY KEY,
    full_date       DATE NOT NULL,
    day_name        VARCHAR(9) NOT NULL,
    week_of_year    TINYINT NOT NULL,
    month_number    TINYINT NOT NULL,
    month_name      VARCHAR(9) NOT NULL,
    quarter         TINYINT NOT NULL,
    half_year       VARCHAR(7) NOT NULL,
    year            SMALLINT NOT NULL,
    is_weekend      BOOLEAN NOT NULL
);


-- Employee Dimension
CREATE OR REPLACE TABLE dim_employee (
    employee_key       INT AUTOINCREMENT PRIMARY KEY,
    employee_id        VARCHAR(10) NOT NULL UNIQUE,
    department         VARCHAR(50),
    division           VARCHAR(50),
    job_title          VARCHAR(60),
    salary_band        VARCHAR(2),
    employment_status  VARCHAR(10),
    hire_date          DATE
);


-- Attendance Status Dimension
CREATE OR REPLACE TABLE dim_attendance_status (
    attendance_status_key  TINYINT PRIMARY KEY,
    status_name            VARCHAR(10) NOT NULL,
    is_worked_day          BOOLEAN NOT NULL
);


-- Review Period Dimension
CREATE OR REPLACE TABLE dim_review_period (
    review_period_key  TINYINT PRIMARY KEY,
    review_period      VARCHAR(7) NOT NULL,
    year               SMALLINT NOT NULL,
    half               TINYINT NOT NULL
);

-- 2. FACT TABLES

-- Attendance Fact
CREATE OR REPLACE TABLE fact_attendance (
    attendance_id         VARCHAR(10) PRIMARY KEY,
    date_key              INT NOT NULL,
    employee_key          INT NOT NULL,
    attendance_status_key TINYINT NOT NULL,
    check_in              TIME,
    check_out             TIME,
    hours_worked          NUMBER(4, 2) NOT NULL,

    FOREIGN KEY (date_key)
        REFERENCES dim_date(date_key),

    FOREIGN KEY (employee_key)
        REFERENCES dim_employee(employee_key),

    FOREIGN KEY (attendance_status_key)
        REFERENCES dim_attendance_status(attendance_status_key)
);


-- Performance Fact
CREATE OR REPLACE TABLE fact_performance (
    employee_key      INT NOT NULL,
    review_period_key TINYINT NOT NULL,
    review_date_key   INT NOT NULL,
    score             TINYINT,
    reviewer_status   VARCHAR(10) NOT NULL,

    PRIMARY KEY (employee_key, review_period_key),

    FOREIGN KEY (employee_key)
        REFERENCES dim_employee(employee_key),

    FOREIGN KEY (review_period_key)
        REFERENCES dim_review_period(review_period_key),

    FOREIGN KEY (review_date_key)
        REFERENCES dim_date(date_key)
);

-- 3. SEED DATA

-- Attendance Statuses
INSERT INTO dim_attendance_status (
    attendance_status_key,
    status_name,
    is_worked_day
)
VALUES
    (1, 'Present', TRUE),
    (2, 'Late',    TRUE),
    (3, 'Absent',  FALSE),
    (4, 'Leave',   FALSE);


-- Review Periods
INSERT INTO dim_review_period (
    review_period_key,
    review_period,
    year,
    half
)
VALUES
    (1, '2025-H2', 2025, 2),
    (2, '2026-H1', 2026, 1);
