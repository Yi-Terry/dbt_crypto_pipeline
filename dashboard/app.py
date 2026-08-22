import os

import pandas as pd
import snowflake.connector
import streamlit as st
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv

load_dotenv()

REFRESH_SECONDS = 300


def load_private_key_der(path: str, passphrase: str | None) -> bytes:
    with open(path, "rb") as f:
        p_key = serialization.load_pem_private_key(
            f.read(),
            password=passphrase.encode() if passphrase else None,
        )
    return p_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def get_connection():
    private_key = load_private_key_der(
        os.environ["DBT_SNOWFLAKE_PRIVATE_KEY_PATH"],
        os.getenv("DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE") or None,
    )
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["DBT_SNOWFLAKE_USER"],
        private_key=private_key,
        role=os.environ["DBT_SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.getenv("DBT_SNOWFLAKE_SCHEMA", "ANALYTICS"),
    )


@st.cache_data(ttl=REFRESH_SECONDS)
def load_all_coins() -> pd.DataFrame:
    conn = get_connection()
    try:
        query = """
            select coin_id, coin_name, coin_symbol, coin_image_url, current_price_usd, price_change_pct_24h
            from fct_crypto_daily_snapshot
            where snapshot_date = (select max(snapshot_date) from fct_crypto_daily_snapshot)
            order by market_cap_rank asc
        """
        return pd.read_sql(query, conn)
    finally:
        conn.close()


@st.cache_data(ttl=REFRESH_SECONDS)
def load_price_history(coin_id: str, hours: int = 48) -> pd.DataFrame:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            select loaded_at, current_price_usd
            from stg_coingecko__markets
            where coin_id = %(coin_id)s
              and loaded_at >= dateadd('hour', -%(hours)s, current_timestamp())
            order by loaded_at asc
            """,
            {"coin_id": coin_id, "hours": hours},
        )
        return cur.fetch_pandas_all()
    finally:
        conn.close()


def render_coin_metric(container, row) -> None:
    if row.get("COIN_IMAGE_URL"):
        container.image(row["COIN_IMAGE_URL"], width=32)
    container.metric(
        label=f"{row['COIN_NAME']} ({row['COIN_SYMBOL'].upper()})",
        value=f"${row['CURRENT_PRICE_USD']:,.2f}",
        delta=f"{row['PRICE_CHANGE_PCT_24H']:.2f}%",
    )


st.set_page_config(page_title="Crypto Dashboard", page_icon="\U0001FA99", layout="wide")
st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] { font-size: clamp(1.1rem, 2.2vw, 2rem); white-space: nowrap; overflow: visible; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Crypto Dashboard")

if st.button("Refresh"):
    load_all_coins.clear()

all_coins = load_all_coins()

if all_coins.empty:
    st.warning("No data found in fct_crypto_daily_snapshot yet.")
else:
    st.subheader("Top 5 Coins")
    top5 = all_coins.head(5)
    cols = st.columns(len(top5), gap="large")
    for col, (_, row) in zip(cols, top5.iterrows()):
        render_coin_metric(col, row)

    st.divider()
    st.subheader("Look Up a Coin")
    choice = st.selectbox("Coin", all_coins["COIN_NAME"], index=None, placeholder="Search for a coin...")
    if choice is not None:
        selected_row = all_coins.loc[all_coins["COIN_NAME"] == choice].iloc[0]
        render_coin_metric(st, selected_row)

        history = load_price_history(selected_row["COIN_ID"])
        if history.empty:
            st.info("Not enough hourly history yet to plot a trend.")
        else:
            st.line_chart(history.set_index("LOADED_AT")["CURRENT_PRICE_USD"])

st.caption(f"Auto-refreshes every {REFRESH_SECONDS // 60} min, or click Refresh above.")
