{{
    config(
    materialized = 'incremental',
    unique_key = 'coin_id',
    incremental_strategy= 'merge',
    on_schema_change='append_new_columns'
    )
}}

with staged as (
        select * from {{ ref('fct_crypto_daily_snapshot') }}
        {% if is_incremental() %}
        where loaded_at > (select coalesce(max(loaded_at), '1900-01-01') from {{ this }})
        {% endif %}
)
select
    coin_id,
    coin_name,
    snapshot_date,
    current_price_usd,
    price_change_pct_24h,
    dense_rank() over (partition by snapshot_date order by price_change_pct_24h desc) as pct_change_rank,
    loaded_at
from staged