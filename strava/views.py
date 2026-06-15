import datetime

from django.db.models import Count, FloatField, IntegerField, Max, Sum
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import ListView

from strava.models import Activity, Gear


def dashboard(request):
    return render(request, 'pages/dashboard.html', {
        'active_page': 'dashboard',
        'latest_activity': {
            'name': 'Morning run in High Tatras',
            'date': 'Today',
            'time': '7:14 AM',
            'type': 'trail',
            'dist': '12.4',
            'pace': '5:01 /km',
            'dur': '1:02:14',
            'elev': '430',
            'kudos': 14,
            'comments': 3,
            'gear': 'Asics Gel-Kayano 32',
            'pb': True,
        },
    })


class ActivitiesView(ListView):
    model = Activity
    template_name = 'pages/activities.html'
    context_object_name = 'activities'

    def get_template_names(self):
        if getattr(self.request, 'htmx', False):
            return ['pages/_activities_results.html']
        return [self.template_name]

    def get_queryset(self):
        params = self.request.GET
        return (
            Activity.objects.select_related('gear')
            .search(params.get('q'))
            .for_sport(params.get('sport'))
            .for_gear(params.get('gear'))
            .for_month(params.get('month'))
            .sorted_by(params.get('sort'), params.get('dir', 'desc'))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'activities'

        params = self.request.GET
        context['q'] = params.get('q', '')
        context['sport'] = params.get('sport', 'all')
        context['gear'] = params.get('gear', 'all')
        context['month'] = params.get('month', 'all')
        context['sort'] = params.get('sort', '')
        context['dir'] = params.get('dir', 'desc')
        context['view'] = params.get('view', 'grid')

        qs = self.object_list
        agg = qs.aggregate(
            total_distance=Sum('distance'),
            total_elevation=Sum(Cast(KeyTextTransform('total_elevation_gain', 'json'), output_field=FloatField())),
            total_time=Sum(Cast(KeyTextTransform('moving_time', 'json'), output_field=FloatField())),
        )
        today = timezone.now().date()
        week_start = today - datetime.timedelta(days=today.weekday())

        from strava.choices import SportType
        context['sport_type_list'] = [
            (st, SportType(st).label)
            for st in Activity.objects.values_list('sport_type', flat=True).distinct().order_by('sport_type')
        ]
        context['gear_list'] = Gear.objects.filter(activity__isnull=False).distinct().order_by('brand_name', 'model_name')
        context['month_list'] = [
            (d.strftime('%Y-%m'), d.strftime('%b %Y'))
            for d in Activity.objects.dates('start_date', 'month', order='DESC')
        ]
        context['summary'] = {
            'count': qs.count(),
            'distance_km': round((agg['total_distance'] or 0) / 1000),
            'elevation_m': round(agg['total_elevation'] or 0),
            'time_h': round((agg['total_time'] or 0) / 3600),
            'this_week': qs.filter(start_date__date__gte=week_start).count(),
        }
        return context


class GearView(ListView):
    model = Gear
    template_name = 'pages/gear.html'
    context_object_name = 'gear_list'

    def get_template_names(self):
        if getattr(self.request, 'htmx', False):
            return ['pages/_gear_results.html']
        return [self.template_name]

    def get_queryset(self):
        params = self.request.GET
        return (
            Gear.objects.annotate(
                activity_count=Count('activity'),
                distance_sum=Sum('activity__distance'),
                last_activity=Max('activity__start_date'),
            )
            .search(params.get('q'))
            .of_type(params.get('type'))
            .sorted_by(params.get('sort'), params.get('dir', 'asc'))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'gear'

        params = self.request.GET
        context['q'] = params.get('q', '')
        context['type'] = params.get('type', 'all')
        context['sort'] = params.get('sort', '')
        context['dir'] = params.get('dir', 'asc')

        gear_list = list(context['gear_list'])
        for g in gear_list:
            g.distance_km = round((g.distance_sum or 0) / 1000)
            g.wear_pct = min(100, round(g.distance_km / g.lifespan_km * 100)) if g.lifespan_km else 0
            g.wear_class = 'wear-low' if g.wear_pct < 40 else 'wear-mid' if g.wear_pct < 75 else 'wear-high'
            g.is_retired = g.wear_pct >= 100
            if g.is_retired:
                g.badge_class, g.badge_label = 'badge-retired', 'Retired'
            elif g.primary:
                g.badge_class, g.badge_label = 'badge-primary', 'Primary'
            elif g.wear_pct >= 75:
                g.badge_class = 'badge-alert'
                g.badge_label = 'Service due' if g.gear_type == 'bike' else 'Replace soon'
            else:
                g.badge_class = g.badge_label = ''

        bikes = [g for g in gear_list if g.gear_type == 'bike']
        shoes = [g for g in gear_list if g.gear_type == 'shoe']
        context['gear_list'] = gear_list
        context['bikes'] = bikes
        context['shoes'] = shoes
        context['total_items'] = len(gear_list)
        context['summary'] = {
            'bikes': len(bikes),
            'shoes': len(shoes),
            'total_km': sum(g.distance_km for g in gear_list),
            'activities': sum(g.activity_count for g in gear_list),
        }
        return context


class GalleryView(ListView):
    model = Activity
    template_name = 'pages/gallery.html'
    context_object_name = 'photos'

    def get_template_names(self):
        if getattr(self.request, 'htmx', False):
            return ['pages/_gallery_results.html']
        return [self.template_name]

    def get_queryset(self):
        params = self.request.GET
        qs = (
            Activity.objects
            .search(params.get('q'))
            .for_sport_category(params.get('sport'))
            .for_year(params.get('year'))
        )
        sort = params.get('sort', 'newest')
        if sort == 'oldest':
            return qs.order_by('start_date')
        if sort == 'kudos':
            kudos = Cast(KeyTextTransform('kudos_count', 'json'), output_field=IntegerField())
            return qs.annotate(_kudos=kudos).order_by(kudos.desc(nulls_last=True), '-start_date')
        return qs.order_by('-start_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'gallery'

        params = self.request.GET
        context['q'] = params.get('q', '')
        context['sport'] = params.get('sport', 'all')
        context['year'] = params.get('year', 'all')
        context['sort'] = params.get('sort', 'newest')

        # A gallery item is an activity that has a primary photo. Photo presence is read via
        # the Activity.photo property (json.photos.primary.urls), so it's filtered in Python.
        photos = [a for a in context['photos'] if a.photo]
        context['photos'] = photos
        context['count'] = len(photos)
        context['year_list'] = [d.year for d in Activity.objects.dates('start_date', 'year', order='DESC')]
        return context
