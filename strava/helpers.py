"""Small, pure helper functions shared across the strava app.

Generic, side-effect-free utilities — formatting, geo, string and date helpers — with no
dependency on the request cycle. Split out of analytics.py so both it and the views can
share them without pulling in the heavier analytics computations.
"""
import math
import unicodedata

from django.utils import timezone

from strava.consts import MIN_HIKE_PACE_SEC


def local_date(activity):
    """The activity's start date in the active timezone (dates group by local day)."""
    return timezone.localtime(activity.start_date).date()


def has_gps(activity):
    return activity.start_lat is not None


def unaccent(s):
    """Lowercase and strip diacritics — the server-side twin of the map filter's JS
    ``unaccent()`` so a filtered search here matches what the map shows."""
    normalized = unicodedata.normalize('NFD', s or '')
    return ''.join(c for c in normalized if not unicodedata.combining(c)).lower()


def fmt_pace(seconds):
    """Seconds-per-unit formatted as m:ss (a per-km or per-100m pace)."""
    m, s = divmod(int(round(seconds)), 60)
    return f'{m}:{s:02d}'


def fmt_hms(seconds):
    """Seconds as h:mm:ss, dropping the hours part when under an hour (m:ss)."""
    total = int(round(seconds))
    h, r = divmod(total, 3600)
    m, s = divmod(r, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two lat/lng points, in kilometres."""
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def home_location(activities):
    """Estimate "home" as the busiest start location. Start points are bucketed on a
    ~1 km grid (2-decimal rounding); the most-used bucket's averaged coordinates are
    returned as ``(lat, lng)``, or ``None`` when no activity has GPS."""
    clusters = {}
    for a in activities:
        if a.start_lat is None or a.start_lng is None:
            continue
        key = (round(a.start_lat, 2), round(a.start_lng, 2))
        agg = clusters.setdefault(key, [0, 0.0, 0.0])
        agg[0] += 1
        agg[1] += a.start_lat
        agg[2] += a.start_lng
    if not clusters:
        return None
    count, lat_sum, lng_sum = max(clusters.values(), key=lambda agg: agg[0])
    return lat_sum / count, lng_sum / count


def hike_pace_ok(a):
    """A genuine hike isn't faster than MIN_HIKE_PACE_SEC per km. Activities with no pace
    data (missing time/distance) are kept — there's nothing to disqualify on."""
    if not a.moving_time or not a.distance:
        return True
    return a.moving_time / (a.distance / 1000) >= MIN_HIKE_PACE_SEC
