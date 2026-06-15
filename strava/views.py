import datetime

from django.db.models import FloatField, Sum
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


def gear(request):
    return render(request, 'pages/gear.html', {
        'active_page': 'gear',
    })


def gallery(request):
    return render(request, 'pages/gallery.html', {
        'active_page': 'gallery',
    })
