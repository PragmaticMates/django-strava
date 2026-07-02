import datetime
import logging

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.management import call_command
from django.db.models import Count, F, Max, Sum
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from strava import analytics, helpers
from strava.api import format_strava_error
from strava.consts import MONTHS
from strava.models import Activity, Gear
from strava.sports import SPORT_GROUPS, group_data, sport_matches, sport_options


logger = logging.getLogger('strava')

GEAR_DONUT_PALETTE = [
    ('#EBE6F2', '#7C4DB8'),
    ('#D5E5D3', '#3A8050'),
    ('#BDD8ED', '#007FB6'),
    ('#F5D0BC', '#FC5200'),
    ('#F3E1C7', '#C98A1B'),
    ('#E6D4E8', '#9B4DCA'),
]


class DashboardView(TemplateView):
    template_name = 'strava/pages/dashboard.html'

    def get_template_names(self):
        # An htmx request comes from the map filter controls (search + sport/gear/year
        # pills); it only needs the recomputed sections, swapped in via hx-swap-oob.
        if getattr(self.request, 'htmx', False):
            return ['strava/hx/dashboard_results.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'dashboard'

        all_activities = list(Activity.objects.select_related('gear').order_by('-start_date'))
        today = timezone.localdate()

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

        # Sport filter dropdown: every sport in the data (not just GPS-mapped ones) + groups.
        context['sport_options'] = sport_options(Activity.objects.all())
        context['sport_groups'] = group_data()

        tokens = helpers.unaccent(q).split()

        def matches(a):
            haystack = helpers.unaccent(f'{a.name} {a.type}')
            return (
                all(t in haystack for t in tokens)
                and sport_matches(sport, a.sport_type)
                and (gear == 'all' or str(a.gear_id or '') == gear)
                and (year == 'all' or str(helpers.local_date(a).year) == year)
            )

        activities = [a for a in all_activities if matches(a)]

        # ---- Totals for the active filter ----
        total_secs = sum((a.moving_time or 0) for a in activities)
        context['stat'] = {
            'distance_km': round(sum(a.distance for a in activities) / 1000),
            'elev': round(sum((a.total_elevation_gain or 0) for a in activities)),
            'time_h': int(total_secs // 3600),
            'time_m': int(total_secs % 3600 // 60),
            'activities': len(activities),
            'active_days': len({helpers.local_date(a) for a in activities}),
        }

        # ---- Latest activities ----
        context['latest_activity'] = activities[0] if activities else None
        context['latest_activities'] = activities[:4]

        # ---- Activity map markers (from each activity's start_latlng) ----
        # Built from every activity (the map filters them in JS); map_hidden_count counts
        # only the filtered activities without GPS so it tracks what the map displays.
        context['map_markers'], context['map_activities'] = analytics.map_data(all_activities)
        context['map_hidden_count'] = sum(1 for a in activities if not helpers.has_gps(a))

        # ---- Activity of the year (biggest effort this year, else overall) ----
        # Ranked by calories (a cross-sport effort proxy) rather than distance, which isn't
        # comparable across sports. Summary-only activities have no calories and count as 0.
        season_year = int(year) if year != 'all' and year.isdigit() else today.year
        year_acts = [a for a in activities if helpers.local_date(a).year == season_year]
        pool = year_acts or activities
        context['aoty'] = max(pool, key=lambda a: a.calories or 0) if pool else None

        # ---- Personal records + running performance ----
        # Scoped by the year filter only (the widgets have their own sport tabs, which the
        # sport/gear/search filters would otherwise empty). Home is the most-used start
        # location across all activities, stable across the year filter.
        records_acts = [a for a in all_activities
                        if year == 'all' or str(helpers.local_date(a).year) == year]
        home = helpers.home_location(all_activities)
        context['records'] = analytics.records(records_acts, home)
        context['run_perf'] = analytics.run_performance(records_acts)

        # ---- Trends (weekly / monthly / yearly) + activity calendar ----
        context['trends'] = analytics.trends(activities, today)
        context['calendar'] = analytics.activity_calendar(activities, today)

        # ---- Gear health table + usage donut ----
        context['gear_health'], context['gear_usage'] = self._gear_sections(
            activities, no_filter=not q and sport == 'all' and gear == 'all' and year == 'all')

        # ---- "By the Numbers" — fun stats + summary, over the filtered activities ----
        context['fun_stats'], context['summary'] = analytics.by_the_numbers(activities)
        context['last_updated'] = timezone.localtime()
        return context

    def _gear_sections(self, activities, no_filter):
        """Gear health rows + usage-donut slices, aggregated over the filtered activities
        (not DB-wide totals) so gear stats track the active filter like every other
        section. With no active filter, gear unused for over a year is hidden."""
        gear_acts, gear_dist = {}, {}
        for a in activities:
            if a.gear_id:
                gear_acts[a.gear_id] = gear_acts.get(a.gear_id, 0) + 1
                gear_dist[a.gear_id] = gear_dist.get(a.gear_id, 0) + a.distance
        gears = list(Gear.objects.all())
        if no_filter:
            gears = [g for g in gears if not g.is_old]
        for g in gears:
            g.activity_count = gear_acts.get(g.pk, 0)
            g.distance_sum = gear_dist.get(g.pk, 0)
            g.distance_km = round((g.distance_sum or 0) / 1000)
            g.wear_pct = min(100, round(g.distance_km / g.lifespan_km * 100)) if g.lifespan_km else 0
            g.wear_alert = 75 <= g.wear_pct < 100
        if not no_filter:
            # Under an active filter, only show gear used by the matching activities.
            gears = [g for g in gears if g.activity_count]
        gear_health = sorted(gears, key=lambda g: g.activity_count, reverse=True)

        used = sorted((g for g in gears if g.activity_count), key=lambda g: g.activity_count, reverse=True)
        gear_usage = [
            {
                'name': str(g),
                'acts': g.activity_count,
                'color': GEAR_DONUT_PALETTE[i % len(GEAR_DONUT_PALETTE)][0],
                'hoverColor': GEAR_DONUT_PALETTE[i % len(GEAR_DONUT_PALETTE)][1],
            }
            for i, g in enumerate(used)
        ]
        return gear_health, gear_usage


class RefreshView(UserPassesTestMixin, DashboardView):
    """Footer refresh button (POST): run the ``import_strava`` management command to
    pull the latest activities from the Strava API, then re-render every dashboard
    section as out-of-band swaps (plus the footer timestamp) so the page updates in
    place. GET is not allowed — the button always posts.

    Restricted to logged-in superusers (the button is hidden for everyone else, and
    this guards the endpoint against direct requests) — importing hits the Strava API
    and writes to the database, so it isn't a public action."""

    raise_exception = True  # 403 for non-superusers instead of a login redirect
    http_method_names = ['post']

    def test_func(self):
        return self.request.user.is_superuser
    template_name = 'strava/hx/dashboard_refresh.html'
    error_template_name = 'strava/hx/dashboard_refresh_error.html'

    def get_template_names(self):
        return [self.template_name]

    def post(self, request, *args, **kwargs):
        try:
            call_command('import_strava')
        except Exception as error:
            # The Strava API can reject the import (inactive app, expired token, rate
            # limit, outage). Surface the reason in the footer instead of a 500 that
            # would leave the button spinning with no feedback.
            logger.exception('Strava import from the dashboard refresh button failed')
            return render(request, self.error_template_name, {'error': format_strava_error(error)})
        context = self.get_context_data()
        return self.render_to_response(context)


class ActivitiesView(ListView):
    model = Activity
    template_name = 'strava/pages/activities.html'
    context_object_name = 'activities'

    def get_template_names(self):
        if getattr(self.request, 'htmx', False):
            return ['strava/hx/activities_results.html']
        return [self.template_name]

    def get_queryset(self):
        params = self.request.GET
        return (
            Activity.objects.select_related('gear')
            .search(params.get('q'))
            .for_sport_selection(params.get('sport'))
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
            total_elevation=Sum('total_elevation_gain'),
            total_time=Sum('moving_time'),
        )
        today = timezone.now().date()
        week_start = today - datetime.timedelta(days=today.weekday())

        context['sport_options'] = sport_options(Activity.objects.all())
        context['sport_groups'] = group_data()
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
    template_name = 'strava/pages/gear.html'
    context_object_name = 'gear_list'

    def get_template_names(self):
        if getattr(self.request, 'htmx', False):
            return ['strava/hx/gear_results.html']
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
    template_name = 'strava/pages/gallery.html'
    context_object_name = 'photos'

    def get_template_names(self):
        if getattr(self.request, 'htmx', False):
            return ['strava/hx/gallery_results.html']
        return [self.template_name]

    def get_queryset(self):
        params = self.request.GET
        # A gallery item is an activity with a primary photo; filter that in SQL.
        qs = (
            Activity.objects
            .exclude(photo_url='')
            .search(params.get('q'))
            .for_sport_selection(params.get('sport'))
            .for_year(params.get('year'))
        )
        sort = params.get('sort', 'newest')
        if sort == 'oldest':
            return qs.order_by('start_date')
        if sort == 'kudos':
            return qs.order_by(F('kudos_count').desc(nulls_last=True), '-start_date')
        return qs.order_by('-start_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'gallery'

        params = self.request.GET
        context['q'] = params.get('q', '')
        context['sport'] = params.get('sport', 'all')
        context['year'] = params.get('year', 'all')
        context['sort'] = params.get('sort', 'newest')

        # Photo presence is now filtered in the queryset (photo_url), so the list is ready.
        photos = list(context['photos'])
        context['photos'] = photos
        context['count'] = len(photos)
        context['year_list'] = [d.year for d in Activity.objects.dates('start_date', 'year', order='DESC')]
        context['sport_options'] = sport_options(Activity.objects.exclude(photo_url=''))
        context['sport_groups'] = group_data()
        return context


class CompareView(TemplateView):
    """Year-over-year comparison matrix: one metric per row, one season per column.

    Each numeric row is scaled into a bar (relative to the row's best year) and
    carries a year-on-year delta; the best year gets a crown, the current year is
    highlighted. A trailing block of "signature effort" rows names the standout
    activity per year (activity of the year, longest, biggest climb, …). The single
    control is a sport filter, wired via htmx to re-render just the matrix body."""

    template_name = 'strava/pages/compare.html'

    # Activity.type values that have a meaningful "/km" pace (rides use km/h, swims
    # /100m, so they're excluded from the pace metric and the fastest-pace effort row).
    PACE_TYPES = {'run', 'trail', 'hike', 'walk'}
    # Paces faster than this (seconds per km) are GPS/distance glitches — a corrupt
    # near-zero distance or time reads as an impossibly quick pace — not real efforts;
    # 2:30/km is already quicker than an elite 10k, so anything below is dropped.
    MIN_PLAUSIBLE_PACE_SEC = 150

    def _paceable(self, a):
        """A run/trail/hike/walk with a plausible /km pace (see MIN_PLAUSIBLE_PACE_SEC)."""
        if a.type not in self.PACE_TYPES or not a.moving_time or not a.distance:
            return False
        return a.moving_time / (a.distance / 1000) >= self.MIN_PLAUSIBLE_PACE_SEC

    def get_template_names(self):
        # A sport-filter click posts here via htmx; it only needs the matrix body
        # (filter bar + table), swapped into #cmp-body.
        if getattr(self.request, 'htmx', False):
            return ['strava/hx/compare_body.html']
        return [self.template_name]

    _local_date = staticmethod(helpers.local_date)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'compare'

        sport = self.request.GET.get('sport') or 'all'
        context['sport'] = sport

        all_activities = list(Activity.objects.select_related('gear'))
        activities = [a for a in all_activities if sport_matches(sport, a.sport_type)]

        # Sport filter: "All sports" plus the top-sport groups actually present in the
        # data (an empty group would filter to nothing, so it's hidden).
        present = {a.sport_type for a in all_activities}
        seg = [{'key': 'all', 'label': 'All sports', 'icon': 'all', 'active': sport == 'all'}]
        for group in SPORT_GROUPS:
            if present.intersection(group['types']):
                seg.append({'key': group['key'], 'label': str(group['label']),
                            'icon': group['icon'], 'active': sport == group['key']})
        context['sport_seg'] = seg

        today = timezone.localdate()

        by_year = {}
        for a in activities:
            by_year.setdefault(self._local_date(a).year, []).append(a)

        if not by_year:
            context['years'] = context['rows'] = context['aoty_rows'] = []
            return context

        # Contiguous span so every season sits side by side, even a gap year.
        years = list(range(min(by_year), max(by_year) + 1))
        context['years'] = [
            {'year': y, 'current': y == today.year,
             'tag': (f'through {MONTHS[today.month - 1]} {today.day}'
                     if y == today.year else 'full season')}
            for y in years
        ]

        context['rows'] = self._numeric_rows(years, by_year, today)
        context['aoty_rows'] = self._effort_rows(years, by_year,
                                                 helpers.home_location(all_activities), today)
        return context

    def _numeric_rows(self, years, by_year, today):
        ld = self._local_date

        def distance(acts):
            return round(sum(a.distance for a in acts) / 1000) if acts else None

        def elevation(acts):
            return round(sum((a.total_elevation_gain or 0) for a in acts)) if acts else None

        def hours(acts):
            return int(round(sum((a.moving_time or 0) for a in acts) / 3600)) if acts else None

        def count(acts):
            return len(acts) or None

        def active_days(acts):
            return len({ld(a) for a in acts}) or None

        def kudos(acts):
            return sum(a.kudos_count for a in acts) if acts else None

        def prs(acts):
            return sum(a.pr_count for a in acts) if acts else None

        def achievements(acts):
            return sum(a.achievement_count for a in acts) if acts else None

        def avg_pace(acts):
            # Distance-weighted pace for the whole year (total time / total distance),
            # not the single fastest run — a short sprint race isn't representative.
            paceable = [a for a in acts if self._paceable(a)]
            total_km = sum(a.distance for a in paceable) / 1000
            return sum(a.moving_time for a in paceable) / total_km if total_km else None

        def biggest_week(acts):
            if not acts:
                return None
            daily = {}
            for a in acts:
                daily[ld(a)] = daily.get(ld(a), 0.0) + a.distance / 1000
            items = list(daily.items())
            best = 0.0
            for d0, _ in items:
                window = sum(km for d, km in items if 0 <= (d - d0).days <= 6)
                best = max(best, window)
            return round(best) or None

        # (name, unit, icon, small-unit, format, lower-is-better, value fn)
        specs = [
            ('Distance', 'kilometres', 'dist', 'km', 'int', False, distance),
            ('Elevation gain', 'metres climbed', 'elev', 'm', 'int', False, elevation),
            ('Moving time', 'hours active', 'time', 'h', 'int', False, hours),
            ('Activities', 'sessions logged', 'acts', '', 'int', False, count),
            ('Active days', 'days on the move', 'days', 'd', 'int', False, active_days),
            ('Average pace', 'lower is faster', 'pace', '/km', 'pace', True, avg_pace),
            ('Biggest week', 'peak 7-day block', 'week', 'km', 'int', False, biggest_week),
            ('Kudos received', 'from the community', 'kudos', '', 'int', False, kudos),
            ('PRs set', 'personal records', 'prs', '', 'int', False, prs),
            ('Achievements', 'badges earned', 'ach', '', 'int', False, achievements),
        ]
        rows = []
        for name, unit, icon, small, fmt, lower, fn in specs:
            values = [fn(by_year.get(y, [])) for y in years]
            if any(v is not None for v in values):
                rows.append(self._numeric_row(years, values, name, unit, icon, small, fmt, lower, today))
        return rows

    def _numeric_row(self, years, values, name, unit, icon, small, fmt, lower, today):
        present = [v for v in values if v is not None]
        best_val = (min if lower else max)(present)
        vmax, vmin = max(present), min(present)
        first_idx = next(i for i, v in enumerate(values) if v is not None)
        best_idx = values.index(best_val)  # first year holding the best value (ties → earliest)

        cells = []
        for i, (year, v) in enumerate(zip(years, values)):
            current = year == today.year
            if v is None:
                cells.append({'has': False, 'current': current})
                continue
            if lower:
                # Lower is better (pace): the fastest year fills the bar; slower years
                # shrink toward a 30% floor so the spread stays legible.
                width = 100.0 if vmax == vmin else 30 + (vmax - v) / (vmax - vmin) * 70
            else:
                width = 100.0 if vmax == 0 else v / vmax * 100
            if i == first_idx:
                delta = {'kind': 'base'}
            elif values[i - 1] is None:
                delta = {'kind': 'none'}
            else:
                delta = self._delta(values[i - 1], v, lower)
            cells.append({
                'has': True, 'current': current, 'best': i == best_idx,
                'display': self._fmt_value(v, fmt), 'small': small,
                'w': round(width, 1), 'delta': delta,
            })
        return {'name': name, 'unit': unit, 'icon': icon, 'cells': cells}

    @staticmethod
    def _delta(prev, value, lower):
        """Year-on-year change badge. For pace (lower-better) the change is shown in
        seconds and a drop counts as improvement; otherwise it's a percentage."""
        if lower:
            diff = int(round(value - prev))
            if diff < 0:
                return {'dir': 'up', 'text': f'−{abs(diff)}s'}
            if diff > 0:
                return {'dir': 'down', 'text': f'+{diff}s'}
            return {'dir': 'up', 'text': '0s'}
        if prev == 0:
            return {'dir': 'up' if value >= 0 else 'down', 'text': '—'}
        pct = round((value - prev) / prev * 100)
        return {'dir': 'up' if value >= prev else 'down',
                'text': f'{"+" if pct >= 0 else "−"}{abs(pct)}%'}

    @staticmethod
    def _fmt_value(value, fmt):
        if fmt == 'pace':
            return helpers.fmt_pace(value)
        return f'{value:,}'

    def _effort_rows(self, years, by_year, home, today):
        """Signature-effort rows: the standout activity per year for a handful of
        superlatives, shown as name + a compact stat line."""
        def dist_seg(a):
            return {'v': f'{a.distance_km:.1f}', 'u': 'km'}

        def elev_seg(a):
            return {'v': f'{a.elevation:,}', 'u': 'm'}

        def pace_of(a):
            return a.moving_time / (a.distance / 1000)

        def build(icon, name, unit, pick, segs, valid=None):
            cells, any_present = [], False
            for y in years:
                acts = by_year.get(y, [])
                if valid:
                    acts = [a for a in acts if valid(a)]
                current = y == today.year
                if not acts:
                    cells.append({'current': current})
                    continue
                any_present = True
                best = pick(acts)
                cells.append({'current': current, 'id': best.pk,
                              'title': best.name, 'segments': segs(best)})
            return {'icon': icon, 'name': name, 'unit': unit, 'cells': cells} if any_present else None

        haversine = helpers.haversine_km
        rows = [
            build('trophy', 'Activity of the year', 'signature effort',
                  lambda acts: max(acts, key=lambda a: a.calories or 0),
                  lambda a: [dist_seg(a), elev_seg(a)]),
            build('longest', 'Longest activity', 'biggest single outing',
                  lambda acts: max(acts, key=lambda a: a.distance),
                  lambda a: [dist_seg(a), elev_seg(a)]),
            build('climb', 'Most elevation', 'single climb',
                  lambda acts: max(acts, key=lambda a: a.total_elevation_gain or 0),
                  lambda a: [elev_seg(a), dist_seg(a)],
                  valid=lambda a: a.total_elevation_gain),
        ]
        if home:
            rows.append(build(
                'pin', 'Furthest from home', 'travel effort',
                lambda acts: max(acts, key=lambda a: haversine(home[0], home[1], a.start_lat, a.start_lng)),
                lambda a: [{'v': f'{round(haversine(home[0], home[1], a.start_lat, a.start_lng)):,}',
                            'u': 'km away'}],
                valid=lambda a: a.start_lat is not None and a.start_lng is not None))
        rows.append(build(
            'bolt', 'Fastest avg pace', 'quickest effort',
            lambda acts: min(acts, key=pace_of),
            lambda a: [{'v': helpers.fmt_pace(pace_of(a)), 'u': '/km'}, dist_seg(a)],
            valid=self._paceable))
        return [r for r in rows if r]


class ActivityCardView(DetailView):
    """Render a single activity's float card, fetched lazily when its map marker is
    clicked. Keeps the dashboard from server-rendering a card for every marker up
    front (which dominated page load once the marker cap was raised)."""
    model = Activity
    template_name = 'strava/widgets/activity.html'
    context_object_name = 'activity'

    def get_queryset(self):
        return Activity.objects.select_related('gear')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['show_close'] = True  # card is shown standalone (visible, with a close button)
        # Cards opened from a map marker (?map=1) drop the redundant route trace — the
        # route is already drawn on the map behind the card — and show a full-bleed photo.
        context['map_card'] = self.request.GET.get('map') == '1'
        return context
