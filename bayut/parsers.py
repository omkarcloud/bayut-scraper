"""Bayut raw payloads -> clean dicts. Pure functions, no I/O.

Inputs (captured 2026-11-07, bayut/fixtures/):
  * Algolia hits of bayut-production-ads-en (listing cards: `listing_card`),
    -ads-project-en (`project_record`), -agencies-en (`agency_record`),
    -agents-en (`agent_record`), -locations-en (`location_record`);
  * the server state of the www.bayut.com pages — `server_state(html)` reads
    the <script id="browserInitialState"> JSON: property page `property.data`
    + `agent.data` (`listing_details`), agency page `agency.data` +
    `agencyAgents.data` (`agency_page`), broker page `agent.data`
    (`agent_page`).

Every record carries its text in up to 15 renderings (`name`, `name_l1` …);
`language` picks the suffix (bayut/refs.LANGUAGES) and falls back to the
English field when the rendering is missing.

Skipped on purpose (internal ranking / tracking, duplicates): productScore,
productVariant, v6*Score, truBroker*Score, indyScore, popularBiScore,
verifiedScore, trucheckedScore, cityLevelScore, locationPurposeTier,
sourceID, hash, objectID, userExternalID (= ownerID), touchedAt,
_highlightResult, photoIDs (turned into links), extraFields.dldBuildingNK /
dldPropertySK (internal join keys), detailedAdCountStats and
bestDefaultFiltersForLeaderboard (the TruBroker leaderboard cube),
trubrokerAgentsProfileImageIDs, agencySg / exStatus (opaque tiers),
roles, trackID, geo_point (= geography).
"""
import json
import re
from datetime import datetime, timezone
from html import unescape

from bayut import refs

PHOTO_SIZE = "800x600"
THUMB_SIZE = "400x300"
CURRENCY = "AED"

_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>", re.I)


def html_text(value):
    """Listing copy with <br/> as newlines and other tags dropped; None when
    empty. Same rules as realestate_com_au.parsers.text, kept local so this
    module stands alone (the open-source kit ships it without other sites)."""
    if not isinstance(value, str):
        return None
    cleaned = _TAG_RE.sub("", _BR_RE.sub("\n", value))
    cleaned = unescape(cleaned).replace("\r", "")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or None


_STATE_RE = re.compile(r'<script id="browserInitialState"[^>]*>(.*?)</script>', re.S)
_TITLE_RE = re.compile(r"<title>([^<]*)</title>", re.I)


# ---- page state -------------------------------------------------------------------

def page_title(html):
    match = _TITLE_RE.search(html or "")
    return match.group(1).strip() if match else ""


def _balanced_json(text, start):
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def server_state(html):
    """The page's `__STRAT_SERVER_STATE__` value dict, or None."""
    match = _STATE_RE.search(html or "")
    if not match:
        return None
    script = match.group(1)
    start = script.find('{"value":')
    if start < 0:
        return None
    raw = _balanced_json(script, start)
    if raw is None:
        return None
    try:
        return json.loads(raw).get("value")
    except ValueError:
        return None


def _loaded(state, *path):
    """state[path...]["data"] when that slice loaded with data, else None."""
    node = state
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    if isinstance(node, dict) and node.get("data") not in (None, {}, []):
        return node["data"]
    return None


# ---- value helpers ------------------------------------------------------------------

def _get(obj, *path, default=None):
    for key in path:
        if isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list) and isinstance(key, int) and -len(obj) <= key < len(obj):
            obj = obj[key]
        else:
            return default
        if obj is None:
            return default
    return obj


def _int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        digits = value.replace(",", "").strip()
        try:
            return int(float(digits))
        except ValueError:
            return None
    return None


def _float(value, digits=None):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(str(value).replace(",", "").strip())
    except ValueError:
        return None
    return round(number, digits) if digits is not None else number


def _id(value):
    """Bayut ids are numeric strings ("17117341"): an int when they are."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    return int(s) if s.isdigit() else (s or None)


record_id = _id


def _bool(value):
    return value if isinstance(value, bool) else None


def _clean(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _iso(value):
    """Unix seconds (int/float) or an ISO string -> ISO 8601 UTC."""
    if value in (None, "", 0):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        raw = value.strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw or None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc)
        return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


def _date(value):
    iso = _iso(value)
    return iso[:10] if iso else None


def _l(obj, key, suffix):
    """Localized field with English fallback."""
    if not isinstance(obj, dict):
        return None
    if suffix:
        value = _clean(obj.get(key + suffix))
        if value not in (None, [], {}):
            return value
    return _clean(obj.get(key))


def _lang_suffix(language):
    return refs.language_suffix(language)


def photo_link(photo_id, size=PHOTO_SIZE):
    photo_id = _id(photo_id)
    if not photo_id:
        return None
    return f"https://images.bayut.com/thumbnails/{photo_id}-{size}.jpeg"


def _logo(obj):
    """An agency / developer logo: the S3 url when the record carries one,
    else the thumbnail of its image id."""
    if not isinstance(obj, dict):
        return None
    logo = obj.get("logo")
    if isinstance(logo, dict) and logo.get("url"):
        return logo["url"]
    logo_id = (logo or {}).get("id") if isinstance(logo, dict) else None
    return photo_link(logo_id or obj.get("logoID"), THUMB_SIZE)


def _coordinates(obj):
    geo = _get(obj, "geography") or _get(obj, "_geoloc") or {}
    lat, lng = _float(geo.get("lat")), _float(geo.get("lng"))
    if lat is None or lng is None:
        return None
    return {"latitude": lat, "longitude": lng}


def _area(sqm):
    sqm = _float(sqm)
    if sqm is None or sqm <= 0:
        return None
    return {"sqm": round(sqm, 2), "sqft": refs.sqm_to_sqft(sqm)}


def _phone(block):
    if not isinstance(block, dict):
        return None
    out = {
        "mobile": _clean(block.get("mobile")) or _clean(_get(block, "mobileNumbers", 0)),
        "phone": _clean(block.get("phone")) or _clean(_get(block, "phoneNumbers", 0)),
        "whatsapp": _clean(block.get("whatsapp")),
        "proxy_mobile": _clean(block.get("proxyMobile")),
        "proxy_phone": _clean(block.get("proxyPhone")),
        "mobile_numbers": [n for n in block.get("mobileNumbers") or [] if n] or None,
        "phone_numbers": [n for n in block.get("phoneNumbers") or [] if n] or None,
    }
    return out if any(v for v in out.values()) else None


def _contact_methods(block):
    if not isinstance(block, dict):
        return None
    return {
        "call": _bool(block.get("call")),
        "whatsapp": _bool(block.get("whatsapp")),
        "sms": _bool(block.get("sms")),
        "email": _bool(block.get("email")),
    }


# ---- shared sub-records -------------------------------------------------------------

def _location_node(node, suffix):
    if not isinstance(node, dict):
        return None
    return {
        "id": _id(node.get("externalID")),
        "name": _l(node, "name", suffix),
        "slug": _clean(node.get("slug")),
        "level": _int(node.get("level")),
        "type": _clean(node.get("type")),
    }


def _location(chain, suffix, purpose="for-sale", category=None, language="en"):
    """A listing's location array (UAE > city > community > building) ->
    the leaf with its chain."""
    if isinstance(chain, str):
        try:
            chain = json.loads(chain)
        except ValueError:
            chain = None
    nodes = [n for n in (_location_node(x, suffix) for x in chain or []) if n]
    if not nodes:
        return None
    nodes.sort(key=lambda n: n["level"] if n["level"] is not None else 99)
    leaf = nodes[-1]
    by_level = {n["level"]: n for n in nodes}
    return {
        "name": leaf["name"],
        "slug": leaf["slug"],
        "type": leaf["type"],
        "link": refs.location_search_link(leaf["slug"], purpose, category, language),
        "city": _get(by_level, 1, "name"),
        "community": _get(by_level, 2, "name"),
        "sub_community": _get(by_level, 3, "name") if len(nodes) > 4 or (len(nodes) == 4 and leaf["type"] != "condo-building") else None,
        "building": leaf["name"] if leaf["type"] == "condo-building" else None,
        "hierarchy": nodes,
    }


def _category(chain, suffix):
    if isinstance(chain, str):
        try:
            chain = json.loads(chain)
        except ValueError:
            chain = None
    nodes = [c for c in chain or [] if isinstance(c, dict)]
    if not nodes:
        return None
    nodes.sort(key=lambda c: c.get("level") if c.get("level") is not None else 99)
    leaf, root = nodes[-1], nodes[0]
    return {
        "id": _id(leaf.get("externalID")),
        "name": _l(leaf, "name", suffix),
        "name_singular": _l(leaf, "nameSingular", suffix),
        "slug": _clean(leaf.get("slug")),
        "group": _l(root, "name", suffix) if root is not leaf else None,
        "group_slug": _clean(root.get("slug")) if root is not leaf else None,
    }


def _agency_brief(obj, suffix, language="en", default_type="agency"):
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except ValueError:
            obj = None
    if not isinstance(obj, dict):
        return None
    external_id = obj.get("externalID") or obj.get("external_id")
    slug = _clean(obj.get("slug"))
    agency_type = _clean(obj.get("type")) or default_type
    return {
        "id": _id(external_id),
        "name": _l(obj, "name", suffix),
        "slug": slug,
        "link": refs.agency_link(slug, agency_type, language) if agency_type != "developer" else None,
        "type": agency_type,
        "logo": _logo(obj),
        "location": _l(obj, "location", suffix),
        "licenses": _licenses(obj.get("licenses")),
        "phone": _phone(obj.get("phoneNumber")),
    }


def _licenses(items):
    out = [{"authority": _clean(x.get("authority")), "number": _clean(x.get("number"))}
           for x in items or [] if isinstance(x, dict) and (x.get("number") or x.get("authority"))]
    return out or None


def _agent_brief(obj, language="en"):
    if not isinstance(obj, dict):
        return None
    slug = _clean(obj.get("slug"))
    return {
        "id": _id(obj.get("externalID") or obj.get("external_id")),
        "name": _clean(obj.get("name")),
        "slug": slug,
        "link": refs.agent_link(slug, language),
        "photo": photo_link(obj.get("user_image_id"), THUMB_SIZE),
        "is_trubroker": _bool(obj.get("isTruBroker")),
    }


def _completion(status, details):
    details = details if isinstance(details, dict) else {}
    if not status and not details:
        return None
    return {
        "status": _clean(status),
        "start_date": _date(details.get("startDate")),
        "completion_date": _date(details.get("completionDate")),
        "completion_percentage": _float(details.get("completionPercentage"), 2),
    }


def _plan_summary(items):
    first = items[0] if isinstance(items, list) and items and isinstance(items[0], dict) else None
    if not first:
        return None
    breakdown = first.get("breakdown") or {}
    return {
        "pre_handover_percentage": _float(first.get("preHandoverPercentageSum")),
        "post_handover_percentage": _float(first.get("postHandoverPercentageSum")),
        "down_payment_percentage": _float(breakdown.get("downPaymentPercentage")),
        "during_construction_percentage": _float(breakdown.get("preHandoverPercentage")),
        "handover_percentage": _float(breakdown.get("handoverPercentage")),
        "post_handover_installments_percentage": _float(breakdown.get("postHandoverPercentage")),
    }


def _installments(items):
    out = [{"description": _clean(x.get("description")), "percentage": _float(x.get("valuePercentage"))}
           for x in items or [] if isinstance(x, dict)]
    return out or None


def _payment_plans(items, suffix):
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except ValueError:
            items = None
    out = []
    for plan in items or []:
        if not isinstance(plan, dict):
            continue
        out.append({
            "title": _l(plan, "title", suffix),
            "type": _clean(plan.get("type")),
            "down_payment_percentage": _float(_get(plan, "downPayment", "valuePercentage")),
            "pre_handover_percentage": _float(plan.get("preHandoverSum")),
            "handover_percentage": _float(_get(plan, "handoverPayment", "valuePercentage")),
            "post_handover_percentage": _float(plan.get("postHandoverSum")),
            "pre_handover_installments": _installments(plan.get("preHandoverInstallments")),
            "post_handover_installments": _installments(plan.get("postHandoverInstallments")),
        })
    return out or None


def _amenities(groups, suffix):
    if isinstance(groups, str):
        try:
            groups = json.loads(groups)
        except ValueError:
            groups = None
    out = []
    for group in groups or []:
        if not isinstance(group, dict):
            continue
        items = []
        for item in group.get("amenities") or []:
            if not isinstance(item, dict):
                continue
            items.append({
                "name": _l(item, "text", suffix),
                "slug": _clean(item.get("slug")),
                "value": _clean(item.get("value")),
            })
        out.append({"group": _l(group, "text", suffix), "amenities": items})
    return out or None


def _price(hit):
    hidden = _bool(hit.get("hidePrice")) or False
    amount = _float(hit.get("price"))
    if hidden or not amount:
        amount = None
    return {
        "amount": amount,
        "currency": CURRENCY,
        "period": _clean(hit.get("rentFrequency")) if hit.get("purpose") == "for-rent" else None,
        "is_hidden": hidden,
    }


def _photos(cover, photo_ids, count):
    ids = [_id(x) for x in photo_ids or [] if _id(x)]
    cover_id = _id((cover or {}).get("id")) if isinstance(cover, dict) else None
    links = [photo_link(x) for x in ids]
    return {
        "count": _int(count) if count is not None else (len(ids) or None),
        "cover": photo_link(cover_id) or (links[0] if links else None),
        "links": links or None,
    }


def _project_brief(obj, suffix, language="en"):
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except ValueError:
            obj = None
    if not isinstance(obj, dict):
        return None
    return {
        "id": _id(obj.get("externalID")),
        "name": _l(obj, "title", suffix),
        "completion": _completion(obj.get("completionStatus"), obj.get("completionDetails")),
        # a project's agency is its developer (the brief never carries `type`)
        "developer": _agency_brief(obj.get("agency"), suffix, language, default_type="developer"),
    }


# ---- listings ---------------------------------------------------------------------------

def listing_card(hit, language="en"):
    """One listing as the ads index carries it (search / agent listings)."""
    if not isinstance(hit, dict):
        return None
    suffix = _lang_suffix(language)
    external_id = hit.get("externalID")
    purpose = _clean(hit.get("purpose"))
    category = _category(hit.get("category"), suffix)
    extra = hit.get("extraFields") if isinstance(hit.get("extraFields"), dict) else {}
    offplan = hit.get("offplanDetails") if isinstance(hit.get("offplanDetails"), dict) else {}
    verification = hit.get("verification") if isinstance(hit.get("verification"), dict) else {}
    floor_plan_id = _int(hit.get("floorPlanID"))
    return {
        "id": _id(external_id),
        "link": refs.property_link(external_id, language) if external_id else None,
        "title": _l(hit, "title", suffix),
        "purpose": purpose,
        "status": _clean(hit.get("state")),
        "reference_number": _clean(hit.get("referenceNumber")),
        "price": _price(hit),
        "bedrooms": _int(hit.get("rooms")),
        "bathrooms": _int(hit.get("baths")),
        "area": _area(hit.get("area")),
        "plot_area": _area(hit.get("plotArea")),
        "category": category,
        "location": _location(hit.get("location"), suffix, purpose or "for-sale",
                              (category or {}).get("slug"), language),
        "coordinates": _coordinates(hit),
        "completion": _completion(hit.get("completionStatus"), hit.get("completionDetails")),
        "furnishing": _clean(hit.get("furnishingStatus")),
        "sale_type": _clean(offplan.get("saleType")),
        "is_verified": _bool(hit.get("isVerified")),
        "verification": {
            "status": _clean(verification.get("status")),
            "verified_at": _iso(verification.get("verifiedAt")),
            "trucheck_at": _iso(verification.get("trucheckedAt")),
        } if verification else None,
        "features": [f for f in hit.get("adFeatures") or [] if isinstance(f, str)] or None,
        "payment_plan": _plan_summary(hit.get("paymentPlanSummaries")),
        "photos": _photos(hit.get("coverPhoto"), hit.get("photoIDs"), hit.get("photoCount")),
        "video_count": _int(hit.get("videoCount")) or 0,
        "panorama_count": _int(hit.get("panoramaCount")) or 0,
        "has_floor_plan": bool(floor_plan_id) if floor_plan_id is not None else bool(hit.get("floorPlanID")),
        "listing_tier": _clean(hit.get("product")),
        "agency": _agency_brief(hit.get("agency"), suffix, language),
        "agent": _agent_brief(hit.get("ownerAgent"), language) or (
            {"id": _id(hit.get("ownerID")), "name": _clean(hit.get("contactName")), "slug": None,
             "link": None, "photo": None, "is_trubroker": None} if hit.get("ownerID") else None),
        "contact": {
            "name": _clean(hit.get("contactName")),
            "phone": _phone(hit.get("phoneNumber")),
            "methods": _contact_methods(hit.get("contactMethodAvailability")),
        },
        "project": _project_brief(hit.get("project"), suffix, language) if hit.get("project") else None,
        "has_sale_transactions": _bool(extra.get("hasSaleTransactions")),
        "has_rent_transactions": _bool(extra.get("hasRentTransactions")),
        "created_at": _iso(hit.get("createdAt")),
        "updated_at": _iso(hit.get("updatedAt")),
        "reactivated_at": _iso(hit.get("reactivatedAt")),
    }


def _media_list(items, kind):
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except ValueError:
            items = None
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        if kind == "photo":
            out.append({
                "id": _id(item.get("id")),
                "link": photo_link(item.get("id")),
                "title": _clean(item.get("title")),
                "order": _int(item.get("orderIndex")),
            })
        else:
            out.append({k: v for k, v in {
                "id": _id(item.get("id")),
                "title": _clean(item.get("title")),
                "link": _clean(item.get("url")) or _clean(item.get("link")),
                "host": _clean(item.get("host")),
                "type": _clean(item.get("type")) or _clean(item.get("typeTitle")),
                "image": photo_link(item.get("image_id") or item.get("imageID") or item.get("id"))
                if kind in ("floor_plan", "panorama") else None,
            }.items() if v is not None or k in ("id", "title", "link")})
    return out or None


def listing_details(state, language="en"):
    """The property page: the full record of `property.data` plus the
    listing agent of `agent.data`. None when the page carried no listing."""
    suffix = _lang_suffix(language)
    data = _loaded(state, "property")
    if not isinstance(data, dict) or not data.get("externalID"):
        return None
    record = listing_card(data, language)
    offplan = data.get("offplanDetails") if isinstance(data.get("offplanDetails"), dict) else {}
    description = data.get("description")
    photo_items = _media_list(data.get("photos"), "photo")
    record.update({
        "description": html_text(description),
        "description_html": _clean(description),
        "is_description_translated": _bool(data.get("descriptionTranslated")),
        "amenities": _amenities(data.get("amenities"), suffix),
        "photos": {
            **record["photos"],
            "links": record["photos"]["links"] or [p["link"] for p in photo_items or [] if p.get("link")] or None,
            "items": photo_items,
        },
        "floor_plans": _media_list(data.get("floorPlans"), "floor_plan"),
        "panoramas": _media_list(data.get("panoramas"), "panorama"),
        "videos": _media_list(data.get("videos"), "video"),
        "payment_plans": _payment_plans(data.get("paymentPlans"), suffix),
        "offplan": {
            "sale_type": _clean(offplan.get("saleType")),
            "original_price": _float(offplan.get("originalPrice")),
            "paid_price": _float(offplan.get("paidPrice")),
            "dld_waiver": offplan.get("dldWaiver"),
        } if offplan else None,
        "is_studio": _bool(data.get("isStudio")),
        "is_developer_listing": _bool(data.get("isDeveloper")),
        "has_exact_coordinates": _bool(data.get("hasExactGeography")),
        "approved_at": _iso(data.get("approvedAt")),
    })
    agency = data.get("agency")
    if isinstance(agency, str):
        try:
            agency = json.loads(agency)
        except ValueError:
            agency = None
    if isinstance(agency, dict):
        record["agency"] = {**(record["agency"] or {}), "created_at": _iso(agency.get("createdAt")),
                           "is_active": _bool(agency.get("active")), "tier": _clean(agency.get("product"))}
    agent = _loaded(state, "agent")
    if isinstance(agent, dict):
        record["agent"] = agent_record(agent, language)
    return record


# ---- agencies -----------------------------------------------------------------------------

def agency_record(obj, language="en", description=None):
    """One agency / developer as the agencies index (or an agency page's
    `agency.data`, same shape) carries it."""
    if not isinstance(obj, dict):
        return None
    suffix = _lang_suffix(language)
    stats = obj.get("stats") if isinstance(obj.get("stats"), dict) else {}
    agent_stats = obj.get("agentStats") if isinstance(obj.get("agentStats"), dict) else {}
    agency_type = _clean(obj.get("type")) or "agency"
    slug = _clean(obj.get("slug"))
    sale, rent = _int(stats.get("adsSaleCount")), _int(stats.get("adsRentCount"))
    total = _int(stats.get("adsCount"))
    if total is None and (sale is not None or rent is not None):
        total = (sale or 0) + (rent or 0)
    return {
        "id": _id(obj.get("externalID")),
        "name": _l(obj, "name", suffix),
        "slug": slug,
        "link": refs.agency_link(slug, agency_type, language) if agency_type != "developer" else None,
        "type": agency_type,
        "description": html_text(description) if description else None,
        "logo": _logo(obj),
        "location": _l(obj, "location", suffix),
        "locations": [n for n in (_location_node(x, suffix) for x in obj.get("locations") or []) if n] or None,
        "licenses": _licenses(obj.get("licenses")),
        "phone": _phone(obj.get("phoneNumber")),
        "contact_methods": _contact_methods(obj.get("contactMethodAvailability")),
        "agents_count": _int(obj.get("agentsCount")) if obj.get("agentsCount") is not None
        else _int(agent_stats.get("agentCount")),
        "trubroker_agents_count": _int(agent_stats.get("trubrokerAgentCount")) if agent_stats
        else _int(stats.get("trubrokerAgentCount")),
        "listings": {"total": total, "for_sale": sale, "for_rent": rent},
        "listing_categories": [c for c in (stats.get("categoryTypes" + suffix) or stats.get("categoryTypes") or [])
                               if isinstance(c, str)] or None,
        "service_areas_count": _int(stats.get("serviceAreasCount")) if stats.get("serviceAreasCount") is not None
        else (len(stats["serviceAreas"]) if isinstance(stats.get("serviceAreas"), list) else None),
        "purposes": [p for p in obj.get("purpose") or stats.get("purposes") or [] if isinstance(p, str)] or None,
        "languages": [c for c in obj.get("language_codes") or agent_stats.get("languageCodes") or []
                      if isinstance(c, str)] or None,
        "specialities": [c for c in obj.get("speciality_codes") or [] if isinstance(c, str)] or None,
        "is_featured": _bool(obj.get("isFeatured")),
        "is_elite": _bool(obj.get("eliteStatus")),
        "tier": _clean(obj.get("product")),
        "is_active": _bool(obj.get("active")),
        "created_at": _iso(obj.get("createdAt")),
    }


def agency_page(state, language="en"):
    """The /companies/<slug>/ page: the agency record with its description,
    plus the first page of its agents. None when the page carried no agency."""
    data = _loaded(state, "agency")
    if not isinstance(data, dict) or not data.get("externalID"):
        return None
    record = agency_record(data, language, description=data.get("description"))
    roster = _loaded(state, "agencyAgents")
    hits = roster.get("hits") if isinstance(roster, dict) else None
    record["agents_preview"] = [a for a in (agent_record(h, language) for h in hits or []) if a] or None
    return record


# ---- agents -------------------------------------------------------------------------------

def agent_record(obj, language="en"):
    """One agent as the agents index carries it, or as a page's `agent.data`
    (camel + snake keys; the page adds experience, nationality, BRN, social
    links)."""
    if not isinstance(obj, dict):
        return None
    suffix = _lang_suffix(language)
    stats = obj.get("stats") if isinstance(obj.get("stats"), dict) else {}
    slug = _clean(obj.get("slug"))
    areas = obj.get("service_areas" + suffix) or obj.get("service_areas") or []
    area_ids = obj.get("service_areas_external_ids") or []
    service_areas = []
    for i, name in enumerate(areas):
        if not isinstance(name, str):
            continue
        service_areas.append({"id": _id(area_ids[i]) if i < len(area_ids) else None, "name": name})
    agency = obj.get("agency") if isinstance(obj.get("agency"), dict) else None
    social = obj.get("social_media") if isinstance(obj.get("social_media"), dict) else None
    phone_block = {
        "mobile": obj.get("cell"),
        "phone": obj.get("phone"),
        "whatsapp": obj.get("whatsapp"),
        "proxyMobile": obj.get("proxy_mobile"),
        "proxyPhone": obj.get("proxy_phone"),
        "mobileNumbers": obj.get("cell_numbers"),
        "phoneNumbers": obj.get("phone_numbers"),
    }
    phone = _phone(phone_block)
    if phone is not None or obj.get("proxy_whatsapp"):
        phone = {**(phone or {}), "proxy_whatsapp": _clean(obj.get("proxy_whatsapp"))}
    return {
        "id": _id(obj.get("externalID") or obj.get("external_id")),
        "name": _l(obj, "name", suffix),
        "slug": slug,
        "link": refs.agent_link(slug, language),
        "photo": _clean(obj.get("user_image")) or photo_link(obj.get("user_image_id"), THUMB_SIZE),
        "about": _clean(_l(obj, "about_user", suffix)),
        "email": _clean(obj.get("email")),
        "phone": phone,
        "contact_methods": _contact_methods(obj.get("contactMethodAvailability")),
        "agency": _agency_brief(agency, suffix, language) if agency else None,
        "is_trubroker": _bool(obj.get("isTruBroker")),
        "badges": {
            "is_highly_responsive": _bool(obj.get("isHighlyResponsive")),
            "is_quality_lister": _bool(obj.get("isQualityLister")),
            "has_badges": _bool(obj.get("hasBadges")),
        },
        "experience_points": _int(obj.get("totalXP")),
        "experience_years": _int(obj.get("experience")),
        "nationality": _l(obj, "country", suffix),
        "active_emirate": _clean(obj.get("activeInEmirate")),
        "languages": [x for x in obj.get("user_langs" + suffix) or obj.get("user_langs") or []
                      if isinstance(x, str)] or None,
        "language_codes": [x for x in obj.get("language_codes") or [] if isinstance(x, str)] or None,
        "specialities": [x for x in obj.get("specialities" + suffix) or obj.get("specialities") or []
                         if isinstance(x, str)] or None,
        "speciality_codes": [x for x in obj.get("speciality_codes") or [] if isinstance(x, str)] or None,
        "service_areas": service_areas or None,
        "listings": {
            "total": _int(stats.get("adsCount")),
            "for_sale": _int(obj.get("sale_count")),
            "for_rent": _int(obj.get("rent_count")),
            "daily_rent": _int(obj.get("daily_rent_count")),
            "trucheck_count": _int(obj.get("trucheck_count")) if obj.get("trucheck_count") is not None
            else _int(stats.get("trucheckCount")),
            "check_count": _int(obj.get("check_count")) if obj.get("check_count") is not None
            else _int(stats.get("checkCount")),
        },
        "brn_number": _clean(obj.get("brnNumber")),
        "bln_number": _clean(obj.get("blnNumber")),
        "social_media": {k: v for k, v in social.items() if isinstance(v, str) and v} or None
        if social else None,
        "status": _clean(obj.get("state")),
        "is_profile_complete": _bool(obj.get("isProfileCompleted")) if "isProfileCompleted" in obj
        else _bool(obj.get("isComplete")),
    }


def agent_page(state, language="en"):
    """The /brokers/<slug>/ page: the agent record plus the claimed-deals
    summary the page shows. None when the page carried no agent."""
    data = _loaded(state, "agent")
    if not isinstance(data, dict) or not (data.get("external_id") or data.get("externalID")):
        return None
    record = agent_record(data, language)
    summary = _get(_loaded(state, "claimedDealsSummary"), "summary")
    counts = _loaded(state, "claimedDealsCounts")
    record["claimed_deals"] = {
        "approved": _int(_get(counts, "approved")),
        "pending": _int(_get(counts, "pending")),
        "for_sale_count": _int(_get(summary, "count", "forSale")),
        "for_rent_count": _int(_get(summary, "count", "forRent")),
        "for_sale_value": _float(_get(summary, "price", "forSale")),
        "for_rent_value": _float(_get(summary, "price", "forRent")),
        "currency": CURRENCY,
    } if isinstance(summary, dict) or isinstance(counts, dict) else None
    return record


# ---- projects -----------------------------------------------------------------------------

def _categories(chains, suffix):
    out = []
    for chain in chains or []:
        cat = _category(chain, suffix)
        if cat and cat not in out:
            out.append(cat)
    return out or None


def project_record(hit, language="en"):
    """One new project as the projects index carries it."""
    if not isinstance(hit, dict):
        return None
    suffix = _lang_suffix(language)
    location = _location(hit.get("location"), suffix, "for-sale", None, language)
    leaf_slug = (location or {}).get("slug")
    description = hit.get("description" + suffix) if suffix else None
    description = description or hit.get("description")
    developer = _agency_brief(hit.get("agency"), suffix, language)
    documents = []
    for doc in hit.get("documents") or []:
        if not isinstance(doc, dict):
            continue
        title = doc.get("title") if isinstance(doc.get("title"), dict) else {"en": doc.get("title")}
        documents.append({
            "title": _clean(title.get(language)) or _clean(title.get("en")),
            "type": _clean(doc.get("tag")),
            "link": _clean(doc.get("fileSource")),
            "is_active": _bool(doc.get("isActive")),
        })
    rooms = [r for r in hit.get("unitRooms") or [] if isinstance(r, (int, float))]
    baths = [b for b in hit.get("unitBaths") or [] if isinstance(b, (int, float))]
    price = _float(hit.get("price"))
    return {
        "id": _id(hit.get("externalID")),
        "name": _l(hit, "title", suffix),
        "slug": _clean(hit.get("slug")),
        "link": refs.project_link(leaf_slug, language),
        "status": _clean(hit.get("state")),
        "purpose": _clean(hit.get("purpose")),
        "developer": developer,
        "location": location,
        "coordinates": _coordinates(hit),
        "category": _category(hit.get("category"), suffix),
        "unit_categories": _categories(hit.get("unitCategories") or hit.get("additionalCategories"), suffix),
        "unit_bedrooms": sorted({int(r) for r in rooms}) or None,
        "unit_bathrooms": sorted({int(b) for b in baths if b}) or None,
        "starting_price": {"amount": price if price and not hit.get("hidePrice") else None,
                           "currency": CURRENCY, "is_hidden": _bool(hit.get("hidePrice")) or False},
        "starting_area": _area(hit.get("area")),
        "completion": _completion(hit.get("completionStatus"), hit.get("completionDetails")),
        "location_completion_status": _clean(hit.get("locationCompletionStatus")),
        "payment_plan": _plan_summary(hit.get("paymentPlanSummaries")),
        "amenities": _amenities(hit.get("amenities"), suffix),
        "description": html_text(description),
        "description_html": _clean(description),
        "documents": documents or None,
        "photos": _photos(hit.get("coverPhoto"), hit.get("photoIDs"), None),
        "listings_count": _int(hit.get("propertyAdCount")),
        "has_listings": _bool(hit.get("hasPropertyAds")),
        "is_sold_out": _bool(hit.get("hasAllPropertyAdsCompleted")),
        "is_developer_owned": _bool(hit.get("isProjectOwned")),
        "contact_methods": _contact_methods(hit.get("contactMethodAvailability")),
        "created_at": _iso(hit.get("createdAt")),
        "updated_at": _iso(hit.get("updatedAt")),
    }


# ---- locations ----------------------------------------------------------------------------

def location_record(hit, language="en"):
    """One place as the locations index carries it."""
    if not isinstance(hit, dict):
        return None
    suffix = _lang_suffix(language)
    slug = _clean(hit.get("slug"))
    chain = [n for n in (_location_node(x, suffix) for x in hit.get("hierarchy") or []) if n]
    by_level = {n["level"]: n for n in chain}
    return {
        "id": _id(hit.get("externalID")),
        "name": _l(hit, "name", suffix),
        "slug": slug,
        "link": refs.location_search_link(slug, "for-sale", "residential", language),
        "type": _clean(hit.get("type")),
        "level": _int(hit.get("level")),
        "city": _get(by_level, 1, "name"),
        "hierarchy": chain or None,
        "coordinates": _coordinates(hit),
        "listings_count": _int(hit.get("adCount")),
        "aliases": [a for a in hit.get("aliases") or [] if isinstance(a, str)] or None,
        "has_children": _bool(hit.get("hasChildren")),
        "completion_status": _clean(hit.get("completionStatus")),
    }


def location_internal_id(hit):
    """The index's own row id (agency / agent searches filter on it)."""
    return _int(hit.get("id")) if isinstance(hit, dict) else None


# ---- paging ------------------------------------------------------------------------------

def pagination(answer, page, limit):
    """Algolia's page / nbPages / nbHits -> the API's pagination block (the
    index caps paging at 50,000 hits, which nbPages already reflects)."""
    total_pages = _int(answer.get("nbPages"))
    total = _int(answer.get("nbHits"))
    return {
        "page": page,
        "items_per_page": limit,
        "total_pages": total_pages if total_pages is not None else 0,
        "total_count": total,
    }
