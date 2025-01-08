"""
protocol-level metric computation.

takes raw indexed events and computes the metrics that actually
matter for evaluating defi protocols:
- TVL (total value locked)
- volume (trading, lending, etc)
- fees generated
- unique users
- user retention

dune dashboards are great for one-off queries but terrible for
systematic analysis. this computes everything programmatically
so you can compare protocols apples-to-apples.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class ProtocolSnapshot:
    protocol: str
    timestamp: datetime
    tvl_usd: float
    volume_24h: float
    fees_24h: float
    unique_users_24h: int
    unique_users_7d: int
    transactions_24h: int


def compute_tvl(deposit_events: list[dict], withdraw_events: list[dict],
                price_map: dict[str, float]) -> float:
    """
    compute total value locked from deposit/withdraw events.

    tvl = sum of all deposits - sum of all withdrawals, converted to USD.
    price_map: {token_address: usd_price}
    """
    total = 0.0

    for event in deposit_events:
        token = event.get("token", "").lower()
        amount = float(event.get("amount", 0))
        decimals = int(event.get("decimals", 18))
        normalized = amount / (10 ** decimals)
        price = price_map.get(token, 0)
        total += normalized * price

    for event in withdraw_events:
        token = event.get("token", "").lower()
        amount = float(event.get("amount", 0))
        decimals = int(event.get("decimals", 18))
        normalized = amount / (10 ** decimals)
        price = price_map.get(token, 0)
        total -= normalized * price

    return max(total, 0)


def compute_volume(swap_events: list[dict], price_map: dict[str, float],
                   hours: int = 24) -> float:
    """
    compute trading volume from swap events within a time window.
    only counts one side of the swap to avoid double counting.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    total = 0.0

    for event in swap_events:
        ts = event.get("timestamp")
        if ts and ts < cutoff:
            continue

        # count the "in" side of the swap
        token_in = event.get("token_in", "").lower()
        amount_in = float(event.get("amount_in", 0))
        decimals = int(event.get("decimals_in", 18))
        normalized = amount_in / (10 ** decimals)
        price = price_map.get(token_in, 0)
        total += normalized * price

    return total


def compute_fees(swap_events: list[dict], fee_rate: float,
                 price_map: dict[str, float], hours: int = 24) -> float:
    """
    estimate fees from swap volume.
    most AMMs charge a flat fee rate (e.g. Uniswap V2 = 0.3%).
    """
    volume = compute_volume(swap_events, price_map, hours)
    return volume * fee_rate


def compute_user_metrics(events: list[dict], days: int = 7) -> dict:
    """
    user analytics from event data.

    returns unique users, new vs returning, and a simple retention rate.
    retention = users active in both current and previous period / previous period users.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    prev_cutoff = cutoff - timedelta(days=days)

    current_users = set()
    prev_users = set()

    for event in events:
        user = event.get("user") or event.get("sender") or event.get("from")
        ts = event.get("timestamp")

        if not user or not ts:
            continue

        if ts >= cutoff:
            current_users.add(user.lower())
        elif ts >= prev_cutoff:
            prev_users.add(user.lower())

    returning = current_users & prev_users
    new_users = current_users - prev_users

    retention = len(returning) / len(prev_users) if prev_users else 0

    return {
        "unique_users": len(current_users),
        "new_users": len(new_users),
        "returning_users": len(returning),
        "retention_rate": round(retention, 4),
        "period_days": days,
    }


def fee_capture_efficiency(fees_24h: float, tvl: float) -> float:
    """
    annualized fee revenue relative to TVL.
    a key metric for evaluating protocol capital efficiency.

    higher = protocol generates more fees per dollar locked.
    uniswap V3 is much higher than V2 because of concentrated liquidity.
    """
    if tvl == 0:
        return 0
    annualized_fees = fees_24h * 365
    return round(annualized_fees / tvl, 4)
