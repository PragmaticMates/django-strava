import json as json_lib
from datetime import datetime, timezone
from unittest.mock import mock_open, patch

import pytest
from django.core.management import call_command

from strava.management.commands.import_strava import Command
from strava.models import Activity, Athlete, Gear


ATHLETE_JSON = {
    "id": 42,
    "firstname": "Ada",
    "lastname": "Lovelace",
    "profile": "https://example.com/avatar.jpg",
    "city": "London",
    "country": "UK",
    "follower_count": 12,
    "friend_count": 7,
}

ACTIVITY_JSON_1 = {
    "id": 100,
    "name": "Morning Run",
    "gear_id": None,
    "sport_type": "Run",
    "distance": 5000,
    "start_date": "2024-06-15T07:30:00+00:00",
}

ACTIVITY_JSON_2 = {
    "id": 200,
    "name": "Evening Ride",
    "gear_id": None,
    "sport_type": "Ride",
    "distance": 20000,
    "start_date": "2024-06-16T18:00:00+00:00",
}


@pytest.mark.django_db
class TestImportStrava:
    @patch("strava.services.sync.gear_ensure", return_value=None)
    @patch("strava.management.commands.import_strava.StravaApi")
    def test_creates_activities(self, mock_api_cls, mock_gear):
        mock_api_cls.return_value.get_athlete.return_value = ATHLETE_JSON
        mock_api_cls.return_value.get_activities.return_value = [
            ACTIVITY_JSON_1,
            ACTIVITY_JSON_2,
        ]
        # The command fetches the detailed activity per summary id.
        details = {100: ACTIVITY_JSON_1, 200: ACTIVITY_JSON_2}
        mock_api_cls.return_value.get_activity.side_effect = lambda activity_id: details[activity_id]

        call_command("import_strava")

        assert Activity.objects.count() == 2
        a1 = Activity.objects.get(id=100)
        assert a1.name == "Morning Run"
        assert a1.sport_type == "Run"

        a2 = Activity.objects.get(id=200)
        assert a2.name == "Evening Ride"
        assert a2.sport_type == "Ride"

        # Imported activities are linked to the synced athlete.
        assert a1.athlete_id == 42
        assert a2.athlete_id == 42

    @patch("strava.services.sync.gear_ensure", return_value=None)
    @patch("strava.management.commands.import_strava.StravaApi")
    def test_imports_athlete(self, mock_api_cls, mock_gear):
        mock_api_cls.return_value.get_athlete.return_value = ATHLETE_JSON
        mock_api_cls.return_value.get_activities.return_value = []

        call_command("import_strava")

        athlete = Athlete.objects.get(id=42)
        assert athlete.full_name == "Ada Lovelace"
        assert athlete.follower_count == 12
        assert Athlete.current() == athlete

    @patch("strava.services.sync.gear_ensure", return_value=None)
    @patch("strava.management.commands.import_strava.StravaApi")
    def test_backfills_legacy_unowned_rows(self, mock_api_cls, mock_gear):
        # Rows imported before athlete linking existed carry no athlete...
        legacy_activity = Activity.objects.create(
            id=100,
            name="Morning Run",
            start_date=datetime(2024, 6, 15, 7, 30, tzinfo=timezone.utc),
            sport_type="Run",
            distance=5000,
            json=ACTIVITY_JSON_1,
        )
        legacy_gear = Gear.objects.create(
            id="g1", primary=False, brand_name="Nike", model_name="Pegasus",
            description="", json={},
        )
        assert legacy_activity.athlete_id is None
        assert legacy_gear.athlete_id is None

        mock_api_cls.return_value.get_athlete.return_value = ATHLETE_JSON
        mock_api_cls.return_value.get_activities.return_value = []

        call_command("import_strava")

        # ...and are backfilled to the synced athlete on the next import.
        legacy_activity.refresh_from_db()
        legacy_gear.refresh_from_db()
        assert legacy_activity.athlete_id == 42
        assert legacy_gear.athlete_id == 42

    @patch("strava.services.sync.gear_ensure", return_value=None)
    @patch("strava.management.commands.import_strava.StravaApi")
    def test_incremental_passes_after(self, mock_api_cls, mock_gear):
        # Create an existing activity so .exists() is True
        Activity.objects.create(
            id=100,
            name="Morning Run",
            start_date=datetime(2024, 6, 15, 7, 30, tzinfo=timezone.utc),
            sport_type="Run",
            distance=5000,
            json=ACTIVITY_JSON_1,
        )

        mock_api_cls.return_value.get_athlete.return_value = ATHLETE_JSON
        mock_api_cls.return_value.get_activities.return_value = []

        call_command("import_strava")

        mock_api_cls.return_value.get_activities.assert_called_once_with(
            after=datetime(2024, 6, 15, 7, 30, tzinfo=timezone.utc)
        )

    @patch("strava.services.sync.gear_ensure", return_value=None)
    @patch("strava.management.commands.import_strava.StravaApi")
    def test_updates_existing_activity(self, mock_api_cls, mock_gear):
        Activity.objects.create(
            id=100,
            name="Old Name",
            start_date=datetime(2024, 6, 15, 7, 30, tzinfo=timezone.utc),
            sport_type="Run",
            distance=5000,
            json=ACTIVITY_JSON_1,
        )

        mock_api_cls.return_value.get_athlete.return_value = ATHLETE_JSON
        updated_json = {**ACTIVITY_JSON_1, "name": "Renamed Run"}
        mock_api_cls.return_value.get_activities.return_value = [updated_json]
        mock_api_cls.return_value.get_activity.side_effect = lambda activity_id: updated_json

        call_command("import_strava")

        assert Activity.objects.count() == 1
        assert Activity.objects.get(id=100).name == "Renamed Run"


@pytest.mark.django_db
class TestImportFromFile:
    @patch("strava.services.sync.gear_ensure", return_value=None)
    def test_creates_activities_from_file(self, mock_gear):
        payload = json_lib.dumps([ACTIVITY_JSON_1, ACTIVITY_JSON_2])
        with patch("strava.management.commands.import_strava.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=payload)):
            Command().import_activities_from_file()

        assert Activity.objects.count() == 2
        assert Activity.objects.get(id=100).name == "Morning Run"

    def test_missing_file_creates_nothing(self):
        with patch("strava.management.commands.import_strava.os.path.exists", return_value=False):
            Command().import_activities_from_file()
        assert Activity.objects.count() == 0
