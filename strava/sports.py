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

from django.utils.translation import gettext_lazy as _

from strava.choices import SportType


def _is_cycling(sport_type):
    return "Ride" in sport_type or sport_type in ("Velomobile", "Handcycle")


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
