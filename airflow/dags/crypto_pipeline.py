from datetime import datetime

from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator

PROJECT_DIR = "/opt/airflow/project"

ENV_SETUP = (
    f"cd {PROJECT_DIR} && "
    f"export $(grep -v '^#' .env | xargs) && "
    f"export SNOWFLAKE_PRIVATE_KEY_PATH={PROJECT_DIR}/keys/svc_crypto_loader_rsa_key.p8 && "
    f"export DBT_SNOWFLAKE_PRIVATE_KEY_PATH={PROJECT_DIR}/keys/svc_crypto_dbt_rsa_key.p8 &&"
)

with DAG(
    dag_id="crypto_pipeline",
    description="CoinGecko -> Snowflake RAW -> dbt staging/marts",
    start_date=datetime(2026, 8, 1),
    schedule="@hourly",
    catchup=False,
    tags=["crypto", "dbt", "snowflake"],
) as dag:

    ingest = BashOperator(
        task_id="ingest_coingecko",
        bash_command=f"{ENV_SETUP} python3 ingestion/fetch_coingecko.py",
    )

    dbt_build = BashOperator(
        task_id="dbt_run_and_test",
        bash_command=(
            f"{ENV_SETUP} "
            f"dbt deps --profiles-dir {PROJECT_DIR} && "
            f"dbt run --profiles-dir {PROJECT_DIR} && "
            f"dbt test --profiles-dir {PROJECT_DIR}"
        ),
    )

    ingest >> dbt_build