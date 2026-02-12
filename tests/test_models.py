from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from strava.models import Activity, Gear


ACTIVITY_JSON = {
    "id": 12345,
    "name": "Morning Run",
    "gear_id": "g123",
    "sport_type": "Run",
    "distance": 5000.50,
    "start_date": "2024-06-15T07:30:00+00:00",
}

GEAR_JSON = {
    "id": "g123",
    "primary": True,
    "brand_name": "Nike",
    "model_name": "Pegasus 40",
    "description": "Daily trainer",
}


class TestActivityReadJson:
    def test_parses_json_dict(self):
        result = Activity.read_json(ACTIVITY_JSON)
        assert result["name"] == "Morning Run"
        assert result["gear_id"] == "g123"
        assert result["sport_type"] == "Run"
        assert result["distance"] == 5000.50
        assert result["start_date"] == datetime.fromisoformat("2024-06-15T07:30:00+00:00")

    def test_null_gear_id(self):
        json_data = {**ACTIVITY_JSON, "gear_id": None}
        result = Activity.read_json(json_data)
        assert result["gear_id"] is None


@pytest.mark.django_db
class TestActivityStr:
    def test_returns_name(self):
        activity = Activity.objects.create(
            id=1,
            name="Evening Ride",
            start_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            sport_type="Ride",
            distance=10000,
            json=ACTIVITY_JSON,
        )
        assert str(activity) == "Evening Ride"


@pytest.mark.django_db
class TestActivityIsSynced:
    def test_synced_when_matching(self):
        activity = Activity(
            name="Morning Run",
            start_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            sport_type="Run",
            distance=5000.50,
            gear_id="g123",
            json=ACTIVITY_JSON,
        )
        assert activity.is_synced() is True

    def test_not_synced_when_gear_differs(self):
        activity = Activity(
            name="Morning Run",
            start_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            sport_type="Run",
            distance=5000.50,
            gear_id="g999",
            json=ACTIVITY_JSON,
        )
        assert activity.is_synced() is False

    def test_not_synced_when_sport_type_differs(self):
        activity = Activity(
            name="Morning Run",
            start_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            sport_type="Walk",
            distance=5000.50,
            gear_id="g123",
            json=ACTIVITY_JSON,
        )
        assert activity.is_synced() is False


@pytest.mark.django_db
class TestActivityIsGearSynced:
    def test_synced_when_gear_matches(self):
        activity = Activity(
            name="Morning Run",
            start_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            sport_type="Walk",  # sport differs but gear matches
            distance=5000.50,
            gear_id="g123",
            json=ACTIVITY_JSON,
        )
        assert activity.is_gear_synced() is True

    def test_not_synced_when_gear_differs(self):
        activity = Activity(
            name="Morning Run",
            start_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            sport_type="Run",
            distance=5000.50,
            gear_id="g999",
            json=ACTIVITY_JSON,
        )
        assert activity.is_gear_synced() is False


@pytest.mark.django_db
class TestActivityUpdateFromJson:
    @patch("strava.models.StravaApi")
    def test_updates_fields_from_json(self, mock_api_cls):
        gear = Gear.objects.create(
            id="g123",
            primary=True,
            brand_name="Nike",
            model_name="Pegasus 40",
            description="Daily trainer",
            json=GEAR_JSON,
        )
        activity = Activity.objects.create(
            id=1,
            name="Old Name",
            start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
            sport_type="Walk",
            distance=0,
            json=ACTIVITY_JSON,
        )
        activity.update_from_json()
        activity.refresh_from_db()

        assert activity.name == "Morning Run"
        assert activity.sport_type == "Run"
        assert activity.distance == 5000.50
        assert activity.gear_id == "g123"
        # API should not be called since gear already exists
        mock_api_cls.assert_not_called()

    @patch("strava.models.StravaApi")
    def test_fetches_gear_from_api_when_missing(self, mock_api_cls):
        mock_api_cls.return_value.get_gear.return_value = GEAR_JSON

        activity = Activity.objects.create(
            id=2,
            name="Old Name",
            start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
            sport_type="Walk",
            distance=0,
            json=ACTIVITY_JSON,
        )
        activity.update_from_json()

        mock_api_cls.return_value.get_gear.assert_called_once_with("g123")
        assert Gear.objects.filter(id="g123").exists()


class TestGearReadJson:
    def test_parses_json_dict(self):
        result = Gear.read_json(GEAR_JSON)
        assert result["primary"] is True
        assert result["brand_name"] == "Nike"
        assert result["model_name"] == "Pegasus 40"
        assert result["description"] == "Daily trainer"

    def test_null_description_becomes_empty(self):
        json_data = {**GEAR_JSON, "description": None}
        result = Gear.read_json(json_data)
        assert result["description"] == ""


@pytest.mark.django_db
class TestGearStr:
    def test_returns_brand_model(self):
        gear = Gear.objects.create(
            id="g1",
            primary=False,
            brand_name="Adidas",
            model_name="Ultraboost",
            description="",
            json=GEAR_JSON,
        )
        assert str(gear) == "Adidas Ultraboost"
