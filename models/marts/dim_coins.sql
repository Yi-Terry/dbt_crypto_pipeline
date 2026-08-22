{{
    config(
        materialized='incremental',
        unique_key= 'coin_id',
        incremental_strategy='merge',
        on_schema_change='append_new_columns'
    )
}}

with staged as (
    select * from {{ ref('stg_coingecko__markets')}}
    {% if is_incremental() %}
    where loaded_at > (select coalesce(max(loaded_at), '1900-01-01') from {{ this }})
    {% endif %}
),
ranked as (
        select *
        from staged
        qualify row_number() over(partition by coin_id order by loaded_at desc) = 1
)
select
    coin_id,
    coin_symbol,
    coin_name,
    coin_image_url,
    loaded_at
from ranked