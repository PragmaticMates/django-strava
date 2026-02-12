# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

django-strava is a reusable Django app (`strava`) that integrates with the Strava API. It provides models for Activities and Gear, a management command for importing data, and a rich admin interface powered by django-unfold.

## Dependencies

- **Django** (5.1+) with PostgreSQL (uses `jsonb_extract_path_text`, `unaccent`)
- **stravalib** - Strava API client
- **django-environ** - environment variable management
- **django-unfold** - admin UI framework (provides `@action`, `@display` decorators, `RangeNumericListFilter`)

## Architecture

- **models.py** - `Activity` and `Gear` models. Both store raw API JSON in a `JSONField` alongside extracted fields. Sync status is tracked by comparing model fields against stored JSON.
- **api.py** - `StravaApi` wrapper around `stravalib.Client`. Auth credentials come from env vars: `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_ACCESS_TOKEN`, `STRAVA_REFRESH_TOKEN`, `STRAVA_TOKEN_EXPIRES`.
- **querysets.py** - `ActivityQuerySet` with PostgreSQL-specific JSON queries (e.g., `gear_unsynced()` uses `jsonb_extract_path_text`).
- **admin.py** - Uses django-unfold decorators exclusively (not standard Django admin decorators). Rich display methods for pace, speed, heartrate, elevation, etc.
- **choices.py** - `SportType` as `models.TextChoices` with 56 sport types.
- **management/commands/import_strava.py** - `import_strava` command that fetches activities from API or file and creates/updates records.

## Key Patterns

- Raw Strava API responses are stored in `json` JSONField; relevant fields are extracted into model fields via `read_json()` / `update_from_json()`
- Gear is lazily fetched from Strava API when first encountered via a foreign key
- Admin uses `list_select_related` and queryset annotations (`Count`, `Sum`) for performance
- All user-facing strings use `gettext_lazy` for i18n
- Search uses PostgreSQL `unaccent` extension

## License

GNU General Public License v3
