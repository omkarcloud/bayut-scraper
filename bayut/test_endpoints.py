"""Live endpoint smoke tests: one call per /bayut/* route against a running
service, with example values proven to return data (2026-11-07, through the
local route layer on a UAE residential exit). The listing tooling reads these
calls as each route's working example.

Skipped unless BAYUT_BASE points at a running service:

    ONLY_SCRAPER=bayut python run.py --dev        # needs a UAE residential exit
    BAYUT_BASE=http://127.0.0.1:6002 python -m pytest bayut/test_endpoints.py -q
"""
import os

import pytest

BASE = os.environ.get("BAYUT_BASE", "").rstrip("/")

pytestmark = pytest.mark.skipif(not BASE, reason="set BAYUT_BASE to run live endpoint tests")


def call(path, status=200, **params):
    from curl_cffi import requests
    resp = requests.get(BASE + path, params=params, timeout=300)
    assert resp.status_code == status, f"{path} {params} -> {resp.status_code} {resp.text[:300]}"
    body = resp.json()
    assert body, f"{path} returned an empty body"
    return body


# ---- properties ------------------------------------------------------------------------

def test_property_details():
    # a 3-bedroom in Burj Khalifa
    home = call("/bayut/properties/details", property="15783263")
    assert home["id"] == 15783263 and home["location"]["building"] == "Burj Khalifa"
    assert home["price"]["amount"] and home["photos"]["count"] and home["description"]
    assert home["amenities"] and home["agent"]["email"]
    link = call("/bayut/properties/details", property="https://www.bayut.com/property/details-15783263.html")
    assert link["id"] == 15783263
    call("/bayut/properties/details", status=404, property="1")


def test_locations_autocomplete():
    body = call("/bayut/locations/autocomplete", query="palm")
    assert body["results"][0]["name"] == "Palm Jumeirah" and body["results"][0]["id"] == 5460


def test_properties_search():
    body = call("/bayut/properties/search", location="Palm Jumeirah", purpose="for-sale", category="villas",
                limit="5")
    assert body["count"] > 50 and len(body["results"]) == 5 and body["next"]
    assert all(r["location"]["community"] == "Palm Jumeirah" for r in body["results"])
    linked = call("/bayut/properties/search",
                  location="https://www.bayut.com/to-rent/apartments/dubai/dubai-marina/?beds_in=2", limit="3")
    assert linked["purpose"] == "for-rent" and all(r["bedrooms"] == 2 for r in linked["results"])
    call("/bayut/properties/search", status=404, location="Zzqxv Nowhere")


# ---- agents ----------------------------------------------------------------------------

def test_agents_search():
    body = call("/bayut/agents/search", location="Downtown Dubai", trubroker_only="true", limit="5")
    assert body["count"] > 100 and all(r["is_trubroker"] for r in body["results"])


def test_agent_details():
    agent = call("/bayut/agents/details", agent="2512279")
    assert agent["name"] == "Jean Selwan" and agent["agency"]["name"] == "fäm Properties"
    assert agent["email"] and agent["phone"] and agent["brn_number"]
    call("/bayut/agents/details", status=404, agent="999999999")


def test_agent_listings():
    body = call("/bayut/agents/listings", agent="2512279", limit="3")
    assert body["count"] > 10 and body["results"][0]["agent"]["id"] == 2512279


# ---- agencies --------------------------------------------------------------------------

def test_agencies_search():
    body = call("/bayut/agencies/search", query="sotheby")
    assert body["results"][0]["name"] == "Dubai Sotheby's International Realty"


def test_agency_details():
    agency = call("/bayut/agencies/details", agency="5039")
    assert agency["name"] == "Dubai Sotheby's International Realty" and agency["description"]
    assert agency["licenses"] == [{"authority": "RERA", "number": "12521"}]
    call("/bayut/agencies/details", status=404, agency="999999999")


def test_agency_agents():
    body = call("/bayut/agencies/agents", agency="5039", limit="5")
    assert body["count"] > 10 and all(r["agency"]["id"] == 5039 for r in body["results"])


# ---- projects --------------------------------------------------------------------------

def test_projects_search():
    body = call("/bayut/projects/search", location="Dubai", query="binghatti", limit="5")
    assert body["count"] > 10 and all(r["developer"]["name"] == "Binghatti" for r in body["results"])


def test_project_details():
    tower = call("/bayut/projects/details", project="1067")
    assert tower["name"] == "Burj Binghatti Jacob & Co Residences" and tower["developer"]["name"] == "Binghatti"
    assert tower["starting_price"]["amount"] and tower["unit_bedrooms"]
    call("/bayut/projects/details", status=404, project="999999999")
