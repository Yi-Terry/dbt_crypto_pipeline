import os
import sys
from datetime import datetime, timezone

import pandas as pd
import requests
import snowflake.connector
from cryptography.hazmat.primitives import serialization
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
RAW_TABLE  = "COINGECKO_MARKETS"

def fetch_markets(vs_currency: str = "usd", per_page: int = 100) -> pd.DataFrame:
    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": per_page,
        "page": 1,
        "sparkline": "false"
    }
    resp = requests.get(COINGECKO_URL, params=params, timeout=30)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    df["_loaded_at"] = datetime.now(timezone.utc)
    df.columns = [c.upper() for c in df.columns]
    return df

def load_private_key_der(path: str, passphrase: str | None) -> bytes:
    with open(path, "rb") as f:
        p_key = serialization.load_pem_private_key(
            f.read(),
            password=passphrase.encode() if passphrase else None
        )

    return p_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

def get_connection():
    required=["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PRIVATE_KEY_PATH"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        sys.exit(f"Missing required env varrrs: {', '.join(missing)}")

    private_key = load_private_key_der(
        os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        os.getenv("SNOWFALKE_PRIVATE_KEY_PASSPHRASE") or None
    )

    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key=private_key,
        role=os.getenv("SNOWFLAKE_ROLE", "CRYPTO_LOADER"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "CRYPTO_WH"),
        database=os.getenv("SNOWFLAKE_DATABASE", "CRYPTO_DB"),
        schema=os.getenv("SNOWFLAKE_SCHEMA", "RAW")
    )

def load_to_snowflake(df: pd.DataFrame) -> None:
    conn = get_connection()
    try:
        success, nchunks, nrows, _ = write_pandas(
            conn,
            df,
            table_name=RAW_TABLE,
            auto_create_table=True,
            overwrite=False,
        )
        print(f"Loaded {nrows} rows into RAW.{RAW_TABLE} (success={success})")
    finally:
        conn.close()

if __name__ == "__main__":
    markets = fetch_markets()
    print(f"Fetched {len(markets)} coins from CoinGecko")
    load_to_snowflake(markets)