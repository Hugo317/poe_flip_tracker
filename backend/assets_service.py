import io
import sys
from pathlib import Path

from PIL import Image, ImageEnhance
from sqlalchemy import select

from backend.db.models import Asset, _now
from backend.providers.poe_ninja import PoeNinjaProvider, PoeNinjaUnavailable

# poe.ninja's currency/item art is quite dark and muted at the small
# sizes it's shown at in the UI (Hugo's request) — boosted once here,
# at cache time, rather than on every render.
ICON_BRIGHTNESS = 1.20
ICON_CONTRAST = 1.05
ICON_SATURATION = 1.20


def _vivify_icon(image_bytes):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    image = ImageEnhance.Brightness(image).enhance(ICON_BRIGHTNESS)
    image = ImageEnhance.Contrast(image).enhance(ICON_CONTRAST)
    image = ImageEnhance.Color(image).enhance(ICON_SATURATION)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def get_image_cache_dir():
    """OS-appropriate cache directory, deliberately separate from the
    user-data directory (directive Q37) — this holds re-downloadable
    files, not anything that needs backing up."""

    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    elif sys.platform == "win32":
        base = Path.home() / "AppData" / "Local"
    else:
        base = Path.home() / ".cache"

    cache_dir = base / "DivineFlipper" / "images"
    cache_dir.mkdir(parents=True, exist_ok=True)

    return cache_dir


class AssetService:
    """Owns the tradeable-item catalog and its local image cache.
    Provider-agnostic on the outside (directive 36.5: hidden behind
    this interface so a different source could replace poe.ninja
    later) even though PoeNinjaProvider is the only one that exists."""

    def __init__(self, session, provider=None, cache_dir=None):
        self.session = session
        self.provider = provider or PoeNinjaProvider()
        self.cache_dir = cache_dir or get_image_cache_dir()

    def available_leagues(self):
        """Live league list from poe.ninja (current temp league,
        Standard, Hardcore, etc.), or an empty list if unreachable —
        callers should fall back to locally-known leagues."""

        try:
            return self.provider.get_leagues()
        except PoeNinjaUnavailable:
            return []

    def refresh_catalog(self, league):
        """Fetches the live catalog, upserts Asset rows (new ones
        created, existing ones updated and marked seen, anything no
        longer present marked inactive — never deleted, per directive
        25.1/36.6), and downloads any missing icons.

        Returns the live divine_chaos_value, or None if unreachable —
        callers must treat that as "stay offline, use cached data"
        rather than an error (directive 28/36.9)."""

        try:
            overview = self.provider.get_currency_overview(league)
        except PoeNinjaUnavailable:
            return None

        seen_external_ids = set()

        for item in overview["items"]:
            seen_external_ids.add(item["external_id"])
            self._upsert_asset(item)

        self.session.commit()

        # Anything not in this refresh's response is no longer live —
        # mark inactive rather than delete, so historical trades that
        # reference it keep resolving.
        all_assets = self.session.execute(select(Asset)).scalars().all()

        for asset in all_assets:
            asset.is_active = asset.external_id in seen_external_ids

        self.session.commit()

        for asset in all_assets:
            if asset.is_active and asset.icon_path is None:
                self._download_icon(asset)

        self.session.commit()

        return overview["divine_chaos_value"]

    def _upsert_asset(self, item):
        asset = self.session.execute(
            select(Asset).where(Asset.external_id == item["external_id"])
        ).scalar_one_or_none()

        if asset is None:
            asset = Asset(external_id=item["external_id"])
            self.session.add(asset)

        asset.name = item["name"]
        asset.category = item["category"]
        asset.icon_url = item["icon_url"]
        asset.is_active = True
        asset.last_seen_at = _now()

    def _download_icon(self, asset):
        if not asset.icon_url:
            return

        try:
            image_bytes = self.provider.download_image(asset.icon_url)
        except PoeNinjaUnavailable:
            return

        image_bytes = _vivify_icon(image_bytes)

        filename = f"{asset.external_id}.png"

        with (self.cache_dir / filename).open("wb") as file:
            file.write(image_bytes)

        asset.icon_path = filename

    def rebuild_image_cache(self, league):
        """Directive 27: 'Rebuild cache' — wipes every cached icon
        file and forgets each asset's icon_path, then re-downloads
        everything from scratch. For when a cached image is missing
        or corrupted, not for routine use (refresh_catalog already
        covers picking up new/changed items)."""

        for path in self.cache_dir.glob("*.png"):
            path.unlink()

        for asset in self.session.execute(select(Asset)).scalars().all():
            asset.icon_path = None

        self.session.commit()

        return self.refresh_catalog(league)

    def icon_file_path(self, asset):
        """Absolute local path to a cached icon, or None if not
        cached. asset.icon_path itself stays a bare relative filename
        (directive 36.7 — never store an absolute, machine-specific
        path in the database)."""

        if not asset.icon_path:
            return None

        path = self.cache_dir / asset.icon_path
        return path if path.exists() else None

    def active_assets(self):
        return list(
            self.session.execute(
                select(Asset)
                .where(Asset.is_active.is_(True))
                .order_by(Asset.name)
            ).scalars().all()
        )

    def get_asset_by_name(self, name):
        return self.session.execute(
            select(Asset).where(Asset.name == name)
        ).scalar_one_or_none()

    def get_asset(self, asset_id):
        return self.session.get(Asset, asset_id)
