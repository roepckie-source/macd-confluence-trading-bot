
"""
MACD CONFLUENCE TRADING BOT
Backtest V2 - Loss Analysis

Historical simulation only.
No API keys, wallet or real orders.
"""

import numpy as np
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

TRADES_FILE = "backtest_v2_trades.csv"
EQUITY_FILE = "backtest_v2_equity.csv"
SCORE_FILE = "backtest_v2_scores.csv"
SUMMARY_FILE = "backtest_v2_summary.txt"


# ============================================================
# HELPERS
# ============================================================

def apply_slippage(price, direction, is_entry):
    """Apply conservative simulated execution slippage."""

    if direction == "LONG":
        adverse = is_entry
    else:
        adverse = not is_entry

    if adverse:
        return price * (1 + SLIPPAGE_RATE)

    return price * (1 - SLIPPAGE_RATE)


def close_trade(position, raw_exit, timestamp, reason, balance):
    """Close a simulated position and calculate net PNL."""

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
        "entry_time": position["entry_time"],
        "exit_time": timestamp,
        "direction": direction,
        "score": position["score"],
        "reason": position["signal_reason"],
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
# BACKTEST
# ============================================================

def run_backtest_v2(raw_df):
    df = prepare_indicators(raw_df.copy())

    if len(df) < 250:
        raise ValueError("Not enough candles for EMA 200.")

    balance = STARTING_CAPITAL
    peak_equity = STARTING_CAPITAL
    max_drawdown = 0.0

    position = None
    trades = []
    equity_rows = []
    signal_rows = []

    print("\nStarting Backtest V2")
    print(f"Candles: {len(df):,}")
    print(f"Starting capital: ${balance:.2f}")

    # A signal at candle i is entered at candle i+1 open.
    for i in range(1, len(df) - 1):
        candle = df.iloc[i]
        next_candle = df.iloc[i + 1]

        # ----------------------------------------------------
        # 1. Manage any existing position
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

                    # Conservative assumption if both levels
                    # are touched in the same candle.
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
                trade, balance = close_trade(
                    position,
                    exit_price,
                    candle["timestamp"],
                    exit_reason,
                    balance
                )

                trades.append(trade)

                print(
                    f"CLOSED {trade['direction']:5s} | "
                    f"Score {trade['score']:3d} | "
                    f"Net ${trade['net_pnl']:8.2f} | "
                    f"{exit_reason}"
                )

                position = None

        # ----------------------------------------------------
        # 2. Search for new signal if flat
        # ----------------------------------------------------

        if position is None:
            signal = evaluate(df, index=i)

            if signal is not None:
                direction = signal.direction

                signal_rows.append({
                    "timestamp": candle["timestamp"],
                    "direction": direction,
                    "score": signal.score,
                    "reason": signal.reason,
                    "signal_close": float(candle["close"]),
                })

                raw_entry = float(next_candle["open"])

                if direction == "LONG":
                    entry = apply_slippage(
                        raw_entry, direction, is_entry=True
                    )
                    stop_distance = signal.entry - signal.stop_loss
                    target_distance = signal.take_profit - signal.entry
                else:
                    entry = apply_slippage(
                        raw_entry, direction, is_entry=True
                    )
                    stop_distance = signal.stop_loss - signal.entry
                    target_distance = signal.entry - signal.take_profit

                if stop_distance <= 0 or target_distance <= 0:
                    continue

                risk_amount = balance * RISK_PER_TRADE
                quantity = risk_amount / stop_distance

                # Cap simulated notional at available balance.
                # SHORTs are simulations, not real spot orders.
                quantity = min(quantity, balance / entry)

                entry_fee = entry * quantity * FEE_RATE

                if quantity <= 0 or entry_fee >= balance:
                    continue

                if direction == "LONG":
                    stop_loss = entry - stop_distance
                    take_profit = entry + target_distance
                else:
                    stop_loss = entry + stop_distance
                    take_profit = entry - target_distance

                position = {
                    "direction": direction,
                    "entry_time": next_candle["timestamp"],
                    "entry": entry,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "quantity": quantity,
                    "entry_fee": entry_fee,
                    "score": signal.score,
                    "signal_reason": signal.reason,
                }

                balance -= entry_fee

        # ----------------------------------------------------
        # 3. Track marked-to-market equity and drawdown
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
                mark_price * position["quantity"] * FEE_RATE
            )

            marked_equity += unrealized - estimated_exit_fee

        peak_equity = max(peak_equity, marked_equity)

        drawdown = (
            (peak_equity - marked_equity) / peak_equity
            if peak_equity > 0 else 0.0
        )

        max_drawdown = max(max_drawdown, drawdown)

        equity_rows.append({
            "timestamp": candle["timestamp"],
            "cash_balance": balance,
            "marked_equity": marked_equity,
            "drawdown_pct": drawdown * 100,
            "position": (
                position["direction"] if position else "NONE"
            ),
        })

    # --------------------------------------------------------
    # 4. Close open position at end of test
    # --------------------------------------------------------

    if position is not None:
        last = df.iloc[-1]

        trade, balance = close_trade(
            position,
            float(last["close"]),
            last["timestamp"],
            "END_OF_TEST",
            balance
        )

        trades.append(trade)
        position = None

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_rows)
    signals_df = pd.DataFrame(signal_rows)

    trades_df.to_csv(TRADES_FILE, index=False)
    equity_df.to_csv(EQUITY_FILE, index=False)
    signals_df.to_csv(SCORE_FILE, index=False)

    # ========================================================
    # 5. Statistical analysis
    # ========================================================

    total_pnl = balance - STARTING_CAPITAL
    return_pct = total_pnl / STARTING_CAPITAL * 100

    if not trades_df.empty:
        wins_df = trades_df[trades_df["net_pnl"] > 0]
        losses_df = trades_df[trades_df["net_pnl"] <= 0]

        wins = len(wins_df)
        losses = len(losses_df)
        count = len(trades_df)

        win_rate = wins / count * 100

        gross_wins = wins_df["net_pnl"].sum()
        gross_losses = abs(
            trades_df.loc[
                trades_df["net_pnl"] < 0, "net_pnl"
            ].sum()
        )

        profit_factor = (
            gross_wins / gross_losses
            if gross_losses > 0 else float("inf")
        )

        avg_win = (
            wins_df["net_pnl"].mean() if wins else 0.0
        )
        avg_loss = (
            losses_df["net_pnl"].mean() if losses else 0.0
        )

        total_fees = trades_df["total_fees"].sum()

        reason_stats = trades_df.groupby(
            "exit_reason"
        ).agg(
            trades=("net_pnl", "size"),
            net_pnl=("net_pnl", "sum"),
            average_pnl=("net_pnl", "mean"),
        )

        direction_stats = trades_df.groupby(
            "direction"
        ).agg(
            trades=("net_pnl", "size"),
            win_rate=("net_pnl", lambda s: (s > 0).mean() * 100),
            net_pnl=("net_pnl", "sum"),
            average_pnl=("net_pnl", "mean"),
        )

        score_stats = trades_df.groupby(
            pd.cut(
                trades_df["score"],
                bins=[0, 69, 74, 84, 100],
                labels=["Below 70", "70-74", "75-84", "85-100"],
                include_lowest=True
            ),
            observed=False
        ).agg(
            trades=("net_pnl", "size"),
            win_rate=("net_pnl", lambda s: (s > 0).mean() * 100),
            net_pnl=("net_pnl", "sum"),
            average_pnl=("net_pnl", "mean"),
        )

    else:
        wins = losses = count = 0
        win_rate = avg_win = avg_loss = 0.0
        profit_factor = 0.0
        total_fees = 0.0

        reason_stats = pd.DataFrame()
        direction_stats = pd.DataFrame()
        score_stats = pd.DataFrame()

    # ========================================================
    # 6. Print report
    # ========================================================

    lines = [
        "=" * 70,
        "MACD CONFLUENCE BACKTEST V2",
        "=" * 70,
        f"Candles:           {len(df):,}",
        f"First candle:      {df['timestamp'].iloc[0]}",
        f"Last candle:       {df['timestamp'].iloc[-1]}",
        f"Starting capital:  ${STARTING_CAPITAL:.2f}",
        f"Final balance:     ${balance:.2f}",
        f"Net PNL:           ${total_pnl:.2f}",
        f"Return:            {return_pct:.2f}%",
        f"Closed trades:     {count}",
        f"Winning trades:    {wins}",
        f"Losing trades:     {losses}",
        f"Win rate:          {win_rate:.2f}%",
        f"Profit factor:     {profit_factor:.3f}",
        f"Average winner:    ${avg_win:.2f}",
        f"Average loser:     ${avg_loss:.2f}",
        f"Total fees:        ${total_fees:.2f}",
        f"Max drawdown:      {max_drawdown * 100:.2f}%",
        "",
        "EXIT REASON ANALYSIS",
        str(reason_stats),
        "",
        "LONG / SHORT ANALYSIS",
        str(direction_stats),
        "",
        "SIGNAL SCORE ANALYSIS",
        str(score_stats),
        "",
        f"Signals logged: {len(signals_df)}",
        "No real orders were placed.",
    ]

    report = "\n".join(lines)

    print("\n" + report)

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print("\nCreated output files:")
    print(f"- {TRADES_FILE}")
    print(f"- {EQUITY_FILE}")
    print(f"- {SCORE_FILE}")
    print(f"- {SUMMARY_FILE}")


if __name__ == "__main__":
    candles = fetch_historical_data()
    run_backtest_v2(candles)
