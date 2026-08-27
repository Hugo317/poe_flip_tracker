from datetime import datetime

from sqlalchemy import select

from backend.db.models import (
    DivineRate,
    GlobalSettings,
    GoldRate,
    League,
    Sale,
    Trade,
    TradingDay,
)
from backend.db.session import build_engine, build_session_factory


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


DEFAULT_LEAGUE_NAME = "Standard"
DEFAULT_DIVINE_RATE = 200
DEFAULT_GOLD_AMOUNT = 1_000_000
DEFAULT_GOLD_CHAOS_VALUE = 200


class TradeService:
    """
    Domain/accounting layer for open trades, backed by SQLite via
    SQLAlchemy (see backend/db/). Every BUY opens exactly one isolated
    Trade (per-trade inventory, not global FIFO) per the locked
    architecture decision (directive Q18).

    V1 has a single default league (no league picker UI yet — see
    directive discussion), so `self.league` is fixed at construction.
    """

    def __init__(self, session=None):
        if session is None:
            engine = build_engine()
            session_factory = build_session_factory(engine)
            session = session_factory()

        self.session = session

        self.league = self._get_or_create_league()
        self._settings_row = self._get_or_create_global_settings()
        self.trading_day = self._get_or_create_open_trading_day()

    def _get_or_create_league(self):
        league = self.session.execute(
            select(League).where(League.name == DEFAULT_LEAGUE_NAME)
        ).scalar_one_or_none()

        if league is None:
            league = League(name=DEFAULT_LEAGUE_NAME)
            self.session.add(league)
            self.session.commit()

        return league

    def _get_or_create_global_settings(self):
        settings = self.session.get(GlobalSettings, 1)

        if settings is None:
            settings = GlobalSettings(id=1)
            self.session.add(settings)
            self.session.commit()

        return settings

    def _get_or_create_open_trading_day(self):
        # Trading Day now genuinely persists across app restarts, and
        # nothing auto-closes one (directive Q11: user input changes
        # the day, never automatic) — so on launch we simply continue
        # whatever day is still open for this league.
        day = self.session.execute(
            select(TradingDay)
            .where(
                TradingDay.league_id == self.league.id,
                TradingDay.closed_at.is_(None)
            )
            .order_by(TradingDay.id.desc())
        ).scalars().first()

        if day is None:
            day = TradingDay(league_id=self.league.id)
            self.session.add(day)
            self.session.commit()

        return day

    def start_new_trading_day(self):
        self.trading_day.closed_at = _now()

        new_day = TradingDay(league_id=self.league.id)
        self.session.add(new_day)
        self.session.commit()

        self.trading_day = new_day

    # ---------------------------------------------------------------
    # RATES
    # ---------------------------------------------------------------

    def _latest_divine_rate_row(self):
        return self.session.execute(
            select(DivineRate)
            .where(DivineRate.league_id == self.league.id)
            .order_by(DivineRate.id.desc())
        ).scalars().first()

    def _latest_gold_rate_row(self):
        return self.session.execute(
            select(GoldRate)
            .where(GoldRate.league_id == self.league.id)
            .order_by(GoldRate.id.desc())
        ).scalars().first()

    @property
    def divine_rate(self):
        row = self._latest_divine_rate_row()
        return row.chaos_value if row else DEFAULT_DIVINE_RATE

    @property
    def gold_rate_gold_amount(self):
        row = self._latest_gold_rate_row()
        return row.gold_amount if row else DEFAULT_GOLD_AMOUNT

    @property
    def gold_rate_chaos_value(self):
        row = self._latest_gold_rate_row()
        return row.chaos_value if row else DEFAULT_GOLD_CHAOS_VALUE

    def set_divine_rate(self, chaos_value):
        self.session.add(
            DivineRate(league_id=self.league.id, chaos_value=chaos_value)
        )
        self.session.commit()

    def set_gold_rate(self, gold_amount, chaos_value):
        self.session.add(
            GoldRate(
                league_id=self.league.id,
                gold_amount=gold_amount,
                chaos_value=chaos_value
            )
        )
        self.session.commit()

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

    @property
    def sound_master_volume(self):
        return self._settings_row.sound_master_volume

    @property
    def sound_tink_enabled(self):
        return self._settings_row.sound_tink_enabled

    @property
    def sound_warnings_enabled(self):
        return self._settings_row.sound_warnings_enabled

    def set_sound_master_volume(self, value):
        self._settings_row.sound_master_volume = value
        self.session.commit()

    def set_sound_tink_enabled(self, enabled):
        self._settings_row.sound_tink_enabled = enabled
        self.session.commit()

    def set_sound_warnings_enabled(self, enabled):
        self._settings_row.sound_warnings_enabled = enabled
        self.session.commit()

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
            league_id=self.league.id,
            trading_day_id=self.trading_day.id,
            item_name=item_name,
            currency=currency,
            entered_price=entered_price,
            unit_price_chaos=unit_price_chaos,
            quantity_bought=quantity,
            gold_spent=gold_spent
        )

        self.session.add(trade)
        self.session.commit()

        return trade

    # ---------------------------------------------------------------
    # SELL / CLOSE TRADE
    # ---------------------------------------------------------------

    def get_trade(self, trade_id):
        return self.session.get(Trade, trade_id)

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

        sale = Sale(
            trading_day_id=self.trading_day.id,
            quantity=quantity,
            currency=currency,
            entered_price=entered_price,
            unit_price_chaos=unit_price_chaos,
            total_chaos=total_chaos,
            cost_chaos=cost_chaos,
            profit=profit,
            gold_received=gold_received
        )

        # Added through the relationship (not by setting sale.trade_id
        # directly) so trade.sales stays correct in memory even if
        # something already read it earlier in this long-lived session.
        trade.sales.append(sale)

        # Both writes commit together as one transaction, so a trade
        # can never end up with a Sale but a stale quantity_sold.
        trade.quantity_sold += quantity
        self.session.commit()

        return sale

    # ---------------------------------------------------------------
    # QUERIES
    # ---------------------------------------------------------------

    def open_trades(self):
        trades = self.session.execute(
            select(Trade)
            .where(
                Trade.league_id == self.league.id,
                Trade.quantity_sold < Trade.quantity_bought
            )
            .order_by(Trade.id.desc())
        ).scalars().all()

        return list(trades)

    def latest_open_trades(self, limit=6):
        return self.open_trades()[:limit]

    def open_trades_count(self):
        return len(self.open_trades())

    def stash_count(self):
        return sum(trade.remaining for trade in self.open_trades())

    def stash_summary(self):
        """Inventory grouped by item across all open trades (isolated
        per-trade inventory, summed for display) — quantity and FIFO
        cost basis only, per the locked Stash spec."""

        summary = {}

        for trade in self.open_trades():
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
        decision, directive Q14). Backed directly by Sale.trading_day_id,
        set at the moment each sale happens."""

        sales = self.session.execute(
            select(Sale).where(
                Sale.trading_day_id == self.trading_day.id
            )
        ).scalars().all()

        return sum(sale.profit for sale in sales)

    def total_realized_profit(self):
        trades = self.session.execute(
            select(Trade).where(Trade.league_id == self.league.id)
        ).scalars().all()

        return sum(trade.realized_profit for trade in trades)

    def all_transactions(self):
        """Complete historical BUY/SELL activity, newest first — the
        Trades overlay's data source. Distinct from open_trades(): this
        includes every transaction, not just currently-open positions.

        Ordering here is timestamp-based (display only, not used for
        any accounting decision) since Trade.id and Sale.id are
        independent autoincrement sequences and can't be compared
        directly across the two tables."""

        trades = self.session.execute(
            select(Trade).where(Trade.league_id == self.league.id)
        ).scalars().all()

        transactions = []

        for trade in trades:
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
                "timestamp": trade.opened_at
            })

            for sale in trade.sales:
                transactions.append({
                    "type": "SELL",
                    "trade_id": trade.id,
                    "item": trade.item_name,
                    "quantity": sale.quantity,
                    "currency": sale.currency,
                    "entered_price": sale.entered_price,
                    "unit_price_chaos": sale.unit_price_chaos,
                    "total_chaos": sale.total_chaos,
                    "cost_chaos": sale.cost_chaos,
                    "profit": sale.profit,
                    "gold": sale.gold_received,
                    "timestamp": sale.sold_at
                })

        transactions.sort(
            key=lambda transaction: transaction["timestamp"],
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

        today_id = self.trading_day.id

        all_trades = self.session.execute(
            select(Trade).where(Trade.league_id == self.league.id)
        ).scalars().all()

        new_trades_today = [
            trade for trade in all_trades
            if trade.trading_day_id == today_id
        ]
        new_trade_ids = {trade.id for trade in new_trades_today}

        today_sales = self.session.execute(
            select(Sale).where(Sale.trading_day_id == today_id)
        ).scalars().all()

        new_trade_sales = [
            sale for sale in today_sales
            if sale.trade_id in new_trade_ids
        ]
        carryover_sales = [
            sale for sale in today_sales
            if sale.trade_id not in new_trade_ids
        ]

        today_revenue = sum(sale.total_chaos for sale in today_sales)
        today_cost = sum(sale.cost_chaos for sale in today_sales)
        today_profit = sum(sale.profit for sale in today_sales)

        today_buys_volume = sum(
            trade.invested_chaos for trade in new_trades_today
        )
        trading_volume_chaos = today_revenue + today_buys_volume
        transaction_count_today = (
            len(new_trades_today) + len(today_sales)
        )

        roi = (today_profit / today_cost) if today_cost else 0

        closed_today_trades = [
            trade for trade in all_trades
            if not trade.is_open
            and any(
                sale.trading_day_id == today_id
                for sale in trade.sales
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
            sale.gold_received for sale in today_sales
        )

        item_performance = {}

        for sale in today_sales:
            item_name = sale.trade.item_name

            entry = item_performance.setdefault(
                item_name,
                {
                    "item_name": item_name,
                    "quantity_sold": 0,
                    "revenue": 0,
                    "cost": 0,
                    "profit": 0
                }
            )

            entry["quantity_sold"] += sale.quantity
            entry["revenue"] += sale.total_chaos
            entry["cost"] += sale.cost_chaos
            entry["profit"] += sale.profit

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
                sale.profit for sale in new_trade_sales
            ),
            "carryover_sales_count": len(carryover_sales),
            "carryover_sales_profit": sum(
                sale.profit for sale in carryover_sales
            ),
            "completed_trades_today": completed_trades_today,
            "average_profit_per_trade": average_profit_per_trade,
            "gold_spent_today": gold_spent_today,
            "gold_received_today": gold_received_today,
            "total_realized_profit": self.total_realized_profit(),
            "item_performance": item_performance_list
        }
