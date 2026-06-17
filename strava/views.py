import datetime
import unicodedata

from django.db.models import Count, FloatField, IntegerField, Max, Sum
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from strava.models import Activity, Gear


MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

MAP_MARKER_LIMIT = 1000   # cap markers so a busy map stays readable

GEAR_DONUT_PALETTE = [
    ('#EBE6F2', '#7C4DB8'),
    ('#D5E5D3', '#3A8050'),
    ('#BDD8ED', '#007FB6'),
    ('#F5D0BC', '#FC5200'),
    ('#F3E1C7', '#C98A1B'),
    ('#E6D4E8', '#9B4DCA'),
]


class DashboardView(TemplateView):
    template_name = 'pages/dashboard.html'

    def get_template_names(self):
        # An htmx request comes from the map filter controls (search + sport/gear/year
        # pills); it only needs the recomputed sections, swapped in via hx-swap-oob.
        if getattr(self.request, 'htmx', False):
            return ['pages/_dashboard_results.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'dashboard'

        all_activities = list(Activity.objects.select_related('gear').order_by('-start_date'))
        today = timezone.localdate()

        def local_date(activity):
            return timezone.localtime(activity.start_date).date()

        def seconds(activity):
            return activity.json.get('moving_time', 0) or 0

        def elevation(activity):
            return activity.json.get('total_elevation_gain', 0) or 0

        # ---- Filters (mirror the map's client-side search + sport/gear/year pills) ----
        # The map filters its markers in JS; the same filter state is posted here so every
        # section below recomputes over the matching activities. Non-GPS activities (pool
        # swims, treadmill runs) carry no marker but are still counted in the stats.
        params = self.request.GET
        q = (params.get('q') or '').strip()
        sport = params.get('sport') or 'all'
        gear = params.get('gear') or 'all'
        year = params.get('year') or 'all'
        context['q'], context['sport'], context['gear'], context['year'] = q, sport, gear, year

        tokens = self._unaccent(q).split()

        def matches(a):
            haystack = self._unaccent(f'{a.name} {a.type}')
            return (
                all(t in haystack for t in tokens)
                and (sport == 'all' or a.sport_type == sport)
                and (gear == 'all' or str(a.gear_id or '') == gear)
                and (year == 'all' or str(local_date(a).year) == year)
            )

        activities = [a for a in all_activities if matches(a)]

        # ---- Totals for the active filter ----
        # Cover the whole filtered set so the stat band matches the map and the other
        # sections: every matching activity (all years), or one year when the year
        # filter is set (which already narrows `activities`).
        total_secs = sum(seconds(a) for a in activities)
        context['stat'] = {
            'distance_km': round(sum(float(a.distance) for a in activities) / 1000),
            'elev': round(sum(elevation(a) for a in activities)),
            'time_h': int(total_secs // 3600),
            'time_m': int(total_secs % 3600 // 60),
            'activities': len(activities),
            'active_days': len({local_date(a) for a in activities}),
        }

        # ---- Latest activities ----
        context['latest_activity'] = activities[0] if activities else None
        context['latest_activities'] = activities[:4]

        # ---- Activity map markers (from each activity's start_latlng) ----
        # Built from every activity: the map shows all markers and filters them in JS,
        # which is also where the filter pills' options come from. GPS-less activities
        # (pool swims, treadmill runs, …) can't be placed; map_hidden_count surfaces how
        # many so the map isn't seen as dropping data.
        (context['map_markers'], context['map_activities'],
         context['map_hidden_count']) = self._map_data(all_activities)

        # ---- Activity of the year (longest this year, else longest overall) ----
        # A selected year sets the "year"; otherwise it's the current one.
        season_year = int(year) if year != 'all' and year.isdigit() else today.year
        year_acts = [a for a in activities if local_date(a).year == season_year]
        pool = year_acts or activities
        context['aoty'] = max(pool, key=lambda a: a.distance) if pool else None

        # ---- Trends (weekly / monthly / yearly) + activity calendar ----
        weekly, monthly, yearly = {}, {}, {}
        day_counts = {}
        for a in activities:
            d = local_date(a)
            km, elev, secs = float(a.distance) / 1000, elevation(a), seconds(a)
            wk = d - datetime.timedelta(days=d.weekday())
            for buckets, key in ((weekly, wk), (monthly, (d.year, d.month)), (yearly, d.year)):
                b = buckets.setdefault(key, {'km': 0.0, 'elev': 0.0, 'secs': 0.0})
                b['km'] += km
                b['elev'] += elev
                b['secs'] += secs
            day_counts[d] = day_counts.get(d, 0) + 1

        def rows(buckets, label, partial=None):
            out = []
            for key in sorted(buckets):
                b = buckets[key]
                out.append({
                    'label': label(key),
                    'km': round(b['km']),
                    'elev': round(b['elev']),
                    'hours': round(b['secs'] / 3600, 1),
                    'pace': round((b['secs'] / 60) / b['km'], 2) if b['km'] else 0,
                    **({'partial': True} if partial and partial(key) else {}),
                })
            return out

        context['trends'] = {
            'weekly': rows(weekly, lambda k: f'{MONTHS[k.month - 1]} {k.day}')[-52:],
            'monthly': rows(monthly, lambda k: f"{MONTHS[k[1] - 1]} '{str(k[0])[2:]}"),
            'yearly': rows(yearly, str, partial=lambda y: y == today.year),
        }

        weeks = []
        week_start = today - datetime.timedelta(days=today.weekday())
        for w in range(4, -1, -1):
            ws = week_start - datetime.timedelta(weeks=w)
            we = ws + datetime.timedelta(days=6)
            dots = []
            for i in range(7):
                c = day_counts.get(ws + datetime.timedelta(days=i), 0)
                dots.append(2 if c >= 2 else 1 if c == 1 else 0)
            end = f'{we.day}' if we.month == ws.month else f'{MONTHS[we.month - 1]} {we.day}'
            weeks.append({'label': f'{MONTHS[ws.month - 1]} {ws.day} – {end}', 'dots': dots})
        context['calendar'] = weeks

        # ---- Gear health table + usage donut ----
        # Aggregated over the filtered activities (not the DB-wide totals) so gear stats
        # track the active filter like every other section.
        gear_acts, gear_dist = {}, {}
        for a in activities:
            if a.gear_id:
                gear_acts[a.gear_id] = gear_acts.get(a.gear_id, 0) + 1
                gear_dist[a.gear_id] = gear_dist.get(a.gear_id, 0) + float(a.distance)
        gears = list(Gear.objects.all())
        for g in gears:
            g.activity_count = gear_acts.get(g.pk, 0)
            g.distance_sum = gear_dist.get(g.pk, 0)
            g.distance_km = round((g.distance_sum or 0) / 1000)
            g.wear_pct = min(100, round(g.distance_km / g.lifespan_km * 100)) if g.lifespan_km else 0
            g.wear_alert = 75 <= g.wear_pct < 100
        context['gear_health'] = sorted(gears, key=lambda g: g.activity_count, reverse=True)

        used = sorted((g for g in gears if g.activity_count), key=lambda g: g.activity_count, reverse=True)
        context['gear_usage'] = [
            {
                'name': str(g),
                'acts': g.activity_count,
                'color': GEAR_DONUT_PALETTE[i % len(GEAR_DONUT_PALETTE)][0],
                'hoverColor': GEAR_DONUT_PALETTE[i % len(GEAR_DONUT_PALETTE)][1],
            }
            for i, g in enumerate(used)
        ]

        # ---- Summary (data-backed rows only) ----
        context['total_kudos'] = sum((a.json.get('kudos_count', 0) or 0) for a in activities)
        context['total_photos'] = sum(a.photo_count for a in activities)
        context['last_updated'] = timezone.localtime()
        return context

    @staticmethod
    def _unaccent(s):
        """Lowercase and strip diacritics — the server-side twin of the map filter's
        JS ``unaccent()`` so a filtered search here matches what the map shows."""
        normalized = unicodedata.normalize('NFD', s or '')
        return ''.join(c for c in normalized if not unicodedata.combining(c)).lower()

    @staticmethod
    def _map_data(activities):
        """Collect map markers and their activities from ``start_latlng``.

        Returns ``(markers, map_activities, no_gps_count)`` where ``markers`` is a
        list of ``{id, lat, lng, type, title, polyline, sport_type, sport_label,
        gear, gear_label, year}`` dicts the Leaflet map plots (the encoded
        ``polyline`` is drawn as the route when a marker is clicked; ``sport_type``,
        ``gear`` and ``year`` back the map filter pills; ``id`` lazily fetches the
        activity's card via ``ActivityCardView``), ``map_activities`` are the
        matching ``Activity`` objects in the same order, and ``no_gps_count`` is
        how many activities had no ``start_latlng`` (e.g. pool swims, treadmill
        runs) and so can't be placed. The lists are capped at ``MAP_MARKER_LIMIT``.
        """
        def has_gps(a):
            latlng = a.json.get('start_latlng') or []
            return len(latlng) == 2 and bool(latlng[0] or latlng[1])

        markers, map_activities = [], []
        for a in activities:
            if has_gps(a):
                latlng = a.json['start_latlng']
                markers.append({
                    'id': a.pk,  # for lazily fetching the activity's card on marker click
                    'lat': round(float(latlng[0]), 6),
                    'lng': round(float(latlng[1]), 6),
                    'type': a.type,
                    'title': f'{a.name} · {a.dist} km',
                    'polyline': a.polyline,
                    'sport_type': a.sport_type,
                    'sport_label': a.get_sport_type_display(),
                    'gear': str(a.gear_id) if a.gear_id else '',
                    'gear_label': str(a.gear) if a.gear_id else '',
                    'year': timezone.localtime(a.start_date).year,
                })
                map_activities.append(a)
            if len(markers) >= MAP_MARKER_LIMIT:
                break
        no_gps_count = sum(1 for a in activities if not has_gps(a))
        return markers, map_activities, no_gps_count


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


class ActivityCardView(DetailView):
    """Render a single activity's float card, fetched lazily when its map marker is
    clicked. Keeps the dashboard from server-rendering a card for every marker up
    front (which dominated page load once the marker cap was raised)."""
    model = Activity
    template_name = 'widgets/activity.html'
    context_object_name = 'activity'

    def get_queryset(self):
        return Activity.objects.select_related('gear')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['show_close'] = True  # card is shown standalone (visible, with a close button)
        return context
