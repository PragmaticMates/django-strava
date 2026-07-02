"""Single source of truth for the sport filter taxonomy.

The three sport filters (dashboard map pill, activities page, gallery) all share
one dropdown: a flat list of every sport present in the data, preceded by a
"Top sports" category of four grouped meta-sports. Group membership is derived
from ``SportType`` here so the server-side filter (``for_sport_selection``), the
dashboard's in-Python filter (``sport_matches``) and the client-side dropdown
(``sport-filter.js``, fed via ``group_data``) can never drift apart.

A filter value is one of: ``'all'``, a group key (``'group-run'`` …) or an exact
``sport_type`` (``'Run'``, ``'TrailRun'`` …).
"""

from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from strava.choices import SportType


def _is_cycling(sport_type):
    return "Ride" in sport_type or sport_type in ("Velomobile", "Handcycle")


# --------------------------------------------------------------------------- #
# Broad activity categories
# --------------------------------------------------------------------------- #
# The coarse bucket a sport falls in, used for map-marker styling (Activity.type) and
# the category filter (ActivityQuerySet.for_sport_category). Each sport maps to exactly
# one bucket: the first matching rule wins, and anything unmatched is DEFAULT_CATEGORY.
# A rule is either a substring test ("contains") or an explicit membership set ("values").
# This is the single source of truth — Activity.type and the queryset filter both derive
# from it, so the Python and SQL views of "what category is this?" can't drift apart.
ACTIVITY_CATEGORIES = (
    ("trail", {"contains": "Trail"}),
    ("hike", {"values": ("Hike", "Snowshoe")}),
    ("walk", {"values": ("Walk",)}),
    ("ride", {"contains": "Ride"}),
    ("swim", {"contains": "Swim"}),
)
DEFAULT_CATEGORY = "run"


def _rule_matches(rule, sport_type):
    if "contains" in rule:
        return rule["contains"] in sport_type
    return sport_type in rule["values"]


def _rule_q(rule):
    if "contains" in rule:
        return Q(sport_type__contains=rule["contains"])
    return Q(sport_type__in=list(rule["values"]))


def category_for(sport_type):
    """The broad category ('trail'/'hike'/'walk'/'ride'/'swim'/'run') for a sport_type."""
    for name, rule in ACTIVITY_CATEGORIES:
        if _rule_matches(rule, sport_type):
            return name
    return DEFAULT_CATEGORY


def category_q(category):
    """A ``Q`` selecting activities in a broad ``category``, or ``None`` for an unknown
    one (so callers pass the queryset through unfiltered). ``DEFAULT_CATEGORY`` ('run') is
    the catch-all: everything matching none of the explicit category rules."""
    rules = dict(ACTIVITY_CATEGORIES)
    if category in rules:
        return _rule_q(rules[category])
    if category == DEFAULT_CATEGORY:
        q = Q()
        for _name, rule in ACTIVITY_CATEGORIES:
            q &= ~_rule_q(rule)
        return q
    return None


# Exact sport types per personal-records / compare tab. An explicit allow-list (rather
# than the coarse categories above, whose "run" fallback would swallow every unlisted
# sport) keeps unrelated fast activities out of the running/cycling PRs, and lets e-bikes
# be excluded from cycling (motor assistance would unfairly dominate the records).
RECORD_SPORTS = {
    "Running": {"Run", "TrailRun", "VirtualRun"},
    "Cycling": {"Ride", "GravelRide", "MountainBikeRide", "VirtualRide", "Velomobile", "Handcycle"},
    "Hiking": {"Hike", "Snowshoe", "Walk"},
    "Swimming": {"Swim"},
}


# Ordered "Top sports" groups. ``icon`` names a glyph in sport-filter.js.
SPORT_GROUPS = [
    {"key": "group-run", "label": _("Running"), "icon": "run", "types": ["Run", "TrailRun", "VirtualRun"]},
    {"key": "group-ride", "label": _("Cycling"), "icon": "ride",
     "types": [s for s in SportType.values if _is_cycling(s)]},
    {"key": "group-walk", "label": _("Walking"), "icon": "hike", "types": ["Hike", "Walk", "Snowshoe"]},
    {"key": "group-swim", "label": _("Swimming"), "icon": "swim",
     "types": [s for s in SportType.values if "Swim" in s]},
]

_GROUP_BY_KEY = {group["key"]: group for group in SPORT_GROUPS}


def types_for(value):
    """A filter value's sport types: a group key expands to its members, anything
    else (an exact sport_type) maps to itself."""
    group = _GROUP_BY_KEY.get(value)
    return group["types"] if group else [value]


def sport_matches(value, sport_type):
    """Whether a single ``sport_type`` satisfies the filter ``value``."""
    return not value or value == "all" or sport_type in types_for(value)


def group_data():
    """JSON-safe group definitions for ``json_script`` (labels forced to str). Each
    carries its ``glyph`` (SVG markup) so the client dropdown never holds its own icons."""
    from strava.sport_icons import GROUP_GLYPHS  # local import: sport_icons imports us

    return [
        {"key": g["key"], "label": str(g["label"]), "icon": g["icon"],
         "glyph": GROUP_GLYPHS[g["icon"]], "types": g["types"]}
        for g in SPORT_GROUPS
    ]


def sport_options(queryset):
    """``[[sport_type, label, glyph], …]`` for the distinct sports present in
    ``queryset``, sorted by label — the flat "All sports" section of the dropdown.
    The third element is the sport's SVG glyph so the client carries no icon copy."""
    from strava.sport_icons import icon_for  # local import: sport_icons imports us

    # order_by("sport_type") overrides the model's default ordering, which would
    # otherwise leak into the SELECT and defeat .distinct() (duplicate rows).
    types = queryset.order_by("sport_type").values_list("sport_type", flat=True).distinct()
    options = [[t, SportType(t).label, icon_for(t)] for t in types if t]
    options.sort(key=lambda option: option[1])
    return options
