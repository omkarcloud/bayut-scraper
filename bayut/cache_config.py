"""Cache TTL per /bayut/* endpoint (cache.py, keyed on the validated
params). Bayut's search index is live (listings appear, reprice and expire
through the day), so searches cache briefly; profiles and places move slowly.
"""
from datetime import timedelta

# Listing searches: new listings land every few minutes, prices move daily.
SEARCH_CACHE = timedelta(minutes=15)
# One listing's page: a price edit or expiry should show within the hour.
DETAILS_CACHE = timedelta(hours=1)
# Agency / agent / project profiles: contacts and counts move slowly.
AGENCY_CACHE = timedelta(hours=6)
AGENT_CACHE = timedelta(hours=6)
PROJECT_CACHE = timedelta(hours=6)
# Directory searches (agencies, agents, projects): rosters change weekly.
DIRECTORY_CACHE = timedelta(hours=3)
# Place names and ids are static; the ad counts on them are decorative.
LOCATION_CACHE = timedelta(hours=24)
