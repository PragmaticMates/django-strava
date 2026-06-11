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

    def get_queryset(self):
        return Activity.objects.select_related('gear')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'activities'

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
