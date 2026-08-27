from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base
from backend.trades import TradeService


def _open_service(db_path):
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return TradeService(session=session)


def test_data_survives_across_separate_service_instances(tmp_path):
    db_path = tmp_path / "persistence_test.db"

    first = _open_service(db_path)
    trade = first.open_trade(
        item_name="Awakened Sextant", quantity=7,
        currency="CHAOS", entered_price=40
    )
    trade_id = trade.id
    first.session.close()

    second = _open_service(db_path)
    reloaded = second.get_trade(trade_id)

    assert reloaded is not None
    assert reloaded.item_name == "Awakened Sextant"
    assert reloaded.quantity_bought == 7
    assert reloaded.remaining == 7
