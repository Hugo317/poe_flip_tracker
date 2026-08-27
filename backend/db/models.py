from datetime import datetime

from sqlalchemy import ForeignKey, MetaData
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Consistent constraint/index naming so Alembic autogenerate produces
# stable, predictable migration names (directive Q3: use convention).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[str] = mapped_column(default=_now)


class TradingDay(Base):
    __tablename__ = "trading_days"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    started_at: Mapped[str] = mapped_column(default=_now)
    closed_at: Mapped[str | None] = mapped_column(default=None)


class Asset(Base):
    """The tradeable-item catalog, refreshed from the configured
    provider (poe.ninja for V1 — directive 36.5/36.6). Never deleted:
    an item that drops out of the live catalog is marked inactive so
    historical Trades that reference it keep resolving correctly."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)

    # The provider's own stable id (e.g. poe.ninja's "divine") — used
    # as the cache key for the downloaded icon file, per directive
    # 36.7 ("prefer stable asset/item identifiers for cache keys").
    external_id: Mapped[str] = mapped_column(unique=True)

    name: Mapped[str]
    category: Mapped[str]

    # Full remote CDN URL. The UI never depends on this directly
    # (directive 36.7) — it's only used to (re)populate icon_path.
    icon_url: Mapped[str | None] = mapped_column(default=None)

    # Relative path within the local image cache directory, e.g.
    # "divine.png" — never an absolute, machine-specific path.
    icon_path: Mapped[str | None] = mapped_column(default=None)

    is_active: Mapped[bool] = mapped_column(default=True)
    last_seen_at: Mapped[str] = mapped_column(default=_now)


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))

    # The Trading Day this trade was OPENED on. A sale's own
    # trading_day_id (below) is what its profit is attributed to —
    # a trade can stay open across day boundaries.
    trading_day_id: Mapped[int] = mapped_column(
        ForeignKey("trading_days.id")
    )

    # Nullable: a trade can in principle be opened for an item outside
    # the current catalog (e.g. entered while the catalog fetch failed
    # offline). item_name is a permanent snapshot either way, so
    # historical display never depends on asset_id still resolving —
    # per directive 25.1/36.6, an asset going inactive (or, in the
    # offline edge case, never having existed) must never break a past
    # trade's display.
    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id"), default=None
    )

    item_name: Mapped[str]
    currency: Mapped[str]
    entered_price: Mapped[int]
    unit_price_chaos: Mapped[int]
    quantity_bought: Mapped[int]
    quantity_sold: Mapped[int] = mapped_column(default=0)
    gold_spent: Mapped[int] = mapped_column(default=0)
    opened_at: Mapped[str] = mapped_column(default=_now)

    sales: Mapped[list["Sale"]] = relationship(
        back_populates="trade", order_by="Sale.id"
    )

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
        return sum(sale.profit for sale in self.sales)


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"))

    # The Trading Day this SALE happened on — the sole source of
    # truth for "today's profit" style boundaries (directive Q14: a
    # sale's profit belongs to the day it was sold on).
    trading_day_id: Mapped[int] = mapped_column(
        ForeignKey("trading_days.id")
    )

    quantity: Mapped[int]
    currency: Mapped[str]
    entered_price: Mapped[int]
    unit_price_chaos: Mapped[int]
    total_chaos: Mapped[int]
    cost_chaos: Mapped[int]
    profit: Mapped[int]
    gold_received: Mapped[int] = mapped_column(default=0)
    sold_at: Mapped[str] = mapped_column(default=_now)

    trade: Mapped["Trade"] = relationship(back_populates="sales")


class DivineRate(Base):
    """Append-only history — the current rate is the latest row for
    the league. Historical transactions store their own converted
    value independently, so changing this never alters them."""

    __tablename__ = "divine_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    chaos_value: Mapped[int]
    recorded_at: Mapped[str] = mapped_column(default=_now)


class GoldRate(Base):
    """Same append-only history pattern as DivineRate."""

    __tablename__ = "gold_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    gold_amount: Mapped[int]
    chaos_value: Mapped[int]
    recorded_at: Mapped[str] = mapped_column(default=_now)


class GlobalSettings(Base):
    """Singleton row (id is always 1) — global, not league-scoped,
    per directive 36.4 (sound/appearance/backup settings are global)."""

    __tablename__ = "global_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    sound_master_volume: Mapped[int] = mapped_column(default=100)
    sound_tink_enabled: Mapped[bool] = mapped_column(default=True)
    sound_warnings_enabled: Mapped[bool] = mapped_column(default=True)

    # TINK tier boundaries (chaos profit). Below tier_small_max is a
    # small TINK, below tier_medium_max a medium one, at/above it a
    # large one — see backend/sound_rules.py. User-adjustable per
    # Hugo's request; directive 28/37.12 anticipated this.
    sound_tier_small_max: Mapped[int] = mapped_column(default=200)
    sound_tier_medium_max: Mapped[int] = mapped_column(default=800)
