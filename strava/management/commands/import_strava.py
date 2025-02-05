import logging

import os
import json
from django.core.management.base import BaseCommand

from strava.models import Activity

logger = logging.getLogger("file")


class Command(BaseCommand):
    help = "Reads athlete data from Strava"

    def handle(self, *args, **options):
        self.import_activities()

    def import_activities(self):
        file_path = "/data/strava/activities.json"

        # Check if the file exists
        if not os.path.exists(file_path):
            logger.error(self.style.ERROR(f"File not found: {file_path}"))
            return

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            for item in data:
                data = Activity.read_json(item)
                data['json'] = item

                # logger.info(data)
                obj, created = Activity.objects.get_or_create(
                    id=item["id"],
                    defaults=data,
                )
                if created:
                    logger.info(f"Added: {obj}")
                else:
                    logger.info(f"Skipped (exists): {obj}")

            logger.info("JSON file processed successfully")

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
