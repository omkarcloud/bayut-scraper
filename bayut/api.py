"""The /bayut/* endpoint functions (route_glue's route_table calls them with
the schema's loaded kwargs). Every endpoint caches its own parsed result
through cache.cached_call keyed on the validated params (TTLs in
cache_config.py). Place-name resolution (`location="Dubai Marina"`) is one
cached lookup on the site's location index, shared by every search.

Everything but the three profile pages is one Algolia query on the site's
own search proxy (bayut/fetch.py); properties/details, agencies/details and
agents/details read the server-rendered page because it carries what the
index does not (description, amenities, photo list, agent email, BRN).
"""
import time

from cache import cached_call
from bayut import cache_config as ttl
from bayut import parsers, refs
from bayut.fetch import (BayutNotFound, BayutUpstreamError, algolia_params, algolia_query, fetch_agency_page,
                         fetch_agent_page, fetch_property_page)


def _quote(value):
    """A filter value for Algolia's `filters` expression."""
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def _and(*clauses):
    return " AND ".join(c for c in clauses if c)


def _num(value):
    """A number for a filter expression: never scientific notation (Algolia
    rejects "1e+06"), no trailing .0 on integral values."""
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:.4f}".rstrip("0").rstrip(".")


def _paged(answer, cards, page, limit):
    return {"results": cards, "pagination": parsers.pagination(answer, page, limit)}


def _hits(answer):
    return answer.get("hits") if isinstance(answer.get("hits"), list) else []


# ---- locations ---------------------------------------------------------------------------

def _location_lookup(ref):
    """The location index row for an externalID / slug / place name
    (None when the index knows no such place)."""
    if ref.get("external_id"):
        params = algolia_params(hitsPerPage=1, filters=f"externalID:{ref['external_id']}")
    elif ref.get("slug"):
        params = algolia_params(hitsPerPage=1, filters=f"slug:{_quote(ref['slug'])}")
    else:
        params = algolia_params(hitsPerPage=1, query=ref.get("name") or "")
    hits = _hits(algolia_query(refs.LOCATIONS_INDEX, params, "location lookup"))
    return hits[0] if hits else None


def _resolve_location(ref):
    """Cached location row for a search's `location` ref; raises NotFound
    for an unknown place. A search link that names no location (a whole-UAE
    search) resolves to None."""
    key = {k: ref.get(k) for k in ("external_id", "slug", "name") if ref.get(k)}
    if not key:
        return None
    row = cached_call("bayut.location", key, lambda **k: _location_lookup(k) or {}, ttl.LOCATION_CACHE)
    if not row:
        label = key.get("external_id") or key.get("slug") or key.get("name")
        raise BayutNotFound(f"location {label!r} is not known to Bayut")
    return row


def _location_summary(row, language):
    return parsers.location_record(row, language) if row else None


def _autocomplete(query, type, language, limit):
    params = algolia_params(hitsPerPage=limit, query=query,
                            filters=f"type:{_quote(type)}" if type else None)
    answer = algolia_query(refs.LOCATIONS_INDEX, params, "location autocomplete")
    rows = [r for r in (parsers.location_record(h, language) for h in _hits(answer)) if r]
    return {"query": query, "count": len(rows), "results": rows}


def locations_autocomplete(**data):
    """Bayut's own location search box: cities, communities, sub-communities and
    buildings matching the start of a name, each with its id, slug, type,
    level, city, coordinates, live listing count and aliases."""
    return cached_call("bayut.autocomplete", data, _autocomplete, ttl.LOCATION_CACHE)


# ---- properties/search ----------------------------------------------------------------------

def _agency_filter(ref):
    if not ref:
        return None
    if ref.get("id"):
        return f"agency.externalID:{ref['id']}"
    return f"agency.slug:{_quote(ref['slug'])}"


def _listing_filters(purpose, category, location_row, price_min, price_max, beds_min, beds_max, baths_min,
                     baths_max, area_min, area_max, rent_frequency, completion_status, furnishing, sale_type,
                     verified, has_video, has_360_tour, has_floor_plan, agency, agent, posted_within_days):
    clauses = []
    if purpose:
        clauses.append(f"purpose:{purpose}")
    if category:
        clauses.append(f"category.slug:{category}")
    if location_row:
        clauses.append(f"location.externalID:{location_row.get('externalID')}")
    if price_min is not None:
        clauses.append(f"price>={_num(price_min)}")
    if price_max is not None:
        clauses.append(f"price<={_num(price_max)}")
    if beds_min is not None:
        clauses.append(f"rooms>={beds_min}")
    if beds_max is not None:
        clauses.append(f"rooms<={beds_max}")
    if baths_min is not None:
        clauses.append(f"baths>={baths_min}")
    if baths_max is not None:
        clauses.append(f"baths<={baths_max}")
    if area_min is not None:
        clauses.append(f"area>={_num(refs.sqft_to_sqm(area_min))}")
    if area_max is not None:
        clauses.append(f"area<={_num(refs.sqft_to_sqm(area_max))}")
    if rent_frequency:
        clauses.append(f"rentFrequency:{rent_frequency}")
    if completion_status:
        clauses.append(f"completionStatus:{completion_status}")
    if furnishing:
        clauses.append(f"furnishingStatus:{furnishing}")
    if sale_type:
        clauses.append(f"offplanDetails.saleType:{sale_type}")
    if verified:
        clauses.append("isVerified:true")
    if has_video:
        clauses.append("videoCount>0")
    if has_360_tour:
        clauses.append("panoramaCount>0")
    if has_floor_plan:
        clauses.append("floorPlanID>0")
    if agency:
        clauses.append(_agency_filter(agency))
    if agent:
        clauses.append(f"ownerID:{agent}")
    if posted_within_days:
        clauses.append(f"createdAt>={int(time.time()) - posted_within_days * 86400}")
    return _and(*clauses)


def _properties_search(location, purpose, category, query, price_min, price_max, beds_min, beds_max, baths_min,
                       baths_max, area_min, area_max, rent_frequency, completion_status, furnishing, sale_type,
                       verified, has_video, has_360_tour, has_floor_plan, agency, agent, posted_within_days,
                       latitude, longitude, radius_km, sort, language, page, limit):
    link_filters = dict((location or {}).get("filters") or {})
    # a pasted search link's own values are the defaults; explicit params win
    purpose = purpose or (location or {}).get("purpose") or "for-sale"
    category = category or (location or {}).get("category")
    explicit = dict(price_min=price_min, price_max=price_max, beds_min=beds_min, beds_max=beds_max,
                    baths_min=baths_min, baths_max=baths_max, area_min=area_min, area_max=area_max,
                    rent_frequency=rent_frequency, completion_status=completion_status, furnishing=furnishing,
                    sale_type=sale_type, verified=verified, sort=sort)
    for key, value in explicit.items():
        if value is None:
            explicit[key] = link_filters.get(key)
    if page == 1 and link_filters.get("page"):
        page = min(int(link_filters["page"]), 5000)
    if explicit["rent_frequency"] and purpose == "for-sale":
        explicit["rent_frequency"] = None
    location_row = _resolve_location(location) if location else None
    filters = _listing_filters(
        purpose, category, location_row, explicit["price_min"], explicit["price_max"], explicit["beds_min"],
        explicit["beds_max"], explicit["baths_min"], explicit["baths_max"], explicit["area_min"],
        explicit["area_max"], explicit["rent_frequency"], explicit["completion_status"], explicit["furnishing"],
        explicit["sale_type"], explicit["verified"], has_video, has_360_tour, has_floor_plan, agency, agent,
        posted_within_days)
    params = algolia_params(
        query=query or "", hitsPerPage=limit, page=page - 1, filters=filters,
        aroundLatLng=f"{latitude},{longitude}" if latitude is not None else None,
        aroundRadius=int(radius_km * 1000) if radius_km else None)
    index = refs.SORTS.get(explicit["sort"] or "popular", refs.ADS_INDEX)
    answer = algolia_query(index, params, "listing search")
    cards = [c for c in (parsers.listing_card(h, language) for h in _hits(answer)) if c]
    return {
        "location": _location_summary(location_row, language),
        "purpose": purpose,
        "category": category,
        "query": query,
        "sort": explicit["sort"] or "popular",
        **_paged(answer, cards, page, limit),
    }


def properties_search(**data):
    """Search live UAE listings for sale or rent on Bayut's own search index with
    every site filter (price, beds, baths, area, completion, furnishing,
    off-plan sale type, TruCheck verification, video / 360 tour / floor plan,
    agency, agent, posted date, radius) and five sort orders; 25 cards per
    page, up to 50,000 results per search. Each card carries price, size,
    location chain, coordinates, photos, verification, the agent and the
    agency with phone numbers."""
    return cached_call("bayut.search", data, _properties_search, ttl.SEARCH_CACHE)


# ---- properties/details ---------------------------------------------------------------------

def _property_details(property, language):
    html = fetch_property_page(property, language)
    record = parsers.listing_details(parsers.server_state(html), language)
    if record is None:
        title = parsers.page_title(html)
        if "not found" in title.lower():
            raise BayutNotFound(f"listing {property} not found")
        raise BayutUpstreamError(f"listing {property}: page carried no listing ({title!r})")
    return record


def property_details(**data):
    """One listing's full page: price, size, description, amenities, every
    photo, payment plans, off-plan details, verification, the listing agent's
    profile (email, phones, languages, service areas) and the agency."""
    return cached_call("bayut.details", data, _property_details, ttl.DETAILS_CACHE)


# ---- agencies --------------------------------------------------------------------------------

def _location_internal_id(location):
    row = _resolve_location(location) if location else None
    return parsers.location_internal_id(row), row


def _agencies_search(query, location, type, language, page, limit):
    internal_id, row = _location_internal_id(location)
    clauses = [f"type:{type}"] + [f"NOT externalID:{t}" for t in refs.TEST_AGENCY_IDS]
    if internal_id is not None:
        clauses.append(f"stats.locationsWithAds:{internal_id}")
    params = algolia_params(query=query or "", hitsPerPage=limit, page=page - 1, filters=_and(*clauses))
    answer = algolia_query(refs.AGENCIES_INDEX, params, "agency search")
    rows = [r for r in (parsers.agency_record(h, language) for h in _hits(answer)) if r]
    return {"query": query, "type": type, "location": _location_summary(row, language),
            **_paged(answer, rows, page, limit)}


def agencies_search(**data):
    """Search Bayut's agency directory (brokerages, or developers with
    type=developer) by name and / or area: licences, phones, agent counts and
    live listing counts; 25 per page."""
    return cached_call("bayut.agencies_search", data, _agencies_search, ttl.DIRECTORY_CACHE)


def _agency_hit(ref):
    """The agencies-index row for an id / slug ref (NotFound when unknown)."""
    if ref.get("id"):
        filters = f"externalID:{ref['id']}"
    else:
        filters = f"slug:{_quote(ref['slug'])}"
    hits = _hits(algolia_query(refs.AGENCIES_INDEX, algolia_params(hitsPerPage=1, filters=filters),
                               "agency lookup"))
    if not hits:
        raise BayutNotFound(f"agency {ref.get('id') or ref.get('slug')} not found")
    return hits[0]


def _agency_details(agency, language):
    hit = _agency_hit(agency)
    record = parsers.agency_record(hit, language)
    slug = hit.get("slug") or agency.get("slug") or (f"x-{agency['id']}" if agency.get("id") else None)
    if record["type"] != "developer" and slug:
        # the page adds the description and a roster preview (developers
        # have no /companies/ page: their index row is the whole record)
        try:
            page = parsers.agency_page(parsers.server_state(fetch_agency_page(slug, language)), language)
        except BayutNotFound:
            page = None
        if page:
            page["specialities"] = page["specialities"] or record["specialities"]
            page["languages"] = page["languages"] or record["languages"]
            page["purposes"] = page["purposes"] or record["purposes"]
            page["created_at"] = page["created_at"] or record["created_at"]
            page["is_elite"] = page["is_elite"] if page["is_elite"] is not None else record["is_elite"]
            return page
    record["agents_preview"] = None
    return record


def agency_details(**data):
    """One agency's profile: description, licences, phones, contact methods,
    agent and TruBroker counts, live listing counts, categories, languages,
    specialities and a preview of its agents. A developer returns its
    directory record."""
    return cached_call("bayut.agency", data, _agency_details, ttl.AGENCY_CACHE)


def _agency_id(ref):
    if ref.get("id"):
        return ref["id"]
    hit = cached_call("bayut.agency_row", {"slug": ref["slug"]}, lambda slug: _agency_hit({"slug": slug}),
                      ttl.AGENCY_CACHE)
    return str(hit.get("externalID"))


def _agency_agents(agency, language, page, limit):
    agency_id = _agency_id(agency)
    params = algolia_params(hitsPerPage=limit, page=page - 1, filters=f"agency.external_id:{agency_id}")
    answer = algolia_query(refs.AGENTS_INDEX, params, "agency agents")
    rows = [r for r in (parsers.agent_record(h, language) for h in _hits(answer)) if r]
    if not rows and page == 1:
        _agency_hit({"id": agency_id})   # 404 for an unknown agency, an empty roster otherwise
    first_agency = (rows[0].get("agency") or {}) if rows else {}
    slug = agency.get("slug") or first_agency.get("slug")
    return {"agency": {"id": parsers.record_id(agency_id), "name": first_agency.get("name"),
                       "slug": slug, "link": refs.agency_link(slug, "agency", language)},
            **_paged(answer, rows, page, limit)}


def agency_agents(**data):
    """Every agent at one agency with email, phones, languages, specialities,
    service areas, TruBroker badges and listing counts; 25 per page."""
    return cached_call("bayut.agency_agents", data, _agency_agents, ttl.DIRECTORY_CACHE)


# ---- agents ----------------------------------------------------------------------------------

def _agents_search(query, location, emirate, speaks, trubroker_only, language, page, limit):
    internal_id, row = _location_internal_id(location)
    clauses = [f"NOT agency.external_id:{t}" for t in refs.TEST_AGENCY_IDS]
    if internal_id is not None:
        clauses.append(f"stats.locationsWithAds:{internal_id}")
    if emirate:
        clauses.append(f"activeInEmirate:{_quote(emirate)}")
    if speaks:
        codes = sorted({code.lower() for code in speaks})
        clauses.append("(" + " OR ".join(f"language_codes:{_quote(code)}" for code in codes) + ")")
    if trubroker_only:
        clauses.append("isTruBroker:true")
    params = algolia_params(query=query or "", hitsPerPage=limit, page=page - 1, filters=_and(*clauses))
    answer = algolia_query(refs.AGENTS_INDEX, params, "agent search")
    rows = [r for r in (parsers.agent_record(h, language) for h in _hits(answer)) if r]
    return {"query": query, "location": _location_summary(row, language), "emirate": emirate,
            **_paged(answer, rows, page, limit)}


def agents_search(**data):
    """Search Bayut's agent directory by name, area, emirate, spoken language
    or TruBroker badge: email, phones, agency, badges and listing counts;
    25 per page."""
    return cached_call("bayut.agents_search", data, _agents_search, ttl.DIRECTORY_CACHE)


def _agent_hit(agent_id):
    hits = _hits(algolia_query(refs.AGENTS_INDEX, algolia_params(hitsPerPage=1, filters=f"externalID:{agent_id}"),
                               "agent lookup"))
    if not hits:
        raise BayutNotFound(f"agent {agent_id} not found")
    return hits[0]


def _agent_details(agent, language):
    hit = _agent_hit(agent)
    record = parsers.agent_record(hit, language)
    if hit.get("slug"):
        # the broker page adds experience, nationality, BRN, social links
        # and the claimed-deals summary
        try:
            page = parsers.agent_page(parsers.server_state(fetch_agent_page(hit["slug"], language)), language)
        except BayutNotFound:
            page = None
        if page:
            for key in ("language_codes", "speciality_codes", "experience_points", "badges", "active_emirate"):
                if page.get(key) in (None, {}) or (isinstance(page.get(key), dict)
                                                    and not any(v is not None for v in page[key].values())):
                    page[key] = record.get(key)
            return page
    record["claimed_deals"] = None
    return record


def agent_details(**data):
    """One agent's profile: email, phones, WhatsApp, agency, BRN and BLN numbers,
    years of experience, nationality, languages, specialities, service areas,
    social links, TruBroker badges, listing counts and claimed deals."""
    return cached_call("bayut.agent", data, _agent_details, ttl.AGENT_CACHE)


def _agent_listings(agent, purpose, sort, language, page, limit):
    filters = _and(f"ownerID:{agent}", f"purpose:{purpose}" if purpose else None)
    params = algolia_params(hitsPerPage=limit, page=page - 1, filters=filters)
    answer = algolia_query(refs.SORTS.get(sort or "popular", refs.ADS_INDEX), params, "agent listings")
    cards = [c for c in (parsers.listing_card(h, language) for h in _hits(answer)) if c]
    if not cards and page == 1:
        _agent_hit(agent)   # 404 for an unknown agent, an empty list otherwise
    return {"agent": {"id": parsers.record_id(agent), "name": (cards[0]["agent"] or {}).get("name") if cards else None,
                      "link": (cards[0]["agent"] or {}).get("link") if cards else None},
            "purpose": purpose, "sort": sort or "popular", **_paged(answer, cards, page, limit)}


def agent_listings(**data):
    """One agent's live listings (for sale, for rent or both) in any sort order,
    as search cards; 25 per page."""
    return cached_call("bayut.agent_listings", data, _agent_listings, ttl.SEARCH_CACHE)


# ---- projects --------------------------------------------------------------------------------

def _projects_search(location, query, developer, completion_status, language, page, limit):
    row = _resolve_location(location) if location else None
    clauses = []
    if row:
        clauses.append(f"location.externalID:{row.get('externalID')}")
    if developer:
        clauses.append(_agency_filter(developer))
    if completion_status:
        clauses.append(f"completionStatus:{completion_status}")
    params = algolia_params(query=query or "", hitsPerPage=limit, page=page - 1, filters=_and(*clauses))
    answer = algolia_query(refs.PROJECTS_INDEX, params, "project search")
    rows = [r for r in (parsers.project_record(h, language) for h in _hits(answer)) if r]
    return {"query": query, "location": _location_summary(row, language),
            "completion_status": completion_status, **_paged(answer, rows, page, limit)}


def projects_search(**data):
    """Search Bayut's new-projects (off-plan) index by area, name or developer:
    starting price, unit mix, completion date and progress, payment plan,
    amenities and listing counts; 25 per page."""
    return cached_call("bayut.projects_search", data, _projects_search, ttl.DIRECTORY_CACHE)


def _project_details(project, language):
    if project.get("id"):
        filters = f"externalID:{project['id']}"
    else:
        filters = f"location.slug:{_quote(project['location_slug'])}"
    hits = _hits(algolia_query(refs.PROJECTS_INDEX, algolia_params(hitsPerPage=1, filters=filters),
                               "project lookup"))
    if not hits:
        raise BayutNotFound(f"project {project.get('id') or project.get('location_slug')} not found")
    return parsers.project_record(hits[0], language)


def project_details(**data):
    """One new project: developer, location, starting price and size, unit types
    and bedrooms, completion date and progress, payment plan, amenities,
    description, brochure and photos."""
    return cached_call("bayut.project", data, _project_details, ttl.PROJECT_CACHE)
