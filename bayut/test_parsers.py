"""Offline tests for the Bayut parsers and reference resolvers.

    python -m pytest bayut/test_parsers.py -q

Fixtures are real www.bayut.com answers captured 2026-11-07 through a UAE
residential exit (bayut/fixtures/): Algolia hits of the ads / project /
agency / agent / location indexes (happy path + empty answers) and the
server-rendered listing, agency and broker pages (plus their "Not found"
pages). No network.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bayut import parsers as P, refs  # noqa: E402

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f) if name.endswith(".json") else f.read()


def hits(name):
    return fixture(name)["hits"]


# ---- refs: record resolvers ------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("17117341", "17117341"),
    (" 17117341 ", "17117341"),
    ("details_17117341", "17117341"),
    ("priced-to-sell-rare-fully-upgraded-home-vot-16786646", "16786646"),
    ("https://www.bayut.com/property/details-17117341.html", "17117341"),
    ("https://www.bayut.com/ar/property/details-17117341.html?x=1", "17117341"),
    ("//bayut.com/property/details-7435290.html", "7435290"),
])
def test_resolve_property(value, expected):
    assert refs.resolve_property(value) == expected


@pytest.mark.parametrize("value", [
    "", "dubai marina", "https://example.com/property/details-17117341.html",
    "https://www.bayut.com/companies/k-u-n-real-estate-102520/",
])
def test_resolve_property_invalid(value):
    with pytest.raises(ValueError):
        refs.resolve_property(value)


@pytest.mark.parametrize("value,expected", [
    ("102520", {"id": "102520"}),
    ("k-u-n-real-estate-102520", {"id": "102520", "slug": "k-u-n-real-estate-102520"}),
    ("merath-development", {"slug": "merath-development"}),
    ("https://www.bayut.com/companies/k-u-n-real-estate-102520/", {"id": "102520", "slug": "k-u-n-real-estate-102520"}),
    ("https://www.bayut.com/ar/companies/white-co-10212/?page=2", {"id": "10212", "slug": "white-co-10212"}),
])
def test_resolve_agency(value, expected):
    assert refs.resolve_agency(value) == expected


@pytest.mark.parametrize("value", ["", "K U N", "https://www.bayut.com/brokers/tony-yannieh-2401468/",
                                   "https://zillow.com/companies/x-1/"])
def test_resolve_agency_invalid(value):
    with pytest.raises(ValueError):
        refs.resolve_agency(value)


@pytest.mark.parametrize("value,expected", [
    ("2401468", "2401468"),
    ("tony-yannieh-2401468", "2401468"),
    ("https://www.bayut.com/brokers/tony-yannieh-2401468/", "2401468"),
    ("https://www.bayut.com/ru/brokers/tony-yannieh-2401468/?utm=x", "2401468"),
])
def test_resolve_agent(value, expected):
    assert refs.resolve_agent(value) == expected


@pytest.mark.parametrize("value", ["", "tony yannieh", "tony-yannieh", "https://www.bayut.com/companies/x-1/"])
def test_resolve_agent_invalid(value):
    with pytest.raises(ValueError):
        refs.resolve_agent(value)


@pytest.mark.parametrize("value,expected", [
    ("2749", {"id": "2749"}),
    ("beverly_grande-2749", {"id": "2749"}),
    ("https://www.bayut.com/new-projects/dubai/motor-city/beverly-grande/",
     {"location_slug": "/dubai/motor-city/beverly-grande"}),
    ("https://www.bayut.com/ar/new-projects/dubai/motor-city/beverly-grande",
     {"location_slug": "/dubai/motor-city/beverly-grande"}),
])
def test_resolve_project(value, expected):
    assert refs.resolve_project(value) == expected


@pytest.mark.parametrize("value", ["", "beverly grande", "https://www.bayut.com/new-projects/developers/emaar/",
                                   "https://www.bayut.com/for-sale/apartments/dubai/"])
def test_resolve_project_invalid(value):
    with pytest.raises(ValueError):
        refs.resolve_project(value)


# ---- refs: locations and search links --------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("5003", {"external_id": "5003"}),
    ("/dubai/dubai-marina", {"slug": "/dubai/dubai-marina"}),
    ("dubai/Dubai-Marina/", {"slug": "/dubai/dubai-marina"}),
    ("Dubai Marina", {"name": "Dubai Marina"}),
    ("jvc", {"name": "jvc"}),
])
def test_resolve_search_location_plain(value, expected):
    assert refs.resolve_search_location(value) == expected


def test_resolve_search_location_link_carries_filters():
    ref = refs.resolve_search_location(
        "https://www.bayut.com/ar/to-rent/apartments/dubai/dubai-marina/"
        "?price_min=50000&price_max=120000&beds_in=1,2&baths_in=2&rent_frequency=yearly"
        "&furnishing_status=furnished&sort=date_desc&page=3&is_verified=true")
    assert ref["slug"] == "/dubai/dubai-marina"
    assert ref["purpose"] == "for-rent"
    assert ref["category"] == "apartments"
    assert ref["filters"] == {
        "price_min": 50000.0, "price_max": 120000.0, "beds_min": 1, "beds_max": 2, "baths_min": 2,
        "baths_max": 2, "rent_frequency": "yearly", "furnishing": "furnished", "sort": "newest",
        "page": 3, "verified": True}


def test_resolve_search_location_link_shapes():
    ref = refs.resolve_search_location("https://www.bayut.com/for-sale/property/dubai/")
    assert ref == {"slug": "/dubai", "purpose": "for-sale", "category": "residential", "filters": {}}
    ref = refs.resolve_search_location("https://www.bayut.com/for-sale/off-plan/apartments/dubai/")
    assert ref["filters"] == {"completion_status": "under-construction"}
    ref = refs.resolve_search_location("https://www.bayut.com/for-sale/2-bedroom-apartments/dubai/motor-city/")
    assert ref["category"] == "apartments" and ref["filters"] == {"beds_min": 2, "beds_max": 2}
    ref = refs.resolve_search_location("https://www.bayut.com/to-rent/villas/")
    assert ref["slug"] is None and ref["purpose"] == "for-rent"


@pytest.mark.parametrize("value", ["", "https://www.bayut.com/companies/", "https://www.bayut.com/for-sale/",
                                   "https://www.bayut.com/for-sale/castles/dubai/",
                                   "https://propertyfinder.ae/for-sale/apartments/dubai/"])
def test_resolve_search_location_invalid(value):
    with pytest.raises(ValueError):
        refs.resolve_search_location(value)


def test_resolve_location_ref_links():
    assert refs.resolve_location_ref("https://www.bayut.com/companies/dubai/") == {"slug": "/dubai"}
    assert refs.resolve_location_ref("https://www.bayut.com/brokers/uae/") == {"slug": "/uae"}
    assert refs.resolve_location_ref("https://www.bayut.com/new-projects/dubai/motor-city/") == {"slug": "/dubai/motor-city"}
    assert refs.resolve_location_ref("https://www.bayut.com/for-sale/apartments/dubai/jvc/") == {"slug": "/dubai/jvc"}
    with pytest.raises(ValueError):
        refs.resolve_location_ref("https://www.bayut.com/new-projects/developers/emaar/")


def test_links():
    assert refs.property_link("17117341") == "https://www.bayut.com/property/details-17117341.html"
    assert refs.property_link("17117341", "ar") == "https://www.bayut.com/ar/property/details-17117341.html"
    assert refs.agency_link("white-co-10212") == "https://www.bayut.com/companies/white-co-10212/"
    assert refs.agent_link("tony-yannieh-2401468", "ru") == "https://www.bayut.com/ru/brokers/tony-yannieh-2401468/"
    assert refs.project_link("/dubai/motor-city/beverly-grande") == \
        "https://www.bayut.com/new-projects/dubai/motor-city/beverly-grande/"
    assert refs.location_search_link("/dubai/dubai-marina", "for-rent", "apartments") == \
        "https://www.bayut.com/to-rent/apartments/dubai/dubai-marina/"
    assert refs.location_search_link("/dubai", "for-sale", None) == "https://www.bayut.com/for-sale/property/dubai/"


def test_area_conversion():
    assert refs.sqm_to_sqft(100) == 1076.39
    assert round(refs.sqft_to_sqm(1076.39), 2) == 100.0


# ---- listing cards -----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sale_card():
    return P.listing_card(hits("search_sale_apartments_dubai_marina.json")[0])


def test_listing_card_identity_and_price(sale_card):
    c = sale_card
    assert c["id"] == 16786646
    assert c["link"] == "https://www.bayut.com/property/details-16786646.html"
    assert c["title"].startswith("Priced to Sell")
    assert c["purpose"] == "for-sale" and c["status"] == "active"
    assert c["reference_number"] == "ADM266096"
    assert c["price"] == {"amount": 3292000.0, "currency": "AED", "period": None, "is_hidden": False}
    assert c["bedrooms"] == 2 and c["bathrooms"] == 3
    assert c["area"] == {"sqm": 143.07, "sqft": 1540.0}
    assert c["plot_area"] is None


def test_listing_card_location_and_category(sale_card):
    loc = sale_card["location"]
    assert loc["name"] == "DAMAC Heights" and loc["type"] == "condo-building"
    assert loc["city"] == "Dubai" and loc["community"] == "Dubai Marina" and loc["building"] == "DAMAC Heights"
    assert loc["link"] == "https://www.bayut.com/for-sale/apartments/dubai/dubai-marina/damac-heights/"
    assert [n["id"] for n in loc["hierarchy"]] == [5001, 5002, 5003, 8775]
    assert sale_card["category"] == {"id": 4, "name": "Apartments", "name_singular": "Apartment",
                                     "slug": "apartments", "group": "Residential", "group_slug": "residential"}
    assert sale_card["coordinates"] == {"latitude": 25.087214, "longitude": 55.145463}


def test_listing_card_people_and_media(sale_card):
    c = sale_card
    assert c["agency"]["id"] == 6415 and c["agency"]["slug"] == "haus-haus-real-estate-6415"
    assert c["agency"]["link"] == "https://www.bayut.com/companies/haus-haus-real-estate-6415/"
    assert c["agency"]["logo"] == "https://images.bayut.com/thumbnails/27679864-400x300.jpeg"
    assert c["agent"]["id"] == 2287543 and c["agent"]["is_trubroker"] is True
    assert c["agent"]["link"] == "https://www.bayut.com/brokers/lewis-dady-2287543/"
    assert c["contact"]["name"] == "Lewis Dady"
    assert c["contact"]["phone"]["mobile"] == "+971585116264"
    assert c["contact"]["phone"]["whatsapp"] == "971545695868"
    assert c["contact"]["methods"] == {"call": True, "whatsapp": True, "sms": True, "email": True}
    assert c["photos"]["count"] == 23
    assert c["photos"]["cover"] == "https://images.bayut.com/thumbnails/871703250-800x600.jpeg"
    assert len(c["photos"]["links"]) == 23
    assert c["is_verified"] is True and c["verification"]["status"] == "verified"
    assert c["verification"]["verified_at"] == "2026-11-06T14:27:46Z"
    assert c["has_floor_plan"] is True and c["video_count"] == 0
    assert "marina view" in c["features"]
    assert c["furnishing"] == "furnished" and c["completion"]["status"] == "completed"
    assert c["has_sale_transactions"] is True and c["has_rent_transactions"] is True
    assert c["listing_tier"] == "superhot"
    assert c["created_at"] == "2026-10-08T11:56:56Z"
    assert c["updated_at"] == "2026-11-06T14:27:46Z"
    assert c["project"] is None


def test_listing_card_language():
    hit = hits("search_sale_apartments_dubai_marina.json")[0]
    ar = P.listing_card(hit, "ar")
    assert ar["title"].startswith("شقة")
    assert ar["location"]["name"] == "داماك هايتس"
    assert ar["link"] == "https://www.bayut.com/ar/property/details-16786646.html"
    # a rendering the hit does not carry falls back to English
    assert P.listing_card(hit, "nl")["location"]["name"] == "DAMAC Heights"


def test_listing_card_rental_and_sparse_fields():
    c = P.listing_card(hits("search_rent_dubai_newest.json")[0])
    assert c["purpose"] == "for-rent"
    assert c["price"]["period"] == "yearly" and c["price"]["amount"] == 185000.0
    assert c["category"]["slug"] == "villas"
    assert c["location"]["building"] is None and c["location"]["community"] == "Al Badaa"
    assert c["is_verified"] is False
    assert c["has_floor_plan"] is False and c["video_count"] == 0 and c["panorama_count"] == 0
    assert c["sale_type"] is None and c["has_sale_transactions"] is None


def test_listing_card_offplan_project():
    c = P.listing_card(hits("agent_listings_2401468.json")[0])
    assert c["completion"]["status"] == "under-construction"
    assert c["completion"]["completion_date"] is not None
    assert c["project"]["developer"]["type"] == "developer"
    assert c["payment_plan"]["down_payment_percentage"] is not None
    assert c["sale_type"] == "new"


def test_listing_card_never_crashes_on_partial_hits():
    assert P.listing_card({}) ["id"] is None
    assert P.listing_card({"externalID": "1", "location": "not json", "category": None, "agency": "x"})["id"] == 1
    assert P.listing_card(None) is None
    assert P.listing_card({"externalID": "5", "price": 0, "hidePrice": True})["price"]["amount"] is None


def test_empty_search_answer():
    answer = fixture("search_empty.json")
    assert answer["hits"] == []
    assert P.pagination(answer, 1, 3) == {"page": 1, "items_per_page": 3, "total_pages": 0, "total_count": 0}


def test_pagination_from_answer():
    assert P.pagination(fixture("search_sale_apartments_dubai_marina.json"), 2, 3) == \
        {"page": 2, "items_per_page": 3, "total_pages": 1192, "total_count": 3575}


# ---- listing page --------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def details():
    return P.listing_details(P.server_state(fixture("property_details_17117341.html")))


def test_server_state_reads_the_page():
    state = P.server_state(fixture("property_details_17117341.html"))
    assert state["router"]["routeName"] == "property"
    assert P.server_state("<html></html>") is None
    assert P.server_state("") is None


def test_listing_details_record(details):
    d = details
    assert d["id"] == 17117341
    assert d["title"].startswith("EXCLUSIVE INVESTOR OFFER")
    assert d["price"]["amount"] == 1135000.0
    assert d["completion"] == {"status": "under-construction", "start_date": None,
                               "completion_date": "2027-12-30", "completion_percentage": 2.0}
    assert d["sale_type"] == "new"
    assert d["offplan"]["sale_type"] == "new" and d["offplan"]["original_price"] is None
    assert d["description"].startswith("Beverly Grande | Elevated Luxury Living in Motor City")
    assert "<strong>" in d["description_html"]
    assert d["is_description_translated"] is False
    assert d["approved_at"] == "2026-11-06T12:35:40Z"


def test_listing_details_media_and_amenities(details):
    d = details
    assert d["photos"]["count"] == 23
    assert len(d["photos"]["items"]) == 23 and len(d["photos"]["links"]) == 23
    assert d["photos"]["items"][0] == {
        "id": 878270502, "link": "https://images.bayut.com/thumbnails/878270502-800x600.jpeg",
        "title": "1 Screenshot 2026-11-06 120735. png", "order": 0}
    assert d["floor_plans"] is None and d["panoramas"] is None and d["videos"] is None
    groups = {g["group"]: [a["slug"] for a in g["amenities"]] for g in d["amenities"]}
    assert groups["Features"] == ["furnished", "electricity-backup", "centrally-air-conditioned"]
    assert d["payment_plans"][0]["down_payment_percentage"] == 20.0
    assert d["payment_plans"][0]["pre_handover_installments"] == [{"description": "During Construction",
                                                                   "percentage": 40.0}]


def test_listing_details_agent_and_agency(details):
    agent = details["agent"]
    assert agent["id"] == 2211685 and agent["email"] == "arsalan@kun.ae"
    assert agent["phone"]["mobile"] == "+971585303096" and agent["phone"]["proxy_whatsapp"] == "+971545695868"
    assert agent["experience_years"] == 6 and agent["nationality"] == "Pakistan"
    assert agent["languages"] == ["English", "Urdu", "Arabic", "Hindi"]
    assert agent["service_areas"][0] == {"id": 14852, "name": "DAMAC Lagoons"}
    assert agent["agency"]["licenses"] == [{"authority": "RERA", "number": "30343"}]
    agency = details["agency"]
    assert agency["id"] == 102520 and agency["tier"] == "premium" and agency["created_at"] == "2023-05-08T11:13:36Z"


def test_listing_details_not_found_page():
    html = fixture("property_details_missing.html")
    assert P.page_title(html) == "Not found | bayut"
    assert P.listing_details(P.server_state(html)) is None


# ---- agencies -------------------------------------------------------------------------------------

def test_agency_record_from_index():
    a = P.agency_record(hits("agency_102520.json")[0])
    assert a["id"] == 102520 and a["name"] == "K U N Real Estate"
    assert a["link"] == "https://www.bayut.com/companies/k-u-n-real-estate-102520/"
    assert a["type"] == "agency" and a["description"] is None
    assert a["licenses"] == [{"authority": "RERA", "number": "30343"}]
    assert a["phone"]["mobile"] == "+971585039019"
    assert a["agents_count"] == 11 and a["trubroker_agents_count"] == 7
    assert a["listings"] == {"total": 202, "for_sale": 198, "for_rent": 4}
    assert "Apartments" in a["listing_categories"]
    assert a["service_areas_count"] == 44
    assert a["languages"][0] == "en" and "residential_sales" in a["specialities"]
    assert a["purposes"] == ["for-rent", "for-sale"]
    assert a["is_featured"] is False and a["is_elite"] is False and a["tier"] == "premium"
    assert a["created_at"] == "2023-05-08T11:13:36Z"
    assert a["locations"] == [{"id": 5002, "name": "Dubai", "slug": "/dubai", "level": 1, "type": None}]


def test_developer_record_from_index():
    a = P.agency_record(hits("agency_merath_development.json")[0], "ar")
    assert a["type"] == "developer" and a["link"] is None and a["slug"] == "merath-development"
    assert a["listings"]["for_sale"] == 4 and a["phone"] is None and a["licenses"] is None


def test_agencies_search_hits_parse():
    rows = [P.agency_record(h) for h in hits("agencies_search_white.json")]
    assert len(rows) == 3 and rows[0]["name"] == "White & Co" and rows[0]["agents_count"] == 462
    devs = [P.agency_record(h) for h in hits("agencies_search_developers.json")]
    assert all(d["type"] == "developer" for d in devs)


def test_agency_page():
    a = P.agency_page(P.server_state(fixture("agency_page_102520.html")))
    assert a["id"] == 102520
    assert a["description"].startswith("KUN is one of the Real Estate companies")
    assert a["listings"] == {"total": 202, "for_sale": 198, "for_rent": 4}
    assert a["agents_count"] == 9 and a["trubroker_agents_count"] == 7
    assert len(a["agents_preview"]) == 9
    assert a["agents_preview"][0]["email"] == "shahzaib.zuberi@kun.ae"
    assert a["languages"] == ["ar", "en", "hi", "mr", "pa", "ru", "uk", "ur", "ur-hi"]


def test_agency_page_not_found():
    html = fixture("agency_page_missing.html")
    assert P.page_title(html) == "Not found | bayut"
    assert P.agency_page(P.server_state(html)) is None
    assert fixture("agency_missing.json")["hits"] == []


# ---- agents ----------------------------------------------------------------------------------------

def test_agent_record_from_index():
    a = P.agent_record(hits("agent_2401468.json")[0])
    assert a["id"] == 2401468 and a["name"] == "Tony Yannieh"
    assert a["link"] == "https://www.bayut.com/brokers/tony-yannieh-2401468/"
    assert a["email"] == "tony.yannieh@firstandtop.ae"
    assert a["phone"]["mobile"] == "+971503385063" and a["phone"]["proxy_phone"] == "+97144483993"
    assert a["agency"]["id"] == 101720 and len(a["agency"]["licenses"]) == 4
    assert a["is_trubroker"] is True
    assert a["badges"] == {"is_highly_responsive": True, "is_quality_lister": True, "has_badges": True}
    assert a["experience_points"] == 8410 and a["active_emirate"] == "Dubai"
    assert a["languages"] == ["English", "Arabic", "French"] and a["language_codes"] == ["en", "ar", "fr"]
    assert a["listings"] == {"total": 43, "for_sale": 41, "for_rent": 2, "daily_rent": 0,
                             "trucheck_count": 39, "check_count": 3}
    assert a["service_areas"][0] == {"id": 6542, "name": "Fujairah"}
    # page-only fields are null from the index
    assert a["experience_years"] is None and a["brn_number"] is None and a["social_media"] is None


def test_agents_search_and_roster_hits():
    rows = [P.agent_record(h) for h in hits("agents_search_ahmed.json")]
    assert len(rows) == 3 and all(r["is_trubroker"] for r in rows)
    roster = [P.agent_record(h) for h in hits("agency_agents_102520.json")]
    assert all(r["agency"]["id"] == 102520 for r in roster)


def test_agent_page():
    a = P.agent_page(P.server_state(fixture("agent_page_2401468.html")))
    assert a["id"] == 2401468 and a["email"] == "tony.yannieh@firstandtop.ae"
    assert a["experience_years"] == 5 and a["nationality"] == "Lebanon"
    assert a["brn_number"] == "84887" and a["bln_number"] == "202601061203"
    assert a["social_media"] == {"Instagram": "https://www.instagram.com/realestatebytony.dxb?igsh=ZW5rZzkzeXUwczl5&utm_source=qr"}
    assert a["claimed_deals"]["currency"] == "AED" and a["claimed_deals"]["approved"] == 0
    assert a["listings"]["total"] == 43
    assert a["agency"]["slug"] == "first-top-real-estate-101720"


def test_agent_page_not_found():
    assert P.agent_page(P.server_state(fixture("agent_page_missing.html"))) is None
    assert fixture("agent_missing.json")["hits"] == []


# ---- projects -------------------------------------------------------------------------------------

def test_project_record():
    p = P.project_record(hits("project_2749.json")[0])
    assert p["id"] == 2749 and p["name"] == "Beverly Grande" and p["slug"] == "beverly_grande-2749"
    assert p["link"] == "https://www.bayut.com/new-projects/dubai/motor-city/beverly-grande/"
    assert p["developer"]["name"] == "HMB Homes" and p["developer"]["type"] == "developer"
    assert p["location"]["building"] == "Beverly Grande" and p["location"]["community"] == "Motor City"
    assert p["unit_bedrooms"] == [0, 1, 2, 3]
    assert p["unit_categories"][0]["slug"] == "apartments"
    assert p["starting_price"] == {"amount": 791000.0, "currency": "AED", "is_hidden": False}
    assert p["starting_area"] == {"sqm": 38.18, "sqft": 411.0}
    assert p["completion"]["completion_date"] == "2027-12-30"
    assert p["location_completion_status"] == "off-plan"
    assert p["payment_plan"]["pre_handover_percentage"] == 60.0
    assert p["documents"][0]["type"] == "project_brochure" and p["documents"][0]["link"].endswith(".pdf")
    assert p["description"].startswith("Beverly Grande by HMB Homes")
    assert p["photos"]["count"] == 4
    assert p["listings_count"] == 100 and p["has_listings"] is True and p["is_sold_out"] is False
    assert p["created_at"] == "2025-06-03T20:00:00Z"


def test_project_record_arabic():
    p = P.project_record(hits("project_2749.json")[0], "ar")
    assert p["name"] == "بيفرلي غراندي"
    assert p["link"] == "https://www.bayut.com/ar/new-projects/dubai/motor-city/beverly-grande/"


def test_projects_search_hits_parse():
    rows = [P.project_record(h) for h in hits("projects_search_dubai.json")]
    assert len(rows) == 3
    assert rows[0]["name"] == "Cresswell Homes" and rows[0]["starting_price"]["amount"] is None
    assert fixture("project_missing.json")["hits"] == []


# ---- locations -----------------------------------------------------------------------------------

def test_location_record():
    rows = [P.location_record(h) for h in hits("locations_marina.json")]
    assert rows[0]["id"] == 5003 and rows[0]["name"] == "Dubai Marina"
    assert rows[0]["slug"] == "/dubai/dubai-marina" and rows[0]["type"] == "neighbourhood"
    assert rows[0]["link"] == "https://www.bayut.com/for-sale/property/dubai/dubai-marina/"
    assert rows[0]["city"] == "Dubai" and rows[0]["level"] == 2
    assert rows[0]["listings_count"] == 10277 and rows[0]["aliases"] == ["Marina Dubai", "Marsa Dubai", "Dubai Marsa"]
    assert rows[0]["coordinates"] == {"latitude": 25.083189748036, "longitude": 55.14430056087}
    assert rows[1]["city"] == "Abu Dhabi"
    assert P.location_record(hits("locations_marina.json")[0], "zh")["name"] == "迪拜码头"


def test_location_internal_id_and_empty():
    assert P.location_internal_id(hits("location_5003.json")[0]) == 36
    assert fixture("locations_empty.json")["hits"] == []
    assert P.location_record(None) is None
