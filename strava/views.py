from django.shortcuts import render


def dashboard(request):
    return render(request, 'dashboard.html', {
        'active_page': 'dashboard',
    })


def activities(request):
    return render(request, 'activities.html', {
        'active_page': 'activities',
    })


def gear(request):
    return render(request, 'gear.html', {
        'active_page': 'gear',
    })


def gallery(request):
    return render(request, 'gallery.html', {
        'active_page': 'gallery',
    })
