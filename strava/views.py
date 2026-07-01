import datetime
import logging
import math
import unicodedata

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.management import call_command
from django.db.models import Count, F, Max, Sum
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from strava.api import format_strava_error
from strava.models import Activity, Gear
from strava.sports import group_data, sport_matches, sport_options


logger = logging.getLogger('strava')

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

        def local_date(activity):
            return timezone.localtime(activity.start_date).date()

        def seconds(activity):
            return activity.moving_time or 0

        def elevation(activity):
            return activity.total_elevation_gain or 0

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

        tokens = self._unaccent(q).split()

        def matches(a):
            haystack = self._unaccent(f'{a.name} {a.type}')
            return (
                all(t in haystack for t in tokens)
                and sport_matches(sport, a.sport_type)
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
        # Markers come from every activity (the map filters them in JS), but the
        # "without GPS not shown" note counts only activities matching the active
        # filter so it tracks what the map currently displays.
        context['map_markers'], context['map_activities'], _ = self._map_data(all_activities)
        context['map_hidden_count'] = sum(1 for a in activities if not self._has_gps(a))

        # ---- Activity of the year (biggest effort this year, else overall) ----
        # A selected year sets the "year"; otherwise it's the current one.
        # Ranked by calories burned rather than distance: distance isn't comparable
        # across sports (20 km running is a far bigger effort than 20 km riding),
        # whereas calories is a cross-sport effort proxy. Calories is a
        # DetailedActivity-only field, so summary-only activities count as 0.
        season_year = int(year) if year != 'all' and year.isdigit() else today.year
        year_acts = [a for a in activities if local_date(a).year == season_year]
        pool = year_acts or activities
        context['aoty'] = max(pool, key=lambda a: a.calories or 0) if pool else None

        # ---- Personal records (per sport tab) ----
        # Each record carries the id of the activity that set it so the widget can
        # open that activity's card on click. The widget has its own sport tabs, so it's
        # scoped by the year filter only — applying the sport/gear/search filters would
        # empty the other tabs and make the records jump around on a text search.
        records_acts = [a for a in all_activities
                        if year == 'all' or str(local_date(a).year) == year]
        # Home is the most-used start location across all activities (stable across the
        # year filter); the per-year "furthest from home" record measures against it.
        home = self._home_location(all_activities)
        context['records'] = self._records(records_acts, home)

        # ---- Running performance (best times per race distance + estimates) ----
        # Year-scoped like the records widget, drawn from each run's Strava best_efforts.
        context['run_perf'] = self._run_performance(records_acts)

        # ---- Trends (weekly / monthly / yearly) + activity calendar ----
        weekly, monthly, yearly = {}, {}, {}
        day_counts = {}
        for a in activities:
            d = local_date(a)
            km, elev, secs = float(a.distance) / 1000, elevation(a), seconds(a)
            wk = d - datetime.timedelta(days=d.weekday())
            for buckets, key in ((weekly, wk), (monthly, (d.year, d.month)), (yearly, d.year)):
                b = buckets.setdefault(key, {'km': 0.0, 'elev': 0.0, 'secs': 0.0, 'acts': 0})
                b['km'] += km
                b['elev'] += elev
                b['secs'] += secs
                b['acts'] += 1
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
                    'acts': b['acts'],
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
        # With no active filter the gear stats default to currently-relevant kit, so
        # hide gear that hasn't been used in over a year.
        no_filter = not q and sport == 'all' and gear == 'all' and year == 'all'
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
        # ---- "By the Numbers" — fun stats + summary, over the filtered activities ----
        context['fun_stats'], context['summary'] = self._by_the_numbers(activities)
        context['last_updated'] = timezone.localtime()
        return context

    # Exact sport types per records tab. An explicit allow-list (rather than the coarse
    # Activity.type bucket, whose "run" fallback swallows every unlisted sport such as
    # AlpineSki) keeps unrelated, fast activities out of the running/cycling PRs.
    RECORD_SPORTS = {
        'Running': {'Run', 'TrailRun', 'VirtualRun'},
        # E-bikes (EBikeRide / EMountainBikeRide) are excluded — motor assistance
        # would unfairly dominate the cycling records.
        'Cycling': {'Ride', 'GravelRide', 'MountainBikeRide',
                    'VirtualRide', 'Velomobile', 'Handcycle'},
        'Hiking': {'Hike', 'Snowshoe', 'Walk'},
        'Swimming': {'Swim'},
    }

    # Rides averaging faster than this (km/h) are excluded from the fastest-avg-speed
    # PR as implausible (GPS errors or mis-tagged motorized activities).
    MAX_RIDE_AVG_KMH = 60
    # Likewise for the instantaneous top-speed PR. Higher than the average cap, since
    # real descents legitimately exceed 60 km/h; only clear GPS glitches are dropped.
    MAX_RIDE_TOP_KMH = 100
    # Hikes faster than this pace (seconds per km) are excluded from the hiking
    # longest/fastest PRs — anything quicker than 7:00/km is almost certainly a
    # mis-tagged run rather than a hike.
    MIN_HIKE_PACE_SEC = 7 * 60

    # Running-performance widget: (display label, Strava best-effort name lowercased,
    # distance in metres). Best times come from each run's `best_efforts`; the estimate
    # is a Riegel projection (T2 = T1·(D2/D1)^1.06) from the athlete's best efforts.
    RUN_PERF_DISTANCES = [
        ('5 km', '5k', 5000.0),
        ('10 km', '10k', 10000.0),
        ('Half Marathon', 'half-marathon', 21097.5),
        ('Marathon', 'marathon', 42195.0),
    ]
    RIEGEL_EXP = 1.06

    # "By the Numbers" fun-stat reference values.
    EARTH_CIRCUMFERENCE_KM = 40075
    EVEREST_HEIGHT_M = 8849
    MARATHON_KM = 42.195
    CO2_KG_PER_KM = 0.12   # ~avg car tailpipe CO2 per km, avoided by cycling instead

    def _records(self, activities, home=None):
        """Personal records grouped by the four sport tabs (Running / Cycling /
        Hiking / Swimming). Returns ``{tab: [record, ...]}`` where each record is a
        ``{'label', 'value', 'unit', 'id'}`` dict — ``id`` is the pk of the activity
        that holds the record, so clicking the row opens that activity's card.
        ``home`` is the (lat, lng) the "furthest from home" record measures against."""
        return {
            name: self._sport_records(name, [a for a in activities if a.sport_type in sports], home)
            for name, sports in self.RECORD_SPORTS.items()
        }

    def _sport_records(self, name, acts, home=None):
        if not acts:
            return []
        recs = []

        # Longest distance. For hiking, ignore run-paced activities (likely mis-tagged).
        longest_pool = [a for a in acts if self._hike_pace_ok(a)] if name == 'Hiking' else acts
        if longest_pool:
            longest = max(longest_pool, key=lambda a: a.distance)
            recs.append(self._rec('Longest', longest, f'{float(longest.distance) / 1000:.1f}', 'km'))

        # Fastest — avg speed for rides, per-100m for swims, avg pace otherwise.
        # Derived from distance/time (like Activity.pace_parts) to avoid relying on
        # the raw API speed units. Hiking again drops run-paced activities.
        moving = [a for a in acts if a.moving_time and a.distance]
        if name == 'Hiking':
            moving = [a for a in moving if self._hike_pace_ok(a)]
        if name == 'Cycling':
            # Drop rides whose average speed exceeds MAX_RIDE_AVG_KMH — those are GPS
            # glitches or mis-tagged motorized activities, not real cycling PRs.
            rides = [a for a in moving
                     if (float(a.distance) / 1000) / (a.moving_time / 3600) <= self.MAX_RIDE_AVG_KMH]
            if rides:
                best = max(rides, key=lambda a: float(a.distance) / a.moving_time)
                kmh = (float(best.distance) / 1000) / (best.moving_time / 3600)
                recs.append(self._rec('Fastest (avg. speed)', best, f'{kmh:.1f}', 'km/h'))
        elif name == 'Swimming':
            if moving:
                best = min(moving, key=lambda a: a.moving_time / (float(a.distance) / 100))
                recs.append(self._rec('Fastest (per 100 m)', best,
                                      self._fmt_pace(best.moving_time / (float(best.distance) / 100)), '/100m'))
        else:
            if moving:
                best = min(moving, key=lambda a: a.moving_time / (float(a.distance) / 1000))
                recs.append(self._rec('Fastest (avg. pace)', best,
                                      self._fmt_pace(best.moving_time / (float(best.distance) / 1000)), '/km'))

        # Most elevation (not meaningful for swimming)
        if name != 'Swimming':
            climbs = [a for a in acts if a.total_elevation_gain]
            if climbs:
                best = max(climbs, key=lambda a: a.total_elevation_gain)
                recs.append(self._rec('Most Elevation', best, f'{best.total_elevation_gain:,.0f}', 'm'))

        # Top speed only for cycling (descents legitimately hit 50–70 km/h). For other
        # sports the GPS max_speed is dominated by noisy spikes — a single bad fix on a
        # slow run reads as 50+ km/h — so show the reliable longest moving time instead.
        if name == 'Cycling':
            speeds = [a for a in acts if a.max_speed and a.max_speed * 3.6 <= self.MAX_RIDE_TOP_KMH]
            if speeds:
                best = max(speeds, key=lambda a: a.max_speed)
                recs.append(self._rec('Top Speed', best, f'{best.max_speed * 3.6:.1f}', 'km/h'))
        else:
            timed = [a for a in acts if a.moving_time]
            if timed:
                best = max(timed, key=lambda a: a.moving_time)
                recs.append(self._rec('Longest Time', best, best.dur, ''))

        # Furthest from home — the activity starting farthest from the usual start point.
        if home:
            located = [a for a in acts if a.start_lat is not None and a.start_lng is not None]
            if located:
                best = max(located, key=lambda a: self._haversine_km(
                    home[0], home[1], a.start_lat, a.start_lng))
                dist = self._haversine_km(home[0], home[1], best.start_lat, best.start_lng)
                recs.append(self._rec('Furthest from Home', best, f'{dist:,.0f}', 'km'))

        return recs

    @staticmethod
    def _rec(label, activity, value, unit):
        return {'label': label, 'value': value, 'unit': unit, 'id': activity.pk}

    @staticmethod
    def _home_location(activities):
        """Estimate "home" as the busiest start location. Start points are bucketed on a
        ~1 km grid (2-decimal rounding); the most-used bucket's averaged coordinates are
        returned as ``(lat, lng)``, or ``None`` when no activity has GPS."""
        clusters = {}
        for a in activities:
            if a.start_lat is None or a.start_lng is None:
                continue
            key = (round(a.start_lat, 2), round(a.start_lng, 2))
            agg = clusters.setdefault(key, [0, 0.0, 0.0])
            agg[0] += 1
            agg[1] += a.start_lat
            agg[2] += a.start_lng
        if not clusters:
            return None
        count, lat_sum, lng_sum = max(clusters.values(), key=lambda agg: agg[0])
        return lat_sum / count, lng_sum / count

    @staticmethod
    def _haversine_km(lat1, lng1, lat2, lng2):
        """Great-circle distance between two lat/lng points, in kilometres."""
        radius = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lng2 - lng1)
        a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        return 2 * radius * math.asin(math.sqrt(a))

    def _hike_pace_ok(self, a):
        """A genuine hike isn't faster than MIN_HIKE_PACE_SEC per km. Activities with no
        pace data (missing time/distance) are kept — there's nothing to disqualify on."""
        if not a.moving_time or not a.distance:
            return True
        return a.moving_time / (float(a.distance) / 1000) >= self.MIN_HIKE_PACE_SEC

    @staticmethod
    def _fmt_pace(seconds):
        """Seconds-per-unit formatted as m:ss (a per-km or per-100m pace)."""
        m, s = divmod(int(round(seconds)), 60)
        return f'{m}:{s:02d}'

    @staticmethod
    def _fmt_hms(seconds):
        """Seconds as h:mm:ss, dropping the hours part when under an hour (m:ss)."""
        total = int(round(seconds))
        h, r = divmod(total, 3600)
        m, s = divmod(r, 60)
        return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'

    def _run_performance(self, activities):
        """Per-distance running performance from Strava ``best_efforts``.

        Returns a row per RUN_PERF_DISTANCES with the actual best time at that
        distance (and the activity that set it, for the click-to-open card) plus a
        Riegel estimate range projected from the athlete's best efforts at every
        recorded distance. Best/estimate are ``'—'`` when there's nothing to compute."""
        runs = [a for a in activities if a.sport_type in self.RECORD_SPORTS['Running']]

        best_by_name = {}   # lowercased effort name -> (elapsed_seconds, activity_pk)
        predictors = {}     # effort distance (m) -> fastest elapsed_seconds seen
        for a in runs:
            for e in (a.json.get('best_efforts') or []):
                t, d = e.get('elapsed_time'), e.get('distance')
                if not isinstance(t, (int, float)) or not t or not d:
                    continue
                name = (e.get('name') or '').lower()
                if name not in best_by_name or t < best_by_name[name][0]:
                    best_by_name[name] = (t, a.pk)
                if d not in predictors or t < predictors[d]:
                    predictors[d] = t

        perf = []
        for label, key, dist in self.RUN_PERF_DISTANCES:
            row = {'dist': label, 'best': '—', 'best_id': None, 'est': '—'}
            if key in best_by_name:
                t, pk = best_by_name[key]
                row['best'], row['best_id'] = self._fmt_hms(t), pk
            if predictors:
                est = min(pt * (dist / pd) ** self.RIEGEL_EXP for pd, pt in predictors.items())
                row['est'] = f'{self._fmt_hms(est * 0.975)} – {self._fmt_hms(est * 1.025)}'
            perf.append(row)
        return perf

    def _by_the_numbers(self, activities):
        """Fun-stat and summary tallies for the "By the Numbers" cards, computed over
        the (already filtered) activities so they track the active filter. Returns
        ``(fun_stats, summary)`` dicts. Calories / achievements / PR counts come from
        the stored Strava JSON; the rest from promoted model fields."""
        total_km = sum(float(a.distance) for a in activities) / 1000
        total_elev = sum((a.total_elevation_gain or 0) for a in activities)
        cycling_km = sum(float(a.distance) for a in activities
                         if a.sport_type in self.RECORD_SPORTS['Cycling']) / 1000

        # Heart rate averaged across activities, weighted by moving time.
        hr = [a for a in activities if a.average_heartrate and a.moving_time]
        avg_hr = (round(sum(a.average_heartrate * a.moving_time for a in hr)
                        / sum(a.moving_time for a in hr)) if hr else 0)

        fun_stats = {
            'around_earth': f'{total_km / self.EARTH_CIRCUMFERENCE_KM * 100:.1f}%',
            'everest': f'{total_elev / self.EVEREST_HEIGHT_M:.1f}x',
            'co2_saved': f'{round(cycling_km * self.CO2_KG_PER_KM):,} kg',
            'marathons': f'{round(total_km / self.MARATHON_KM):,}',
        }
        summary = {
            'photos': sum(a.photo_count for a in activities),
            'calories': sum((a.calories or 0) for a in activities),
            'kudos': sum(a.kudos_count for a in activities),
            'avg_hr': avg_hr,
            'achievements': sum(a.achievement_count for a in activities),
            'prs': sum(a.pr_count for a in activities),
        }
        return fun_stats, summary

    @staticmethod
    def _unaccent(s):
        """Lowercase and strip diacritics — the server-side twin of the map filter's
        JS ``unaccent()`` so a filtered search here matches what the map shows."""
        normalized = unicodedata.normalize('NFD', s or '')
        return ''.join(c for c in normalized if not unicodedata.combining(c)).lower()

    @staticmethod
    def _has_gps(a):
        return a.start_lat is not None

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
        has_gps = DashboardView._has_gps
        markers, map_activities = [], []
        for a in activities:
            if has_gps(a):
                markers.append({
                    'id': a.pk,  # for lazily fetching the activity's card on marker click
                    'lat': a.start_lat,
                    'lng': a.start_lng,
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
