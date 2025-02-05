from datetime import datetime

from django.db import models
from django.utils.translation import gettext_lazy as _

from strava.api import StravaApi
from strava.choices import SportType
from strava.querysets import ActivityQuerySet

# {
#   "resource_state" : 2,
#   "athlete" : {
#     "id" : 134815,
#     "resource_state" : 1
#   },
#   "name" : "Happy Friday",
#   "distance" : 24931.4,
#   "moving_time" : 4500,
#   "elapsed_time" : 4500,
#   "total_elevation_gain" : 0,
#   "type" : "Ride",
#   "sport_type" : "MountainBikeRide",
#   "workout_type" : null,
#   "id" : 154504250376823,
#   "external_id" : "garmin_push_12345678987654321",
#   "upload_id" : 987654321234567891234,
#   "start_date" : "2018-05-02T12:15:09Z",
#   "start_date_local" : "2018-05-02T05:15:09Z",
#   "timezone" : "(GMT-08:00) America/Los_Angeles",
#   "utc_offset" : -25200,
#   "start_latlng" : null,
#   "end_latlng" : null,
#   "location_city" : null,
#   "location_state" : null,
#   "location_country" : "United States",
#   "achievement_count" : 0,
#   "kudos_count" : 3,
#   "comment_count" : 1,
#   "athlete_count" : 1,
#   "photo_count" : 0,
#   "map" : {
#     "id" : "a12345678987654321",
#     "summary_polyline" : null,
#     "resource_state" : 2
#   },
#   "trainer" : true,
#   "commute" : false,
#   "manual" : false,
#   "private" : false,
#   "flagged" : false,
#   "gear_id" : "b12345678987654321",
#   "from_accepted_tag" : false,
#   "average_speed" : 5.54,
#   "max_speed" : 11,
#   "average_cadence" : 67.1,
#   "average_watts" : 175.3,
#   "weighted_average_watts" : 210,
#   "kilojoules" : 788.7,
#   "device_watts" : true,
#   "has_heartrate" : true,
#   "average_heartrate" : 140.3,
#   "max_heartrate" : 178,
#   "max_watts" : 406,
#   "pr_count" : 0,
#   "total_photo_count" : 1,
#   "has_kudoed" : false,
#   "suffer_score" : 82
# }
class Activity(models.Model):
  name = models.CharField(_("name"), max_length=100)
  start_date = models.DateTimeField(_("start date"))
  sport_type = models.CharField(_("sport type"), max_length=29, choices=SportType.choices)
  gear = models.ForeignKey("Gear", on_delete=models.SET_NULL,
                           blank=True, null=True, default=None)
  json = models.JSONField()
  objects = ActivityQuerySet.as_manager()

  class Meta:
    verbose_name = _("activity")
    verbose_name_plural = _("activities")

  def __str__(self):
      return self.name

  @classmethod
  def read_json(cls, json):
    return {
      # 'id': json['id'],
      'name': json['name'],
      'gear_id': json['gear_id'],
      'sport_type': json['sport_type'],
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

# {
#   "id" : "b1231",
#   "primary" : false,
#   "resource_state" : 3,
#   "distance" : 388206,
#   "brand_name" : "BMC",
#   "model_name" : "Teammachine",
#   "frame_type" : 3,
#   "description" : "My Bike."
# }
class Gear(models.Model):
  id = models.CharField(max_length=36, primary_key=True, editable=False)  # default=uuid.uuid4
  primary = models.BooleanField(_("primary"), default=False)
  brand_name = models.CharField(_("brand name"), max_length=30)
  model_name = models.CharField(_("brand name"), max_length=50)
  description = models.CharField(_("description"), max_length=100)
  json = models.JSONField()

  def __str__(self):
      return f'{self.brand_name} {self.model_name}'

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
