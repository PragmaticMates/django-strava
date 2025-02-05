import logging

import os
import json
from django.core.management.base import BaseCommand

from strava.api import StravaApi
from strava.models import Activity

logger = logging.getLogger("file")


class Command(BaseCommand):
    help = "Reads athlete data from Strava"

    def handle(self, *args, **options):
        # self.import_activities_from_file()
        # self.import_activities_from_api()
        pass

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
        activities = api.get_activities()
        self.create_activities(activities)

    def create_activities(self, activities):
        for activity in activities:
            self.create_activity_from_json(activity)

    def create_activity_from_json(self, json_data):
        data = Activity.read_json(json_data)
        data['json'] = json_data

        Activity.objects.filter(id=json_data["id"]).update(json=json_data)

        obj, created = Activity.objects.update_or_create(
            id=json_data["id"],
            defaults=data,
        )

        if created:
            logger.info(f"Added: {obj}")
        else:
            logger.info(f"Skipped (exists): {obj}")
