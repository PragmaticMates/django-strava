import logging

import os
import json
from django.core.management.base import BaseCommand

from strava.api import StravaApi
from strava.models import Activity, Athlete, Gear
from strava.services import sync

logger = logging.getLogger("file")


class Command(BaseCommand):
    help = "Reads athlete data from Strava"

    def handle(self, *args, **options):
        # self.import_activities_from_file()
        self.import_activities_from_api()

    def import_activities_from_file(self):
        file_path = "/data/strava/activities.json"

        # Check if the file exists
        if not os.path.exists(file_path):
            logger.error(self.style.ERROR(f"File not found: {file_path}"))
            return

        with open(file_path, "r", encoding="utf-8") as file:
            activities = json.load(file)

        self.create_activities(activities)

    def import_activities_from_api(self):
        api = StravaApi()
        # Refresh the athlete profile (nav name/avatar/counts) on every import.
        athlete = Athlete.store(api.get_athlete())
        after = Activity.objects.latest().start_date if Activity.objects.exists() else None
        for summary in api.get_activities(after=after):
            self.create_activity_from_json(api.get_activity(summary['id']), athlete)
        # Backfill rows imported before athlete linking existed. Safe because the app is
        # single-athlete: every unowned activity/gear belongs to the one athlete.
        Activity.objects.filter(athlete__isnull=True).update(athlete=athlete)
        Gear.objects.filter(athlete__isnull=True).update(athlete=athlete)

    def create_activities(self, activities, athlete=None):
        for activity in activities:
            self.create_activity_from_json(activity, athlete)

    def create_activity_from_json(self, json_data, athlete=None):
        data = Activity.read_json(json_data)
        data['json'] = json_data
        data['athlete'] = athlete

        sync.gear_ensure(gear_id=data.get('gear_id'), athlete=athlete)
        activity, created = Activity.objects.update_or_create(
            id=json_data["id"],
            defaults=data,
        )

        if created:
            logger.info(f"Added: {activity}")
        else:
            logger.info(f"Skipped (exists): {activity}")
