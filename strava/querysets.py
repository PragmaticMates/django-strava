from django.db import models
from django.db.models import F, Value, Q, CharField, Func


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
