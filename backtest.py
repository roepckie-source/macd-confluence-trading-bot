
"""
MACD CONFLUENCE TRADING BOT
Historical Backtest V1

Paper trading / historical simulation only.
No API keys, wallet or real orders.
"""

import time
import requests
import pandas as pd
import numpy as np

from datetime import datetime, timedelta, timezone

from strategy import prepare_indicators, evaluate


# ============================================================
# CONFIGURATION
# ============================================================

PRODUCT = "BTC-USD"
GRANULARITY = 900             # 15-minute candles
MONTHS_BACK = 6

STARTING_CAPITAL = 1000.0
RISK_PER_TRADE = 0.01         # 1% risk budget
FEE_RATE = 0.001              # 0.10% per side
SLIPPAGE_RATE = 0.0005        # 0.05% per side

OUTPUT_TRADES = "backtest_trades.csv"
OUTPUT_EQUITY = "backtest_equity.csv"

API_URL = (
    "https://api.exchange.coinbase.com"
    f"/products/{PRODUCT}/candles"
)


# ============================================================
# HISTORICAL DATA
# ============================================================

def fetch_historical_data():
    """Download historical candles in chunks within API limits."""

    end_time = datetime.now(timezone.utc).replace(
        second=0, microsecond=0
    )
    start_time = end_time - timedelta(days=MONTHS_BACK * 30)

    print("=" * 70)
    print("MACD CONFLUENCE - HISTORICAL BACKTEST")
    print("=" * 70)
    print(f"Product: {PRODUCT}")
    print(f"Timeframe: {GRANULARITY // 60} minutes")
    print(f"From: {start_time.isoformat()}")
    print(f"To:   {end_time.isoformat()}")
    print("Downloading historical candles...")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "MACD-Confluence-Paper-Backtest/1.0",
        "Accept": "application/json",
    })

    # Use chunks smaller than Coinbase's maximum candle window.
    chunk_seconds = GRANULARITY * 250
    cursor = start_time
    all_rows = []

    while cursor < end_time:
        chunk_end = min(
            cursor + timedelta(seconds=chunk_seconds),
            end_time
        )

        params = {
            "granularity": GRANULARITY,
            "start": cursor.isoformat(),
            "end": chunk_end.isoformat(),
        }

        response = None

        for attempt in range(5):
            try:
                response = session.get(
                    API_URL,
                    params=params,
                    timeout=30
                )

                if response.status_code == 429:
                    time.sleep(2 * (attempt + 1))
                    continue

                response.raise_for_status()
                break

            except requests.RequestException as exc:
                if attempt == 4:
                    raise RuntimeError(
                        f"Coinbase download failed: {exc}"
                    ) from exc
                time.sleep(2 * (attempt + 1))

        if response is None or response.status_code != 200:
            raise RuntimeError(
                "Could not download a historical data chunk."
            )

        rows = response.json()

        if not isinstance(rows, list):
            raise RuntimeError(
                f"Unexpected Coinbase response: {rows}"
            )

        all_rows.extend(rows)

        cursor = chunk_end
        time.sleep(0.25)

    if not all_rows:
        raise RuntimeError("No historical candles received.")

    # Coinbase candle format:
    # [time, low, high, open, close, volume]
    df = pd.DataFrame(
        all_rows,
        columns=[
            "timestamp", "low", "high",
            "open", "close", "volume"
        ]
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"], unit="s", utc=True
    )

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = (
        df.dropna()
        .drop_duplicates(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    # Keep only candles within the requested period.
    df = df[
        (df["timestamp"] >= pd.Timestamp(start_time))
        & (df["timestamp"] < pd.Timestamp(end_time))
    ].copy()

    # Exclude the latest potentially unfinished candle.
    latest_open = df["timestamp"].iloc[-1]
    now = pd.Timestamp.now(tz="UTC")

    if now < latest_open + pd.Timedelta(seconds=GRANULARITY):
        df = df.iloc[:-1].copy()

    df = df.reset_index(drop=True)

    if len(df) < 500:
        raise RuntimeError(
            f"Too few candles received: {len(df)}. "
            "Check the API response and date range."
        )

    print(f"Downloaded candles: {len(df):,}")
    print(f"First candle: {df['timestamp'].iloc[0]}")
    print(f"Last candle:  {df['timestamp'].iloc[-1]}")

    return df


# ============================================================
# BACKTEST ENGINE
# ============================================================

def run_backtest(df):
    """Run the existing strategy against historical candles."""

    df = prepare_indicators(df)

    balance = STARTING_CAPITAL
    peak_equity = STARTING_CAPITAL
    max_drawdown = 0.0

    position = None
    trades = []
    equity_rows = []

    # Evaluate each candle using indicators calculated from
    # current and previous data only. Enter at the NEXT open.
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
                # Conservative gap handling.
                if candle["open"] <= stop:
                    exit_price = candle["open"]
                    exit_reason = "STOP_LOSS_GAP"
                elif candle["open"] >= target:
                    exit_price = target
                    exit_reason = "TAKE_PROFIT"
                else:
                    stop_hit = candle["low"] <= stop
                    target_hit = candle["high"] >= target

                    # If both are hit in one candle, assume SL first.
                    if stop_hit:
                        exit_price = stop
                        exit_reason = "STOP_LOSS"
                    elif target_hit:
                        exit_price = target
                        exit_reason = "TAKE_PROFIT"

            else:  # SHORT
                if candle["open"] >= stop:
                    exit_price = candle["open"]
                    exit_reason = "STOP_LOSS_GAP"
                elif candle["open"] <= target:
                    exit_price = target
                    exit_reason = "TAKE_PROFIT"
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
                if direction == "LONG":
                    fill_exit = exit_price * (1 - SLIPPAGE_RATE)
                    gross_pnl = (
                        fill_exit - position["entry"]
                    ) * position["quantity"]
                else:
                    fill_exit = exit_price * (1 + SLIPPAGE_RATE)
                    gross_pnl = (
                        position["entry"] - fill_exit
                    ) * position["quantity"]

                exit_fee = (
                    fill_exit * position["quantity"] * FEE_RATE
                )

                net_pnl = (
                    gross_pnl
                    - position["entry_fee"]
                    - exit_fee
                )

                balance += gross_pnl - exit_fee

                trades.append({
                    "entry_time": position["entry_time"],
                    "exit_time": candle["timestamp"],
                    "direction": direction,
                    "score": position["score"],
                    "entry": position["entry"],
                    "exit": fill_exit,
                    "stop_loss": position["stop_loss"],
                    "take_profit": position["take_profit"],
                    "quantity": position["quantity"],
                    "gross_pnl": gross_pnl,
                    "entry_fee": position["entry_fee"],
                    "exit_fee": exit_fee,
                    "net_pnl": net_pnl,
                    "exit_reason": exit_reason,
                    "balance": balance,
                })

                print(
                    f"EXIT {direction:5s} | "
                    f"{candle['timestamp']} | "
                    f"Net PNL: ${net_pnl:.2f} | "
                    f"Balance: ${balance:.2f} | "
                    f"{exit_reason}"
                )

                position = None

        # ----------------------------------------------------
        # Look for a new signal only when flat
        # ----------------------------------------------------

        if position is None:
            signal = evaluate(df, index=i)

            if signal is not None:
                direction = signal.direction

                # Entry is at the next candle's open, not
                # the signal candle's close.
                raw_entry = float(next_candle["open"])

                if direction == "LONG":
                    entry = raw_entry * (1 + SLIPPAGE_RATE)
                    stop_distance = (
                        signal.entry - signal.stop_loss
                    )
                    target_distance = (
                        signal.take_profit - signal.entry
                    )
                else:
                    entry = raw_entry * (1 - SLIPPAGE_RATE)
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

                # Conservative spot-style notional cap.
                # Short trades remain simulations only.
                max_notional = balance
                quantity = min(quantity, max_notional / entry)

                entry_fee = entry * quantity * FEE_RATE

                # Re-anchor SL and TP around the actual simulated
                # entry while preserving the strategy's ATR distances.
                if direction == "LONG":
                    stop_loss = entry - stop_distance
                    take_profit = entry + target_distance
                else:
                    stop_loss = entry + stop_distance
                    take_profit = entry - target_distance

                # Avoid positions that cannot cover entry fees.
                if quantity <= 0 or entry_fee >= balance:
                    continue

                position = {
                    "direction": direction,
                    "entry_time": next_candle["timestamp"],
                    "entry": entry,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "quantity": quantity,
                    "entry_fee": entry_fee,
                    "score": signal.score,
                }

                # Deduct entry fee immediately.
                balance -= entry_fee

                print(
                    f"ENTRY {direction:5s} | "
                    f"{next_candle['timestamp']} | "
                    f"Score: {signal.score} | "
                    f"Price: ${entry:.2f} | "
                    f"SL: ${stop_loss:.2f} | "
                    f"TP: ${take_profit:.2f}"
                )

        # ----------------------------------------------------
        # Track realized equity and drawdown
        # ----------------------------------------------------

        equity_rows.append({
            "timestamp": candle["timestamp"],
            "balance": balance,
            "position": (
                position["direction"] if position else "NONE"
            ),
        })

        peak_equity = max(peak_equity, balance)
        drawdown = (
            (peak_equity - balance) / peak_equity
            if peak_equity > 0 else 0
        )
        max_drawdown = max(max_drawdown, drawdown)

    # Close any remaining position at the final available close.
    if position is not None:
        last = df.iloc[-1]
        raw_exit = float(last["close"])

        if position["direction"] == "LONG":
            fill_exit = raw_exit * (1 - SLIPPAGE_RATE)
            gross_pnl = (
                fill_exit - position["entry"]
            ) * position["quantity"]
        else:
            fill_exit = raw_exit * (1 + SLIPPAGE_RATE)
            gross_pnl = (
                position["entry"] - fill_exit
            ) * position["quantity"]

        exit_fee = fill_exit * position["quantity"] * FEE_RATE
        net_pnl = (
            gross_pnl - position["entry_fee"] - exit_fee
        )
        balance += gross_pnl - exit_fee

        trades.append({
            "entry_time": position["entry_time"],
            "exit_time": last["timestamp"],
            "direction": position["direction"],
            "score": position["score"],
            "entry": position["entry"],
            "exit": fill_exit,
            "stop_loss": position["stop_loss"],
            "take_profit": position["take_profit"],
            "quantity": position["quantity"],
            "gross_pnl": gross_pnl,
            "entry_fee": position["entry_fee"],
            "exit_fee": exit_fee,
            "net_pnl": net_pnl,
            "exit_reason": "END_OF_TEST",
            "balance": balance,
        })

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_rows)

    trades_df.to_csv(OUTPUT_TRADES, index=False)
    equity_df.to_csv(OUTPUT_EQUITY, index=False)

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)

    total_pnl = balance - STARTING_CAPITAL
    return_pct = total_pnl / STARTING_CAPITAL * 100

    if not trades_df.empty:
        wins = int((trades_df["net_pnl"] > 0).sum())
        losses = int((trades_df["net_pnl"] <= 0).sum())
        win_rate = wins / len(trades_df) * 100

        gross_wins = trades_df.loc[
            trades_df["net_pnl"] > 0, "net_pnl"
        ].sum()

        gross_losses = abs(trades_df.loc[
            trades_df["net_pnl"] < 0, "net_pnl"
        ].sum())

        profit_factor = (
            gross_wins / gross_losses
            if gross_losses > 0 else float("inf")
        )

        avg_trade = trades_df["net_pnl"].mean()
        total_fees = (
            trades_df["entry_fee"].sum()
            + trades_df["exit_fee"].sum()
        )
    else:
        wins = losses = 0
        win_rate = 0.0
        profit_factor = 0.0
        avg_trade = 0.0
        total_fees = 0.0

    print(f"Starting capital:  ${STARTING_CAPITAL:,.2f}")
    print(f"Final balance:    ${balance:,.2f}")
    print(f"Net PNL:          ${total_pnl:,.2f}")
    print(f"Return:           {return_pct:.2f}%")
    print(f"Closed trades:    {len(trades_df)}")
    print(f"Winning trades:   {wins}")
    print(f"Losing trades:    {losses}")
    print(f"Win rate:         {win_rate:.2f}%")
    print(f"Profit factor:    {profit_factor:.2f}")
    print(f"Average trade:    ${avg_trade:.2f}")
    print(f"Fees paid:        ${total_fees:.2f}")
    print(f"Max drawdown:     {max_drawdown * 100:.2f}%")

    print("\nFiles created:")
    print(f"- {OUTPUT_TRADES}")
    print(f"- {OUTPUT_EQUITY}")

    if len(trades_df) == 0:
        print(
            "\nWARNING: No trades were closed. "
            "Do not interpret this as evidence of profitability."
        )

    print("\nHistorical simulation only. No real orders placed.")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    candles = fetch_historical_data()
    run_backtest(candles)
