"""Template access to the current Strava athlete (nav name/avatar/counts).

    {% load strava_athlete %}
    {% strava_athlete as athlete %}
    {{ athlete.full_name }}

Returns None before the first import, so templates guard with `{% if athlete %}`.
Using a tag (rather than a context processor) keeps this self-contained in the app —
the consuming project needs no TEMPLATES settings change.
"""

from django import template

from strava.models import Athlete

register = template.Library()


@register.simple_tag
def strava_athlete():
    """The athlete the frontend renders, or None before the first import."""
    return Athlete.current()
