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

        # Rates and General sound preferences are persisted (see
        # SETTINGS_FILE) so they survive restarts even before the full
        # SQLite backend exists.
        settings = _load_settings()
        self.divine_rate = settings.get("divine_rate", 200)
        self.gold_rate_gold_amount = settings.get(
            "gold_rate_gold_amount", 1_000_000
        )
        self.gold_rate_chaos_value = settings.get(
            "gold_rate_chaos_value", 200
        )
        self.sound_master_volume = settings.get(
            "sound_master_volume", 100
        )
        self.sound_tink_enabled = settings.get(
            "sound_tink_enabled", True
        )
        self.sound_warnings_enabled = settings.get(
            "sound_warnings_enabled", True
        )

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

    @staticmethod
    def _persist(key, value):
        settings = _load_settings()
        settings[key] = value
        _save_settings(settings)

    def set_divine_rate(self, chaos_value):
        self.divine_rate = chaos_value
        self._persist("divine_rate", chaos_value)

    def set_gold_rate(self, gold_amount, chaos_value):
        self.gold_rate_gold_amount = gold_amount
        self.gold_rate_chaos_value = chaos_value

        settings = _load_settings()
        settings["gold_rate_gold_amount"] = gold_amount
        settings["gold_rate_chaos_value"] = chaos_value
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
    # GENERAL (SOUND PREFERENCES)
    # ---------------------------------------------------------------
    # Preferences only — no sound actually plays yet (that's a later
    # build step), but the controls Q49 locked in are real and persist.

    def set_sound_master_volume(self, value):
        self.sound_master_volume = value
        self._persist("sound_master_volume", value)

    def set_sound_tink_enabled(self, enabled):
        self.sound_tink_enabled = enabled
        self._persist("sound_tink_enabled", enabled)

    def set_sound_warnings_enabled(self, enabled):
        self.sound_warnings_enabled = enabled
        self._persist("sound_warnings_enabled", enabled)

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

    # ---------------------------------------------------------------
    # ANALYTICS
    # ---------------------------------------------------------------

    def analytics_summary(self):
        """Everything the Analytics overlay needs for the current
        Trading Day, in one call. ROI and New Trades vs Carry-over
        Sales follow the locked accounting rules (directive Q18/19):
        a partially-sold new trade contributes only the sold portion,
        and Gold is never mixed into trading profit/ROI."""

        boundary = self.trading_day_start_sequence

        new_trades_today = [
            trade for trade in self.trades
            if trade.sequence >= boundary
        ]
        new_trade_ids = {trade.id for trade in new_trades_today}

        today_sells = []

        for trade in self.trades:
            for sell in trade.sells:
                if sell["sequence"] >= boundary:
                    today_sells.append((trade, sell))

        new_trade_sales = [
            (trade, sell) for trade, sell in today_sells
            if trade.id in new_trade_ids
        ]
        carryover_sales = [
            (trade, sell) for trade, sell in today_sells
            if trade.id not in new_trade_ids
        ]

        today_revenue = sum(
            sell["total_chaos"] for _, sell in today_sells
        )
        today_cost = sum(
            sell["cost_chaos"] for _, sell in today_sells
        )
        today_profit = sum(
            sell["profit"] for _, sell in today_sells
        )

        today_buys_volume = sum(
            trade.invested_chaos for trade in new_trades_today
        )
        trading_volume_chaos = today_revenue + today_buys_volume
        transaction_count_today = (
            len(new_trades_today) + len(today_sells)
        )

        roi = (today_profit / today_cost) if today_cost else 0

        closed_today_trades = [
            trade for trade in self.trades
            if not trade.is_open
            and any(
                sell["sequence"] >= boundary for sell in trade.sells
            )
        ]
        completed_trades_today = len(closed_today_trades)
        average_profit_per_trade = (
            sum(trade.realized_profit for trade in closed_today_trades)
            / completed_trades_today
            if completed_trades_today else 0
        )

        gold_spent_today = sum(
            trade.gold_spent for trade in new_trades_today
        )
        gold_received_today = sum(
            sell["gold_received"] for _, sell in today_sells
        )

        item_performance = {}

        for trade, sell in today_sells:
            entry = item_performance.setdefault(
                trade.item_name,
                {
                    "item_name": trade.item_name,
                    "quantity_sold": 0,
                    "revenue": 0,
                    "cost": 0,
                    "profit": 0
                }
            )

            entry["quantity_sold"] += sell["quantity"]
            entry["revenue"] += sell["total_chaos"]
            entry["cost"] += sell["cost_chaos"]
            entry["profit"] += sell["profit"]

        item_performance_list = sorted(
            item_performance.values(),
            key=lambda entry: entry["profit"],
            reverse=True
        )

        return {
            "today_profit": today_profit,
            "today_revenue": today_revenue,
            "today_cost": today_cost,
            "roi": roi,
            "trading_volume_chaos": trading_volume_chaos,
            "transaction_count_today": transaction_count_today,
            "new_trades_count": len(new_trades_today),
            "new_trade_sales_count": len(new_trade_sales),
            "new_trade_sales_profit": sum(
                sell["profit"] for _, sell in new_trade_sales
            ),
            "carryover_sales_count": len(carryover_sales),
            "carryover_sales_profit": sum(
                sell["profit"] for _, sell in carryover_sales
            ),
            "completed_trades_today": completed_trades_today,
            "average_profit_per_trade": average_profit_per_trade,
            "gold_spent_today": gold_spent_today,
            "gold_received_today": gold_received_today,
            "total_realized_profit": self.total_realized_profit(),
            "item_performance": item_performance_list
        }
