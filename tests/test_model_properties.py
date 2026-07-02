"""Tests for Activity / Gear display properties and API-backed helpers."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from django.utils import timezone as dj_timezone

from strava.models import Activity, Gear


def activity(**overrides):
    defaults = dict(
        name="Act",
        start_date=datetime(2025, 6, 15, tzinfo=timezone.utc),
        sport_type="Run",
        distance=10000,
        moving_time=3000,
        json={},
    )
    defaults.update(overrides)
    return Activity(**defaults)


# --------------------------------------------------------------------------- #
# Activity.type bucketing
# --------------------------------------------------------------------------- #
class TestActivityType:
    @pytest.mark.parametrize("sport_type,expected", [
        ("TrailRun", "trail"),
        ("Hike", "hike"),
        ("Snowshoe", "hike"),
        ("Walk", "walk"),
        ("Ride", "ride"),
        ("GravelRide", "ride"),
        ("Swim", "swim"),
        ("Run", "run"),
        ("Workout", "run"),   # unlisted sports fall through to "run"
    ])
    def test_type(self, sport_type, expected):
        assert activity(sport_type=sport_type).type == expected


# --------------------------------------------------------------------------- #
# Distance / duration / elevation
# --------------------------------------------------------------------------- #
class TestScalars:
    def test_dist_km_rounded(self):
        # 10240 m → 10.24 km → 10.2 km (1 decimal)
        assert activity(distance=10240).dist == 10.2

    def test_dur_with_hours(self):
        assert activity(moving_time=3725).dur == "1h 02m"

    def test_dur_under_hour(self):
        assert activity(moving_time=125).dur == "2m 05s"

    def test_dur_zero_when_missing(self):
        assert activity(moving_time=None).dur == "0m 00s"

    def test_elev_rounds(self):
        assert activity(total_elevation_gain=123.6).elev == 124

    def test_elev_zero_when_missing(self):
        assert activity(total_elevation_gain=None).elev == 0


# --------------------------------------------------------------------------- #
# Pace
# --------------------------------------------------------------------------- #
class TestPace:
    def test_run_pace_per_km(self):
        # 10 km in 3000 s = 300 s/km = 5:00 /km
        val, unit = activity(sport_type="Run", distance=10000, moving_time=3000).pace_parts
        assert (val, unit) == ("5:00", "/km")

    def test_ride_pace_kmh(self):
        # 30 km in 3600 s = 30 km/h
        val, unit = activity(sport_type="Ride", distance=30000, moving_time=3600).pace_parts
        assert unit == "km/h"
        assert val == "30.0"

    def test_swim_pace_per_100m(self):
        # 2000 m in 3000 s = 150 s / 100 m = 2:30 /100m
        val, unit = activity(sport_type="Swim", distance=2000, moving_time=3000).pace_parts
        assert (val, unit) == ("2:30", "/100m")

    def test_no_data_returns_dash(self):
        assert activity(moving_time=0).pace_parts == ("-", "")

    def test_pace_string_joins_unit(self):
        assert activity(sport_type="Run", distance=10000, moving_time=3000).pace == "5:00 /km"

    def test_pace_string_no_unit(self):
        assert activity(moving_time=0).pace == "-"


# --------------------------------------------------------------------------- #
# Passthrough / flag properties
# --------------------------------------------------------------------------- #
class TestFlags:
    def test_count_aliases(self):
        a = activity(kudos_count=7, comment_count=3, total_photo_count=2)
        assert (a.kudos, a.comments, a.photo_count) == (7, 3, 2)

    def test_pb_true_false(self):
        assert activity(pr_count=1).pb is True
        assert activity(pr_count=0).pb is False

    def test_photo_none_when_blank(self):
        assert activity(photo_url="").photo is None
        assert activity(photo_url="http://x/p.jpg").photo == "http://x/p.jpg"

    def test_has_gps(self):
        assert activity(start_lat=48.7).has_gps is True
        assert activity(start_lat=None).has_gps is False

    def test_has_heartrate(self):
        assert activity(average_heartrate=140.0, max_heartrate=180.0).has_heartrate is True
        assert activity(average_heartrate=None, max_heartrate=180.0).has_heartrate is False

    def test_polyline_prefers_full_over_summary(self):
        a = activity(json={"map": {"polyline": "FULL", "summary_polyline": "SUM"}})
        assert a.polyline == "FULL"

    def test_polyline_falls_back_to_summary(self):
        a = activity(json={"map": {"summary_polyline": "SUM"}})
        assert a.polyline == "SUM"

    def test_polyline_empty_without_map(self):
        assert activity(json={}).polyline == ""

    def test_get_absolute_url(self):
        a = activity()
        a.id = 987
        assert a.get_absolute_url() == "https://strava.com/activities/987"


# --------------------------------------------------------------------------- #
# Activity API-backed helpers
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
class TestActivityApiHelpers:
    ACT_JSON = {
        "id": 5, "name": "Fetched", "gear_id": None, "sport_type": "Run",
        "distance": 8000, "start_date": "2025-06-15T07:00:00+00:00",
    }

    @patch("strava.models.StravaApi")
    def test_fetch_from_api_stores_and_updates(self, mock_api_cls):
        mock_api_cls.return_value.get_activity.return_value = self.ACT_JSON
        a = Activity.objects.create(
            id=5, name="Old", start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
            sport_type="Walk", distance=0, json={},
        )
        a.fetch_from_api()
        a.refresh_from_db()
        mock_api_cls.return_value.get_activity.assert_called_once_with(5)
        assert a.name == "Fetched"
        assert a.sport_type == "Run"
        assert a.json == self.ACT_JSON

    @patch("strava.models.StravaApi")
    def test_send_to_api_pushes_then_refetches(self, mock_api_cls):
        mock_api_cls.return_value.get_activity.return_value = self.ACT_JSON
        a = Activity.objects.create(
            id=5, name="Renamed", start_date=datetime(2025, 6, 15, tzinfo=timezone.utc),
            sport_type="Run", distance=8000, gear_id=None, json=self.ACT_JSON,
        )
        a.send_to_api()
        mock_api_cls.return_value.update_activity.assert_called_once_with(
            id=5, name="Renamed", sport_type="Run", gear_id=None,
        )
        # send_to_api ends by re-fetching the detailed payload.
        mock_api_cls.return_value.get_activity.assert_called_once_with(5)


# --------------------------------------------------------------------------- #
# Gear
# --------------------------------------------------------------------------- #
GEAR_JSON = {
    "id": "g1", "primary": True, "brand_name": "Nike",
    "model_name": "Peg", "description": "trainer",
}


@pytest.mark.django_db
class TestGear:
    def _gear(self, **overrides):
        defaults = dict(id="g1", primary=False, brand_name="Nike", model_name="Peg",
                        description="", gear_type="shoe", json=GEAR_JSON)
        defaults.update(overrides)
        return Gear.objects.create(**defaults)

    def _activity(self, id, gear, distance=5000, start_date=None):
        return Activity.objects.create(
            id=id, name=f"A{id}",
            start_date=start_date or datetime(2025, 6, 15, tzinfo=timezone.utc),
            sport_type="Run", distance=distance, gear=gear, json={},
        )

    def test_distance_sums_activities(self):
        g = self._gear()
        self._activity(1, g, distance=5000)
        self._activity(2, g, distance=3000)
        assert g.distance == 8000

    def test_lifespan_km_by_type(self):
        assert self._gear(id="s", gear_type="shoe").lifespan_km == Gear.SHOE_LIFESPAN_KM
        assert self._gear(id="b", gear_type="bike").lifespan_km == Gear.BIKE_LIFESPAN_KM

    def test_is_old_without_activities(self):
        # Never used → treated as old.
        assert self._gear().is_old is True

    def test_is_old_recent_activity(self):
        g = self._gear()
        self._activity(1, g, start_date=dj_timezone.now() - timedelta(days=10))
        assert g.is_old is False

    def test_is_old_stale_activity(self):
        g = self._gear()
        self._activity(1, g, start_date=dj_timezone.now() - timedelta(days=400))
        assert g.is_old is True

    def test_get_or_create_returns_none_for_falsy_id(self):
        assert Gear.get_or_create(None) is None
        assert Gear.get_or_create("") is None

    def test_get_or_create_returns_existing(self):
        g = self._gear()
        with patch("strava.models.StravaApi") as mock_api:
            assert Gear.get_or_create("g1").pk == g.pk
            mock_api.assert_not_called()   # no API hit when already present

    @patch("strava.models.StravaApi")
    def test_get_or_create_fetches_when_missing(self, mock_api_cls):
        mock_api_cls.return_value.get_gear.return_value = {**GEAR_JSON, "id": "g2"}
        gear = Gear.get_or_create("g2")
        mock_api_cls.return_value.get_gear.assert_called_once_with("g2")
        assert gear.pk == "g2"
        assert gear.brand_name == "Nike"

    @patch("strava.models.StravaApi")
    def test_fetch_from_api_updates_fields(self, mock_api_cls):
        g = self._gear(brand_name="Old")
        mock_api_cls.return_value.get_gear.return_value = {**GEAR_JSON, "brand_name": "New"}
        g.fetch_from_api()
        g.refresh_from_db()
        assert g.brand_name == "New"

    def test_read_json_bike_detection(self):
        # A frame_type present → bike; absent → shoe.
        assert Gear.read_json({**GEAR_JSON, "frame_type": 3})["gear_type"] == "bike"
        assert Gear.read_json(GEAR_JSON)["gear_type"] == "shoe"
