from django.contrib import admin
from django.db.models import Count, Sum
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from unfold.contrib.filters.admin import RangeNumericListFilter

from unfold.decorators import action, display

from strava.models import Activity, Gear


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


class DistanceFilter(RangeNumericListFilter):
    parameter_name = "distance"
    title = _("Distance")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    search_fields = ("id", "name", "gear__brand_name", "gear__model_name")
    actions = ["update_from_json", "fetch_from_api", "send_to_api"]
    date_hierarchy = "start_date"
    list_display = ("id", "name", "sport_type", "distance", "gear", "is_synced", "is_gear_synced", "start_date")
    list_select_related = ("gear",)
    list_display_links = ("id", "name")
    list_editable = ("gear",)
    list_filter = (ActivitySyncFilter, DistanceFilter, "gear", "sport_type")
    list_per_page = 300

    @action(description=_("Update from JSON"))
    def update_from_json(self, request, queryset):
        for obj in queryset:
            obj.update_from_json()

    @action(description=_("Fetch from API"))
    def fetch_from_api(self, request, queryset):
        for obj in queryset:
            obj.fetch_from_api()

    @action(description=_("Send to API"))
    def send_to_api(self, request, queryset):
        for obj in queryset:
            obj.send_to_api()

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
    list_display = ("id", "brand_name", "model_name", "description", "show_activity_count", "show_distance", "show_age")
    list_display_links = ("id", "brand_name", "model_name")
    list_filter = ("brand_name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            activity_count=Count("activity"),
            distance_sum=Sum("activity__distance"),
        )

    @action(description=_("Fetch from API"))
    def fetch_from_api(self, request, queryset):
        for obj in queryset:
            obj.fetch_from_api()

    @display(description=_("Total activities"), ordering="activity_count")
    def show_activity_count(self, obj):
        url = reverse_lazy("admin:strava_activity_changelist")
        url += f"?gear__id__exact={obj.id}"
        return mark_safe(f'<a href="{url}" class="text-primary-600">{obj.activity_count}</a>')

    @display(description=_("Total distance"), ordering="distance")
    def show_distance(self, obj):
        return f'{round(obj.distance_sum/1000, 2)} km'

    @display(description=_("Is old"), ordering="distance")
    def show_age(self, obj):
        # TODO: check gear type (shoes only)
        return obj.distance_sum > 400000
    show_age.boolean = True
