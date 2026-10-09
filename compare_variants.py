"""
MACD CONFLUENCE TRADING BOT
Three-Variant Comparison

V1: Original strategy
V2: Strict score >= 85
V3: Original strategy + 8-candle cooldown

Historical simulation only.
No API keys, wallet or real orders.
"""

import time
import pandas as pd

from backtest import fetch_historical_data
from strategy import prepare_indicators, evaluate


# ============================================================
# CONFIGURATION
# ============================================================

STARTING_CAPITAL = 1000.0

RISK_PER_TRADE = 0.01

FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0005

STRICT_MIN_SCORE = 85
COOLDOWN_CANDLES = 8

OUTPUT_FILE = "variant_comparison.csv"
TRADES_FILE = "variant_trades.csv"


# ============================================================
# EXECUTION HELPERS
# ============================================================

def apply_slippage(price, direction, is_entry):
    """
    Apply adverse slippage to simulated executions.
    """

    if direction == "LONG":
        adverse = is_entry
    else:
        adverse = not is_entry

    if adverse:
        return price * (1 + SLIPPAGE_RATE)

    return price * (1 - SLIPPAGE_RATE)


def close_position(position, raw_exit, timestamp, reason, balance):
    """
    Close a position and calculate its net PNL.
    """

    direction = position["direction"]
    quantity = position["quantity"]

    exit_price = apply_slippage(
        raw_exit,
        direction,
        is_entry=False
    )

    if direction == "LONG":
        gross_pnl = (
            exit_price - position["entry"]
        ) * quantity
    else:
        gross_pnl = (
            position["entry"] - exit_price
        ) * quantity

    exit_fee = exit_price * quantity * FEE_RATE

    # Entry fee was already deducted from balance.
    balance += gross_pnl - exit_fee

    net_pnl = (
        gross_pnl
        - position["entry_fee"]
        - exit_fee
    )

    trade = {
        "variant": position["variant"],
        "direction": direction,
        "score": position["score"],
        "entry_time": position["entry_time"],
        "exit_time": timestamp,
        "entry": position["entry"],
        "exit": exit_price,
        "stop_loss": position["stop_loss"],
        "take_profit": position["take_profit"],
        "quantity": quantity,
        "gross_pnl": gross_pnl,
        "entry_fee": position["entry_fee"],
        "exit_fee": exit_fee,
        "total_fees": position["entry_fee"] + exit_fee,
        "net_pnl": net_pnl,
        "exit_reason": reason,
        "balance": balance,
    }

    return trade, balance


# ============================================================
# BACKTEST ENGINE
# ============================================================

def run_variant(df, variant):
    """
    Run one strategy variant on identical historical candles.
    """

    balance = STARTING_CAPITAL
    peak_equity = STARTING_CAPITAL
    max_drawdown = 0.0

    position = None
    trades = []

    last_exit_index = -10**9

    for i in range(1, len(df) - 1):

        candle = df.iloc[i]
        next_candle = df.iloc[i + 1]

        # ----------------------------------------------------
        # Manage an existing position
        # ----------------------------------------------------

        if position is not None:

            direction = position["direction"]
            stop = position["stop_loss"]
            target = position["take_profit"]

            exit_price = None
            exit_reason = None

            if direction == "LONG":

                if candle["open"] <= stop:
                    exit_price = float(candle["open"])
                    exit_reason = "STOP_LOSS_GAP"

                elif candle["open"] >= target:
                    exit_price = target
                    exit_reason = "TAKE_PROFIT_GAP"

                else:
                    stop_hit = candle["low"] <= stop
                    target_hit = candle["high"] >= target

                    # Conservative assumption:
                    # if both levels are touched, stop first.
                    if stop_hit:
                        exit_price = stop
                        exit_reason = "STOP_LOSS"

                    elif target_hit:
                        exit_price = target
                        exit_reason = "TAKE_PROFIT"

            else:

                if candle["open"] >= stop:
                    exit_price = float(candle["open"])
                    exit_reason = "STOP_LOSS_GAP"

                elif candle["open"] <= target:
                    exit_price = target
                    exit_reason = "TAKE_PROFIT_GAP"

                else:
                    stop_hit = candle["high"] >= stop
                    target_hit = candle["low"] <= target

                    if stop_hit:
                        exit_price = stop
                        exit_reason = "STOP_LOSS"

                    elif target_hit:
                        exit_price = target
                        exit_reason = "TAKE_PROFIT"

            if exit_price is not None:

                trade, balance = close_position(
                    position,
                    exit_price,
                    candle["timestamp"],
                    exit_reason,
                    balance
                )

                trades.append(trade)

                position = None
                last_exit_index = i

        # ----------------------------------------------------
        # Look for a new signal
        # ----------------------------------------------------

        if position is None:

            # V3: Wait after the last completed trade.
            if (
                variant == "V3_COOLDOWN"
                and i - last_exit_index <= COOLDOWN_CANDLES
            ):
                pass

            else:

                signal = evaluate(df, index=i)

                if signal is not None:

                    # V2: Require a higher signal score.
                    if (
                        variant == "V2_STRICT"
                        and signal.score < STRICT_MIN_SCORE
                    ):
                        signal = None

                if signal is not None:

                    direction = signal.direction

                    # Enter at the next candle's open.
                    raw_entry = float(next_candle["open"])

                    entry = apply_slippage(
                        raw_entry,
                        direction,
                        is_entry=True
                    )

                    if direction == "LONG":

                        stop_distance = (
                            signal.entry - signal.stop_loss
                        )

                        target_distance = (
                            signal.take_profit - signal.entry
                        )

                    else:

                        stop_distance = (
                            signal.stop_loss - signal.entry
                        )

                        target_distance = (
                            signal.entry - signal.take_profit
                        )

                    if stop_distance <= 0 or target_distance <= 0:
                        continue

                    risk_amount = balance * RISK_PER_TRADE

                    quantity = risk_amount / stop_distance

                    # Cap notional at available cash.
                    quantity = min(
                        quantity,
                        balance / entry
                    )

                    entry_fee = entry * quantity * FEE_RATE

                    if quantity <= 0 or entry_fee >= balance:
                        continue

                    # Preserve ATR distances from the original signal.
                    if direction == "LONG":

                        stop_loss = entry - stop_distance
                        take_profit = entry + target_distance

                    else:

                        stop_loss = entry + stop_distance
                        take_profit = entry - target_distance

                    position = {
                        "variant": variant,
                        "direction": direction,
                        "score": signal.score,
                        "entry_time": next_candle["timestamp"],
                        "entry": entry,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "quantity": quantity,
                        "entry_fee": entry_fee,
                    }

                    balance -= entry_fee

        # ----------------------------------------------------
        # Track marked-to-market equity
        # ----------------------------------------------------

        marked_equity = balance

        if position is not None:

            mark_price = float(candle["close"])

            if position["direction"] == "LONG":

                unrealized = (
                    mark_price - position["entry"]
                ) * position["quantity"]

            else:

                unrealized = (
                    position["entry"] - mark_price
                ) * position["quantity"]

            estimated_exit_fee = (
                mark_price
                * position["quantity"]
                * FEE_RATE
            )

            marked_equity += unrealized - estimated_exit_fee

        peak_equity = max(
            peak_equity,
            marked_equity
        )

        if peak_equity > 0:

            drawdown = (
                peak_equity - marked_equity
            ) / peak_equity

            max_drawdown = max(
                max_drawdown,
                drawdown
            )

    # --------------------------------------------------------
    # Close any remaining position at the end of the test
    # --------------------------------------------------------

    if position is not None:

        last = df.iloc[-1]

        trade, balance = close_position(
            position,
            float(last["close"]),
            last["timestamp"],
            "END_OF_TEST",
            balance
        )

        trades.append(trade)

    # --------------------------------------------------------
    # Calculate metrics
    # --------------------------------------------------------

    trades_df = pd.DataFrame(trades)

    if trades_df.empty:

        wins = 0
        losses = 0
        win_rate = 0.0
        profit_factor = 0.0
        avg_trade = 0.0
        fees = 0.0

    else:

        wins_df = trades_df[
            trades_df["net_pnl"] > 0
        ]

        losses_df = trades_df[
            trades_df["net_pnl"] < 0
        ]

        wins = len(wins_df)
        losses = len(losses_df)

        win_rate = (
            wins / len(trades_df) * 100
        )

        gross_wins = wins_df["net_pnl"].sum()

        gross_losses = abs(
            losses_df["net_pnl"].sum()
        )

        profit_factor = (
            gross_wins / gross_losses
            if gross_losses > 0
            else float("inf")
        )

        avg_trade = trades_df["net_pnl"].mean()

        fees = trades_df["total_fees"].sum()

    result = {
        "variant": variant,
        "starting_capital": STARTING_CAPITAL,
        "final_balance": balance,
        "net_pnl": balance - STARTING_CAPITAL,
        "return_pct": (
            balance / STARTING_CAPITAL - 1
        ) * 100,
        "trades": len(trades_df),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "average_trade": avg_trade,
        "total_fees": fees,
        "max_drawdown_pct": max_drawdown * 100,
    }

    return result, trades_df


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("MACD CONFLUENCE - THREE VARIANT COMPARISON")
    print("=" * 70)

    raw_df = fetch_historical_data()

    print("\nPreparing indicators...")

    df = prepare_indicators(raw_df.copy())

    variants = [
        "V1_BASELINE",
        "V2_STRICT",
        "V3_COOLDOWN",
    ]

    results = []
    all_trades = []

    for variant in variants:

        print("\n" + "-" * 70)
        print(f"Running {variant}")
        print("-" * 70)

        result, trades_df = run_variant(
            df,
            variant
        )

        results.append(result)

        if not trades_df.empty:
            all_trades.append(trades_df)

        print(f"Final balance: ${result['final_balance']:.2f}")
        print(f"Net PNL:       ${result['net_pnl']:.2f}")
        print(f"Return:        {result['return_pct']:.2f}%")
        print(f"Trades:        {result['trades']}")
        print(f"Win rate:      {result['win_rate_pct']:.2f}%")
        print(f"Profit factor: {result['profit_factor']:.3f}")
        print(f"Fees:          ${result['total_fees']:.2f}")
        print(f"Max drawdown:  {result['max_drawdown_pct']:.2f}%")

    # --------------------------------------------------------
    # Save results
    # --------------------------------------------------------

    results_df = pd.DataFrame(results)

    results_df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    if all_trades:

        trades_output = pd.concat(
            all_trades,
            ignore_index=True
        )

    else:

        trades_output = pd.DataFrame()

    trades_output.to_csv(
        TRADES_FILE,
        index=False
    )

    print("\n" + "=" * 70)
    print("FINAL COMPARISON")
    print("=" * 70)

    print(
        results_df.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}"
        )
    )

    print("\nFiles created:")
    print(f"- {OUTPUT_FILE}")
    print(f"- {TRADES_FILE}")

    print("\nHistorical simulation only. No real orders placed.")


if __name__ == "__main__":
    main()