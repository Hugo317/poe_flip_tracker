# Defaults only — Hugo asked for these to be adjustable in-app, so the
# real values live in GlobalSettings (sound_tier_small_max/
# sound_tier_medium_max) and get passed in by the caller. These stay
# here just as the fallback/starting values a fresh database seeds.
DEFAULT_TIER_SMALL_MAX = 200
DEFAULT_TIER_MEDIUM_MAX = 800


def classify_sale_feedback(
    profit,
    tier_small_max=DEFAULT_TIER_SMALL_MAX,
    tier_medium_max=DEFAULT_TIER_MEDIUM_MAX
):
    """Maps a single sale's profit to a feedback category. Runs once
    per sale, partial or not — each sale is its own event. Boundary
    values (tier_small_max, tier_medium_max exactly) round up into the
    next tier."""

    if profit < 0:
        return "warning"

    if profit == 0:
        return "neutral"

    if profit < tier_small_max:
        return "tink_small"

    if profit < tier_medium_max:
        return "tink_medium"

    return "tink_large"
