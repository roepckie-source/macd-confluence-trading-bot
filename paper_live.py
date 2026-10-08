"""
MACD CONFLUENCE TRADING BOT
PAPER LIVE V2

Real public BTC market data
Paper trading only

NO API KEYS
NO WALLET
NO REAL ORDERS

Strategy:
- MACD 12/26/9
- EMA 200 High/Close/Low
- Zero-line pullback
- MACD momentum turn
- Breakout confirmation
- ATR Stop Loss
- ATR Take Profit
- 1% risk per trade
"""

import json
import os
import time
from datetime import datetime, timezone

from market_data import get_btc_candles
from strategy import prepare_indicators, evaluate
from paper_trader import PaperTrader


# ============================================================
# CONFIGURATION
# ============================================================

SYMBOL = "BTC/USDT"

TIMEFRAME = "15m"

STARTING_BALANCE = 1000.00

CHECK_INTERVAL_SECONDS = 60

MIN_SCORE = 70

# Run continuously until manually stopped.
# Set to 120 for a 2-hour test.
MAX_RUNTIME_MINUTES = 120

STATE_FILE = "paper_state.json"

TRADE_LOG_FILE = "paper_trades.json"


# ============================================================
# TIME
# ============================================================

def utc_now():
    return datetime.now(
        timezone.utc
    )


def utc_string():
    return utc_now().strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


# ============================================================
# STATE
# ============================================================

def save_state(trader):

    data = {
        "balance": trader.balance,
        "starting_balance": trader.starting_balance,
        "total_fees": trader.total_fees,
        "winning_trades": trader.winning_trades,
        "losing_trades": trader.losing_trades,
    }

    if trader.position is not None:

        position = trader.position

        data["position"] = {
            "symbol": position.symbol,
            "direction": position.direction,
            "entry": position.entry,
            "quantity": position.quantity,
            "stop_loss": position.stop_loss,
            "take_profit": position.take_profit,
            "entry_fee": position.entry_fee,
            "entry_time": position.entry_time,
        }

    else:

        data["position"] = None

    try:

        with open(
            STATE_FILE,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                indent=2,
            )

    except Exception as error:

        print(
            f"WARNING: Could not save state: "
            f"{error}"
        )


# ============================================================
# TRADE LOG
# ============================================================

def save_trade(result):

    trade = {
        "timestamp": utc_string(),
        "symbol": result.symbol,
        "direction": result.direction,
        "entry": result.entry,
        "exit": result.exit,
        "quantity": result.quantity,
        "gross_pnl": result.gross_pnl,
        "fees": result.fees,
        "net_pnl": result.net_pnl,
        "reason": result.reason,
        "balance_after": result.balance_after,
    }

    trades = []

    if os.path.exists(TRADE_LOG_FILE):

        try:

            with open(
                TRADE_LOG_FILE,
                "r",
                encoding="utf-8",
            ) as file:

                trades = json.load(file)

                if not isinstance(
                    trades,
                    list,
                ):
                    trades = []

        except Exception:

            trades = []

    trades.append(trade)

    try:

        with open(
            TRADE_LOG_FILE,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                trades,
                file,
                indent=2,
            )

    except Exception as error:

        print(
            f"WARNING: Could not save trade: "
            f"{error}"
        )


# ============================================================
# STATUS
# ============================================================

def print_status(
    df,
    trader,
    signal,
    candle_time,
):

    latest = df.iloc[-1]

    stats = trader.statistics()

    print()
    print("=" * 72)
    print("MACD CONFLUENCE PAPER LIVE V2")
    print("=" * 72)

    print(
        f"UTC:             {utc_string()}"
    )

    print(
        f"Symbol:          {SYMBOL}"
    )

    print(
        f"Timeframe:       {TIMEFRAME}"
    )

    print(
        f"Candle:          {candle_time}"
    )

    print(
        f"BTC Price:       "
        f"${latest['close']:,.2f}"
    )

    print()
    print("--- MACD ---")

    print(
        f"MACD:            "
        f"{latest['macd']:.4f}"
    )

    print(
        f"Signal:          "
        f"{latest['macd_signal']:.4f}"
    )

    print(
        f"Histogram:       "
        f"{latest['macd_hist']:.4f}"
    )

    print()
    print("--- EMA 200 BAND ---")

    print(
        f"EMA High:        "
        f"${latest['ema_high']:,.2f}"
    )

    print(
        f"EMA Close:       "
        f"${latest['ema_close']:,.2f}"
    )

    print(
        f"EMA Low:         "
        f"${latest['ema_low']:,.2f}"
    )

    print()
    print("--- ATR ---")

    print(
        f"ATR:             "
        f"${latest['atr']:,.2f}"
    )

    print()
    print("--- SIGNAL ---")

    if signal is None:

        print(
            "Signal:          NONE"
        )

    else:

        print(
            f"Signal:          "
            f"{signal.direction}"
        )

        print(
            f"Score:           "
            f"{signal.score}/100"
        )

        print(
            f"Entry:           "
            f"${signal.entry:,.2f}"
        )

        print(
            f"Stop Loss:       "
            f"${signal.stop_loss:,.2f}"
        )

        print(
            f"Take Profit:     "
            f"${signal.take_profit:,.2f}"
        )

        print(
            f"Reason:          "
            f"{signal.reason}"
        )

    print()
    print("--- POSITION ---")

    if trader.position is None:

        print(
            "Position:        NONE"
        )

    else:

        position = trader.position

        print(
            f"Position:        "
            f"{position.direction}"
        )

        print(
            f"Entry:           "
            f"${position.entry:,.2f}"
        )

        print(
            f"Quantity:        "
            f"{position.quantity:.8f}"
        )

        print(
            f"Stop Loss:       "
            f"${position.stop_loss:,.2f}"
        )

        print(
            f"Take Profit:     "
            f"${position.take_profit:,.2f}"
        )

    print()
    print("--- ACCOUNT ---")

    print(
        f"Start Balance:   "
        f"${stats['starting_balance']:,.2f}"
    )

    print(
        f"Current Balance: "
        f"${stats['current_balance']:,.2f}"
    )

    print(
        f"Total PNL:       "
        f"${stats['total_pnl']:,.2f}"
    )

    print(
        f"Return:          "
        f"{stats['total_return_percent']:.2f}%"
    )

    print(
        f"Trades:          "
        f"{stats['trades']}"
    )

    print(
        f"Winners:         "
        f"{stats['winning_trades']}"
    )

    print(
        f"Losers:          "
        f"{stats['losing_trades']}"
    )

    print(
        f"Win Rate:        "
        f"{stats['win_rate']:.2f}%"
    )

    print(
        f"Fees:            "
        f"${stats['total_fees']:.4f}"
    )

    print("=" * 72)


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 72)
    print("MACD CONFLUENCE TRADING BOT")
    print("PAPER LIVE V2")
    print("=" * 72)

    print()
    print("MODE:             PAPER ONLY")
    print("API KEYS:         NONE")
    print("WALLET:           NONE")
    print("REAL ORDERS:      DISABLED")
    print(f"SYMBOL:           {SYMBOL}")
    print(f"TIMEFRAME:        {TIMEFRAME}")
    print(
        f"STARTING BALANCE: "
        f"${STARTING_BALANCE:.2f}"
    )
    print(
        f"MAX RUNTIME:      "
        f"{MAX_RUNTIME_MINUTES} minutes"
    )
    print()

    trader = PaperTrader(
        starting_balance=STARTING_BALANCE
    )

    start_time = time.time()

    last_closed_candle = None

    total_cycles = 0

    total_new_candles = 0

    while True:

        # ====================================================
        # RUNTIME LIMIT
        # ====================================================

        elapsed_seconds = (
            time.time() -
            start_time
        )

        elapsed_minutes = (
            elapsed_seconds /
            60
        )

        if (
            MAX_RUNTIME_MINUTES > 0
            and
            elapsed_minutes >=
            MAX_RUNTIME_MINUTES
        ):

            print()
            print(
                "=" * 72
            )

            print(
                "MAX RUNTIME REACHED"
            )

            print(
                f"Runtime: "
                f"{elapsed_minutes:.2f} minutes"
            )

            print(
                "=" * 72
            )

            trader.print_statistics()

            save_state(
                trader
            )

            break

        try:

            total_cycles += 1

            # =================================================
            # DOWNLOAD MARKET DATA
            # =================================================

            df = get_btc_candles()

            if df.empty:

                print(
                    "WARNING: No market data."
                )

                time.sleep(
                    CHECK_INTERVAL_SECONDS
                )

                continue

            # =================================================
            # IMPORTANT:
            # Ignore the currently forming candle.
            #
            # Coinbase returns the latest candle,
            # which may not yet be closed.
            #
            # We therefore use [-2] as the latest
            # completed candle.
            # =================================================

            if len(df) < 3:

                print(
                    "WARNING: Not enough candles."
                )

                time.sleep(
                    CHECK_INTERVAL_SECONDS
                )

                continue

            closed_df = df.iloc[:-1].copy()

            closed_df = (
                closed_df
                .reset_index(
                    drop=True
                )
            )

            # =================================================
            # INDICATORS
            # =================================================

            closed_df = prepare_indicators(
                closed_df
            )

            candle_time = (
                closed_df.iloc[-1][
                    "timestamp"
                ]
            )

            # =================================================
            # CHECK CURRENT PRICE
            #
            # Use latest available candle close
            # for paper position monitoring.
            # =================================================

            current_price = float(
                df.iloc[-1]["close"]
            )

            # =================================================
            # CHECK EXISTING POSITION
            # =================================================

            result = trader.check_position(
                current_price=current_price,
                timestamp=utc_string(),
            )

            if result is not None:

                print()
                print(
                    "PAPER POSITION CLOSED"
                )

                save_trade(
                    result
                )

                save_state(
                    trader
                )

            # =================================================
            # NEW CLOSED CANDLE?
            # =================================================

            new_candle = (
                candle_time
                != last_closed_candle
            )

            signal = None

            if new_candle:

                last_closed_candle = (
                    candle_time
                )

                total_new_candles += 1

                print()
                print(
                    "=" * 72
                )

                print(
                    "NEW CLOSED 15-MINUTE CANDLE"
                )

                print(
                    f"Time: {candle_time}"
                )

                print(
                    "=" * 72
                )

                # =============================================
                # STRATEGY
                # =============================================

                signal = evaluate(
                    closed_df
                )

                # =============================================
                # SIGNAL
                # =============================================

                if signal is None:

                    print(
                        "No trading signal."
                    )

                else:

                    print(
                        f"Signal detected: "
                        f"{signal.direction}"
                    )

                    print(
                        f"Score: "
                        f"{signal.score}/100"
                    )

                    print(
                        f"Reason: "
                        f"{signal.reason}"
                    )

                    # =========================================
                    # OPEN PAPER TRADE
                    # =========================================

                    if (
                        signal.score >= MIN_SCORE
                        and
                        trader.position is None
                    ):

                        opened = (
                            trader.open_position(
                                symbol=SYMBOL,
                                signal=signal,
                                timestamp=str(
                                    candle_time
                                ),
                            )
                        )

                        if opened:

                            save_state(
                                trader
                            )

                    elif (
                        trader.position is not None
                    ):

                        print(
                            "Signal ignored: "
                            "position already open."
                        )

            # =================================================
            # STATUS
            # =================================================

            print_status(
                closed_df,
                trader,
                signal,
                candle_time,
            )

            print()
            print(
                f"Cycle: "
                f"{total_cycles}"
            )

            print(
                f"New candles: "
                f"{total_new_candles}"
            )

            print(
                f"Runtime: "
                f"{elapsed_minutes:.1f} min"
            )

            print()
            print(
                f"Next check in "
                f"{CHECK_INTERVAL_SECONDS} seconds..."
            )

            time.sleep(
                CHECK_INTERVAL_SECONDS
            )

        except KeyboardInterrupt:

            print()
            print(
                "=" * 72
            )

            print(
                "PAPER TRADER STOPPED"
            )

            print(
                "=" * 72
            )

            trader.print_statistics()

            save_state(
                trader
            )

            break

        except Exception as error:

            print()
            print(
                "=" * 72
            )

            print(
                "ERROR"
            )

            print(
                str(error)
            )

            print(
                "The bot will retry."
            )

            print(
                "=" * 72
            )

            time.sleep(
                CHECK_INTERVAL_SECONDS
            )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()