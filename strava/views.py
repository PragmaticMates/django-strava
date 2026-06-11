from django.shortcuts import render
from django.views.generic import ListView

from strava.models import Activity


def dashboard(request):
    return render(request, 'dashboard.html', {
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
    template_name = 'activities.html'
    context_object_name = 'activities'

    def get_queryset(self):
        return Activity.objects.select_related('gear')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'activities'
        return context


def gear(request):
    return render(request, 'gear.html', {
        'active_page': 'gear',
    })


def gallery(request):
    return render(request, 'gallery.html', {
        'active_page': 'gallery',
    })
