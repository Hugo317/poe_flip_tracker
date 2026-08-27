import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def _now():
    # Seconds precision matters here: Trading Day boundaries and
    # transaction ordering are compared as plain strings, and two
    # events in the same minute would otherwise be indistinguishable.
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Small persisted settings cache (rates only) — separate from real
# trade-data persistence, which is intentionally still in-memory until
# the SQLite backend step. Lets the Divine/Gold rate survive restarts
# without waiting on that much bigger piece of work.
SETTINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "settings.json"


def _load_settings():
    try:
        with SETTINGS_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_settings(settings):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with SETTINGS_FILE.open("w", encoding="utf-8") as file:
        json.dump(settings, file, indent=2)


@dataclass
class Trade:
    id: int
    item_name: str
    currency: str
    entered_price: int
    unit_price_chaos: int
    quantity_bought: int
    gold_spent: int
    opened_at: str
    quantity_sold: int = 0
    sells: list = field(default_factory=list)
    sequence: int = 0

    @property
    def remaining(self):
        return self.quantity_bought - self.quantity_sold

    @property
    def is_open(self):
        return self.remaining > 0

    @property
    def invested_chaos(self):
        return self.unit_price_chaos * self.quantity_bought

    @property
    def realized_profit(self):
        return sum(sell["profit"] for sell in self.sells)


class TradeService:
    """
    In-memory domain/accounting layer for open trades.

    Each BUY opens exactly one isolated Trade (per-trade inventory,
    not global FIFO) per the locked architecture decision. This will
    be swapped for a SQLite-backed repository later without changing
    callers, per the planned service/repository split.
    """

    def __init__(self):
        self.trades = []
        self._next_id = 1

        # Monotonic event ordering. Wall-clock timestamps (seconds
        # precision) are kept for display, but anything that needs a
        # reliable "did this happen before or after X" answer — the
        # Trading Day boundary, transaction ordering — uses this
        # instead, since two events can share the same clock second.
        self._next_sequence_number = 1

        # Placeholders until the full Rates/Settings step exists;
        # divine_rate is persisted (see SETTINGS_FILE) so it survives
        # restarts even before that.
        settings = _load_settings()
        self.divine_rate = settings.get("divine_rate", 200)
        self.gold_rate_gold_amount = 1_000_000
        self.gold_rate_chaos_value = 200

        # Trading Day: user-controlled, never auto-rolls. Until real
        # persistence exists (a later build step), a "day" only lasts
        # for the current in-memory session, but the boundary logic
        # (today's profit = only sells since this boundary) is real
        # and will keep working once a day can genuinely carry over.
        self.trading_day_started_at = _now()
        self.trading_day_start_sequence = self._new_sequence()

    def _new_sequence(self):
        sequence = self._next_sequence_number
        self._next_sequence_number += 1
        return sequence

    def start_new_trading_day(self):
        self.trading_day_started_at = _now()
        self.trading_day_start_sequence = self._new_sequence()

    # ---------------------------------------------------------------
    # RATES
    # ---------------------------------------------------------------

    def set_divine_rate(self, chaos_value):
        self.divine_rate = chaos_value

        settings = _load_settings()
        settings["divine_rate"] = chaos_value
        _save_settings(settings)

    def divine_to_chaos(self, divine_amount):
        return divine_amount * self.divine_rate

    def gold_to_chaos(self, gold_amount):
        if not gold_amount:
            return 0

        return (
            gold_amount * self.gold_rate_chaos_value
            // self.gold_rate_gold_amount
        )

    # ---------------------------------------------------------------
    # BUY
    # ---------------------------------------------------------------

    def open_trade(
        self,
        item_name,
        quantity,
        currency,
        entered_price,
        gold_spent=0
    ):
        if currency == "DIVINE":
            unit_price_chaos = self.divine_to_chaos(entered_price)
        else:
            unit_price_chaos = entered_price

        trade = Trade(
            id=self._next_id,
            item_name=item_name,
            currency=currency,
            entered_price=entered_price,
            unit_price_chaos=unit_price_chaos,
            quantity_bought=quantity,
            gold_spent=gold_spent,
            opened_at=_now(),
            sequence=self._new_sequence()
        )

        self._next_id += 1
        self.trades.append(trade)

        return trade

    # ---------------------------------------------------------------
    # SELL / CLOSE TRADE
    # ---------------------------------------------------------------

    def get_trade(self, trade_id):
        for trade in self.trades:
            if trade.id == trade_id:
                return trade

        return None

    def sell_from_trade(
        self,
        trade_id,
        quantity,
        currency,
        entered_price,
        gold_received=0
    ):
        trade = self.get_trade(trade_id)

        if trade is None:
            raise ValueError(f"Trade {trade_id} not found.")

        if quantity <= 0 or quantity > trade.remaining:
            raise ValueError(
                f"Cannot sell {quantity}; "
                f"only {trade.remaining} remaining on this trade."
            )

        if currency == "DIVINE":
            unit_price_chaos = self.divine_to_chaos(entered_price)
        else:
            unit_price_chaos = entered_price

        total_chaos = unit_price_chaos * quantity
        cost_chaos = trade.unit_price_chaos * quantity
        profit = total_chaos - cost_chaos

        sell_record = {
            "quantity": quantity,
            "currency": currency,
            "entered_price": entered_price,
            "unit_price_chaos": unit_price_chaos,
            "total_chaos": total_chaos,
            "cost_chaos": cost_chaos,
            "profit": profit,
            "gold_received": gold_received,
            "timestamp": _now(),
            "sequence": self._new_sequence()
        }

        trade.quantity_sold += quantity
        trade.sells.append(sell_record)

        return sell_record

    # ---------------------------------------------------------------
    # QUERIES
    # ---------------------------------------------------------------

    def open_trades(self):
        open_trades = [
            trade for trade in self.trades if trade.is_open
        ]

        return sorted(
            open_trades,
            key=lambda trade: trade.sequence,
            reverse=True
        )

    def latest_open_trades(self, limit=6):
        return self.open_trades()[:limit]

    def open_trades_count(self):
        return len(self.open_trades())

    def stash_count(self):
        return sum(trade.remaining for trade in self.trades)

    def stash_summary(self):
        """Inventory grouped by item across all open trades (isolated
        per-trade inventory, summed for display) — quantity and FIFO
        cost basis only, per the locked Stash spec."""

        summary = {}

        for trade in self.trades:
            if trade.remaining <= 0:
                continue

            entry = summary.setdefault(
                trade.item_name,
                {
                    "item_name": trade.item_name,
                    "quantity": 0,
                    "cost_chaos": 0
                }
            )

            entry["quantity"] += trade.remaining
            entry["cost_chaos"] += (
                trade.remaining * trade.unit_price_chaos
            )

        return sorted(
            summary.values(),
            key=lambda entry: entry["item_name"]
        )

    def today_profit(self):
        """Realized profit from sells made during the current Trading
        Day only — a sale's profit belongs to the day it was sold on,
        regardless of when the underlying trade was opened (locked
        decision, directive Q14)."""

        total = 0

        for trade in self.trades:
            for sell in trade.sells:
                if sell["sequence"] >= self.trading_day_start_sequence:
                    total += sell["profit"]

        return total

    def total_realized_profit(self):
        return sum(trade.realized_profit for trade in self.trades)

    def all_transactions(self):
        """Complete historical BUY/SELL activity, newest first — the
        Trades overlay's data source. Distinct from open_trades(): this
        includes every transaction, not just currently-open positions."""

        transactions = []

        for trade in self.trades:
            transactions.append({
                "type": "BUY",
                "trade_id": trade.id,
                "item": trade.item_name,
                "quantity": trade.quantity_bought,
                "currency": trade.currency,
                "entered_price": trade.entered_price,
                "unit_price_chaos": trade.unit_price_chaos,
                "total_chaos": trade.invested_chaos,
                "cost_chaos": None,
                "profit": None,
                "gold": trade.gold_spent,
                "timestamp": trade.opened_at,
                "sequence": trade.sequence
            })

            for sell in trade.sells:
                transactions.append({
                    "type": "SELL",
                    "trade_id": trade.id,
                    "item": trade.item_name,
                    "quantity": sell["quantity"],
                    "currency": sell["currency"],
                    "entered_price": sell["entered_price"],
                    "unit_price_chaos": sell["unit_price_chaos"],
                    "total_chaos": sell["total_chaos"],
                    "cost_chaos": sell["cost_chaos"],
                    "profit": sell["profit"],
                    "gold": sell["gold_received"],
                    "timestamp": sell["timestamp"],
                    "sequence": sell["sequence"]
                })

        transactions.sort(
            key=lambda transaction: transaction["sequence"],
            reverse=True
        )

        return transactions

    def recent_activity(self, limit=5):
        activity = []

        for transaction in self.all_transactions()[:limit]:
            activity.append({
                "type": transaction["type"],
                "item": transaction["item"],
                "quantity": transaction["quantity"],
                "total_chaos": transaction["total_chaos"],
                "profit": transaction["profit"],
                "timestamp": transaction["timestamp"]
            })

        return activity
