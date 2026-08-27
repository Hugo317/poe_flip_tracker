import json
from fractions import Fraction
from pathlib import Path

# Data source: poedb.tw/us/Currency_Exchange (datamined from the game's
# own Currency Exchange config), scraped 2026-08-27. Every stackable
# currency-tab item Faustus actually accepts has a "Base Gold Fee"
# here — everything else (Breachstones, Splinters, Reliquary Keys,
# Recombinators, Sextants, Scouting Reports, Sets, Blessings, etc.) is
# genuinely not tradable through the Currency Exchange in-game, so it
# has no entry (Hugo confirmed).
DATA_PATH = Path(__file__).resolve().parent / "data" / "gold_exchange_fees.json"

_fee_table = None


def _load_fee_table():
    global _fee_table

    if _fee_table is None:
        with open(DATA_PATH) as f:
            raw = json.load(f)

        _fee_table = {
            entry["name"]: Fraction(entry["numerator"], entry["denominator"])
            for entry in raw
        }

    return _fee_table


def gold_fee_per_unit(item_name):
    """Base Gold Fee for one unit of item_name, or None if it isn't a
    real Currency Exchange item."""
    return _load_fee_table().get(item_name)


def is_gold_exchange_eligible(item_name):
    return gold_fee_per_unit(item_name) is not None


def gold_cost_for(item_name, quantity):
    """Gold cost for quantity units of item_name, rounded up to the
    nearest whole Gold — or None if item_name has no known fee."""
    fee = gold_fee_per_unit(item_name)

    if fee is None:
        return None

    total = fee * quantity
    return -(-total.numerator // total.denominator)
