"""Service layer: pure computation over ``Activity``/``Gear`` collections.

Views stay thin orchestrators (gather request params, fetch, hand off, assign context);
all the arithmetic lives here so it's framework-light and unit-testable in isolation.
"""
from strava.services import activities, analytics, compare, dashboard, gear

__all__ = ["activities", "analytics", "compare", "dashboard", "gear"]
