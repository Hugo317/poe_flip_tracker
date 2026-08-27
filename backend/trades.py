from dataclasses import dataclass, field
from datetime import datetime


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


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

        # Placeholders until the Rates/Settings step exists.
        self.divine_rate = 200
        self.gold_rate_gold_amount = 1_000_000
        self.gold_rate_chaos_value = 200

    # ---------------------------------------------------------------
    # RATES
    # ---------------------------------------------------------------

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
            opened_at=_now()
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
            "timestamp": _now()
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
            key=lambda trade: (trade.opened_at, trade.id),
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
        return sum(trade.realized_profit for trade in self.trades)

    def recent_activity(self, limit=5):
        activity = []

        for trade in self.trades:
            activity.append({
                "type": "BUY",
                "item": trade.item_name,
                "quantity": trade.quantity_bought,
                "total_chaos": trade.invested_chaos,
                "profit": None,
                "timestamp": trade.opened_at
            })

            for sell in trade.sells:
                activity.append({
                    "type": "SELL",
                    "item": trade.item_name,
                    "quantity": sell["quantity"],
                    "total_chaos": sell["total_chaos"],
                    "profit": sell["profit"],
                    "timestamp": sell["timestamp"]
                })

        activity.sort(key=lambda entry: entry["timestamp"], reverse=True)

        return activity[:limit]
