import logging
import os
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "source_db"),
}

SNOWFLAKE_CONFIG = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT"),
    "user": os.getenv("SNOWFLAKE_USER"),
    "password": os.getenv("SNOWFLAKE_PASSWORD"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "ANALYTICS_WH"),
    "database": os.getenv("SNOWFLAKE_DATABASE", "ANALYTICS_DB"),
    "role": os.getenv("SNOWFLAKE_ROLE", "SYSADMIN"),
}


def _snowflake_connect():
    import snowflake.connector

    return snowflake.connector.connect(
        account=SNOWFLAKE_CONFIG["account"],
        user=SNOWFLAKE_CONFIG["user"],
        password=SNOWFLAKE_CONFIG["password"],
        warehouse=SNOWFLAKE_CONFIG["warehouse"],
        database=SNOWFLAKE_CONFIG["database"],
        role=SNOWFLAKE_CONFIG["role"],
        schema="ANALYTICS",
    )