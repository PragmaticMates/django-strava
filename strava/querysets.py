from django.db import models
from django.db.models import F, Value, Q, CharField, FloatField, Func, ExpressionWrapper


class ActivityQuerySet(models.QuerySet):
    def for_athlete(self, athlete):
        # Scope to one athlete's rows. ``None`` (no athlete selected/connected yet) is a
        # no-op so callers can pass the resolved athlete unconditionally.
        if athlete is None:
            return self
        return self.filter(athlete=athlete)

    def gear_unsynced(self):
        # Compare the athlete-editable `gear_id` column against the gear_id in the stored
        # (immutable) Strava payload — a mismatch means an admin edit hasn't been pushed
        # back to Strava. This is a genuine diff against the JSON archive, so it reads
        # `json` directly via jsonb_extract_path_text rather than a promoted column.
        return self.annotate(
            casted_json_gear_id=Func(
                F("json"),
                Value("gear_id"),
                function="jsonb_extract_path_text",
                output_field=CharField()
            ),
        ).exclude(Q(gear_id=F('casted_json_gear_id')) | Q(gear_id=None, json__gear_id=None))

    def summary_only(self):
        # Activities stored with SummaryActivity data only; they still need the
        # DetailedActivity payload (best efforts, splits, laps, ...) fetched from the API.
        # `is_detailed` is a promoted boolean (see Activity.read_json), so this is a plain
        # column filter — no more jsonb_extract_path_text.
        return self.filter(is_detailed=False)

    def detailed(self):
        return self.filter(is_detailed=True)

    def search(self, query):
        qs = self
        for token in (query or '').split():
            qs = qs.filter(
                Q(name__unaccent__icontains=token)
                | Q(sport_type__unaccent__icontains=token)
            )
        return qs

    def for_sport(self, sport_type):
        if not sport_type or sport_type == 'all':
            return self
        return self.filter(sport_type=sport_type)

    def for_sport_selection(self, value):
        # Group-aware sport filter shared by the dashboard, activities and gallery.
        # ``value`` is 'all', a group key ('group-run', …) or an exact sport_type.
        from strava.sports import types_for
        if not value or value == 'all':
            return self
        return self.filter(sport_type__in=types_for(value))

    def for_gear(self, gear_id):
        if not gear_id or gear_id == 'all':
            return self
        return self.filter(gear_id=gear_id)

    def for_month(self, year_month):
        if not year_month or year_month == 'all':
            return self
        try:
            year, month = (int(part) for part in year_month.split('-'))
        except (ValueError, TypeError):
            return self
        return self.filter(start_date__year=year, start_date__month=month)

    def for_year(self, year):
        if not year or year == 'all':
            return self
        try:
            return self.filter(start_date__year=int(year))
        except (ValueError, TypeError):
            return self

    def sorted_by(self, key, direction='desc'):
        fields = {
            'name': F('name'),
            'date': F('start_date'),
            'dist': F('distance'),
            'time': F('moving_time'),
            'elev': F('total_elevation_gain'),
            'cal': F('calories'),
            'pace': ExpressionWrapper(
                F('moving_time') / Func(F('distance'), Value(0), function='NULLIF'),
                output_field=FloatField(),
            ),
        }
        if key not in fields:
            return self
        expression = fields[key]
        order = expression.desc(nulls_last=True) if direction == 'desc' else expression.asc(nulls_last=True)
        return self.order_by(order)


class GearQuerySet(models.QuerySet):
    def for_athlete(self, athlete):
        if athlete is None:
            return self
        return self.filter(athlete=athlete)

    def search(self, query):
        qs = self
        for token in (query or '').split():
            qs = qs.filter(
                Q(brand_name__unaccent__icontains=token)
                | Q(model_name__unaccent__icontains=token)
            )
        return qs

    def of_type(self, gear_type):
        if gear_type in ('bike', 'shoe'):
            return self.filter(gear_type=gear_type)
        return self

    def sorted_by(self, key, direction='asc'):
        # Sort fields reference annotations added by the view (see GearView).
        fields = {
            'name': F('brand_name'),
            'distance': F('distance_sum'),
            'rides': F('activity_count'),
            'recent': F('last_activity'),
        }
        if key not in fields:
            return self.order_by('-primary', 'brand_name', 'model_name')
        expression = fields[key]
        order = expression.desc(nulls_last=True) if direction == 'desc' else expression.asc(nulls_last=True)
        return self.order_by(order)
