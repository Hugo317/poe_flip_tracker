from datetime import datetime

from sqlalchemy import func, select

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


class TradeHasSalesError(Exception):
    """Raised by delete_trade when the trade's inventory has already
    been consumed by one or more sales (directive 30's protection for
    BUYs already consumed by FIFO) — delete those sales first."""


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

    Directive Q8: the active league persists across launches
    (GlobalSettings.active_league_name) and is switchable at any time
    via switch_league() — each league's trades/history stay isolated
    by league_id.
    """

    def __init__(self, session=None):
        if session is None:
            engine = build_engine()
            session_factory = build_session_factory(engine)
            session = session_factory()

        self.session = session

        self._settings_row = self._get_or_create_global_settings()

        league_name = (
            self._settings_row.active_league_name or DEFAULT_LEAGUE_NAME
        )
        self.league = self._get_or_create_league(league_name)
        self.trading_day = self._get_or_create_open_trading_day()

    def _get_or_create_league(self, name):
        league = self.session.execute(
            select(League).where(League.name == name)
        ).scalar_one_or_none()

        if league is None:
            league = League(name=name)
            self.session.add(league)
            self.session.commit()

        return league

    def switch_league(self, league_name):
        self.league = self._get_or_create_league(league_name)
        self._settings_row.active_league_name = league_name
        self.session.commit()

        self.trading_day = self._get_or_create_open_trading_day()

    def local_league_names(self):
        return [
            row.name for row in
            self.session.execute(select(League)).scalars().all()
        ]

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
        stats = self.analytics_summary(self.trading_day.id)

        self.trading_day.closed_at = _now()
        self.trading_day.snapshot_new_trades = stats["new_trades_count"]
        self.trading_day.snapshot_carryover_sales = (
            stats["carryover_sales_count"]
        )
        self.trading_day.snapshot_realized_profit = stats["today_profit"]
        self.trading_day.snapshot_roi = stats["roi"]
        self.trading_day.snapshot_revenue = stats["today_revenue"]
        self.trading_day.snapshot_inventory_value = (
            stats["inventory_value"]
        )
        self.trading_day.snapshot_gold_spent = stats["gold_spent_today"]
        self.trading_day.snapshot_average_profit_per_trade = (
            stats["average_profit_per_trade"]
        )
        self.trading_day.snapshot_completed_trades = (
            stats["completed_trades_today"]
        )

        new_day = TradingDay(league_id=self.league.id)
        self.session.add(new_day)
        self.session.commit()

        self.trading_day = new_day

    def closed_trading_days(self):
        return self.session.execute(
            select(TradingDay)
            .where(
                TradingDay.league_id == self.league.id,
                TradingDay.closed_at.is_not(None)
            )
            .order_by(TradingDay.id.desc())
        ).scalars().all()

    def all_trading_days(self):
        """Every Trading Day for this league (closed and the current
        open one), oldest first — the backbone for the Analytics
        "Last 7 Days"/"All" scopes and the profit-over-time chart."""
        return self.session.execute(
            select(TradingDay)
            .where(TradingDay.league_id == self.league.id)
            .order_by(TradingDay.id.asc())
        ).scalars().all()

    def last_n_trading_day_ids(self, n):
        days = self.all_trading_days()
        return [day.id for day in days[-n:]]

    def profit_over_time(self):
        """(label, profit) per Trading Day, oldest first. Closed days
        use their frozen snapshot (never recomputed); the current open
        day uses a live analytics_summary() call."""
        points = []

        for day in self.all_trading_days():
            if day.closed_at is not None:
                profit = day.snapshot_realized_profit or 0
            else:
                profit = self.analytics_summary(day.id)["today_profit"]

            points.append((day.started_at[:10], profit))

        return points

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

    def total_gold_spent_this_league(self):
        return self.session.execute(
            select(func.coalesce(func.sum(Trade.gold_spent), 0))
            .where(Trade.league_id == self.league.id)
        ).scalar_one()

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

    @property
    def sound_master_volume(self):
        return self._settings_row.sound_master_volume

    @property
    def sound_tink_enabled(self):
        return self._settings_row.sound_tink_enabled

    @property
    def sound_warnings_enabled(self):
        return self._settings_row.sound_warnings_enabled

    @property
    def sound_tier_small_max(self):
        return self._settings_row.sound_tier_small_max

    @property
    def sound_tier_medium_max(self):
        return self._settings_row.sound_tier_medium_max

    def set_sound_master_volume(self, value):
        self._settings_row.sound_master_volume = value
        self.session.commit()

    def set_sound_tink_enabled(self, enabled):
        self._settings_row.sound_tink_enabled = enabled
        self.session.commit()

    def set_sound_warnings_enabled(self, enabled):
        self._settings_row.sound_warnings_enabled = enabled
        self.session.commit()

    def set_sound_tier_thresholds(self, small_max, medium_max):
        self._settings_row.sound_tier_small_max = small_max
        self._settings_row.sound_tier_medium_max = medium_max
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
        gold_spent=0,
        asset_id=None
    ):
        if currency == "DIVINE":
            unit_price_chaos = self.divine_to_chaos(entered_price)
        else:
            unit_price_chaos = entered_price

        trade = Trade(
            league_id=self.league.id,
            trading_day_id=self.trading_day.id,
            asset_id=asset_id,
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
    # DELETE (directive 30/42: strong confirmation is the UI's job;
    # this layer only enforces the protection rule and keeps
    # inventory/stats correct afterward — nothing else caches a
    # derived value, so there is nothing else to recalculate.)
    # ---------------------------------------------------------------

    def delete_sale(self, sale_id):
        sale = self.session.get(Sale, sale_id)

        if sale is None:
            raise ValueError(f"Sale {sale_id} not found.")

        trade = sale.trade
        trade.quantity_sold -= sale.quantity

        self.session.delete(sale)
        self.session.commit()

    def delete_trade(self, trade_id):
        trade = self.get_trade(trade_id)

        if trade is None:
            raise ValueError(f"Trade {trade_id} not found.")

        if trade.quantity_sold > 0:
            raise TradeHasSalesError(
                f"Trade {trade_id} has {len(trade.sales)} sale(s) "
                f"against it — delete those first."
            )

        self.session.delete(trade)
        self.session.commit()

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

    def open_trades_for_item(self, item_name):
        return [
            trade for trade in self.open_trades()
            if trade.item_name == item_name
        ]

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
                "sale_id": None,
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
                    "sale_id": sale.id,
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
        return self.all_transactions()[:limit]

    # ---------------------------------------------------------------
    # ANALYTICS
    # ---------------------------------------------------------------

    def analytics_summary(self, trading_day_ids=None):
        """Everything the Analytics page needs for a set of Trading
        Days (the current one by default; a single id or any iterable
        of ids otherwise — used for the live "Today" view, a single
        historical day's frozen snapshot, and the Analytics "Last 7
        Days"/"All" scopes, which just aggregate over more ids). ROI
        and New Trades vs Carry-over Sales follow the locked
        accounting rules (directive Q18/19): a partially-sold new
        trade contributes only the sold portion, and Gold is never
        mixed into trading profit/ROI."""

        if trading_day_ids is None:
            trading_day_ids = {self.trading_day.id}
        elif isinstance(trading_day_ids, int):
            trading_day_ids = {trading_day_ids}
        else:
            trading_day_ids = set(trading_day_ids)

        all_trades = self.session.execute(
            select(Trade).where(Trade.league_id == self.league.id)
        ).scalars().all()

        new_trades_today = [
            trade for trade in all_trades
            if trade.trading_day_id in trading_day_ids
        ]
        new_trade_ids = {trade.id for trade in new_trades_today}

        today_sales = self.session.execute(
            select(Sale).where(Sale.trading_day_id.in_(trading_day_ids))
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
                sale.trading_day_id in trading_day_ids
                for sale in trade.sales
            )
        ]
        completed_trades_today = len(closed_today_trades)
        average_profit_per_trade = (
            sum(trade.realized_profit for trade in closed_today_trades)
            / completed_trades_today
            if completed_trades_today else 0
        )

        trade_rois = [
            trade.realized_profit / trade.invested_chaos
            for trade in closed_today_trades
            if trade.invested_chaos
        ]
        average_roi_per_trade = (
            sum(trade_rois) / len(trade_rois) if trade_rois else 0
        )
        win_rate = (
            sum(1 for trade in closed_today_trades if trade.realized_profit > 0)
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

        for entry in item_performance.values():
            entry["roi"] = (
                entry["profit"] / entry["cost"] if entry["cost"] else 0
            )
            # Average price actually paid per unit for the sold
            # portion — used by the ROI-vs-price correlation chart.
            entry["avg_buy_price"] = (
                entry["cost"] / entry["quantity_sold"]
                if entry["quantity_sold"] else 0
            )

        item_performance_list = sorted(
            item_performance.values(),
            key=lambda entry: entry["profit"],
            reverse=True
        )

        # Unrealized inventory is valued at cost price (directive
        # Q30) and reflects ALL currently open trades, not just ones
        # opened on this particular day — inventory carries over.
        inventory_value = sum(
            trade.invested_chaos for trade in all_trades if trade.is_open
        )

        return {
            "inventory_value": inventory_value,
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
            "average_roi_per_trade": average_roi_per_trade,
            "win_rate": win_rate,
            "gold_spent_today": gold_spent_today,
            "gold_received_today": gold_received_today,
            "total_realized_profit": self.total_realized_profit(),
            "item_performance": item_performance_list
        }
