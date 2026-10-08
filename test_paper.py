"""
MACD CONFLUENCE TRADING BOT
Integration Test V1

Tests:
    strategy.py
    paper_trader.py

PAPER TRADING ONLY
No API keys
No real orders
"""

import pandas as pd
import numpy as np

from strategy import (
    prepare_indicators,
    evaluate,
)

from paper_trader import (
    PaperTrader,
)


# ============================================================
# TEST DATA
# ============================================================

def create_test_data(
    candles: int = 500
) -> pd.DataFrame:

    np.random.seed(123)

    # Start price
    price = 70000.0

    prices = []

    for i in range(candles):

        # Create several trend phases
        phase = i % 150

        if phase < 50:

            drift = 80

        elif phase < 100:

            drift = -60

        else:

            drift = 40

        noise = np.random.normal(
            0,
            180
        )

        price += drift + noise

        price = max(
            price,
            1000
        )

        prices.append(price)

    prices = np.array(prices)

    opens = (
        prices +
        np.random.normal(
            0,
            80,
            candles
        )
    )

    highs = (
        prices +
        np.random.uniform(
            50,
            250,
            candles
        )
    )

    lows = (
        prices -
        np.random.uniform(
            50,
            250,
            candles
        )
    )

    volumes = np.random.uniform(
        100,
        1000,
        candles
    )

    df = pd.DataFrame({

        "open": opens,

        "high": highs,

        "low": lows,

        "close": prices,

        "volume": volumes,
    })

    return df


# ============================================================
# STRATEGY TEST
# ============================================================

def test_strategy():

    print()
    print("=" * 70)
    print("TEST 1: STRATEGY")
    print("=" * 70)

    df = create_test_data()

    df = prepare_indicators(
        df
    )

    print(
        "PASS: Test market data created"
    )

    required_columns = [

        "macd",

        "macd_signal",

        "macd_hist",

        "ema_high",

        "ema_close",

        "ema_low",

        "atr",
    ]

    for column in required_columns:

        assert column in df.columns

    print(
        "PASS: All indicators present"
    )

    signals = []

    for i in range(
        250,
        len(df)
    ):

        signal = evaluate(
            df,
            i
        )

        if signal is not None:

            signals.append(
                signal
            )

    print(
        f"PASS: Strategy evaluated "
        f"{len(df) - 250} candles"
    )

    print(
        f"Signals generated: "
        f"{len(signals)}"
    )

    if signals:

        for signal in signals[:3]:

            print()
            print(
                f"Signal: "
                f"{signal.direction}"
            )

            print(
                f"Score: "
                f"{signal.score}/100"
            )

            print(
                f"Entry: "
                f"{signal.entry:.2f}"
            )

            print(
                f"SL: "
                f"{signal.stop_loss:.2f}"
            )

            print(
                f"TP: "
                f"{signal.take_profit:.2f}"
            )

    print()
    print(
        "PASS: Strategy test completed"
    )

    return df, signals


# ============================================================
# PAPER TRADER TEST
# ============================================================

def test_paper_trader():

    print()
    print("=" * 70)
    print("TEST 2: PAPER TRADER")
    print("=" * 70)

    trader = PaperTrader(
        starting_balance=1000
    )

    print(
        "PASS: Paper trader initialized"
    )

    # --------------------------------------------------------
    # Fake LONG signal
    # --------------------------------------------------------

    class TestSignal:

        direction = "LONG"

        score = 85

        entry = 100.0

        stop_loss = 95.0

        take_profit = 110.0

        trend_score = 25

        macd_score = 30

        pullback_score = 20

        breakout_score = 10

        reason = "integration test"

    signal = TestSignal()

    opened = trader.open_position(

        symbol="BTC/USDT",

        signal=signal,

        timestamp="TEST",
    )

    assert opened is True

    print(
        "PASS: LONG position opened"
    )

    assert trader.position is not None

    # --------------------------------------------------------
    # Check price
    # --------------------------------------------------------

    result = trader.check_position(

        current_price=105,

        timestamp="TEST",
    )

    assert result is None

    print(
        "PASS: Position remains open"
    )

    # --------------------------------------------------------
    # Hit TP
    # --------------------------------------------------------

    result = trader.check_position(

        current_price=110,

        timestamp="TEST",
    )

    assert result is not None

    print(
        "PASS: TP detected"
    )

    assert result.reason == (
        "TAKE_PROFIT"
    )

    print(
        "PASS: Correct exit reason"
    )

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    stats = trader.statistics()

    assert stats["trades"] == 1

    print(
        "PASS: Trade counted"
    )

    assert stats["winning_trades"] == 1

    print(
        "PASS: Winning trade counted"
    )

    print()
    print(
        f"Final balance: "
        f"${stats['current_balance']:.2f}"
    )

    print(
        f"Net PNL: "
        f"${stats['total_pnl']:.2f}"
    )

    print(
        f"Win rate: "
        f"{stats['win_rate']:.2f}%"
    )

    print()
    print(
        "PASS: Paper trader test completed"
    )


# ============================================================
# FULL TEST
# ============================================================

def main():

    print()
    print("=" * 70)
    print("MACD CONFLUENCE TRADING BOT")
    print("INTEGRATION TEST V1")
    print("=" * 70)

    # Strategy
    df, signals = test_strategy()

    # Paper trader
    test_paper_trader()

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("ALL INTEGRATION TESTS PASSED")
    print("=" * 70)

    print()
    print(
        "Strategy + Paper Trader are working."
    )

    print(
        "No API keys."
    )

    print(
        "No wallet."
    )

    print(
        "No real orders."
    )

    print()


if __name__ == "__main__":
    main()
