import pytest

from backend.trades import TradeHasSalesError


def test_buy_creates_one_open_trade(trade_service):
    trade = trade_service.open_trade(
        item_name="Chaos Orb", quantity=10,
        currency="CHAOS", entered_price=1
    )

    assert trade.id is not None
    assert trade.quantity_bought == 10
    assert trade.quantity_sold == 0
    assert trade.is_open
    assert trade.remaining == 10
    assert trade in trade_service.open_trades()


def test_sell_creates_a_sale_and_reduces_remaining(trade_service):
    trade = trade_service.open_trade(
        item_name="Divine Orb", quantity=5,
        currency="CHAOS", entered_price=100
    )

    sale = trade_service.sell_from_trade(
        trade_id=trade.id, quantity=5,
        currency="CHAOS", entered_price=150
    )

    assert sale.quantity == 5
    assert sale.profit == (150 - 100) * 5
    assert trade.remaining == 0
    assert not trade.is_open


def test_partial_sell_keeps_trade_open(trade_service):
    trade = trade_service.open_trade(
        item_name="Exalted Orb", quantity=10,
        currency="CHAOS", entered_price=20
    )

    trade_service.sell_from_trade(
        trade_id=trade.id, quantity=4,
        currency="CHAOS", entered_price=30
    )

    assert trade.remaining == 6
    assert trade.is_open
    assert trade in trade_service.open_trades()


def test_full_close_removes_trade_from_open_trades(trade_service):
    trade = trade_service.open_trade(
        item_name="Orb of Alchemy", quantity=3,
        currency="CHAOS", entered_price=5
    )

    trade_service.sell_from_trade(
        trade_id=trade.id, quantity=3,
        currency="CHAOS", entered_price=8
    )

    assert not trade.is_open
    assert trade not in trade_service.open_trades()


def test_isolated_inventory_across_multiple_buys(trade_service):
    """Directive Q18: multiple BUYs of the same item are isolated
    trades, not merged / not global FIFO — selling from one never
    touches another's inventory."""

    first = trade_service.open_trade(
        item_name="Vaal Orb", quantity=10,
        currency="CHAOS", entered_price=5
    )
    second = trade_service.open_trade(
        item_name="Vaal Orb", quantity=10,
        currency="CHAOS", entered_price=8
    )

    trade_service.sell_from_trade(
        trade_id=first.id, quantity=10,
        currency="CHAOS", entered_price=9
    )

    assert first.remaining == 0
    assert second.remaining == 10
    assert second.is_open

    stash = trade_service.stash_summary()
    vaal_entry = next(e for e in stash if e["item_name"] == "Vaal Orb")
    assert vaal_entry["quantity"] == 10
    assert vaal_entry["cost_chaos"] == 10 * 8


def test_insufficient_inventory_raises(trade_service):
    trade = trade_service.open_trade(
        item_name="Regal Orb", quantity=3,
        currency="CHAOS", entered_price=10
    )

    with pytest.raises(ValueError):
        trade_service.sell_from_trade(
            trade_id=trade.id, quantity=4,
            currency="CHAOS", entered_price=15
        )

    with pytest.raises(ValueError):
        trade_service.sell_from_trade(
            trade_id=trade.id, quantity=0,
            currency="CHAOS", entered_price=15
        )


def test_profit_calculation_chaos(trade_service):
    trade = trade_service.open_trade(
        item_name="Blessed Orb", quantity=20,
        currency="CHAOS", entered_price=12
    )

    sale = trade_service.sell_from_trade(
        trade_id=trade.id, quantity=20,
        currency="CHAOS", entered_price=15
    )

    assert sale.cost_chaos == 20 * 12
    assert sale.total_chaos == 20 * 15
    assert sale.profit == 20 * 15 - 20 * 12


def test_profit_calculation_divine_uses_locked_conversion(trade_service):
    trade_service.set_divine_rate(200)

    trade = trade_service.open_trade(
        item_name="Mirror Shard", quantity=1,
        currency="DIVINE", entered_price=2
    )
    assert trade.unit_price_chaos == 2 * 200

    sale = trade_service.sell_from_trade(
        trade_id=trade.id, quantity=1,
        currency="DIVINE", entered_price=3
    )
    assert sale.unit_price_chaos == 3 * 200
    assert sale.profit == 3 * 200 - 2 * 200


def test_roi_calculation_via_analytics_summary(trade_service):
    trade = trade_service.open_trade(
        item_name="Ancient Orb", quantity=10,
        currency="CHAOS", entered_price=10
    )
    trade_service.sell_from_trade(
        trade_id=trade.id, quantity=10,
        currency="CHAOS", entered_price=15
    )

    summary = trade_service.analytics_summary()

    cost = 10 * 10
    profit = 10 * 15 - cost
    assert summary["roi"] == pytest.approx(profit / cost)


def test_gold_accounting_stored_separately_from_profit(trade_service):
    trade = trade_service.open_trade(
        item_name="Orb of Scouring", quantity=5,
        currency="CHAOS", entered_price=10, gold_spent=500
    )
    sale = trade_service.sell_from_trade(
        trade_id=trade.id, quantity=5,
        currency="CHAOS", entered_price=20, gold_received=800
    )

    assert trade.gold_spent == 500
    assert sale.gold_received == 800
    # Gold never leaks into the profit figure (directive Q22).
    assert sale.profit == 5 * 20 - 5 * 10


def test_historical_rate_preservation(trade_service):
    trade_service.set_divine_rate(150)
    trade = trade_service.open_trade(
        item_name="Hinekora's Lock", quantity=1,
        currency="DIVINE", entered_price=1
    )
    original_unit_price = trade.unit_price_chaos
    assert original_unit_price == 150

    # Changing the rate afterward must not retroactively change what
    # this trade already recorded.
    trade_service.set_divine_rate(999)
    assert trade.unit_price_chaos == original_unit_price


def test_trading_day_boundary_is_the_sale_date_not_the_buy_date(
    trade_service
):
    trade = trade_service.open_trade(
        item_name="Awakened Sextant", quantity=1,
        currency="CHAOS", entered_price=10
    )
    opening_day_id = trade.trading_day_id

    trade_service.start_new_trading_day()
    assert trade_service.trading_day.id != opening_day_id

    sale = trade_service.sell_from_trade(
        trade_id=trade.id, quantity=1,
        currency="CHAOS", entered_price=20
    )

    # The sale belongs to the day it happened on, not the day the
    # trade was opened on (directive Q14).
    assert sale.trading_day_id == trade_service.trading_day.id
    assert sale.trading_day_id != opening_day_id
    assert trade_service.today_profit() == sale.profit


def test_new_trades_vs_carryover_sales(trade_service):
    carryover_trade = trade_service.open_trade(
        item_name="Simple Sextant", quantity=1,
        currency="CHAOS", entered_price=10
    )
    trade_service.start_new_trading_day()

    new_trade = trade_service.open_trade(
        item_name="Prime Sextant", quantity=1,
        currency="CHAOS", entered_price=10
    )

    trade_service.sell_from_trade(
        trade_id=carryover_trade.id, quantity=1,
        currency="CHAOS", entered_price=20
    )
    trade_service.sell_from_trade(
        trade_id=new_trade.id, quantity=1,
        currency="CHAOS", entered_price=30
    )

    summary = trade_service.analytics_summary()

    assert summary["new_trades_count"] == 1
    assert summary["carryover_sales_count"] == 1
    assert summary["new_trade_sales_count"] == 1


def test_delete_sale_restores_inventory(trade_service):
    trade = trade_service.open_trade(
        item_name="Tempering Orb", quantity=10,
        currency="CHAOS", entered_price=5
    )
    sale = trade_service.sell_from_trade(
        trade_id=trade.id, quantity=4,
        currency="CHAOS", entered_price=8
    )

    trade_service.delete_sale(sale.id)

    assert trade.remaining == 10
    assert trade.quantity_sold == 0
    assert len(trade.sales) == 0


def test_delete_trade_blocked_once_sold(trade_service):
    trade = trade_service.open_trade(
        item_name="Sacred Orb", quantity=5,
        currency="CHAOS", entered_price=5
    )
    trade_service.sell_from_trade(
        trade_id=trade.id, quantity=1,
        currency="CHAOS", entered_price=10
    )

    with pytest.raises(TradeHasSalesError):
        trade_service.delete_trade(trade.id)

    # Still fully deletable once its sale is gone.
    trade_service.delete_sale(trade.sales[0].id)
    trade_service.delete_trade(trade.id)
    assert trade_service.get_trade(trade.id) is None
