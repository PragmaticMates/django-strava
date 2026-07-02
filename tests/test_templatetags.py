"""Tests for the strava_athlete template tag.

The test settings define no TEMPLATES engine, so the tag's callable is exercised
directly rather than through a rendered template (mirroring test_sport_icons).
"""
import pytest

from strava.models import Athlete
from strava.templatetags.strava_athlete import strava_athlete


@pytest.mark.django_db
class TestStravaAthleteTag:
    def test_returns_none_before_import(self):
        assert strava_athlete() is None

    def test_returns_current_athlete(self):
        athlete = Athlete.store({"id": 42, "firstname": "Ada", "lastname": "Lovelace"})
        assert strava_athlete() == athlete
