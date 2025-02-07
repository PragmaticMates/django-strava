from datetime import datetime

from django.db import models
from django.utils.translation import gettext_lazy as _

from strava.api import StravaApi
from strava.choices import SportType
from strava.querysets import ActivityQuerySet


class Activity(models.Model):
  name = models.CharField(_("name"), max_length=100)
  start_date = models.DateTimeField(_("start date"))
  sport_type = models.CharField(_("sport type"), max_length=29, choices=SportType.choices)
  distance = models.DecimalField(_("distance"), max_digits=12, decimal_places=2)
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
    return {
      # 'id': json['id'],
      'name': json['name'],
      'gear_id': json['gear_id'],
      'sport_type': json['sport_type'],
      'distance': json['distance'],
      'start_date': datetime.fromisoformat(json['start_date'])
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
    StravaApi().update_activity(id=self.id, gear_id=self.gear_id)
    self.json['gear_id'] = self.gear_id
    self.save(update_fields=["json"])
    self.update_from_json()

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


class Gear(models.Model):
  id = models.CharField(max_length=36, primary_key=True, editable=False)  # default=uuid.uuid4
  primary = models.BooleanField(_("primary"), default=False)
  brand_name = models.CharField(_("brand name"), max_length=30)
  model_name = models.CharField(_("model name"), max_length=50)
  description = models.CharField(_("description"), max_length=100)
  json = models.JSONField()

  def __str__(self):
      return f'{self.brand_name} {self.model_name}'

  @property
  def distance(self):
      return self.activity_set.aggregate(models.Sum('distance'))['distance__sum']

  @property
  def is_old(self):
    # TODO: check gear type (shoes only)
    return self.distance > 400

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
      'description': json['description'] or ''
    }

  def update_from_json(self):
    for attr, value in Gear.read_json(self.json).items():
      setattr(self, attr, value)
    self.save()
