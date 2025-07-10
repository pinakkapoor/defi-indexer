"""tests for protocol metric computation"""

from datetime import datetime, timedelta
from analytics.protocol_metrics import (
    compute_tvl,
    compute_volume,
    compute_fees,
    compute_user_metrics,
    fee_capture_efficiency,
)


def test_tvl_basic():
    deposits = [
        {"token": "0xweth", "amount": 1e18, "decimals": 18},
        {"token": "0xusdc", "amount": 5000e6, "decimals": 6},
    ]
    withdrawals = [
        {"token": "0xweth", "amount": 0.5e18, "decimals": 18},
    ]
    prices = {"0xweth": 2000, "0xusdc": 1.0}

    tvl = compute_tvl(deposits, withdrawals, prices)
    # 1 ETH - 0.5 ETH = 0.5 ETH * $2000 = $1000 + $5000 USDC = $6000
    assert abs(tvl - 6000) < 1, f"tvl {tvl} expected ~6000"


def test_tvl_no_negative():
    """TVL should not go negative"""
    deposits = [{"token": "0xweth", "amount": 1e18, "decimals": 18}]
    withdrawals = [{"token": "0xweth", "amount": 2e18, "decimals": 18}]
    prices = {"0xweth": 2000}

    tvl = compute_tvl(deposits, withdrawals, prices)
    assert tvl >= 0


def test_volume():
    now = datetime.utcnow()
    swaps = [
        {"token_in": "0xweth", "amount_in": 1e18, "decimals_in": 18, "timestamp": now},
        {"token_in": "0xusdc", "amount_in": 3000e6, "decimals_in": 6, "timestamp": now},
        # old swap — should be excluded from 24h window
        {"token_in": "0xweth", "amount_in": 10e18, "decimals_in": 18,
         "timestamp": now - timedelta(hours=48)},
    ]
    prices = {"0xweth": 2000, "0xusdc": 1.0}

    vol = compute_volume(swaps, prices, hours=24)
    assert abs(vol - 5000) < 1, f"volume {vol} expected ~5000"


def test_fees():
    now = datetime.utcnow()
    swaps = [
        {"token_in": "0xweth", "amount_in": 10e18, "decimals_in": 18, "timestamp": now},
    ]
    prices = {"0xweth": 2000}

    fees = compute_fees(swaps, fee_rate=0.003, price_map=prices, hours=24)
    # volume = 10 ETH * $2000 = $20000, fees = $20000 * 0.3% = $60
    assert abs(fees - 60) < 1


def test_user_metrics():
    now = datetime.utcnow()
    events = [
        {"user": "0xalice", "timestamp": now},
        {"user": "0xbob", "timestamp": now},
        {"user": "0xalice", "timestamp": now},  # duplicate
        {"user": "0xcharlie", "timestamp": now - timedelta(days=10)},  # prev period
        {"user": "0xalice", "timestamp": now - timedelta(days=10)},  # returning
    ]

    metrics = compute_user_metrics(events, days=7)
    assert metrics["unique_users"] == 2  # alice, bob in current period
    assert metrics["returning_users"] == 1  # alice was in both periods
    assert metrics["retention_rate"] > 0


def test_fee_capture_efficiency():
    # $100/day fees, $1M TVL
    eff = fee_capture_efficiency(100, 1_000_000)
    # annualized: $36,500 / $1M = 3.65%
    assert abs(eff - 0.0365) < 0.001


if __name__ == "__main__":
    test_tvl_basic()
    test_tvl_no_negative()
    test_volume()
    test_fees()
    test_user_metrics()
    test_fee_capture_efficiency()
    print("all tests passed")
