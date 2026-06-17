from datetime import datetime, timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from strava.api import StravaApi
from strava.choices import SportType
from strava.querysets import ActivityQuerySet, GearQuerySet


class Activity(models.Model):
  name = models.CharField(_("name"), max_length=100)
  start_date = models.DateTimeField(_("start date"))
  sport_type = models.CharField(_("sport type"), max_length=29, choices=SportType.choices)
  distance = models.DecimalField(_("distance"), max_digits=12, decimal_places=2)
  moving_time = models.PositiveIntegerField(_("moving time"), null=True, blank=True)
  elapsed_time = models.PositiveIntegerField(_("elapsed time"), null=True, blank=True)
  total_elevation_gain = models.FloatField(_("elevation gain"), null=True, blank=True)
  average_speed = models.FloatField(_("average speed"), null=True, blank=True)
  max_speed = models.FloatField(_("max speed"), null=True, blank=True)
  average_heartrate = models.FloatField(_("average heartrate"), null=True, blank=True)
  max_heartrate = models.FloatField(_("max heartrate"), null=True, blank=True)
  kudos_count = models.PositiveIntegerField(_("kudos"), default=0)
  total_photo_count = models.PositiveIntegerField(_("photos"), default=0)
  photo_url = models.URLField(_("photo URL"), max_length=500, blank=True, default="")
  start_lat = models.FloatField(_("start latitude"), null=True, blank=True)
  start_lng = models.FloatField(_("start longitude"), null=True, blank=True)
  gear = models.ForeignKey("Gear", on_delete=models.SET_NULL,
                           blank=True, null=True, default=None)
  json = models.JSONField()
  objects = ActivityQuerySet.as_manager()

  class Meta:
    verbose_name = _("activity")
    verbose_name_plural = _("activities")
    get_latest_by = "start_date"
    ordering = ("-start_date",)

  def __str__(self):
      return self.name

  def get_absolute_url(self):
    return f'https://strava.com/activities/{self.id}'

  @classmethod
  def read_json(cls, json):
    primary = (json.get('photos') or {}).get('primary') or {}
    urls = primary.get('urls') or {}
    latlng = json.get('start_latlng') or []
    # Treat (0, 0) / missing coords as "no GPS" (e.g. pool swims, treadmill runs).
    has_gps = len(latlng) == 2 and bool(latlng[0] or latlng[1])
    return {
      # 'id': json['id'],
      'name': json['name'],
      'gear_id': json['gear_id'],
      'sport_type': json['sport_type'],
      'distance': json['distance'],
      'start_date': datetime.fromisoformat(json['start_date']),
      'moving_time': json.get('moving_time'),
      'elapsed_time': json.get('elapsed_time'),
      'total_elevation_gain': json.get('total_elevation_gain'),
      'average_speed': json.get('average_speed'),
      'max_speed': json.get('max_speed'),
      'average_heartrate': json.get('average_heartrate'),
      'max_heartrate': json.get('max_heartrate'),
      'kudos_count': json.get('kudos_count', 0) or 0,
      'total_photo_count': json.get('total_photo_count', 0) or 0,
      'photo_url': urls.get('600') or urls.get('100') or '',
      'start_lat': round(float(latlng[0]), 6) if has_gps else None,
      'start_lng': round(float(latlng[1]), 6) if has_gps else None,
    }

  def update_from_json(self):
    for attr, value in Activity.read_json(self.json).items():
      setattr(self, attr, value)

    if self.gear_id and not Gear.objects.filter(id=self.gear_id).exists():
      gear_data = StravaApi().get_gear(self.gear_id)
      print(gear_data)

      data = Gear.read_json(gear_data)
      data['json'] = gear_data

      # logger.info(data)
      obj, created = Gear.objects.get_or_create(
        id=gear_data["id"],
        defaults=data,
      )
      print(obj, created)

    self.save()

  def fetch_from_api(self):
    data = StravaApi().get_activity(self.id)
    self.json = data
    self.save(update_fields=["json"])
    self.update_from_json()

  def send_to_api(self):
    StravaApi().update_activity(
      id=self.id,
      name=self.name,
      sport_type=self.sport_type,
      gear_id=self.gear_id
    )
    self.fetch_from_api()

  def is_synced(self):
      conditions = [
        self.gear_id == self.json['gear_id'],
        self.sport_type == self.json['sport_type'],
      ]
      return all(conditions)
  is_synced.boolean = True

  def is_gear_synced(self):
      conditions = [
        self.gear_id == self.json['gear_id'],
      ]
      return all(conditions)
  is_gear_synced.boolean = True

  @property
  def type(self):
    s = self.sport_type
    if 'Trail' in s:
      return 'trail'
    if s in ('Hike', 'Snowshoe'):
      return 'hike'
    if s == 'Walk':
      return 'walk'
    if 'Ride' in s:
      return 'ride'
    if 'Swim' in s:
      return 'swim'
    return 'run'

  @property
  def dist(self):
    return round(float(self.distance) / 1000, 1)

  @property
  def dur(self):
    t = self.moving_time or 0
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f'{h}h {m:02d}m' if h else f'{m}m {s:02d}s'

  @property
  def pace_parts(self):
    t = self.moving_time or 0
    d = float(self.distance)
    if not t or not d:
      return '-', ''
    d_km = d / 1000
    if self.type == 'ride':
      return f'{d_km / (t / 3600):.1f}', 'km/h'
    if self.type == 'swim':
      pace_s = t / (d / 100)
      m, s = divmod(int(pace_s), 60)
      return f'{m}:{s:02d}', '/100m'
    pace_s = t / d_km
    m, s = divmod(int(pace_s), 60)
    return f'{m}:{s:02d}', '/km'

  @property
  def pace(self):
    val, unit = self.pace_parts
    if not unit:
      return val
    return f'{val} {unit}'

  @property
  def elev(self):
    return round(self.total_elevation_gain or 0)

  @property
  def kudos(self):
    return self.kudos_count

  @property
  def comments(self):
    return self.json.get('comment_count', 0)

  @property
  def photo_count(self):
    return self.total_photo_count

  @property
  def pb(self):
    return bool(self.json.get('pr_count', 0))

  @property
  def photo(self):
    return self.photo_url or None

  @property
  def has_gps(self):
    return self.start_lat is not None

  @property
  def has_heartrate(self):
    return self.average_heartrate is not None and self.max_heartrate is not None

  @property
  def polyline(self):
    m = self.json.get('map') or {}
    return m.get('polyline') or m.get('summary_polyline', '')


class Gear(models.Model):
  SHOE_LIFESPAN_KM = 700
  BIKE_LIFESPAN_KM = 12000

  GEAR_TYPES = (('bike', _("bike")), ('shoe', _("shoe")))

  id = models.CharField(max_length=36, primary_key=True, editable=False)  # default=uuid.uuid4
  primary = models.BooleanField(_("primary"), default=False)
  brand_name = models.CharField(_("brand name"), max_length=30)
  model_name = models.CharField(_("model name"), max_length=50)
  description = models.CharField(_("description"), max_length=100)
  gear_type = models.CharField(_("type"), max_length=4, choices=GEAR_TYPES, default='shoe')
  json = models.JSONField()
  objects = GearQuerySet.as_manager()

  def __str__(self):
      return f'{self.brand_name} {self.model_name}'

  @property
  def distance(self):
      return self.activity_set.aggregate(models.Sum('distance'))['distance__sum']

  @property
  def is_old(self):
    last_used = self.activity_set.aggregate(models.Max('start_date'))['start_date__max']
    if last_used is None:
      return True
    return last_used < timezone.now() - timedelta(days=365)

  @property
  def lifespan_km(self):
    return self.BIKE_LIFESPAN_KM if self.gear_type == 'bike' else self.SHOE_LIFESPAN_KM

  @classmethod
  def get_or_create(cls, id):
    if not id:
      return None
    try:
      return Gear.objects.get(id=id)
    except Gear.DoesNotExist:
      pass

    gear_data = StravaApi().get_gear(id)
    data = Gear.read_json(gear_data)
    data['json'] = gear_data

    gear, created = Gear.objects.get_or_create(
      id=gear_data["id"],
      defaults=data,
    )
    return gear

  def fetch_from_api(self):
    data = StravaApi().get_gear(self.id)
    self.json = data
    self.save(update_fields=["json"])
    self.update_from_json()

  @classmethod
  def read_json(cls, json):
    return {
      # 'id': json['id'],
      'primary': json['primary'],
      'brand_name': json['brand_name'],
      'model_name': json['model_name'],
      'description': json['description'] or '',
      # Per the Strava API, only bikes carry a frame_type (DetailedGear); shoes have none.
      'gear_type': 'bike' if json.get('frame_type') is not None else 'shoe',
    }

  def update_from_json(self):
    for attr, value in Gear.read_json(self.json).items():
      setattr(self, attr, value)
    self.save()
