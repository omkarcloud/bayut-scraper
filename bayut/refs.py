"""Reference resolvers, link builders and the vocabulary tables for /bayut/*.

ONE param per input (tripadvisor QueryOrIdField convention): every record
param accepts the bare Bayut id OR the site link for the same record.
Resolvers raise ValueError with a user-facing message (RefField turns it
into a 400).

Identifiers (www.bayut.com, UAE storefront, captured 2026-11-07):
  * listing   externalID, 6-9 digits: /property/details-17117341.html
              (Algolia slug "details_17117341" or "<title-words>-17117341")
  * agency    externalID + slug "<name>-<externalID>": /companies/k-u-n-real-estate-102520/
              developers have no id in the slug: /companies/ never serves
              them, the agencies index does (slug "merath-development")
  * agent     externalID + slug "<name>-<externalID>": /brokers/tony-yannieh-2401468/
  * project   externalID (Algolia slug "beverly_grande-2749"); the public
              page is the project's own location node:
              /new-projects/dubai/motor-city/beverly-grande/
  * location  externalID (5002 = Dubai, 5003 = Dubai Marina) and a slug
              path (/dubai/dubai-marina); search pages are
              /<for-sale|to-rent>/<category>/<location path>/

Languages: every Algolia record carries its text in up to 15 renderings
(`name`, `name_l1` ... `name_l14`); the suffixes used by www.bayut.com's
own language switch are l1 = ar, l2 = zh, l3 = ru, l4 = de, l5 = fr,
l6 = es, l7 = it, l8 = nl (the /ar/, /zh/ ... path prefixes).
"""
import re
from urllib.parse import parse_qs, unquote, urlparse

SITE = "https://www.bayut.com"
HOST_RE = re.compile(r"(^|\.)bayut\.com$", re.I)

# public language code -> (Algolia field suffix, URL path prefix)
LANGUAGES = {
    "en": ("", ""),
    "ar": ("_l1", "/ar"),
    "zh": ("_l2", "/zh"),
    "ru": ("_l3", "/ru"),
    "de": ("_l4", "/de"),
    "fr": ("_l5", "/fr"),
    "es": ("_l6", "/es"),
    "it": ("_l7", "/it"),
    "nl": ("_l8", "/nl"),
}

PURPOSES = ("for-sale", "for-rent")
# URL segment <-> Algolia purpose value
PURPOSE_SEGMENTS = {"for-sale": "for-sale", "to-rent": "for-rent"}

# category.slug values of the ads index (counts checked 2026-11-07; the
# two level-0 slugs match everything under them)
CATEGORIES = (
    "residential", "apartments", "villas", "townhouses", "penthouse", "hotel-apartments",
    "villa-compound", "residential-plots", "residential-floors", "residential-building",
    "commercial", "offices", "shops", "warehouses", "labour-camps", "bulk-units",
    "commercial-plots", "commercial-floors", "commercial-buildings", "factories",
    "industrial-land", "mixed-use-land", "showrooms",
)
# the search URL spells the "all residential" category "property"
URL_CATEGORY_ALIASES = {"property": "residential", "penthouses": "penthouse"}

RENT_FREQUENCIES = ("yearly", "monthly", "weekly", "daily")
COMPLETION_STATUSES = ("completed", "under-construction")
FURNISHING = ("furnished", "unfurnished")
SALE_TYPES = ("new", "resale")
AGENCY_TYPES = ("agency", "developer")
EMIRATES = ("Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Umm Al Quwain",
            "Fujairah", "Al Ain")

# public sort -> Algolia index (replicas of bayut-production-ads-en; the
# site's own ?sort= tokens map onto the same replicas)
SORTS = {
    "popular": "bayut-production-ads-en",
    "newest": "bayut-production-ads-date-desc-en",
    "price_asc": "bayut-production-ads-price-asc-en",
    "price_desc": "bayut-production-ads-price-desc-en",
    "verified": "bayut-production-ads-verified-score-en",
}
URL_SORTS = {"date_desc": "newest", "price_asc": "price_asc", "price_desc": "price_desc",
             "verified_score": "verified", "city_level_score": "popular"}

ADS_INDEX = SORTS["popular"]
PROJECTS_INDEX = "bayut-production-ads-project-en"
AGENCIES_INDEX = "bayut-production-agencies-en"
AGENTS_INDEX = "bayut-production-agents-en"
LOCATIONS_INDEX = "bayut-production-locations-en"

# Bayut's own test agency, excluded by the site's agency / agent searches
TEST_AGENCY_IDS = ("8436",)

SQFT_PER_SQM = 10.7639104

_DIGITS_RE = re.compile(r"^[0-9]{1,12}$")
_PROPERTY_LINK_RE = re.compile(r"/property/details-([0-9]{3,12})\.html", re.I)
_PROPERTY_SLUG_RE = re.compile(r"^(?:details[_-]|.*-)([0-9]{3,12})$", re.I)
_SLUG_ID_RE = re.compile(r"-([0-9]{1,12})$")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$", re.I)
_LOCATION_PATH_RE = re.compile(r"^/?[a-z0-9-]+(/[a-z0-9-]+)*/?$", re.I)
_LANG_PREFIX_RE = re.compile(r"^/(ar|zh|ru|de|fr|es|it|nl)(?=/|$)", re.I)


# ---- helpers -------------------------------------------------------------------------

def _is_link(value):
    return value.startswith(("http://", "https://", "//"))


def _parse_link(value):
    """urlparse of a bayut.com link (ValueError for another site)."""
    url = value if not value.startswith("//") else "https:" + value
    parts = urlparse(url)
    if not HOST_RE.search((parts.hostname or "").lower()):
        raise ValueError("Must be a bayut.com link.")
    return parts


def _strip_lang(path):
    """"/ar/for-sale/..." -> "/for-sale/..." (the language prefix is just a
    rendering of the same route)."""
    return _LANG_PREFIX_RE.sub("", path) or "/"


def language_suffix(language):
    return LANGUAGES.get(language or "en", LANGUAGES["en"])[0]


def language_prefix(language):
    return LANGUAGES.get(language or "en", LANGUAGES["en"])[1]


# ---- listings --------------------------------------------------------------------------

def resolve_property(value):
    """Bare listing externalID, an Algolia-style slug ending in the id, or a
    /property/details-<id>.html link -> the externalID (string)."""
    value = (value or "").strip()
    if _DIGITS_RE.match(value):
        return value
    if _is_link(value):
        parts = _parse_link(value)
        match = _PROPERTY_LINK_RE.search(parts.path)
        if match:
            return match.group(1)
        raise ValueError("Must be a bayut.com listing link "
                         "(https://www.bayut.com/property/details-17117341.html).")
    match = _PROPERTY_SLUG_RE.match(value)
    if match and _SLUG_RE.match(value):
        return match.group(1)
    raise ValueError("Must be a Bayut listing id (17117341) or a bayut.com listing link.")


def property_link(external_id, language="en"):
    return f"{SITE}{language_prefix(language)}/property/details-{external_id}.html"


# ---- agencies --------------------------------------------------------------------------

def resolve_agency(value):
    """Bare agency externalID, an agency slug ("k-u-n-real-estate-102520",
    "merath-development") or a /companies/<slug>/ link -> {"id": ..} when
    the id is known, else {"slug": ..}."""
    value = (value or "").strip()
    if _DIGITS_RE.match(value):
        return {"id": value}
    if _is_link(value):
        parts = _parse_link(value)
        match = re.search(r"/companies/([^/?#]+)", _strip_lang(parts.path), re.I)
        if not match:
            raise ValueError("Must be a bayut.com agency link "
                             "(https://www.bayut.com/companies/<name>-<id>/).")
        value = unquote(match.group(1))
    if not _SLUG_RE.match(value):
        raise ValueError("Must be a Bayut agency id (102520), an agency slug "
                         "(k-u-n-real-estate-102520) or a bayut.com agency link.")
    match = _SLUG_ID_RE.search(value)
    if match:
        return {"id": match.group(1), "slug": value}
    return {"slug": value}


def agency_link(slug, agency_type="agency", language="en"):
    if not slug:
        return None
    return f"{SITE}{language_prefix(language)}/companies/{slug}/"


# ---- agents ----------------------------------------------------------------------------

def resolve_agent(value):
    """Bare agent externalID, the "<name>-<externalID>" slug or a
    /brokers/<slug>/ link -> the externalID (string)."""
    value = (value or "").strip()
    if _DIGITS_RE.match(value):
        return value
    if _is_link(value):
        parts = _parse_link(value)
        match = re.search(r"/brokers/([^/?#]+)", _strip_lang(parts.path), re.I)
        if not match:
            raise ValueError("Must be a bayut.com agent link "
                             "(https://www.bayut.com/brokers/<name>-<id>/).")
        value = unquote(match.group(1))
    match = _SLUG_ID_RE.search(value)
    if match and _SLUG_RE.match(value):
        return match.group(1)
    raise ValueError("Must be a Bayut agent id (2401468), an agent slug "
                     "(tony-yannieh-2401468) or a bayut.com agent link.")


def agent_link(slug, language="en"):
    if not slug:
        return None
    return f"{SITE}{language_prefix(language)}/brokers/{slug}/"


# ---- projects --------------------------------------------------------------------------

def resolve_project(value):
    """Bare project externalID, the Algolia slug ("beverly_grande-2749") or
    the project's /new-projects/<location path>/ link -> {"id": ..} or
    {"location_slug": "/dubai/motor-city/beverly-grande"}."""
    value = (value or "").strip()
    if _DIGITS_RE.match(value):
        return {"id": value}
    if _is_link(value):
        parts = _parse_link(value)
        match = re.search(r"/new-projects((?:/[a-z0-9-]+)+)/?$", _strip_lang(parts.path), re.I)
        if not match or match.group(1).startswith("/developers"):
            raise ValueError("Must be a bayut.com project link "
                             "(https://www.bayut.com/new-projects/dubai/motor-city/beverly-grande/).")
        return {"location_slug": match.group(1).lower()}
    match = _SLUG_ID_RE.search(value)
    if match and _SLUG_RE.match(value):
        return {"id": match.group(1)}
    raise ValueError("Must be a Bayut project id (2749), a project slug "
                     "(beverly_grande-2749) or a bayut.com new-projects link.")


def project_link(location_slug, language="en"):
    if not location_slug:
        return None
    return f"{SITE}{language_prefix(language)}/new-projects{location_slug}/"


# ---- locations -------------------------------------------------------------------------

def location_search_link(slug, purpose="for-sale", category="residential", language="en"):
    if not slug:
        return None
    segment = "to-rent" if purpose == "for-rent" else "for-sale"
    # the URL spells the index slugs differently for two categories (URL_CATEGORY_ALIASES)
    cat = {v: k for k, v in URL_CATEGORY_ALIASES.items()}.get(category or "residential", category)
    return f"{SITE}{language_prefix(language)}/{segment}/{cat}/{slug.strip('/')}/"


def _int_list(values):
    out = []
    for raw in values or []:
        for part in str(raw).split(","):
            part = part.strip()
            if part.isdigit():
                out.append(int(part))
    return out


def _first_number(values):
    for raw in values or []:
        raw = str(raw).replace(",", "").strip()
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def _parse_search_link(parts):
    """A /<for-sale|to-rent>/[off-plan/|completed/]<category>/<location path>/
    link -> {"slug", "purpose", "category", "filters"} (its own query
    filters carry through as defaults)."""
    path = _strip_lang(parts.path).strip("/")
    segments = [s for s in path.split("/") if s]
    if len(segments) < 2 or segments[0] not in PURPOSE_SEGMENTS:
        raise ValueError("Must be a bayut.com search link "
                         "(https://www.bayut.com/for-sale/apartments/dubai/dubai-marina/).")
    purpose = PURPOSE_SEGMENTS[segments[0]]
    filters = {}
    rest = segments[1:]
    if rest and rest[0] in ("off-plan", "completed"):
        filters["completion_status"] = "under-construction" if rest[0] == "off-plan" else "completed"
        rest = rest[1:]
    if not rest:
        raise ValueError("The search link carries no category / location.")
    category = rest[0].lower()
    # "/for-sale/2-bedroom-apartments/dubai/" style bedroom pages
    beds_match = re.match(r"^(studio|[0-9]+)-bedroom-(.+)$", category)
    if beds_match:
        beds = 0 if beds_match.group(1) == "studio" else int(beds_match.group(1))
        filters["beds_min"] = filters["beds_max"] = beds
        category = beds_match.group(2)
    category = URL_CATEGORY_ALIASES.get(category, category)
    if category not in CATEGORIES:
        raise ValueError(f"Unknown category '{category}' in the search link.")
    slug = "/" + "/".join(s.lower() for s in rest[1:]) if len(rest) > 1 else None
    query = parse_qs(parts.query)
    for key, target in (("price_min", "price_min"), ("price_max", "price_max"),
                        ("area_min", "area_min"), ("area_max", "area_max")):
        number = _first_number(query.get(key))
        if number is not None:
            filters[target] = number
    beds = _int_list(query.get("beds_in"))
    if beds:
        filters["beds_min"], filters["beds_max"] = min(beds), max(beds)
    baths = _int_list(query.get("baths_in"))
    if baths:
        filters["baths_min"], filters["baths_max"] = min(baths), max(baths)
    for key, target, allowed in (("rent_frequency", "rent_frequency", RENT_FREQUENCIES),
                                 ("furnishing_status", "furnishing", FURNISHING),
                                 ("completion_status", "completion_status", COMPLETION_STATUSES),
                                 ("sale_type", "sale_type", SALE_TYPES)):
        value = (query.get(key) or [None])[0]
        if value and value.lower() in allowed:
            filters[target] = value.lower()
    sort = (query.get("sort") or [None])[0]
    if sort and sort.lower() in URL_SORTS:
        filters["sort"] = URL_SORTS[sort.lower()]
    if (query.get("is_verified") or [None])[0] in ("true", "1"):
        filters["verified"] = True
    page = _int_list(query.get("page"))
    if page:
        filters["page"] = page[0]
    return {"slug": slug, "purpose": purpose, "category": category, "filters": filters}


def resolve_search_location(value):
    """properties/search `location`: a location externalID (5003), a slug
    path (/dubai/dubai-marina or dubai/dubai-marina), a free-text place name
    ("Dubai Marina" — resolved through the site's own location index), OR a
    pasted bayut.com search link (whose filters carry through)."""
    value = (value or "").strip()
    if not value:
        raise ValueError("Must not be empty.")
    if _DIGITS_RE.match(value):
        return {"external_id": value}
    if _is_link(value):
        return _parse_search_link(_parse_link(value))
    if "/" in value and _LOCATION_PATH_RE.match(value):
        return {"slug": "/" + value.strip("/").lower()}
    return {"name": value}


def resolve_location_ref(value):
    """A location for the agency / agent / project searches: externalID,
    slug path, place name or a bayut.com link whose path is a location."""
    value = (value or "").strip()
    if not value:
        raise ValueError("Must not be empty.")
    if _DIGITS_RE.match(value):
        return {"external_id": value}
    if _is_link(value):
        parts = _parse_link(value)
        path = _strip_lang(parts.path).strip("/")
        segments = [s for s in path.split("/") if s]
        if segments and segments[0] in PURPOSE_SEGMENTS:
            return {"slug": _parse_search_link(parts)["slug"]}
        if segments and segments[0] in ("companies", "brokers", "new-projects"):
            segments = segments[1:]
        if segments and segments[0] == "developers":
            raise ValueError("A developer link is not a location.")
        if not segments:
            raise ValueError("The link carries no location.")
        return {"slug": "/" + "/".join(s.lower() for s in segments)}
    if "/" in value and _LOCATION_PATH_RE.match(value):
        return {"slug": "/" + value.strip("/").lower()}
    return {"name": value}


def sqft_to_sqm(value):
    return None if value is None else float(value) / SQFT_PER_SQM


def sqm_to_sqft(value):
    return None if value is None else round(float(value) * SQFT_PER_SQM, 2)
