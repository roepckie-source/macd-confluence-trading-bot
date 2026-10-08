"""
MACD CONFLUENCE TRADING BOT
Paper Live V1

LIVE MARKET DATA
PAPER TRADING ONLY

No API keys
No wallet
No real orders
"""

import time
from datetime import datetime, timezone

from market_data import (
    get_btc_candles,
)

from strategy import (
    prepare_indicators,
    evaluate,
)

from paper_trader import (
    PaperTrader,
)


# ============================================================
# CONFIGURATION
# ============================================================

SYMBOL = "BTC/USDT"

STARTING_BALANCE = 1000.00

# Check every 60 seconds
CHECK_INTERVAL = 60

# Only trade when score reaches this level
MIN_SCORE = 70


# ============================================================
# DISPLAY
# ============================================================

def print_status(
    df,
    trader,
    signal,
):

    latest = df.iloc[-1]

    print()
    print("=" * 70)
    print("MACD CONFLUENCE PAPER LIVE")
    print("=" * 70)

    print(
        f"UTC:          "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"Symbol:       {SYMBOL}"
    )

    print(
        f"Timeframe:    15m"
    )

    print(
        f"BTC Price:    "
        f"${latest['close']:,.2f}"
    )

    print(
        f"MACD:         "
        f"{latest['macd']:.4f}"
    )

    print(
        f"MACD Signal:  "
        f"{latest['macd_signal']:.4f}"
    )

    print(
        f"Histogram:    "
        f"{latest['macd_hist']:.4f}"
    )

    print(
        f"EMA High:     "
        f"${latest['ema_high']:,.2f}"
    )

    print(
        f"EMA Close:    "
        f"${latest['ema_close']:,.2f}"
    )

    print(
        f"EMA Low:      "
        f"${latest['ema_low']:,.2f}"
    )

    print(
        f"ATR:          "
        f"${latest['atr']:,.2f}"
    )

    # --------------------------------------------------------
    # POSITION
    # --------------------------------------------------------

    if trader.position is None:

        print(
            "Position:     NONE"
        )

    else:

        position = trader.position

        print(
            f"Position:     "
            f"{position.direction}"
        )

        print(
            f"Entry:        "
            f"${position.entry:,.2f}"
        )

        print(
            f"Stop Loss:    "
            f"${position.stop_loss:,.2f}"
        )

        print(
            f"Take Profit:  "
            f"${position.take_profit:,.2f}"
        )

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    if signal is None:

        print(
            "Signal:       NONE"
        )

    else:

        print(
            f"Signal:       "
            f"{signal.direction}"
        )

        print(
            f"Score:        "
            f"{signal.score}/100"
        )

        print(
            f"Entry:        "
            f"${signal.entry:,.2f}"
        )

        print(
            f"Stop Loss:    "
            f"${signal.stop_loss:,.2f}"
        )

        print(
            f"Take Profit:  "
            f"${signal.take_profit:,.2f}"
        )

        print(
            f"Reason:       "
            f"{signal.reason}"
        )

    # --------------------------------------------------------
    # ACCOUNT
    # --------------------------------------------------------

    stats = trader.statistics()

    print()

    print(
        f"Balance:      "
        f"${stats['current_balance']:,.2f}"
    )

    print(
        f"Trades:       "
        f"{stats['trades']}"
    )

    print(
        f"Win Rate:     "
        f"{stats['win_rate']:.2f}%"
    )

    print(
        f"Total PNL:    "
        f"${stats['total_pnl']:.2f}"
    )

    print("=" * 70)


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("MACD CONFLUENCE TRADING BOT")
    print("PAPER LIVE V1")
    print("=" * 70)

    print()
    print("MODE:          PAPER ONLY")
    print("API KEYS:      NONE")
    print("WALLET:        NONE")
    print("REAL ORDERS:   DISABLED")
    print()

    trader = PaperTrader(
        starting_balance=STARTING_BALANCE
    )

    last_candle_time = None

    while True:

        try:

            # ------------------------------------------------
            # MARKET DATA
            # ------------------------------------------------

            df = get_btc_candles()

            # ------------------------------------------------
            # INDICATORS
            # ------------------------------------------------

            df = prepare_indicators(
                df
            )

            latest_candle_time = (
                df.iloc[-1]["timestamp"]
            )

            # ------------------------------------------------
            # ONLY EVALUATE NEW CANDLE
            # ------------------------------------------------

            new_candle = (
                last_candle_time
                != latest_candle_time
            )

            signal = None

            if new_candle:

                last_candle_time = (
                    latest_candle_time
                )

                print()
                print(
                    "NEW 15-MINUTE CANDLE"
                )

                # ------------------------------------------------
                # STRATEGY
                # ------------------------------------------------

                signal = evaluate(
                    df
                )

                # ------------------------------------------------
                # OPEN PAPER POSITION
                # ------------------------------------------------

                if (
                    signal is not None
                    and
                    signal.score >= MIN_SCORE
                    and
                    trader.position is None
                ):

                    trader.open_position(

                        symbol=SYMBOL,

                        signal=signal,

                        timestamp=str(
                            latest_candle_time
                        ),
                    )

            # ------------------------------------------------
            # CHECK EXISTING POSITION
            # ------------------------------------------------

            current_price = float(
                df.iloc[-1]["close"]
            )

            result = trader.check_position(
                current_price=current_price
            )

            if result is not None:

                print(
                    f"Trade closed: "
                    f"{result.reason}"
                )

            # ------------------------------------------------
            # STATUS
            # ------------------------------------------------

            print_status(
                df,
                trader,
                signal,
            )

            # ------------------------------------------------
            # WAIT
            # ------------------------------------------------

            print()
            print(
                f"Next check in "
                f"{CHECK_INTERVAL} seconds..."
            )

            time.sleep(
                CHECK_INTERVAL
            )

        except KeyboardInterrupt:

            print()
            print(
                "Paper trader stopped."
            )

            trader.print_statistics()

            break

        except Exception as error:

            print()
            print(
                "ERROR:"
            )

            print(
                str(error)
            )

            print()
            print(
                "Retrying in 60 seconds..."
            )

            time.sleep(
                CHECK_INTERVAL
            )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
