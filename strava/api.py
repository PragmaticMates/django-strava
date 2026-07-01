import functools
import json
import logging
import time
from datetime import datetime, timezone
from django.conf import settings

from stravalib import Client, exc
from stravalib.util.limiter import (
  DefaultRateLimiter,
  get_seconds_until_next_day,
  get_seconds_until_next_quarter,
  get_rates_from_response_headers,
)

logger = logging.getLogger("file")

STRAVA_CLIENT_ID = getattr(settings, "STRAVA_CLIENT_ID", None)
STRAVA_CLIENT_SECRET = getattr(settings, "STRAVA_CLIENT_SECRET", None)
STRAVA_ACCESS_TOKEN = getattr(settings, "STRAVA_ACCESS_TOKEN", None)
STRAVA_REFRESH_TOKEN = getattr(settings, "STRAVA_REFRESH_TOKEN", None)
STRAVA_TOKEN_EXPIRES = getattr(settings, "STRAVA_TOKEN_EXPIRES", None)

# How aggressively to space out requests to stay within Strava's limits
# (https://developers.strava.com/docs/rate-limits/):
#   "high"   - no proactive throttling (burst until a limit is hit)
#   "medium" - spread requests so the short-term (15 min) limit is not exceeded
#   "low"    - spread requests so the daily limit is not exceeded
STRAVA_RATE_LIMIT_PRIORITY = getattr(settings, "STRAVA_RATE_LIMIT_PRIORITY", "medium")

# How many times to retry a request after hitting a 429 (rate limit exceeded)
# before giving up. Each retry waits until the relevant limit window resets.
STRAVA_RATE_LIMIT_MAX_RETRIES = getattr(settings, "STRAVA_RATE_LIMIT_MAX_RETRIES", 3)


def rate_limited(func):
  """Retry a Strava API call when the rate limit is exceeded.

  stravalib's limiter proactively spaces requests, but a 429 can still
  happen (e.g. the quota was consumed by another process). When it does,
  sleep until the offending limit window resets and retry, rather than
  letting the import fail.
  """

  @functools.wraps(func)
  def wrapper(*args, **kwargs):
    for attempt in range(STRAVA_RATE_LIMIT_MAX_RETRIES + 1):
      try:
        return func(*args, **kwargs)
      except (exc.RateLimitExceeded, exc.Fault) as e:
        response = getattr(e, "response", None)
        status_code = getattr(response, "status_code", None)
        is_rate_limit = isinstance(e, exc.RateLimitExceeded) or status_code == 429
        if not is_rate_limit or attempt >= STRAVA_RATE_LIMIT_MAX_RETRIES:
          raise

        wait = _seconds_until_limit_resets(response)
        logger.warning(
          f"Strava rate limit exceeded on {func.__name__}; "
          f"sleeping {wait}s before retry {attempt + 1}/{STRAVA_RATE_LIMIT_MAX_RETRIES}"
        )
        time.sleep(wait)

  return wrapper


def _seconds_until_limit_resets(response):
  """Seconds to wait before retrying after a 429, based on which limit was hit.

  Prefers the response's rate-limit headers to decide whether the short-term
  (15 min) or the daily limit was exceeded; falls back to the short-term
  window when headers are unavailable.
  """
  headers = getattr(response, "headers", None) or {}
  rates = get_rates_from_response_headers(headers, "GET")
  if rates and rates.long_usage >= rates.long_limit:
    return get_seconds_until_next_day()
  return get_seconds_until_next_quarter()


def format_strava_error(error):
  """Human-readable summary of a Strava API failure.

  Pulls the status code, message and per-field errors out of a stravalib
  ``Fault``'s response body — e.g. a 403 with
  ``{"message": "Forbidden", "errors": [{"resource": "Application",
  "field": "Status", "code": "Inactive"}]}`` becomes
  "Forbidden — Application Status: Inactive (HTTP 403)". Falls back to the
  exception text for non-API errors (network failures, timeouts).
  """
  response = getattr(error, "response", None)
  status_code = getattr(response, "status_code", None)

  payload = {}
  if response is not None:
    try:
      payload = response.json()
    except (ValueError, AttributeError):
      payload = {}

  message = payload.get("message")
  details = ", ".join(
    " ".join(filter(None, (e.get("resource"), e.get("field")))) + f": {e.get('code')}"
    for e in (payload.get("errors") or [])
    if isinstance(e, dict) and e.get("code")
  )

  summary = " — ".join(part for part in (message, details) if part) or str(error)
  if status_code:
    summary = f"{summary} (HTTP {status_code})"
  return summary


class StravaApi:
  def __init__(self):
    self.client = Client(
      access_token=STRAVA_ACCESS_TOKEN,
      refresh_token=STRAVA_REFRESH_TOKEN,
      token_expires=self.get_token_expiration(),
      rate_limiter=DefaultRateLimiter(priority=STRAVA_RATE_LIMIT_PRIORITY),
    )

  def get_token_expiration(self):
    try:
      token_expires = datetime.strptime(STRAVA_TOKEN_EXPIRES, "%Y-%m-%dT%H:%M:%SZ")
      token_expires = token_expires.replace(tzinfo=timezone.utc)
      token_expires = token_expires.timestamp()
      return int(token_expires)
    except TypeError:
      return None

  @rate_limited
  def get_gear(self, id):
    data = json.loads(self.client.get_gear(id).model_dump_json())
    logger.info(self.get_formatted_json(data))
    return data

  @rate_limited
  def get_activity(self, id):
    data = json.loads(self.client.get_activity(id).model_dump_json())
    logger.info(self.get_formatted_json(data))
    return data

  @rate_limited
  def get_activities(self, after=None):
    activities = []

    for activity in self.client.get_activities(after=after):
      activities.append(json.loads(activity.model_dump_json()))
    logger.info(self.get_formatted_json(activities))
    return activities

  @rate_limited
  def update_activity(self, id, **kwargs):
    logger.info(f'Updating activity: {id}: {kwargs}')
    self.client.update_activity(activity_id=id, **kwargs)

  def get_formatted_json(self, data):
    if isinstance(data, str):
      data = json.loads(data)
    return json.dumps(data, indent=4, ensure_ascii=False)

  def refresh_access_token(self):
    token_response = self.client.refresh_access_token(
      client_id=STRAVA_CLIENT_ID,
      client_secret=STRAVA_CLIENT_SECRET,
      refresh_token=STRAVA_REFRESH_TOKEN,
    )
    return token_response["access_token"]

  def read_athlete(self):
    return self.get_formatted_json(self.client.get_athlete().model_dump_json())
