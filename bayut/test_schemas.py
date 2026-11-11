"""Offline tests for the /bayut/* request schemas.

    python -m pytest bayut/test_schemas.py -q
"""
import os
import sys

import pytest
from marshmallow import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bayut import schemas  # noqa: E402


def load(schema, **query):
    return schema().load(query)


def rejects(schema, field, **query):
    with pytest.raises(ValidationError) as info:
        schema().load(query)
    assert field in info.value.normalized_messages(), info.value.normalized_messages()
    return info.value.normalized_messages()[field]


# ---- properties/search ---------------------------------------------------------------------------

def test_properties_search_defaults():
    data = load(schemas.PropertiesSearchSchema)
    assert data["location"] is None and data["purpose"] is None and data["category"] is None
    assert data["page"] == 1 and data["limit"] == 25 and data["language"] == "en"
    assert data["verified"] is None and data["sort"] is None


def test_properties_search_location_forms():
    assert load(schemas.PropertiesSearchSchema, location="5003")["location"] == {"external_id": "5003"}
    assert load(schemas.PropertiesSearchSchema, location="/dubai/dubai-marina")["location"] == {"slug": "/dubai/dubai-marina"}
    assert load(schemas.PropertiesSearchSchema, location="Dubai Marina")["location"] == {"name": "Dubai Marina"}
    data = load(schemas.PropertiesSearchSchema,
                location="https://www.bayut.com/to-rent/apartments/dubai/?price_max=100000&rent_frequency=yearly")
    assert data["location"]["purpose"] == "for-rent"
    assert data["location"]["filters"] == {"price_max": 100000.0, "rent_frequency": "yearly"}


def test_properties_search_filters_and_choices():
    data = load(schemas.PropertiesSearchSchema, purpose="For-Rent", category="Apartments", price_min="50000",
                price_max="120000", beds_min="0", beds_max="2", baths_min="1", area_min="500", area_max="1500",
                rent_frequency="yearly", completion_status="completed", furnishing="furnished", verified="yes",
                has_video="1", has_360_tour="false", has_floor_plan="true", sort="Price_Asc", language="AR",
                page="2", limit="50", posted_within_days="7")
    assert data["purpose"] == "for-rent" and data["category"] == "apartments"
    assert data["price_min"] == 50000.0 and data["beds_min"] == 0 and data["beds_max"] == 2
    assert data["area_min"] == 500.0 and data["rent_frequency"] == "yearly"
    assert data["verified"] is True and data["has_video"] is True and data["has_360_tour"] is False
    assert data["sort"] == "price_asc" and data["language"] == "ar" and data["limit"] == 50
    assert data["posted_within_days"] == 7


def test_properties_search_record_filters():
    data = load(schemas.PropertiesSearchSchema, agency="https://www.bayut.com/companies/white-co-10212/",
                agent="tony-yannieh-2401468")
    assert data["agency"] == {"id": "10212", "slug": "white-co-10212"} and data["agent"] == "2401468"


def test_properties_search_radius():
    data = load(schemas.PropertiesSearchSchema, latitude="25.08", longitude="55.14", radius_km="2")
    assert data["radius_km"] == 2.0
    messages = rejects(schemas.PropertiesSearchSchema, "radius_km", latitude="25.08", longitude="55.14")
    assert "go together" in messages[0]
    rejects(schemas.PropertiesSearchSchema, "radius_km", latitude="25.08", longitude="55.14", radius_km="500")
    rejects(schemas.PropertiesSearchSchema, "latitude", latitude="95", longitude="55.14", radius_km="2")


def test_properties_search_rejections():
    assert rejects(schemas.PropertiesSearchSchema, "category", category="castles")[0].startswith("Must be one of")
    rejects(schemas.PropertiesSearchSchema, "purpose", purpose="buy")
    rejects(schemas.PropertiesSearchSchema, "price_max", price_min="100", price_max="50")
    rejects(schemas.PropertiesSearchSchema, "beds_max", beds_min="3", beds_max="1")
    rejects(schemas.PropertiesSearchSchema, "rent_frequency", purpose="for-sale", rent_frequency="yearly")
    rejects(schemas.PropertiesSearchSchema, "verified", verified="maybe")
    rejects(schemas.PropertiesSearchSchema, "limit", limit="51")
    rejects(schemas.PropertiesSearchSchema, "page", page="0")
    rejects(schemas.PropertiesSearchSchema, "language", language="jp")
    rejects(schemas.PropertiesSearchSchema, "posted_within_days", posted_within_days="400")
    rejects(schemas.PropertiesSearchSchema, "location", location="https://propertyfinder.ae/x")
    rejects(schemas.PropertiesSearchSchema, "url", url="https://www.bayut.com/for-sale/apartments/dubai/")


# ---- properties/details --------------------------------------------------------------------------

def test_property_schema():
    assert load(schemas.PropertySchema, property="17117341") == {"property": "17117341", "language": "en"}
    assert load(schemas.PropertySchema, property="https://www.bayut.com/property/details-17117341.html",
                language="ru")["property"] == "17117341"
    rejects(schemas.PropertySchema, "property")
    assert "listing id" in rejects(schemas.PropertySchema, "property", property="dubai marina")[0]
    rejects(schemas.PropertySchema, "id", property="17117341", id="17117341")


# ---- agencies ---------------------------------------------------------------------------------------

def test_agencies_search_schema():
    data = load(schemas.AgenciesSearchSchema)
    assert data["type"] == "agency" and data["query"] is None and data["location"] is None
    data = load(schemas.AgenciesSearchSchema, query=" white ", location="Dubai", type="Developer", page="3")
    assert data["query"] == "white" and data["location"] == {"name": "Dubai"} and data["type"] == "developer"
    rejects(schemas.AgenciesSearchSchema, "type", type="bank")
    rejects(schemas.AgenciesSearchSchema, "location", location="https://www.bayut.com/new-projects/developers/emaar/")


def test_agency_schema():
    assert load(schemas.AgencySchema, agency="102520")["agency"] == {"id": "102520"}
    assert load(schemas.AgencySchema, agency="merath-development")["agency"] == {"slug": "merath-development"}
    assert load(schemas.AgencyAgentsSchema, agency="k-u-n-real-estate-102520", limit="5") == {
        "agency": {"id": "102520", "slug": "k-u-n-real-estate-102520"}, "language": "en", "page": 1, "limit": 5}
    assert "agency id" in rejects(schemas.AgencySchema, "agency", agency="K U N Real Estate")[0]
    rejects(schemas.AgencySchema, "agency")


# ---- agents ----------------------------------------------------------------------------------------

def test_agents_search_schema():
    data = load(schemas.AgentsSearchSchema, query="ahmed", emirate="abu dhabi", speaks="EN, ru,en",
                trubroker_only="true", location="5003")
    assert data["emirate"] == "abu dhabi" and data["trubroker_only"] is True
    assert sorted({c.lower() for c in data["speaks"]}) == ["en", "ru"]   # api.py lower-cases and dedupes
    assert data["location"] == {"external_id": "5003"}
    rejects(schemas.AgentsSearchSchema, "emirate", emirate="riyadh")
    rejects(schemas.AgentsSearchSchema, "speaks", speaks="a,b,c,d,e,f")


def test_agent_schemas():
    assert load(schemas.AgentSchema, agent="https://www.bayut.com/brokers/tony-yannieh-2401468/") == {
        "agent": "2401468", "language": "en"}
    data = load(schemas.AgentListingsSchema, agent="2401468", purpose="for-rent", sort="newest")
    assert data["purpose"] == "for-rent" and data["sort"] == "newest" and data["page"] == 1
    assert "agent id" in rejects(schemas.AgentSchema, "agent", agent="tony")[0]
    rejects(schemas.AgentListingsSchema, "sort", agent="2401468", sort="cheapest")


# ---- projects ----------------------------------------------------------------------------------------

def test_projects_schemas():
    data = load(schemas.ProjectsSearchSchema, location="/dubai", developer="emaar-properties",
                completion_status="under-construction", query="binghatti")
    assert data["location"] == {"slug": "/dubai"} and data["developer"] == {"slug": "emaar-properties"}
    assert load(schemas.ProjectSchema, project="2749")["project"] == {"id": "2749"}
    assert load(schemas.ProjectSchema, project="https://www.bayut.com/new-projects/dubai/motor-city/beverly-grande/")[
        "project"] == {"location_slug": "/dubai/motor-city/beverly-grande"}
    assert "project id" in rejects(schemas.ProjectSchema, "project", project="beverly grande")[0]
    rejects(schemas.ProjectsSearchSchema, "completion_status", completion_status="ready")


def test_project_link_matches_only_its_own_project():
    # a place link (/new-projects/dubai/dubai-hills-estate/) must not resolve
    # to some project inside that place: the leaf has nothing one level below
    from bayut import api
    assert api.project_lookup_filter({"id": "2749"}) == "externalID:2749"
    assert api.project_lookup_filter({"location_slug": "/dubai/motor-city/beverly-grande"}) == \
        'location.slug:"/dubai/motor-city/beverly-grande" AND NOT location.level:4'
    assert api.project_lookup_filter({"location_slug": "/dubai/tilal-binghatti"}) == \
        'location.slug:"/dubai/tilal-binghatti" AND NOT location.level:3'


# ---- locations ---------------------------------------------------------------------------------------

def test_locations_autocomplete_schema():
    assert load(schemas.LocationsAutocompleteSchema, query="marina") == {
        "query": "marina", "type": None, "language": "en", "limit": 10}
    assert load(schemas.LocationsAutocompleteSchema, query="marina", type="Condo-Building", limit="50")["type"] == \
        "condo-building"
    rejects(schemas.LocationsAutocompleteSchema, "query")
    rejects(schemas.LocationsAutocompleteSchema, "type", query="x", type="street")
    rejects(schemas.LocationsAutocompleteSchema, "limit", query="x", limit="51")


def test_filter_numbers_never_use_scientific_notation():
    from bayut import api
    assert api._num(1000000.0) == "1000000"
    assert api._num(2.5) == "2.5"
    assert api._num(92.903040) == "92.903"
    filters = api._listing_filters("for-sale", "apartments", {"externalID": "5002"}, 1000000.0, 5e6, 2, 2, None,
                                   None, 1000.0, None, None, None, None, None, True, None, None, None, None, None,
                                   None)
    assert filters == ("purpose:for-sale AND category.slug:apartments AND location.externalID:5002 AND "
                       "price>=1000000 AND price<=5000000 AND rooms>=2 AND rooms<=2 AND area>=92.903 AND "
                       "isVerified:true")
