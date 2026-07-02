"""Write-side orchestration: reconciling a local row with the Strava API.

Everything that touches the *network and* the database lives here — the one place that
pulls a payload from Strava (or pushes an edit back) and folds it into our tables. Kept
out of the models so an ``Activity``/``Gear``/``Athlete`` instance stays a plain data
object (parse via its ``read_json`` classmethod, compute via its properties) and so these
flows are callable and mockable without first constructing a row.

Reads stay in the querysets; the rest of ``services`` is pure computation over already
fetched collections. This module is the counterpart: the writes.
"""
from __future__ import annotations

from django.db import transaction

from strava.api import StravaApi
from strava.models import Activity, Athlete, Gear


def gear_ensure(*, gear_id: str | None, athlete: Athlete | None = None) -> Gear | None:
    """Return the ``Gear`` for ``gear_id``, fetching it from Strava and storing it the
    first time it is seen. An activity without gear (``gear_id`` falsy) returns ``None``."""
    if not gear_id:
        return None

    existing = Gear.objects.filter(id=gear_id).first()
    if existing:
        return existing

    data = StravaApi().get_gear(gear_id)
    fields = Gear.read_json(data)
    fields["json"] = data
    fields["athlete"] = athlete
    gear, _created = Gear.objects.get_or_create(id=data["id"], defaults=fields)
    return gear


def gear_fetch(gear: Gear) -> Gear:
    """Pull ``gear`` from Strava, store the raw payload, and re-derive its columns."""
    gear.json = StravaApi().get_gear(gear.id)
    gear.save(update_fields=["json"])
    for attr, value in Gear.read_json(gear.json).items():
        setattr(gear, attr, value)
    gear.save()
    return gear


@transaction.atomic
def activity_apply_json(activity: Activity, *, athlete: Athlete | None = None) -> Activity:
    """Refresh ``activity``'s promoted columns from its stored ``json`` and make sure its
    gear exists locally (fetched from Strava on first sight). Persists and returns it."""
    for attr, value in Activity.read_json(activity.json).items():
        setattr(activity, attr, value)

    gear_ensure(gear_id=activity.gear_id, athlete=athlete or activity.athlete)

    activity.save()
    return activity


def activity_fetch(activity: Activity) -> Activity:
    """Pull the detailed activity from Strava, store the raw payload, and re-derive columns."""
    activity.json = StravaApi().get_activity(activity.id)
    activity.save(update_fields=["json"])
    return activity_apply_json(activity)


def activity_push(activity: Activity) -> Activity:
    """Push local edits (name/sport/gear) to Strava, then re-fetch so the row reflects the
    server's truth."""
    StravaApi().update_activity(
        id=activity.id,
        name=activity.name,
        sport_type=activity.sport_type,
        gear_id=activity.gear_id,
    )
    return activity_fetch(activity)


def athlete_sync() -> Athlete:
    """Fetch the authenticated athlete from Strava and upsert the local row."""
    return Athlete.store(StravaApi().get_athlete())
