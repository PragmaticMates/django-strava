import logging

from django.core.management.base import BaseCommand

from strava.api import StravaApi

logger = logging.getLogger("file")


class Command(BaseCommand):
    help = "Reads athlete data from Strava"

    def handle(self, *args, **options):
        api = StravaApi()
        logger.info(api.read_athlete())
        # logger.info(api.read_activity(13502141803))
        # logger.info(api.read_activities())
