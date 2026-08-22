{{
    config(
        materialized='incremental',
        unique_key='coin_id_snapshot_date',
        incremental_strategy='merge',
        on_schema_change='append_new_columns'

    )
}}


with staged as (
        select * from {{ ref('stg_coingecko__markets') }}
        {% if is_incremental() %}
        where loaded_at > (select coalesce(max(loaded_at), '1900-01-01') from {{this}})
        {% endif %}
),
ranked as (
        select
            *,
            cast(loaded_at as date) as snapshot_date,
            row_number() over (
                partition by coin_id, cast(loaded_at as date)
                order by loaded_at desc
            ) as rn
        from staged
)
select
    {{dbt_utils.generate_surrogate_key(['coin_id', 'snapshot_date'])}} as coin_id_snapshot_date,
    coin_id,
    coin_symbol,
    coin_name,
    coin_image_url,
    snapshot_date,
    current_price_usd,
    market_cap_usd,
    market_cap_rank,
    total_volume_usd,
    price_change_pct_24h,
    loaded_at
from ranked
where rn =1