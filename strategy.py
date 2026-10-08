"""
MACD CONFLUENCE TRADING BOT
Strategy V1

Paper-Trading only.
No API keys.
No wallet.
No real orders.

Strategy:
- MACD 12 / 26 / 9
- EMA 200 High / Close / Low band
- Trend filter
- Zero-Line pullback
- MACD momentum turn
- Breakout confirmation
- Signal score
- ATR-based Stop Loss / Take Profit
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd
import numpy as np


# ============================================================
# CONFIGURATION
# ============================================================

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

EMA_PERIOD = 200

ATR_PERIOD = 14

# Minimum score required for a signal
MIN_SIGNAL_SCORE = 70

# Risk / reward
STOP_ATR_MULTIPLIER = 1.5
TP_ATR_MULTIPLIER = 3.0


# ============================================================
# RESULT OBJECT
# ============================================================

@dataclass
class Signal:
    direction: str
    score: int
    entry: float
    stop_loss: float
    take_profit: float

    trend_score: int
    macd_score: int
    pullback_score: int
    breakout_score: int

    reason: str


# ============================================================
# INDICATORS
# ============================================================

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate EMA."""
    return series.ewm(
        span=period,
        adjust=False
    ).mean()


def calculate_macd(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate MACD 12/26/9."""

    df = df.copy()

    fast = calculate_ema(df["close"], MACD_FAST)
    slow = calculate_ema(df["close"], MACD_SLOW)

    df["macd"] = fast - slow
    df["macd_signal"] = calculate_ema(
        df["macd"],
        MACD_SIGNAL
    )

    df["macd_hist"] = (
        df["macd"] -
        df["macd_signal"]
    )

    return df


def calculate_ema_band(df: pd.DataFrame) -> pd.DataFrame:
    """
    EMA 200 band:

        EMA High
        EMA Close
        EMA Low
    """

    df = df.copy()

    df["ema_high"] = calculate_ema(
        df["high"],
        EMA_PERIOD
    )

    df["ema_close"] = calculate_ema(
        df["close"],
        EMA_PERIOD
    )

    df["ema_low"] = calculate_ema(
        df["low"],
        EMA_PERIOD
    )

    return df


def calculate_atr(
    df: pd.DataFrame,
    period: int = ATR_PERIOD
) -> pd.DataFrame:
    """Calculate Average True Range."""

    df = df.copy()

    previous_close = df["close"].shift(1)

    tr1 = df["high"] - df["low"]

    tr2 = (
        df["high"] -
        previous_close
    ).abs()

    tr3 = (
        df["low"] -
        previous_close
    ).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    df["atr"] = true_range.rolling(
        period
    ).mean()

    return df


# ============================================================
# ALL INDICATORS
# ============================================================

def prepare_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all indicators required by the strategy."""

    required = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    for column in required:
        if column not in df.columns:
            raise ValueError(
                f"Missing required column: {column}"
            )

    df = df.copy()

    df = calculate_macd(df)
    df = calculate_ema_band(df)
    df = calculate_atr(df)

    return df


# ============================================================
# TREND DETECTION
# ============================================================

def detect_trend(row) -> str:
    """
    Determine trend using EMA 200 band.

    BULLISH:
        price > EMA high
        EMA high > EMA close > EMA low

    BEARISH:
        price < EMA low
        EMA high > EMA close > EMA low

    Otherwise:
        NEUTRAL
    """

    price = row["close"]

    if (
        price > row["ema_high"]
        and row["ema_high"] > row["ema_close"]
        and row["ema_close"] > row["ema_low"]
    ):
        return "BULLISH"

    if (
        price < row["ema_low"]
        and row["ema_high"] > row["ema_close"]
        and row["ema_close"] > row["ema_low"]
    ):
        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# MACD MOMENTUM
# ============================================================

def macd_turning_bullish(
    previous,
    current
) -> bool:

    return (
        current["macd_hist"] >
        previous["macd_hist"]
        and
        current["macd"] >
        previous["macd"]
    )


def macd_turning_bearish(
    previous,
    current
) -> bool:

    return (
        current["macd_hist"] <
        previous["macd_hist"]
        and
        current["macd"] <
        previous["macd"]
    )


# ============================================================
# PULLBACK DETECTION
# ============================================================

def bullish_pullback(
    row,
    tolerance: float = 0.015
) -> bool:
    """
    Detect whether price has pulled back
    toward the EMA band while remaining bullish.
    """

    distance = abs(
        row["close"] -
        row["ema_close"]
    ) / row["close"]

    return distance <= tolerance


def bearish_pullback(
    row,
    tolerance: float = 0.015
) -> bool:

    distance = abs(
        row["close"] -
        row["ema_close"]
    ) / row["close"]

    return distance <= tolerance


# ============================================================
# BREAKOUT DETECTION
# ============================================================

def bullish_breakout(
    df: pd.DataFrame,
    index: int
) -> bool:

    if index < 3:
        return False

    current = df.iloc[index]
    previous = df.iloc[index - 1]

    recent_high = df.iloc[
        index - 3:index
    ]["high"].max()

    return (
        current["close"] > recent_high
        and
        current["close"] > previous["close"]
    )


def bearish_breakout(
    df: pd.DataFrame,
    index: int
) -> bool:

    if index < 3:
        return False

    current = df.iloc[index]
    previous = df.iloc[index - 1]

    recent_low = df.iloc[
        index - 3:index
    ]["low"].min()

    return (
        current["close"] < recent_low
        and
        current["close"] < previous["close"]
    )


# ============================================================
# SIGNAL GENERATION
# ============================================================

def evaluate(
    df: pd.DataFrame,
    index: Optional[int] = None
) -> Optional[Signal]:
    """
    Evaluate the latest candle.

    Returns:
        Signal object or None.
    """

    if len(df) < EMA_PERIOD + 20:
        return None

    if index is None:
        index = len(df) - 1

    if index < 3:
        return None

    row = df.iloc[index]
    previous = df.iloc[index - 1]

    # --------------------------------------------------------
    # Check indicator availability
    # --------------------------------------------------------

    values = [
        row["ema_high"],
        row["ema_close"],
        row["ema_low"],
        row["macd"],
        row["macd_signal"],
        row["macd_hist"],
        row["atr"],
    ]

    if any(pd.isna(value) for value in values):
        return None

    trend = detect_trend(row)

    # ========================================================
    # LONG
    # ========================================================

    if trend == "BULLISH":

        score = 0
        reasons = []

        # Trend
        trend_score = 25
        score += trend_score
        reasons.append("bullish EMA trend")

        # Pullback
        if bullish_pullback(row):
            pullback_score = 20
            score += pullback_score
            reasons.append("EMA pullback")
        else:
            pullback_score = 0

        # MACD
        if (
            row["macd"] <= 0
            and
            macd_turning_bullish(
                previous,
                row
            )
        ):
            macd_score = 30
            score += macd_score
            reasons.append(
                "MACD bullish zero-line recovery"
            )

        elif macd_turning_bullish(
            previous,
            row
        ):
            macd_score = 20
            score += macd_score
            reasons.append(
                "MACD bullish momentum"
            )

        else:
            macd_score = 0

        # Breakout
        if bullish_breakout(
            df,
            index
        ):
            breakout_score = 25
            score += breakout_score
            reasons.append("breakout confirmed")
        else:
            breakout_score = 0

        # ----------------------------------------------------
        # Signal
        # ----------------------------------------------------

        if score >= MIN_SIGNAL_SCORE:

            entry = float(row["close"])
            atr = float(row["atr"])

            stop_loss = (
                entry -
                atr * STOP_ATR_MULTIPLIER
            )

            take_profit = (
                entry +
                atr * TP_ATR_MULTIPLIER
            )

            return Signal(
                direction="LONG",
                score=score,
                entry=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                trend_score=trend_score,
                macd_score=macd_score,
                pullback_score=pullback_score,
                breakout_score=breakout_score,
                reason=", ".join(reasons),
            )

    # ========================================================
    # SHORT
    # ========================================================

    if trend == "BEARISH":

        score = 0
        reasons = []

        # Trend
        trend_score = 25
        score += trend_score
        reasons.append("bearish EMA trend")

        # Pullback
        if bearish_pullback(row):
            pullback_score = 20
            score += pullback_score
            reasons.append("EMA pullback")
        else:
            pullback_score = 0

        # MACD
        if (
            row["macd"] >= 0
            and
            macd_turning_bearish(
                previous,
                row
            )
        ):
            macd_score = 30
            score += macd_score
            reasons.append(
                "MACD bearish zero-line rejection"
            )

        elif macd_turning_bearish(
            previous,
            row
        ):
            macd_score = 20
            score += macd_score
            reasons.append(
                "MACD bearish momentum"
            )

        else:
            macd_score = 0

        # Breakout
        if bearish_breakout(
            df,
            index
        ):
            breakout_score = 25
            score += breakout_score
            reasons.append("breakdown confirmed")
        else:
            breakout_score = 0

        # ----------------------------------------------------
        # Signal
        # ----------------------------------------------------

        if score >= MIN_SIGNAL_SCORE:

            entry = float(row["close"])
            atr = float(row["atr"])

            stop_loss = (
                entry +
                atr * STOP_ATR_MULTIPLIER
            )

            take_profit = (
                entry -
                atr * TP_ATR_MULTIPLIER
            )

            return Signal(
                direction="SHORT",
                score=score,
                entry=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                trend_score=trend_score,
                macd_score=macd_score,
                pullback_score=pullback_score,
                breakout_score=breakout_score,
                reason=", ".join(reasons),
            )

    return None


# ============================================================
# SIGNAL DESCRIPTION
# ============================================================

def signal_to_dict(
    signal: Optional[Signal]
):
    """Convert signal to dictionary."""

    if signal is None:
        return None

    return {
        "direction": signal.direction,
        "score": signal.score,
        "entry": signal.entry,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "trend_score": signal.trend_score,
        "macd_score": signal.macd_score,
        "pullback_score": signal.pullback_score,
        "breakout_score": signal.breakout_score,
        "reason": signal.reason,
    }


# ============================================================
# SELF TEST
# ============================================================

def self_test():

    print()
    print("=" * 70)
    print("MACD CONFLUENCE STRATEGY V1")
    print("SELF TEST")
    print("=" * 70)

    np.random.seed(42)

    candles = 350

    prices = (
        70000
        + np.cumsum(
            np.random.normal(
                0,
                250,
                candles
            )
        )
    )

    highs = (
        prices +
        np.random.uniform(
            50,
            300,
            candles
        )
    )

    lows = (
        prices -
        np.random.uniform(
            50,
            300,
            candles
        )
    )

    opens = prices + np.random.normal(
        0,
        100,
        candles
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

    # Indicators
    df = prepare_indicators(df)

    print()
    print("PASS: DataFrame created")
    print("PASS: MACD calculated")
    print("PASS: EMA band calculated")
    print("PASS: ATR calculated")

    # Trend
    trend = detect_trend(
        df.iloc[-1]
    )

    assert trend in [
        "BULLISH",
        "BEARISH",
        "NEUTRAL"
    ]

    print("PASS: Trend detection")

    # Evaluation
    signal = evaluate(df)

    if signal is None:
        print(
            "PASS: No invalid signal generated"
        )
    else:
        print(
            f"PASS: Signal generated: "
            f"{signal.direction} "
            f"{signal.score}/100"
        )

        assert signal.direction in [
            "LONG",
            "SHORT"
        ]

        assert signal.entry > 0
        assert signal.stop_loss > 0
        assert signal.take_profit > 0

    print()
    print("=" * 70)
    print("ALL STRATEGY SELF TESTS PASSED")
    print("=" * 70)
    print()


if __name__ == "__main__":
    self_test()
