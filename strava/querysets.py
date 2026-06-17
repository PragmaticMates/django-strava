from django.db import models
from django.db.models import F, Value, Q, CharField, FloatField, Func, ExpressionWrapper


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
            qs = qs.filter(
                Q(name__unaccent__icontains=token)
                | Q(sport_type__unaccent__icontains=token)
            )
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

    def for_year(self, year):
        if not year or year == 'all':
            return self
        try:
            return self.filter(start_date__year=int(year))
        except (ValueError, TypeError):
            return self

    def for_sport_category(self, sport):
        # Mirrors the Activity.type property, which buckets sport_type into broad categories.
        if not sport or sport == 'all':
            return self
        if sport == 'trail':
            return self.filter(sport_type__contains='Trail')
        if sport == 'hike':
            return self.filter(sport_type__in=['Hike', 'Snowshoe'])
        if sport == 'walk':
            return self.filter(sport_type='Walk')
        if sport == 'ride':
            return self.filter(sport_type__contains='Ride')
        if sport == 'swim':
            return self.filter(sport_type__contains='Swim')
        if sport == 'run':
            return (self.exclude(sport_type__contains='Trail')
                        .exclude(sport_type__contains='Ride')
                        .exclude(sport_type__contains='Swim')
                        .exclude(sport_type__in=['Hike', 'Snowshoe', 'Walk']))
        return self

    def sorted_by(self, key, direction='desc'):
        fields = {
            'name': F('name'),
            'date': F('start_date'),
            'dist': F('distance'),
            'time': F('moving_time'),
            'elev': F('total_elevation_gain'),
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
