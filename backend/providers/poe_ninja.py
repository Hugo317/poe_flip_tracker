import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://poe.ninja"
REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "DivineFlipper/1.0"

# Directive Q31: never hit the API more often than necessary, and
# back off instead of hammering it on transient failures.
MIN_REQUEST_INTERVAL_SECONDS = 1.0
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.0


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

    def __init__(self):
        self._last_request_at = 0.0

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
        # Icons are served from the PoE CDN, not poe.ninja's API —
        # a different host/service, so the economy-API throttle
        # (Q31) doesn't apply here. A fresh catalog can need ~290 of
        # these; throttling them too would make first launch take
        # minutes for no benefit.
        return self._fetch(url, throttle=False)

    def _get_json(self, url):
        try:
            return json.loads(self._fetch(url, throttle=True))
        except json.JSONDecodeError as error:
            raise PoeNinjaUnavailable(str(error)) from error

    def _throttle(self):
        elapsed = time.monotonic() - self._last_request_at
        wait = MIN_REQUEST_INTERVAL_SECONDS - elapsed

        if wait > 0:
            time.sleep(wait)

        self._last_request_at = time.monotonic()

    def _fetch(self, url, throttle):
        """Single GET with retry/backoff on transient failures
        (connection errors, 429, 5xx). A non-transient HTTP error
        (e.g. 404) fails immediately — retrying won't help."""

        last_error = None

        for attempt in range(MAX_ATTEMPTS):
            if throttle:
                self._throttle()

            try:
                request = urllib.request.Request(
                    url, headers={"User-Agent": USER_AGENT}
                )

                with urllib.request.urlopen(
                    request, timeout=REQUEST_TIMEOUT_SECONDS
                ) as response:
                    return response.read()

            except urllib.error.HTTPError as error:
                last_error = error

                if error.code != 429 and error.code < 500:
                    raise PoeNinjaUnavailable(str(error)) from error

            except (urllib.error.URLError, OSError) as error:
                last_error = error

            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(BACKOFF_BASE_SECONDS * (2 ** attempt))

        raise PoeNinjaUnavailable(str(last_error))
