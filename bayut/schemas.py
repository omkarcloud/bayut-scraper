"""Marshmallow request schemas for every /bayut/* route.

ONE param per input (tripadvisor QueryOrIdField convention, never a sibling
`url` / `id` pair); every record param also accepts the site link for the
same record (resolvers in bayut/refs.py):

    location   a location id (5003), a slug path (/dubai/dubai-marina), a
               place name ("Dubai Marina", resolved through Bayut's own
               location index) OR a pasted bayut.com search link (its
               category / purpose / filters carry through as defaults)
    property   a listing id (17117341) OR its /property/details-<id>.html link
    agency     an agency id (102520), its slug (k-u-n-real-estate-102520 or
               merath-development) OR a /companies/<slug>/ link
    agent      an agent id (2401468), its slug (tony-yannieh-2401468) OR a
               /brokers/<slug>/ link
    project    a project id (2749), its slug (beverly_grande-2749) OR the
               project's /new-projects/<location path>/ link
    developer  projects/search: a developer id / slug / link

`language` picks the rendering of names, titles and descriptions: en
(default), ar, zh, ru, de, fr, es, it, nl — the site's own language switch.
"""
from marshmallow import ValidationError, fields, validate, validates_schema

from bayut import refs
from schema_fields import (BaseSchema, ChoiceField, CommaListField, Flag, LimitField, PageField, PositiveInt,
                           Price, QueryField, RefField)

# Algolia's paginationLimitedTo is 50,000 hits on every Bayut index: with the
# smallest page size that is page 5,000; a page past the real end is an
# empty page.
MAX_PAGE = 5000
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 50
MAX_RADIUS_KM = 50


class SearchLocationField(RefField):
    resolver = staticmethod(refs.resolve_search_location)


class LocationRefField(RefField):
    resolver = staticmethod(refs.resolve_location_ref)


class PropertyRefField(RefField):
    resolver = staticmethod(refs.resolve_property)


class AgencyRefField(RefField):
    resolver = staticmethod(refs.resolve_agency)


class AgentRefField(RefField):
    resolver = staticmethod(refs.resolve_agent)


class ProjectRefField(RefField):
    resolver = staticmethod(refs.resolve_project)


class CountField(fields.Integer):
    """Optional count >= 0 (0 bedrooms = studio)."""

    def __init__(self, max_value=50, **kwargs):
        kwargs.setdefault("load_default", None)
        kwargs.setdefault("validate", validate.Range(min=0, max=max_value))
        super().__init__(strict=False, **kwargs)


class Coordinate(fields.Float):
    def __init__(self, bound, **kwargs):
        kwargs.setdefault("load_default", None)
        kwargs.setdefault("validate", validate.Range(min=-bound, max=bound))
        super().__init__(**kwargs)


def _language():
    return ChoiceField(list(refs.LANGUAGES), load_default="en", metadata={
        "description": "language of names, titles and descriptions: en (default), ar, zh, ru, de, fr, es, it, nl"})


def _page():
    return PageField(max_page=MAX_PAGE, metadata={"description": "1-based results page"})


def _limit():
    # zero-arg on purpose: the publish tooling (derive_facts) resolves
    # zero-arg field factories and module constants, not arguments
    return LimitField(default=DEFAULT_PAGE_SIZE, max_size=MAX_PAGE_SIZE, metadata={
        "description": f"results per page (default {DEFAULT_PAGE_SIZE}, max {MAX_PAGE_SIZE})"})


def _sort():
    return ChoiceField(list(refs.SORTS), metadata={
        "description": "popular (Bayut's own ranking, default), newest, price_asc, price_desc, verified "
                       "(TruCheck-verified first)"})


class _RangeCheck:
    """min <= max checks shared by the listing searches."""
    RANGES = (("price_min", "price_max"), ("beds_min", "beds_max"), ("baths_min", "baths_max"),
              ("area_min", "area_max"))

    @validates_schema
    def _ranges_ordered(self, data, **kwargs):
        for low, high in self.RANGES:
            lo, hi = data.get(low), data.get(high)
            if lo is not None and hi is not None and lo > hi:
                raise ValidationError(f"Must not be below {low}.", high)


class PropertiesSearchSchema(_RangeCheck, BaseSchema):
    location = SearchLocationField(required=False, load_default=None, metadata={
        "description": "location id (5003), slug path (/dubai/dubai-marina), place name ('Dubai Marina', "
                       "'JVC') or a pasted bayut.com search link whose filters carry through; omit for the "
                       "whole UAE"})
    purpose = ChoiceField(list(refs.PURPOSES), metadata={
        "description": "for-sale (default) or for-rent"})
    category = ChoiceField(list(refs.CATEGORIES), metadata={
        "description": "property type: residential (all), apartments, villas, townhouses, penthouse, "
                       "hotel-apartments, villa-compound, residential-plots, residential-floors, "
                       "residential-building, commercial (all), offices, shops, warehouses, labour-camps, "
                       "bulk-units, commercial-plots, commercial-floors, commercial-buildings, factories, "
                       "industrial-land, mixed-use-land, showrooms (default: every type)"})
    query = QueryField(required=False, load_default=None, metadata={
        "description": "free-text keywords matched against the listing (e.g. 'sea view', 'maid room')"})
    price_min = Price(metadata={"description": "minimum price in AED (per rent period for rentals)"})
    price_max = Price(metadata={"description": "maximum price in AED"})
    beds_min = CountField(metadata={"description": "minimum bedrooms (0 = studio)"})
    beds_max = CountField(metadata={"description": "maximum bedrooms"})
    baths_min = CountField(metadata={"description": "minimum bathrooms"})
    baths_max = CountField(metadata={"description": "maximum bathrooms"})
    area_min = Price(metadata={"description": "minimum built-up area in square feet"})
    area_max = Price(metadata={"description": "maximum built-up area in square feet"})
    rent_frequency = ChoiceField(list(refs.RENT_FREQUENCIES), metadata={
        "description": "rentals only: yearly, monthly, weekly or daily"})
    completion_status = ChoiceField(list(refs.COMPLETION_STATUSES), metadata={
        "description": "completed (ready) or under-construction (off-plan)"})
    furnishing = ChoiceField(list(refs.FURNISHING), metadata={"description": "furnished or unfurnished"})
    sale_type = ChoiceField(list(refs.SALE_TYPES), metadata={
        "description": "off-plan sales only: new (from the developer) or resale"})
    verified = Flag(metadata={"description": "true = TruCheck-verified listings only"})
    has_video = Flag(metadata={"description": "true = listings with a video"})
    has_360_tour = Flag(metadata={"description": "true = listings with a 360° panorama"})
    has_floor_plan = Flag(metadata={"description": "true = listings with a floor plan"})
    agency = AgencyRefField(required=False, load_default=None, metadata={
        "description": "only listings of this agency: id, slug or bayut.com agency link"})
    agent = AgentRefField(required=False, load_default=None, metadata={
        "description": "only listings of this agent: id, slug or bayut.com agent link"})
    posted_within_days = PositiveInt(max_value=365, metadata={
        "description": "only listings first posted within the last N days"})
    latitude = Coordinate(90, metadata={"description": "centre of a radius search (with longitude and radius_km)"})
    longitude = Coordinate(180, metadata={"description": "centre of a radius search"})
    radius_km = fields.Float(load_default=None, validate=validate.Range(min=0.1, max=MAX_RADIUS_KM), metadata={
        "description": f"radius in km around latitude/longitude (max {MAX_RADIUS_KM})"})
    sort = _sort()
    language = _language()
    page = _page()
    limit = _limit()

    @validates_schema
    def _radius_needs_centre(self, data, **kwargs):
        given = [k for k in ("latitude", "longitude", "radius_km") if data.get(k) is not None]
        if given and len(given) != 3:
            raise ValidationError("latitude, longitude and radius_km go together.",
                                  "radius_km" if "radius_km" not in given else "latitude")

    @validates_schema
    def _rent_frequency_is_for_rent(self, data, **kwargs):
        # api.py searches for-sale when neither the param nor a pasted link says otherwise
        purpose = data.get("purpose") or (data.get("location") or {}).get("purpose") or "for-sale"
        if data.get("rent_frequency") and purpose == "for-sale":
            raise ValidationError("Only applies to purpose=for-rent.", "rent_frequency")


class PropertySchema(BaseSchema):
    property = PropertyRefField(metadata={
        "description": "listing id (17117341) or a bayut.com listing link"})
    language = _language()


class AgenciesSearchSchema(BaseSchema):
    query = QueryField(required=False, load_default=None, max_length=100, metadata={
        "description": "agency name to search for"})
    location = LocationRefField(required=False, load_default=None, metadata={
        "description": "only agencies with live listings in this location: id, slug path, place name or "
                       "bayut.com link"})
    type = ChoiceField(list(refs.AGENCY_TYPES), load_default="agency", metadata={
        "description": "agency (brokerages, default) or developer"})
    language = _language()
    page = _page()
    limit = _limit()


class AgencySchema(BaseSchema):
    agency = AgencyRefField(metadata={
        "description": "agency id (102520), slug (k-u-n-real-estate-102520) or a bayut.com agency link"})
    language = _language()


class AgencyAgentsSchema(AgencySchema):
    page = _page()
    limit = _limit()


class AgentsSearchSchema(BaseSchema):
    query = QueryField(required=False, load_default=None, max_length=100, metadata={
        "description": "agent name to search for"})
    location = LocationRefField(required=False, load_default=None, metadata={
        "description": "only agents with live listings in this location: id, slug path, place name or "
                       "bayut.com link"})
    emirate = ChoiceField(list(refs.EMIRATES), metadata={
        "description": "emirate the agent is active in: Dubai, Abu Dhabi, Sharjah, Ajman, Ras Al Khaimah, "
                       "Umm Al Quwain, Fujairah, Al Ain"})
    speaks = CommaListField(upper=False, max_items=5, metadata={
        "description": "comma list of language codes the agent speaks (en, ar, ru, hi, ur, fr, zh, ...)"})
    trubroker_only = Flag(metadata={"description": "true = TruBroker-badged agents only"})
    language = _language()
    page = _page()
    limit = _limit()


class AgentSchema(BaseSchema):
    agent = AgentRefField(metadata={
        "description": "agent id (2401468), slug (tony-yannieh-2401468) or a bayut.com agent link"})
    language = _language()


class AgentListingsSchema(AgentSchema):
    purpose = ChoiceField(list(refs.PURPOSES), metadata={
        "description": "for-sale or for-rent (default: both)"})
    sort = _sort()
    page = _page()
    limit = _limit()


class ProjectsSearchSchema(BaseSchema):
    location = LocationRefField(required=False, load_default=None, metadata={
        "description": "location id (5002), slug path (/dubai), place name or bayut.com link; omit for the "
                       "whole UAE"})
    query = QueryField(required=False, load_default=None, max_length=100, metadata={
        "description": "project or developer name to search for"})
    developer = AgencyRefField(required=False, load_default=None, metadata={
        "description": "only projects of this developer: id, slug (emaar-properties) or bayut.com link"})
    completion_status = ChoiceField(list(refs.COMPLETION_STATUSES), metadata={
        "description": "completed or under-construction (default: both)"})
    language = _language()
    page = _page()
    limit = _limit()


class ProjectSchema(BaseSchema):
    project = ProjectRefField(metadata={
        "description": "project id (2749), slug (beverly_grande-2749) or the project's bayut.com "
                       "new-projects link"})
    language = _language()


class LocationsAutocompleteSchema(BaseSchema):
    query = QueryField(max_length=100, metadata={
        "description": "start of a city, community, sub-community or building name ('marina', 'jvc')"})
    type = ChoiceField(["neighbourhood", "condo-building"], metadata={
        "description": "neighbourhood (communities and sub-communities) or condo-building (towers); "
                       "default: every type"})
    language = _language()
    limit = LimitField(default=10, max_size=MAX_PAGE_SIZE, metadata={
        "description": f"suggestions to return (default 10, max {MAX_PAGE_SIZE})"})
