# Crypto Data Pipeline

Ingests hourly market data from CoinGecko into Snowflake, transforms it with dbt, and serves it through a Streamlit dashboard. Orchestrated by Airflow.

## Architecture

```
CoinGecko API --> ingestion/fetch_coingecko.py --> Snowflake RAW.COINGECKO_MARKETS
                                                            |
                                                        dbt run
                                                            |
                                          stg_coingecko__markets (view)
                                                            |
                                        fct_crypto_daily_snapshot (incremental table)
                                                            |
                                                  dashboard/app.py (Streamlit)
```

Airflow (`airflow/dags/crypto_pipeline.py`) runs the whole thing hourly: `ingest_coingecko` fetches and loads raw market data, then `dbt_run_and_test` builds and tests the dbt models.

## Project layout

- `ingestion/fetch_coingecko.py` — pulls market data for the top coins from CoinGecko and writes it to `RAW.COINGECKO_MARKETS` in Snowflake.
- `models/staging/stg_coingecko__markets.sql` — cleans and renames the raw source columns.
- `models/marts/fct_crypto_daily_snapshot.sql` — one row per coin per day, incrementally merged, deduped to the latest snapshot for each day.
- `dashboard/app.py` — Streamlit app showing top coins and per-coin price history.
- `airflow/` — Airflow (Docker Compose) project that schedules the pipeline.
- `keys/` — Snowflake key-pair auth private keys (not committed — see Setup).

## Prerequisites

- Python 3.11+
- A Snowflake account with a database/warehouse for this project
- Key-pair authentication configured for two Snowflake service users: one for loading raw data, one for dbt
- Docker (only if running the pipeline via Airflow)

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Generate RSA key pairs for Snowflake key-pair auth and place the private keys in `keys/` (this directory is gitignored):

   ```bash
   keys/svc_crypto_loader_rsa_key.p8   # used by ingestion/fetch_coingecko.py
   keys/svc_crypto_dbt_rsa_key.p8      # used by dbt and dashboard/app.py
   ```

3. Copy `.env` (gitignored) and fill in your own values:

   ```bash
   SNOWFLAKE_ACCOUNT=
   SNOWFLAKE_DATABASE=
   SNOWFLAKE_WAREHOUSE=

   # used by ingestion/fetch_coingecko.py
   SNOWFLAKE_USER=
   SNOWFLAKE_ROLE=
   SNOWFLAKE_PRIVATE_KEY_PATH=./keys/svc_crypto_loader_rsa_key.p8
   SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=

   # used by dbt (profiles.yml) and dashboard/app.py
   DBT_SNOWFLAKE_USER=
   DBT_SNOWFLAKE_ROLE=
   DBT_SNOWFLAKE_SCHEMA=ANALYTICS
   DBT_SNOWFLAKE_PRIVATE_KEY_PATH=./keys/svc_crypto_dbt_rsa_key.p8
   DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=

   COINGECKO_API_KEY=
   ```

4. Install dbt packages:

   ```bash
   dbt deps
   ```

## Running locally

```bash
# fetch latest market data into Snowflake RAW
python ingestion/fetch_coingecko.py

# build and test the dbt models
dbt run
dbt test

# launch the dashboard
streamlit run dashboard/app.py
```

## Running on Airflow

```bash
cd airflow
docker compose up
```

The `crypto_pipeline` DAG runs hourly and executes ingestion followed by `dbt run` + `dbt test` inside the container, using the `.env` file and keys mounted at `/opt/airflow/project`.

## dbt models

| Model | Materialization | Description |
|---|---|---|
| `stg_coingecko__markets` | view | Renamed pass-through over the raw CoinGecko snapshot |
| `fct_crypto_daily_snapshot` | incremental table | One deduped row per coin per UTC day, merged on `coin_id_snapshot_date` |
