from django.shortcuts import render


MOCK_ACTIVITIES = [
    {'id': 1,  'type': 'ride',  'name': 'Morning Sufferfest',      'date': 'Jun 11, 2026', 'time': '7:04 AM',   'dist': '62.4',  'dur': '2h 08m',   'elev': '940',   'pace': '29.2 km/h', 'gear': 'Cervélo R5',          'kudos': 14, 'comments': 3,  'pb': False},
    {'id': 2,  'type': 'run',   'name': 'Lunch Tempo',             'date': 'Jun 10, 2026', 'time': '12:18 PM',  'dist': '12.1',  'dur': '54m 22s',  'elev': '88',    'pace': '4:30/km',   'gear': 'Nike Vaporfly 3',     'kudos': 7,  'comments': 1,  'pb': False},
    {'id': 3,  'type': 'ride',  'name': 'Evening Spin',            'date': 'Jun 9, 2026',  'time': '6:40 PM',   'dist': '38.7',  'dur': '1h 21m',   'elev': '420',   'pace': '28.6 km/h', 'gear': 'Cannondale Topstone', 'kudos': 9,  'comments': 0,  'pb': False},
    {'id': 4,  'type': 'run',   'name': 'Sunday Long Run',         'date': 'Jun 8, 2026',  'time': '8:15 AM',   'dist': '21.0',  'dur': '1h 44m',   'elev': '310',   'pace': '4:57/km',   'gear': 'Nike Vaporfly 3',     'kudos': 22, 'comments': 5,  'pb': True},
    {'id': 5,  'type': 'ride',  'name': 'Gran Fondo – Malá Fatra', 'date': 'Jun 7, 2026',  'time': '7:00 AM',   'dist': '118.0', 'dur': '4h 22m',   'elev': '2,180', 'pace': '27.0 km/h', 'gear': 'Cervélo R5',          'kudos': 41, 'comments': 12, 'pb': True},
    {'id': 6,  'type': 'trail', 'name': 'Veľká Fatra Trails',      'date': 'Jun 6, 2026',  'time': '6:50 AM',   'dist': '24.3',  'dur': '3h 12m',   'elev': '1,240', 'pace': '7:55/km',   'gear': 'Hoka Speedgoat 5',    'kudos': 18, 'comments': 4,  'pb': False},
    {'id': 7,  'type': 'run',   'name': 'Recovery Jog',            'date': 'Jun 4, 2026',  'time': '7:30 AM',   'dist': '6.8',   'dur': '35m 10s',  'elev': '42',    'pace': '5:10/km',   'gear': 'Nike Pegasus 41',     'kudos': 3,  'comments': 0,  'pb': False},
    {'id': 8,  'type': 'ride',  'name': 'Coffee Ride',             'date': 'Jun 3, 2026',  'time': '9:00 AM',   'dist': '44.5',  'dur': '1h 38m',   'elev': '580',   'pace': '27.2 km/h', 'gear': 'Cannondale Topstone', 'kudos': 11, 'comments': 2,  'pb': False},
    {'id': 9,  'type': 'ride',  'name': 'Tatry Switchbacks',       'date': 'Jun 1, 2026',  'time': '7:20 AM',   'dist': '88.0',  'dur': '3h 14m',   'elev': '1,680', 'pace': '27.2 km/h', 'gear': 'Cervélo R5',          'kudos': 29, 'comments': 7,  'pb': False},
    {'id': 10, 'type': 'run',   'name': 'Parkrun – Bánov',         'date': 'May 31, 2026', 'time': '9:02 AM',   'dist': '5.0',   'dur': '19m 58s',  'elev': '12',    'pace': '3:59/km',   'gear': 'Nike Vaporfly 3',     'kudos': 31, 'comments': 9,  'pb': True},
    {'id': 11, 'type': 'trail', 'name': 'Forest Loops',            'date': 'May 30, 2026', 'time': '6:30 AM',   'dist': '18.2',  'dur': '2h 24m',   'elev': '810',   'pace': '7:55/km',   'gear': 'Hoka Speedgoat 5',    'kudos': 8,  'comments': 1,  'pb': False},
    {'id': 12, 'type': 'ride',  'name': 'Club Ride',               'date': 'May 28, 2026', 'time': '8:00 AM',   'dist': '72.1',  'dur': '2h 35m',   'elev': '1,040', 'pace': '27.9 km/h', 'gear': 'Cervélo R5',          'kudos': 15, 'comments': 3,  'pb': False},
    {'id': 13, 'type': 'run',   'name': 'Track Session',           'date': 'May 27, 2026', 'time': '6:00 PM',   'dist': '10.0',  'dur': '39m 45s',  'elev': '18',    'pace': '3:58/km',   'gear': 'Nike Vaporfly 3',     'kudos': 12, 'comments': 2,  'pb': False},
]


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


def activities(request):
    return render(request, 'activities.html', {
        'active_page': 'activities',
        'activities': MOCK_ACTIVITIES,
    })


def gear(request):
    return render(request, 'gear.html', {
        'active_page': 'gear',
    })


def gallery(request):
    return render(request, 'gallery.html', {
        'active_page': 'gallery',
    })
