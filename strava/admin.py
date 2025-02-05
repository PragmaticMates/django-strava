from django.contrib import admin
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

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


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    search_fields = ("id", "name")
    actions = ["update_from_json", "fetch_from_api"]
    date_hierarchy = "start_date"
    list_display = ("id", "name", "sport_type", "gear", "is_synced", "is_gear_synced", "start_date")
    list_select_related = ("gear",)
    list_display_links = ("id", "name")
    list_editable = ("gear",)
    list_filter = (ActivitySyncFilter, "gear", "sport_type")
    list_per_page = 300

    @action(description=_("Update from JSON"))
    def update_from_json(self, request, queryset):
        for obj in queryset:
            obj.update_from_json()

    @action(description=_("Fetch from API"))
    def fetch_from_api(self, request, queryset):
        for obj in queryset:
            obj.fetch_from_api()

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
    list_display = ("id", "brand_name", "model_name", "description", "show_activity_count")
    list_display_links = ("id", "brand_name", "model_name")
    list_filter = ("brand_name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(activity_count=Count("activity"))

    @action(description=_("Fetch from API"))
    def fetch_from_api(self, request, queryset):
        for obj in queryset:
            obj.fetch_from_api()

    @display(description=_("Total activities"))
    def show_activity_count(self, obj):
        return obj.activity_count
