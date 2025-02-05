import logging

import json
import environ

from stravalib import Client

logger = logging.getLogger("file")

env = environ.Env()

STRAVA_CLIENT_ID = env("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = env("STRAVA_CLIENT_SECRET")
STRAVA_ACCESS_TOKEN = env("STRAVA_ACCESS_TOKEN")
STRAVA_REFRESH_TOKEN = env("STRAVA_REFRESH_TOKEN")


# http://www.strava.com/oauth/authorize?client_id=53638&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=activity:read_all,activity:write
# b4158592b5328be0e13c21cd110e3d3b5c31b3b8

# curl -X POST https://www.strava.com/oauth/token \
# -F client_id=53638 \
# -F client_secret=3510266207a6f727cf600cfe6dfb7a56157d4eaf \
# -F code=837ae937cf27f744344490b528878cb6c02bd215 \
# -F grant_type=authorization_code

class StravaApi:
  def __init__(self):
    self.client = Client(access_token=STRAVA_ACCESS_TOKEN)

  def get_gear(self, id):
    data = json.loads(self.client.get_gear(id).model_dump_json())
    logger.info(self.get_formatted_json(data))
    return data

  def get_activity(self, id):
    data = json.loads(self.client.get_activity(id).model_dump_json())
    logger.info(self.get_formatted_json(data))
    return data

  def get_activities(self):
    activities = []
    for activity in self.client.get_activities():
      activities.append(json.loads(activity.model_dump_json()))
    logger.info(self.get_formatted_json(activities))
    return activities

  def update_activity(self, id, **kwargs):
    logger.info(f'Updating activity: {id}: {kwargs}')
    self.client.update_activity(activity_id=id, **kwargs)

  def get_formatted_json(self, data):
    if isinstance(data, str):
      data = json.loads(data)
    return json.dumps(data, indent=4, ensure_ascii=False)

  def refresh_token(self):
    client = Client()
    token_response = client.refresh_access_token(
      client_id=STRAVA_CLIENT_ID,
      client_secret=STRAVA_CLIENT_SECRET,
      refresh_token=STRAVA_REFRESH_TOKEN,
    )
    new_access_token = token_response["access_token"]

  def read_athlete(self):
    return self.get_formatted_json(self.client.get_athlete().model_dump_json())
