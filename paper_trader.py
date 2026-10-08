"""
MACD CONFLUENCE TRADING BOT
Paper Trader V1

PAPER TRADING ONLY
No API keys
No wallet
No real orders
"""

from dataclasses import dataclass
from typing import Optional

from strategy import Signal


# ============================================================
# CONFIGURATION
# ============================================================

STARTING_BALANCE = 1000.00

# Risk 1% of current account balance per trade
RISK_PER_TRADE = 0.01

# Simulated trading fee
FEE_RATE = 0.001


# ============================================================
# POSITION
# ============================================================

@dataclass
class Position:

    symbol: str
    direction: str

    entry: float
    quantity: float

    stop_loss: float
    take_profit: float

    entry_fee: float

    entry_time: Optional[str] = None


# ============================================================
# TRADE RESULT
# ============================================================

@dataclass
class TradeResult:

    symbol: str
    direction: str

    entry: float
    exit: float

    quantity: float

    gross_pnl: float
    fees: float
    net_pnl: float

    reason: str

    balance_after: float


# ============================================================
# PAPER TRADER
# ============================================================

class PaperTrader:

    def __init__(
        self,
        starting_balance: float = STARTING_BALANCE,
    ):

        self.starting_balance = float(
            starting_balance
        )

        self.balance = float(
            starting_balance
        )

        self.position: Optional[Position] = None

        self.trade_history = []

        self.total_fees = 0.0

        self.winning_trades = 0

        self.losing_trades = 0

    # ========================================================
    # ACCOUNT
    # ========================================================

    def account_value(
        self,
        current_price: Optional[float] = None
    ) -> float:

        if self.position is None:
            return self.balance

        if current_price is None:
            return self.balance

        position = self.position

        if position.direction == "LONG":

            unrealized = (
                current_price -
                position.entry
            ) * position.quantity

        else:

            unrealized = (
                position.entry -
                current_price
            ) * position.quantity

        return self.balance + unrealized

    # ========================================================
    # POSITION SIZE
    # ========================================================

    def calculate_position_size(
        self,
        entry: float,
        stop_loss: float,
    ) -> float:

        risk_amount = (
            self.balance *
            RISK_PER_TRADE
        )

        risk_per_unit = abs(
            entry -
            stop_loss
        )

        if risk_per_unit <= 0:
            return 0.0

        quantity = (
            risk_amount /
            risk_per_unit
        )

        return quantity

    # ========================================================
    # OPEN POSITION
    # ========================================================

    def open_position(
        self,
        symbol: str,
        signal: Signal,
        timestamp: Optional[str] = None,
    ) -> bool:

        # Only one position at a time in V1
        if self.position is not None:

            print(
                "PAPER: position already open"
            )

            return False

        entry = float(signal.entry)

        quantity = self.calculate_position_size(
            entry,
            signal.stop_loss
        )

        if quantity <= 0:

            print(
                "PAPER: invalid position size"
            )

            return False

        position_value = (
            entry *
            quantity
        )

        entry_fee = (
            position_value *
            FEE_RATE
        )

        if entry_fee >= self.balance:

            print(
                "PAPER: insufficient balance"
            )

            return False

        self.balance -= entry_fee

        self.total_fees += entry_fee

        self.position = Position(

            symbol=symbol,

            direction=signal.direction,

            entry=entry,

            quantity=quantity,

            stop_loss=float(
                signal.stop_loss
            ),

            take_profit=float(
                signal.take_profit
            ),

            entry_fee=entry_fee,

            entry_time=timestamp,
        )

        print()
        print("=" * 70)
        print("PAPER TRADE OPENED")
        print("=" * 70)

        print(
            f"Symbol:       {symbol}"
        )

        print(
            f"Direction:    {signal.direction}"
        )

        print(
            f"Entry:        {entry:.4f}"
        )

        print(
            f"Quantity:     {quantity:.8f}"
        )

        print(
            f"Stop Loss:    "
            f"{signal.stop_loss:.4f}"
        )

        print(
            f"Take Profit:  "
            f"{signal.take_profit:.4f}"
        )

        print(
            f"Signal Score: "
            f"{signal.score}/100"
        )

        print(
            f"Entry Fee:    "
            f"${entry_fee:.4f}"
        )

        print(
            f"Balance:      "
            f"${self.balance:.2f}"
        )

        print("=" * 70)
        print()

        return True

    # ========================================================
    # CHECK POSITION
    # ========================================================

    def check_position(
        self,
        current_price: float,
        timestamp: Optional[str] = None,
    ) -> Optional[TradeResult]:

        if self.position is None:
            return None

        position = self.position

        price = float(current_price)

        # ----------------------------------------------------
        # LONG
        # ----------------------------------------------------

        if position.direction == "LONG":

            if price <= position.stop_loss:

                return self.close_position(
                    price,
                    "STOP_LOSS",
                    timestamp,
                )

            if price >= position.take_profit:

                return self.close_position(
                    price,
                    "TAKE_PROFIT",
                    timestamp,
                )

        # ----------------------------------------------------
        # SHORT
        # ----------------------------------------------------

        elif position.direction == "SHORT":

            if price >= position.stop_loss:

                return self.close_position(
                    price,
                    "STOP_LOSS",
                    timestamp,
                )

            if price <= position.take_profit:

                return self.close_position(
                    price,
                    "TAKE_PROFIT",
                    timestamp,
                )

        return None

    # ========================================================
    # CLOSE POSITION
    # ========================================================

    def close_position(
        self,
        exit_price: float,
        reason: str,
        timestamp: Optional[str] = None,
    ) -> Optional[TradeResult]:

        if self.position is None:
            return None

        position = self.position

        exit_price = float(exit_price)

        # ----------------------------------------------------
        # PNL
        # ----------------------------------------------------

        if position.direction == "LONG":

            gross_pnl = (
                exit_price -
                position.entry
            ) * position.quantity

        else:

            gross_pnl = (
                position.entry -
                exit_price
            ) * position.quantity

        # ----------------------------------------------------
        # EXIT FEE
        # ----------------------------------------------------

        exit_value = (
            exit_price *
            position.quantity
        )

        exit_fee = (
            exit_value *
            FEE_RATE
        )

        total_fees = (
            position.entry_fee +
            exit_fee
        )

        net_pnl = (
            gross_pnl -
            total_fees
        )

        # Add PNL to account
        self.balance += (
            gross_pnl -
            exit_fee
        )

        self.total_fees += exit_fee

        # ----------------------------------------------------
        # WIN / LOSS
        # ----------------------------------------------------

        if net_pnl > 0:

            self.winning_trades += 1

        else:

            self.losing_trades += 1

        result = TradeResult(

            symbol=position.symbol,

            direction=position.direction,

            entry=position.entry,

            exit=exit_price,

            quantity=position.quantity,

            gross_pnl=gross_pnl,

            fees=total_fees,

            net_pnl=net_pnl,

            reason=reason,

            balance_after=self.balance,
        )

        self.trade_history.append(
            result
        )

        # Remove position
        self.position = None

        # ----------------------------------------------------
        # OUTPUT
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("PAPER TRADE CLOSED")
        print("=" * 70)

        print(
            f"Symbol:       "
            f"{result.symbol}"
        )

        print(
            f"Direction:    "
            f"{result.direction}"
        )

        print(
            f"Entry:        "
            f"{result.entry:.4f}"
        )

        print(
            f"Exit:         "
            f"{result.exit:.4f}"
        )

        print(
            f"Reason:       "
            f"{result.reason}"
        )

        print(
            f"Gross PNL:    "
            f"${result.gross_pnl:.4f}"
        )

        print(
            f"Fees:         "
            f"${result.fees:.4f}"
        )

        print(
            f"NET PNL:      "
            f"${result.net_pnl:.4f}"
        )

        print(
            f"Balance:      "
            f"${result.balance_after:.2f}"
        )

        print("=" * 70)
        print()

        return result

    # ========================================================
    # STATISTICS
    # ========================================================

    def statistics(self):

        trades = len(
            self.trade_history
        )

        if trades == 0:

            win_rate = 0.0

        else:

            win_rate = (
                self.winning_trades /
                trades
            ) * 100

        total_pnl = (
            self.balance -
            self.starting_balance
        )

        return {

            "starting_balance":
                self.starting_balance,

            "current_balance":
                self.balance,

            "total_pnl":
                total_pnl,

            "total_return_percent":
                (
                    total_pnl /
                    self.starting_balance
                ) * 100,

            "trades":
                trades,

            "winning_trades":
                self.winning_trades,

            "losing_trades":
                self.losing_trades,

            "win_rate":
                win_rate,

            "total_fees":
                self.total_fees,
        }

    # ========================================================
    # PRINT STATISTICS
    # ========================================================

    def print_statistics(self):

        stats = self.statistics()

        print()
        print("=" * 70)
        print("PAPER TRADER STATISTICS")
        print("=" * 70)

        print(
            f"Starting Balance: "
            f"${stats['starting_balance']:.2f}"
        )

        print(
            f"Current Balance:  "
            f"${stats['current_balance']:.2f}"
        )

        print(
            f"Total PNL:        "
            f"${stats['total_pnl']:.2f}"
        )

        print(
            f"Return:           "
            f"{stats['total_return_percent']:.2f}%"
        )

        print(
            f"Trades:           "
            f"{stats['trades']}"
        )

        print(
            f"Winners:          "
            f"{stats['winning_trades']}"
        )

        print(
            f"Losers:           "
            f"{stats['losing_trades']}"
        )

        print(
            f"Win Rate:         "
            f"{stats['win_rate']:.2f}%"
        )

        print(
            f"Fees:             "
            f"${stats['total_fees']:.4f}"
        )

        print("=" * 70)
        print()


# ============================================================
# SELF TEST
# ============================================================

def self_test():

    print()
    print("=" * 70)
    print("PAPER TRADER V1")
    print("SELF TEST")
    print("=" * 70)

    trader = PaperTrader(
        starting_balance=1000.00
    )

    # --------------------------------------------------------
    # Fake signal
    # --------------------------------------------------------

    signal = Signal(

        direction="LONG",

        score=85,

        entry=100.0,

        stop_loss=95.0,

        take_profit=110.0,

        trend_score=25,

        macd_score=30,

        pullback_score=20,

        breakout_score=10,

        reason="self-test",
    )

    # --------------------------------------------------------
    # Open
    # --------------------------------------------------------

    opened = trader.open_position(
        symbol="TEST/USDT",
        signal=signal,
        timestamp="SELF_TEST",
    )

    assert opened is True

    print(
        "PASS: Position opened"
    )

    assert trader.position is not None

    print(
        "PASS: Position exists"
    )

    # --------------------------------------------------------
    # Price movement
    # --------------------------------------------------------

    result = trader.check_position(
        current_price=110.0,
        timestamp="SELF_TEST_EXIT",
    )

    assert result is not None

    print(
        "PASS: Take profit detected"
    )

    assert result.reason == "TAKE_PROFIT"

    print(
        "PASS: Correct exit reason"
    )

    assert trader.position is None

    print(
        "PASS: Position closed"
    )

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    stats = trader.statistics()

    assert stats["trades"] == 1

    print(
        "PASS: Trade statistics"
    )

    assert stats["winning_trades"] == 1

    print(
        "PASS: Winning trade counted"
    )

    print()
    print("=" * 70)
    print("ALL PAPER TRADER SELF TESTS PASSED")
    print("=" * 70)
    print()


if __name__ == "__main__":
    self_test()
