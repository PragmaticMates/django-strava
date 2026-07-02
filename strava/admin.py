import datetime
import logging

from django.contrib import admin, messages
from django.core.management import call_command
from django.db.models import Count, Sum
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from unfold.contrib.filters.admin import RangeNumericListFilter, RelatedDropdownFilter
from unfold.decorators import action, display

from strava.api import format_strava_error
from strava.choices import SportType
from strava.models import Activity, Athlete, Gear
from strava.services import sync


logger = logging.getLogger('strava')


class ActivitySyncFilter(admin.SimpleListFilter):
    title = _("Synchronisation status")
    parameter_name = "sync"

    def lookups(self, request, model_admin):
        return [
            ("gear_unsynced", _("Gear not synced")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "gear_unsynced":
            return queryset.gear_unsynced()


class ActivityDetailFilter(admin.SimpleListFilter):
    title = _("Detail status")
    parameter_name = "detail"

    def lookups(self, request, model_admin):
        return [
            ("summary", _("Summary only (needs fetch)")),
            ("detailed", _("Detailed")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "summary":
            return queryset.summary_only()
        if self.value() == "detailed":
            return queryset.detailed()


class DistanceFilter(RangeNumericListFilter):
    parameter_name = "distance"
    title = _("Distance")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    search_fields = ("id", "name__unaccent")
    actions = ["update_from_json", "fetch_from_api", "send_to_api"]
    actions_list = ["import_strava", "open_strava_activities"]
    date_hierarchy = "start_date"
    list_display = ("show_start_date", "name_and_id", "show_sport_type", "show_distance", "show_elevation", "show_time",
                    "show_speed", "show_heartrate", "show_calories", "gear")
    list_select_related = ("gear",)
    list_display_links = ("name_and_id",)
    list_editable = ("gear",)
    list_filter = (ActivitySyncFilter, ActivityDetailFilter, DistanceFilter,
                   ("athlete", RelatedDropdownFilter), ("gear", RelatedDropdownFilter), "sport_type")
    list_per_page = 100
    readonly_fields = ('distance', 'json', 'start_date', 'athlete')
    # autocomplete_fields = ("gear",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "gear":
            formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
            formfield.empty_label = ""
            if not hasattr(request, "_gear_choices"):
                request._gear_choices = list(formfield.choices)
            formfield.choices = request._gear_choices
            return formfield
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @action(description=_("Import from Strava"), url_path="import-strava")
    def import_strava(self, request, *args):
        try:
            call_command('import_strava')
        except Exception as error:
            # The Strava API can reject the import (inactive app, expired token, rate
            # limit, outage). Show the reason as an admin message instead of a 500.
            logger.exception('Strava import from the admin action failed')
            self.message_user(
                request,
                _("Import from Strava failed — %(error)s") % {"error": format_strava_error(error)},
                level=messages.ERROR,
            )
        else:
            self.message_user(request, _("Import from Strava completed."), level=messages.SUCCESS)
        return redirect(request.META.get("HTTP_REFERER", reverse_lazy("admin:strava_activity_changelist")))

    @action(description=_("Show activities on Strava"), url_path="open-strava-activities")
    def open_strava_activities(self, request, *args):
        return redirect('https://www.strava.com/athlete/training')

    @action(description=_("Update from JSON"))
    def update_from_json(self, request, queryset):
        for obj in queryset:
            sync.activity_apply_json(obj)

    @action(description=_("Fetch from API"))
    def fetch_from_api(self, request, queryset):
        for obj in queryset:
            sync.activity_fetch(obj)

    @action(description=_("Send to API"))
    def send_to_api(self, request, queryset):
        for obj in queryset:
            sync.activity_push(obj)

    @display(description=_("Name"), header=True, ordering="name")
    def name_and_id(self, obj):
        # Activity names are athlete-supplied free text, so escape them (format_html)
        # rather than mark_safe'ing raw HTML — otherwise a crafted name is stored XSS.
        return [
            format_html('<span class="text-primary-600">{}</span>', obj.name),
            obj.id
        ]

    @display(description=_("Sport"), ordering="sport_type", label={
        SportType.RUN: "success",  # green
        SportType.TRAIL_RUN: "warning",  # blue
        SportType.RIDE: "danger",  # orange
        SportType.SWIM: "info",  # red
    })
    def show_sport_type(self, obj):
        return obj.get_sport_type_display()

    @display(description=_("Distance"), ordering="distance")
    def show_distance(self, obj):
        return f'{round(obj.distance / 1000, 2)} km'

    @display(description=_("Elevation"), ordering="total_elevation_gain")
    def show_elevation(self, obj):
        return f'{round(obj.total_elevation_gain or 0)} m'

    @display(description=_("Time"), header=True, ordering="elapsed_time", )
    def show_time(self, obj):
        return [
            f'Elapsed: {datetime.timedelta(seconds=obj.elapsed_time or 0)}',
            f'Moving: {datetime.timedelta(seconds=obj.moving_time or 0)}',
        ]

    @display(description=_("Pace / speed"), header=True, ordering="average_speed")
    def show_speed(self, obj):
        if obj.distance == 0 or not obj.elapsed_time:
            return ['-', '']

        distance_km = obj.distance / 1000
        pace = f'{round((obj.elapsed_time / 60) / distance_km, 2)} min / km'
        speed = f'{round(distance_km / (obj.elapsed_time / 3600), 2)} km / h'

        return [
            pace,
            speed,
        ]

    @display(description=_("Heartrate"), header=True, ordering="average_heartrate",)
    def show_heartrate(self, obj):
        if not obj.has_heartrate:
            return ['-', '']

        return [
            f'Avg: {obj.average_heartrate}',
            f'Max: {obj.max_heartrate}',
            # '♥'
        ]

    @display(description=_("Calories"), ordering="calories")
    def show_calories(self, obj):
        if obj.calories is None:
            return '-'
        return f'{obj.calories} kcal'

    @display(description=_("Date"), header=True, ordering="start_date")
    def show_start_date(self, obj):
        start_date = timezone.localtime(obj.start_date)
        return [
            mark_safe(f'<span class="whitespace-nowrap">{start_date.strftime("%Y-%m-%d")}</span>'),
            start_date.strftime("%H:%M"),
        ]

    @display(description=_("Is synced"))
    def is_synced(self, obj):
        return obj.is_synced()
    is_synced.boolean = True

    @display(description=_("Gear synced"))
    def is_gear_synced(self, obj):
        return obj.is_gear_synced()
    is_gear_synced.boolean = True


@admin.register(Gear)
class GearAdmin(admin.ModelAdmin):
    search_fields = ("id", "brand_name", "model_name", "description")
    actions = ["fetch_from_api"]
    actions_list = ["open_strava_gear"]
    list_display = ("id", "brand_and_model", "show_gear_type", "description",
                    "show_activity_count", "show_distance", "show_age", "primary")
    list_display_links = ("id", "brand_and_model")
    list_filter = (("athlete", RelatedDropdownFilter), "gear_type", "brand_name")
    readonly_fields = ("primary", "brand_name", "model_name", "description", "json", "athlete")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            activity_count=Count("activity"),
            distance_sum=Sum("activity__distance"),
            distance_avg=Sum("activity__distance")/Count("activity"),
        )

    @action(description=_("Show gear on Strava"), url_path="open-strava-gear")
    def open_strava_gear(self, request, *args):
        return redirect('https://www.strava.com/settings/gear')

    @action(description=_("Fetch from API"))
    def fetch_from_api(self, request, queryset):
        for obj in queryset:
            sync.gear_fetch(obj)

    @display(description=_("Brand and model"), ordering="brand_name", header=True)
    def brand_and_model(self, obj):
        return [
            obj.brand_name,
            obj.model_name
        ]

    @display(description=_("Type"), ordering="gear_type", label={
        "bike": "info",
        "shoe": "success",
    })
    def show_gear_type(self, obj):
        return obj.get_gear_type_display()

    @display(description=_("Total activities"), ordering="activity_count")
    def show_activity_count(self, obj):
        url = reverse_lazy("admin:strava_activity_changelist")
        url += f"?gear__id__exact={obj.id}"
        return mark_safe(f'<a href="{url}" class="text-primary-600">{obj.activity_count}</a>')

    @display(description=_("Distance"), ordering="distance_sum", header=True)
    def show_distance(self, obj):
        return [
            f'{round(obj.distance_sum / 1000, 2)} km',
            f'Average: {round(obj.distance_avg / 1000, 2)} km'
        ]

    @display(description=_("Is old"))
    def show_age(self, obj):
        return obj.is_old
    show_age.boolean = True


@admin.register(Athlete)
class AthleteAdmin(admin.ModelAdmin):
    search_fields = ("id", "firstname", "lastname")
    actions_list = ["sync_from_api"]
    actions_row = ["show_activities"]
    actions_detail = ["show_activities"]
    list_display = ("id", "full_name", "location", "follower_count", "friend_count")
    readonly_fields = ("id", "firstname", "lastname", "profile", "city", "country",
                       "follower_count", "friend_count", "json")

    @action(description=_("Show activities"), url_path="show-activities")
    def show_activities(self, request, object_id):
        url = reverse_lazy("admin:strava_activity_changelist")
        return redirect(f"{url}?athlete__id__exact={object_id}")

    @action(description=_("Sync athlete from Strava"), url_path="sync-strava-athlete")
    def sync_from_api(self, request, *args):
        try:
            sync.athlete_sync()
        except Exception as error:
            logger.exception("Strava athlete sync from the admin action failed")
            self.message_user(
                request,
                _("Athlete sync from Strava failed — %(error)s") % {"error": format_strava_error(error)},
                level=messages.ERROR,
            )
        else:
            self.message_user(request, _("Athlete synced from Strava."), level=messages.SUCCESS)
        return redirect(request.META.get("HTTP_REFERER", reverse_lazy("admin:strava_athlete_changelist")))

    @display(description=_("Name"), ordering="firstname")
    def full_name(self, obj):
        return obj.full_name

    @display(description=_("Location"))
    def location(self, obj):
        return obj.location
