from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from django.core.management import call_command

from strava.models import Activity, Gear


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
    @patch("strava.models.Gear.get_or_create", return_value=None)
    @patch("strava.management.commands.import_strava.StravaApi")
    def test_creates_activities(self, mock_api_cls, mock_gear):
        mock_api_cls.return_value.get_activities.return_value = [
            ACTIVITY_JSON_1,
            ACTIVITY_JSON_2,
        ]

        call_command("import_strava")

        assert Activity.objects.count() == 2
        a1 = Activity.objects.get(id=100)
        assert a1.name == "Morning Run"
        assert a1.sport_type == "Run"

        a2 = Activity.objects.get(id=200)
        assert a2.name == "Evening Ride"
        assert a2.sport_type == "Ride"

    @patch("strava.models.Gear.get_or_create", return_value=None)
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

        mock_api_cls.return_value.get_activities.return_value = []

        call_command("import_strava")

        mock_api_cls.return_value.get_activities.assert_called_once_with(
            after=datetime(2024, 6, 15, 7, 30, tzinfo=timezone.utc)
        )

    @patch("strava.models.Gear.get_or_create", return_value=None)
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

        updated_json = {**ACTIVITY_JSON_1, "name": "Renamed Run"}
        mock_api_cls.return_value.get_activities.return_value = [updated_json]

        call_command("import_strava")

        assert Activity.objects.count() == 1
        assert Activity.objects.get(id=100).name == "Renamed Run"
