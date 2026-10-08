"""
MACD CONFLUENCE TRADING BOT
Market Data V1

Public Coinbase BTC-USD market data.
No API key required.
No trading.
"""

import time
from datetime import datetime, timezone

import requests
import pandas as pd


BASE_URL = "https://api.exchange.coinbase.com"

PRODUCT = "BTC-USD"

# Coinbase granularity:
# 900 seconds = 15 minutes
GRANULARITY = 900

LIMIT = 250


def get_btc_candles(
    product: str = PRODUCT,
    granularity: int = GRANULARITY,
    limit: int = LIMIT,
) -> pd.DataFrame:
    """
    Download public OHLCV candles from Coinbase.

    Returns:
        DataFrame with:
        timestamp
        open
        high
        low
        close
        volume
    """

    # Coinbase public candles have a maximum request size.
    # We request a recent window only.
    seconds = granularity * limit

    end = int(
        time.time()
    )

    start = end - seconds

    url = (
        f"{BASE_URL}/products/"
        f"{product}/candles"
    )

    params = {
        "start": str(start),
        "end": str(end),
        "granularity": granularity,
    }

    response = requests.get(
        url,
        params=params,
        timeout=20,
    )

    response.raise_for_status()

    raw = response.json()

    if not raw:
        raise RuntimeError(
            "Coinbase returned no candle data."
        )

    # Coinbase format:
    #
    # [
    #   [
    #       timestamp,
    #       low,
    #       high,
    #       open,
    #       close,
    #       volume
    #   ],
    #   ...
    # ]

    df = pd.DataFrame(
        raw,
        columns=[
            "timestamp",
            "low",
            "high",
            "open",
            "close",
            "volume",
        ],
    )

    # Convert numeric columns
    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        unit="s",
        utc=True,
    )

    # Sort oldest -> newest
    df = df.sort_values(
        "timestamp"
    ).reset_index(
        drop=True
    )

    # Remove invalid rows
    df = df.dropna(
        subset=[
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    )

    return df


def get_latest_price(
    product: str = PRODUCT,
) -> float:
    """Get current BTC price."""

    url = (
        f"{BASE_URL}/products/"
        f"{product}/ticker"
    )

    response = requests.get(
        url,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    return float(
        data["price"]
    )


def print_market_data(
    df: pd.DataFrame,
):

    if df.empty:
        print(
            "No market data available."
        )
        return

    latest = df.iloc[-1]

    print()
    print("=" * 70)
    print("COINBASE BTC MARKET DATA")
    print("=" * 70)

    print(
        f"Product:      {PRODUCT}"
    )

    print(
        f"Timeframe:    15m"
    )

    print(
        f"Candles:      {len(df)}"
    )

    print(
        f"Last candle:  "
        f"{latest['timestamp']}"
    )

    print(
        f"Open:         "
        f"${latest['open']:,.2f}"
    )

    print(
        f"High:         "
        f"${latest['high']:,.2f}"
    )

    print(
        f"Low:          "
        f"${latest['low']:,.2f}"
    )

    print(
        f"Close:        "
        f"${latest['close']:,.2f}"
    )

    print(
        f"Volume:       "
        f"{latest['volume']:.6f}"
    )

    print("=" * 70)
    print()


def self_test():

    print()
    print("=" * 70)
    print("MARKET DATA V1")
    print("PUBLIC DATA SELF TEST")
    print("=" * 70)

    df = get_btc_candles()

    assert not df.empty

    print(
        "PASS: Coinbase returned candle data"
    )

    required_columns = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    for column in required_columns:

        assert column in df.columns

    print(
        "PASS: Required columns present"
    )

    assert len(df) > 200

    print(
        f"PASS: {len(df)} candles received"
    )

    assert (
        df["close"].notna().all()
    )

    print(
        "PASS: Close prices valid"
    )

    latest_price = get_latest_price()

    assert latest_price > 0

    print(
        f"PASS: Current BTC price "
        f"${latest_price:,.2f}"
    )

    print_market_data(
        df
    )

    print(
        "PASS: Market data self test complete"
    )

    print()
    print("=" * 70)
    print("ALL MARKET DATA TESTS PASSED")
    print("=" * 70)
    print()


if __name__ == "__main__":
    self_test()
