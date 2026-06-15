from django.db import models
from django.db.models import F, Value, Q, CharField, FloatField, Func, ExpressionWrapper
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast


class ActivityQuerySet(models.QuerySet):
    def gear_unsynced(self):
        # return self.exclude(json__gear_id=F('gear_id'))  # cast error
        # TODO: refactor
        return self.annotate(
            casted_json_gear_id=Func(
                F("json"),
                Value("gear_id"),
                function="jsonb_extract_path_text",
                output_field=CharField()
            ),
        ).exclude(Q(gear_id=F('casted_json_gear_id')) | Q(gear_id=None, json__gear_id=None))

    def search(self, query):
        qs = self
        for token in (query or '').split():
            qs = qs.filter(name__unaccent__icontains=token)
        return qs

    def for_sport(self, sport_type):
        if not sport_type or sport_type == 'all':
            return self
        return self.filter(sport_type=sport_type)

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

    def sorted_by(self, key, direction='desc'):
        moving_time = Cast(KeyTextTransform('moving_time', 'json'), output_field=FloatField())
        elevation = Cast(KeyTextTransform('total_elevation_gain', 'json'), output_field=FloatField())
        fields = {
            'name': F('name'),
            'date': F('start_date'),
            'dist': F('distance'),
            'time': moving_time,
            'elev': elevation,
            'pace': ExpressionWrapper(
                moving_time / Func(F('distance'), Value(0), function='NULLIF'),
                output_field=FloatField(),
            ),
        }
        if key not in fields:
            return self
        expression = fields[key]
        order = expression.desc(nulls_last=True) if direction == 'desc' else expression.asc(nulls_last=True)
        return self.order_by(order)


class GearQuerySet(models.QuerySet):
    def search(self, query):
        qs = self
        for token in (query or '').split():
            qs = qs.filter(
                Q(brand_name__unaccent__icontains=token)
                | Q(model_name__unaccent__icontains=token)
            )
        return qs

    def of_type(self, gear_type):
        # Per the Strava API, only bikes carry a frame_type (DetailedGear); shoes return
        # frame_type=null. A bike therefore has the key present with a non-null value;
        # everything else (json null or missing key) is a shoe. This matches both a missing
        # key and a present-but-null value without relying on DB-specific null extraction.
        has_frame_type = Q(json__has_key='frame_type') & ~Q(json__frame_type=None)
        if gear_type == 'bike':
            return self.filter(has_frame_type)
        if gear_type == 'shoe':
            return self.exclude(has_frame_type)
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
