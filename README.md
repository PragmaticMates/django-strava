# django-strava

Reusable Django app for Strava API integration. Provides models for Activities and Gear, a management command for importing data, and a rich admin interface powered by [django-unfold](https://github.com/unfoldadmin/django-unfold).

## Requirements

- Python 3.10+
- Django 5.1+
- PostgreSQL (uses `jsonb_extract_path_text`, `unaccent`)

## Installation

```bash
pip install django-strava
```

Add `strava` to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "unfold",
    "strava",
]
```

Run migrations:

```bash
python manage.py migrate
```

## Configuration

Set the following environment variables with your Strava API credentials:

```
STRAVA_CLIENT_ID=...
STRAVA_CLIENT_SECRET=...
STRAVA_ACCESS_TOKEN=...
STRAVA_REFRESH_TOKEN=...
STRAVA_TOKEN_EXPIRES=...  # optional, format: 2024-01-01T00:00:00Z
```

## Usage

### Import activities

Import activities from the Strava API:

```bash
python manage.py import_strava
```

The command fetches all activities newer than the latest one in the database. On first run, it imports all available activities.

### Admin interface

The app registers `Activity` and `Gear` models in the Django admin with:

- Filtering by sport type, gear, distance range, and sync status
- Display of pace, speed, heartrate, elevation, and time
- Actions to import, fetch, and sync activities with the Strava API
- Full-text search with PostgreSQL `unaccent` support

### Models

**Activity** - Stores Strava activities with extracted fields (name, sport type, distance, start date, gear) and the raw API JSON response.

**Gear** - Stores gear details (brand, model, description). Automatically fetched from the API when first referenced by an activity.

## License

[GNU General Public License v3](LICENSE)
