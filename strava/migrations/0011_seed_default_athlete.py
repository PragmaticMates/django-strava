from datetime import datetime, timezone

from django.conf import settings
from django.db import migrations

# A fixed past instant. Seeded onto the athlete's token_expires_at so the very first API
# call treats the (likely already-expired) legacy access token as stale and refreshes it
# via the refresh token — stravalib then hands the fresh tokens to StravaApi to persist.
_EXPIRED = datetime(2000, 1, 1, tzinfo=timezone.utc)


def seed_default_athlete(apps, schema_editor):
    """Mark the pre-existing single athlete as default and seed their OAuth tokens from the
    legacy settings, so the site keeps importing after deploy without waiting to re-run the
    OAuth connect flow. All settings reads are guarded so this is safe once they're removed."""
    Athlete = apps.get_model('strava', 'Athlete')
    athlete = Athlete.objects.first()
    if athlete is None:
        return

    if not Athlete.objects.filter(is_default=True).exists():
        athlete.is_default = True

    access = getattr(settings, 'STRAVA_ACCESS_TOKEN', None)
    refresh = getattr(settings, 'STRAVA_REFRESH_TOKEN', None)
    if access and not athlete.access_token:
        athlete.access_token = access
    if refresh and not athlete.refresh_token:
        athlete.refresh_token = refresh
        if athlete.token_expires_at is None:
            athlete.token_expires_at = _EXPIRED

    athlete.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('strava', '0010_athlete_tokens'),
    ]

    operations = [
        migrations.RunPython(seed_default_athlete, noop),
    ]
