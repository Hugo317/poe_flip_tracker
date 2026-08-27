from sqlalchemy import select

from backend.assets_service import AssetService
from backend.db.models import Asset
from backend.providers.poe_ninja import PoeNinjaUnavailable


class FakeProvider:
    """Stands in for PoeNinjaProvider — no network calls, and can be
    told to simulate poe.ninja being unreachable."""

    def __init__(self, items=None, divine_chaos_value=200, fail=False):
        self.items = items or []
        self.divine_chaos_value = divine_chaos_value
        self.fail = fail

    def get_currency_overview(self, league):
        if self.fail:
            raise PoeNinjaUnavailable("simulated outage")

        return {
            "items": self.items,
            "divine_chaos_value": self.divine_chaos_value
        }

    def download_image(self, url):
        if self.fail:
            raise PoeNinjaUnavailable("simulated outage")

        return b"fake-image-bytes"

    def get_leagues(self):
        if self.fail:
            raise PoeNinjaUnavailable("simulated outage")

        return ["Standard"]


def _item(name, external_id, chaos_value=10):
    return {
        "external_id": external_id,
        "name": name,
        "category": "Currency",
        "icon_url": None,
        "chaos_value": chaos_value
    }


def test_refresh_catalog_populates_assets(session, tmp_path):
    provider = FakeProvider(items=[
        _item("Chaos Orb", "1"), _item("Divine Orb", "2", 200)
    ])
    service = AssetService(session=session, provider=provider, cache_dir=tmp_path)

    divine_rate = service.refresh_catalog("Standard")

    assert divine_rate == 200
    names = {asset.name for asset in service.active_assets()}
    assert names == {"Chaos Orb", "Divine Orb"}


def test_refresh_catalog_returns_none_when_unreachable(session, tmp_path):
    provider = FakeProvider(fail=True)
    service = AssetService(session=session, provider=provider, cache_dir=tmp_path)

    result = service.refresh_catalog("Standard")

    assert result is None
    assert service.active_assets() == []


def test_cached_assets_survive_a_later_outage(session, tmp_path):
    provider = FakeProvider(items=[_item("Chaos Orb", "1")])
    service = AssetService(session=session, provider=provider, cache_dir=tmp_path)
    service.refresh_catalog("Standard")

    assert len(service.active_assets()) == 1

    # poe.ninja goes down on a later refresh — cached data must
    # survive untouched (directive 28/36.9: never require internet).
    provider.fail = True
    result = service.refresh_catalog("Standard")

    assert result is None
    assert len(service.active_assets()) == 1


def test_asset_marked_inactive_when_it_drops_out_of_catalog(session, tmp_path):
    provider = FakeProvider(items=[
        _item("Chaos Orb", "1"), _item("Vaal Orb", "2")
    ])
    service = AssetService(session=session, provider=provider, cache_dir=tmp_path)
    service.refresh_catalog("Standard")
    assert len(service.active_assets()) == 2

    # Vaal Orb no longer appears in a later refresh.
    provider.items = [_item("Chaos Orb", "1")]
    service.refresh_catalog("Standard")

    names = {asset.name for asset in service.active_assets()}
    assert names == {"Chaos Orb"}

    all_names = {
        asset.name for asset in
        service.session.execute(select(Asset)).scalars().all()
    }
    assert all_names == {"Chaos Orb", "Vaal Orb"}  # never deleted
