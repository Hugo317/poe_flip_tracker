import json
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://poe.ninja"
REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "DivineFlipper/1.0"


class PoeNinjaUnavailable(Exception):
    """Raised when poe.ninja can't be reached or returns something we
    can't parse. Callers must fall back to cached/offline data rather
    than let this propagate as a hard failure — directive 36.9/28
    (core operation must not require internet)."""


class PoeNinjaProvider:
    """Thin client for poe.ninja's public economy API — the V1 default
    provider (directive 36.5/36.6), deliberately kept this narrow so a
    different source could be swapped in later behind the same two
    methods without touching AssetService or the UI.

    Uses the "stash currency overview" endpoint rather than the newer
    currency-exchange one: the exchange endpoint's item metadata
    (`core.items`) only covers the two reference currencies (Chaos,
    Divine), while `currencyDetails` here is the actual full catalog
    (name + icon for ~290 currency-type items). Its own pricing lines
    key by a different id scheme (`detailsId` vs `currencyDetails`'
    `tradeId`, which ~30% of entries don't even have), so items and
    prices are joined by name instead, which is consistent across both.
    """

    def get_leagues(self):
        data = self._get_json(f"{BASE_URL}/poe1/api/economy/leagues")
        return [league["id"] for league in data]

    def get_currency_overview(self, league):
        """One call gives both the catalog (for AssetService) and live
        pricing (for the Divine rate)."""

        query = urllib.parse.urlencode({"league": league, "type": "Currency"})
        url = (
            f"{BASE_URL}/poe1/api/economy/stash/current/currency/overview"
            f"?{query}"
        )

        data = self._get_json(url)

        lines_by_name = {
            line["currencyTypeName"].lower(): line
            for line in data.get("lines", [])
            if "currencyTypeName" in line
        }

        items = []

        for detail in data.get("currencyDetails", []):
            name = detail["name"]
            line = lines_by_name.get(name.lower())

            items.append({
                "external_id": str(detail["id"]),
                "name": name,
                "category": "Currency",
                "icon_url": detail.get("icon"),
                "chaos_value": (
                    line["chaosEquivalent"] if line else None
                )
            })

        divine_item = next(
            (item for item in items if item["name"] == "Divine Orb"),
            None
        )

        return {
            "items": items,
            "divine_chaos_value": (
                divine_item["chaos_value"] if divine_item else None
            )
        }

    def download_image(self, url):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT}
            )

            with urllib.request.urlopen(
                request, timeout=REQUEST_TIMEOUT_SECONDS
            ) as response:
                return response.read()

        except (urllib.error.URLError, OSError) as error:
            raise PoeNinjaUnavailable(str(error)) from error

    def _get_json(self, url):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT}
            )

            with urllib.request.urlopen(
                request, timeout=REQUEST_TIMEOUT_SECONDS
            ) as response:
                return json.loads(response.read())

        except (urllib.error.URLError, OSError, json.JSONDecodeError) as error:
            raise PoeNinjaUnavailable(str(error)) from error
