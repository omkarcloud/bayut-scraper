"""Bayut transport: plain curl_cffi with browser-impersonated TLS. No
browser, no cookies, no login. Egress: one sticky UAE residential exit per
thread session (config.bayut_proxy(), knob BAYUT_EXIT); a retryable failure
drops the session, so the retry rides a fresh exit.

Bayut's own bot shield, "Humbucker" (/.humbucker/clients/browser.js; the
site's bundle calls it the "Humbucker Browser Client", no third-party
vendor named anywhere), fronts www.bayut.com AND its Algolia proxy host. Verified 2026-11-07 with
curl_cffi chrome / safari17_0 / edge101 (all identical):
  * the pod's own Google Cloud IP and every datacenter proxy exit get
    the 190 KB "Security check | Bayut" page (HTTP 503) on every surface;
  * residential exits in the US / GB / IN / SA / DE / SG get the 580 KB
    JS-challenge shell (HTTP 200, <script src=".../browser.js?client=hb-challenge">);
  * residential exits in the UAE ("ae") get the real pages and the real
    Algolia answers, no cookie or token needed (pod probe 2026-11-07,
    scrapers-patchright-depl-74fddd498d-rfmk6; table in config.py).
  * TRAP: an HTML GET that carries an `Origin` header (or the x-algolia-*
    headers) is 503 even on a UAE exit, and so is an Algolia POST that
    carries `accept: application/json` (the browser client sends `*/*`) —
    the page headers and the Algolia headers below are two separate,
    minimal sets for that reason.
  * /api/* (transactions, price trends, phone-number lookups) is 503 on
    every exit without the browser-minted humbucker token: not used here.

Upstream surfaces, all on UAE residential exits:

  ALGOLIA  POST https://search-dsn.bayut.com/1/indexes/<index>/query
           {"params": "<url-encoded Algolia params>"} with the site's
           browser key (x-algolia-application-id LL8IZ711CS, x-algolia-api-key
           strat_a5e4568c, both from window.CONFIG.runtime of any page).
           Indexes: bayut-production-ads-en (+ date / price / verified
           replicas), -ads-project-en, -agencies-en, -agents-en,
           -locations-en. hitsPerPage up to 1000, paginationLimitedTo
           50,000 hits (a page past that cap answers an empty hit list).
           403 "Invalid Application-ID or API key" = the key rotated
           (BayutUpstreamError, not retried into a fresh exit for nothing);
           404 "Index ... does not exist" = index renamed.
  PAGE     GET /property/details-<id>.html, /companies/<slug>/,
           /brokers/<slug>/ (optionally under /ar/, /zh/ ... prefixes) —
           server-rendered pages whose <script id="browserInitialState">
           carries the full record (bayut/parsers.server_state). An unknown
           id is a real HTTP 404 ("Not found | bayut").

Failure taxonomy (scraper_errors, mapped to HTTP by route_glue):
  BayutUpstreamError  transport failure / 5xx / rotated key   — retryable
  BayutBlocked        503 security check / challenge shell     — retryable
  BayutBadRequest     Algolia 400 (a bad filter expression)    — never retried
  BayutNotFound       404 page / unknown record                — never retried
"""
import json
import os
import re
import sys
import threading
import time
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import egress
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError
from bayut.refs import SITE
from scraper_utils import retry, sessions
from scraper_utils.pages import page_title as _page_title

IMPERSONATE = "chrome"
PAGE_TIMEOUT = 40      # agency pages are ~900 KB
ALGOLIA_TIMEOUT = 20

ALGOLIA_HOST = "https://search-dsn.bayut.com"
ALGOLIA_APP_ID = "LL8IZ711CS"
ALGOLIA_API_KEY = "strat_a5e4568c"   # window.CONFIG.runtime.ALGOLIA_BROWSER_SEARCH_API_KEY, 2026-11-07

PAGE_HEADERS = {
    "accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "accept-language": egress.site_accept_language("bayut"),
    "upgrade-insecure-requests": "1",
}
# No `accept` here on purpose: the browser's Algolia client sends curl's
# default `*/*`, and an explicit `accept: application/json` is answered
# with the 503 security check even on a UAE exit (local run 2026-11-07).
ALGOLIA_HEADERS = {
    "accept-language": egress.site_accept_language("bayut"),
    "content-type": "application/json",
    "x-algolia-application-id": ALGOLIA_APP_ID,
    "x-algolia-api-key": ALGOLIA_API_KEY,
    "origin": SITE,
    "referer": SITE + "/",
}

_TITLE_RE = re.compile(r"<title>([^<]*)</title>", re.I)
# Not the bare "humbucker": every real page loads
# /.humbucker/clients/browser.js?client=strat-bayut-production in its head
# (5.6-10 KB in, fixtures 2026-11-07); the challenge shell is the one whose
# client is hb-challenge, the 503 page the one titled "Security check".
_CHALLENGE_MARKERS = ("hb-challenge", "Security check | Bayut")


class BayutUpstreamError(UpstreamError):
    """Transport failure, 5xx, or a rotated search key — retryable."""


class BayutBlocked(BayutUpstreamError, Blocked):
    """Humbucker security check / challenge shell where a page or JSON was expected — retryable."""


class BayutBadRequest(BadRequest):
    """Algolia rejected the query — never retried."""


class BayutNotFound(NotFound):
    """Listing / agency / agent / project does not exist — never retried."""


# One session per cheroot worker thread: a curl handle must not be shared
# across threads; these calls are stateless so thread-lifetime sessions with
# keep-alive are enough.
_local = threading.local()


def _session():
    return sessions.thread_session(_local, lambda: sessions.curl_session(
        IMPERSONATE, proxy_fn=config.bayut_proxy, accept_language=egress.accept_language))


def _drop_session():
    """Close the thread's session so the retry rides a fresh exit."""
    sessions.drop(_local)


def _retrying(fn):
    """Run fn() under the shared retry policy (BayutUpstreamError only;
    NotFound / BadRequest surface immediately)."""
    return retry.run(fn, config, BayutUpstreamError, lambda e: _drop_session())


def _is_challenge(text):
    head = (text or "")[:6000]
    return any(marker in head for marker in _CHALLENGE_MARKERS)


def _headers(base, sess):
    """The session's own Accept-Language (the exit's) over the module set."""
    headers = dict(base)
    headers["accept-language"] = sess.headers.get("accept-language") or headers["accept-language"]
    return headers


# ---- pages ---------------------------------------------------------------------------

def fetch_page(path, label):
    """GET a server-rendered www.bayut.com page -> HTML text. 404 ->
    BayutNotFound; a security check / challenge shell -> BayutBlocked."""
    def once():
        sess = _session()
        try:
            resp = sess.get(SITE + path, headers=_headers(PAGE_HEADERS, sess), timeout=PAGE_TIMEOUT)
        except Exception as e:
            raise BayutUpstreamError(f"request failed: {type(e).__name__}: {e}")
        if resp.status_code == 404:
            raise BayutNotFound(f"{label} not found")
        text = resp.text
        if resp.status_code in (401, 403, 429, 503) or _is_challenge(text):
            raise BayutBlocked(f"HTTP {resp.status_code} security check for {label}")
        if resp.status_code != 200:
            raise BayutUpstreamError(f"HTTP {resp.status_code} for {label}")
        if "browserInitialState" not in text:
            raise BayutUpstreamError(f"{label}: page carried no state ({_page_title(text)!r})")
        return text
    return _retrying(once)


def fetch_property_page(external_id, language="en"):
    from bayut.refs import language_prefix
    return fetch_page(f"{language_prefix(language)}/property/details-{external_id}.html",
                      f"listing {external_id}")


def fetch_agency_page(slug, language="en"):
    """The /companies/<slug>/ page; the site resolves the trailing id, so
    "x-<id>" works when only the id is known."""
    from bayut.refs import language_prefix
    return fetch_page(f"{language_prefix(language)}/companies/{slug}/", f"agency {slug}")


def fetch_agent_page(slug, language="en"):
    """The /brokers/<slug>/ page (the full slug is required: "x-<id>" is 404)."""
    from bayut.refs import language_prefix
    return fetch_page(f"{language_prefix(language)}/brokers/{slug}/", f"agent {slug}")


# ---- Algolia ---------------------------------------------------------------------------

def algolia_params(**params):
    """Algolia's url-encoded "params" string from keyword args; None values
    are skipped, lists become repeated keys."""
    clean = {}
    for key, value in params.items():
        if value is None or value == "" or value == []:
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        clean[key] = value
    return urlencode(clean, doseq=True)


def _check_algolia(resp, label):
    text = resp.text
    if resp.status_code in (503,) or (_is_challenge(text) and not text.lstrip().startswith("{")):
        raise BayutBlocked(f"HTTP {resp.status_code} security check for {label}")
    try:
        payload = resp.json()
    except Exception:
        if resp.status_code == 200:
            raise BayutBlocked(f"non-JSON search answer for {label}: {text[:100]!r}")
        raise BayutUpstreamError(f"HTTP {resp.status_code} for {label}: {text[:100]!r}")
    if resp.status_code == 400:
        raise BayutBadRequest(payload.get("message") or "bad search request")
    if resp.status_code == 403:
        # the browser key rotated (or an index this key may not read)
        raise BayutUpstreamError(f"search key refused for {label}: {payload.get('message')}")
    if resp.status_code == 404:
        raise BayutUpstreamError(f"search index missing for {label}: {payload.get('message')}")
    if resp.status_code != 200:
        raise BayutUpstreamError(f"HTTP {resp.status_code} for {label}: {payload.get('message')}")
    return payload


def algolia_query(index, params, label=None):
    """POST one query to an index -> the Algolia answer dict (hits, nbHits,
    page, nbPages, hitsPerPage, ...). `params` is the url-encoded string
    from algolia_params()."""
    label = label or f"search {index}"

    def once():
        sess = _session()
        try:
            resp = sess.post(f"{ALGOLIA_HOST}/1/indexes/{index}/query",
                             data=json.dumps({"params": params}),
                             headers=_headers(ALGOLIA_HEADERS, sess), timeout=ALGOLIA_TIMEOUT)
        except Exception as e:
            raise BayutUpstreamError(f"request failed: {type(e).__name__}: {e}")
        payload = _check_algolia(resp, label)
        if not isinstance(payload, dict) or "hits" not in payload:
            raise BayutUpstreamError(f"unexpected search payload for {label}: {str(payload)[:120]}")
        return payload
    return _retrying(once)


def algolia_queries(requests_, label="multi search"):
    """POST several queries at once ([{indexName, params}]) -> the list of
    answers in the same order."""
    def once():
        sess = _session()
        try:
            resp = sess.post(f"{ALGOLIA_HOST}/1/indexes/*/queries",
                             data=json.dumps({"requests": requests_}),
                             headers=_headers(ALGOLIA_HEADERS, sess), timeout=ALGOLIA_TIMEOUT)
        except Exception as e:
            raise BayutUpstreamError(f"request failed: {type(e).__name__}: {e}")
        payload = _check_algolia(resp, label)
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise BayutUpstreamError(f"unexpected multi-search payload: {str(payload)[:120]}")
        return results
    return _retrying(once)
