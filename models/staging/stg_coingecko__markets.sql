with source as (
    select *
    from {{ source('raw', 'coingecko_markets') }}
),
renamed as (
        select
            id                as coin_id,
            symbol            as coin_symbol,
            name              as coin_name,
            current_price     as current_price_usd,
            market_cap        as market_cap_usd,
            market_cap_rank   as market_cap_rank,
            total_volume      as total_volume_usd,
            price_change_percentage_24h as price_change_pct_24h,
            _loaded_at        as loaded_at
        from source
)
select * from renamed