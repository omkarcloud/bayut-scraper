"""Configuration for the Bayut Scraper. Everything can be set with an
environment variable; the defaults work out of the box inside the UAE.

    PORT         port the API listens on (default 8000)
    BAYUT_PROXY  proxy URL for every request, e.g. http://user:pass@host:port
                 (default: none — direct). bayut.com serves its pages and its
                 search only to connections in the UAE: from anywhere else its
                 own bot shield answers a "Security check" page. Outside the
                 UAE, set a UAE residential proxy here (any provider's `ae`
                 country exit); every retry after a block then leaves through
                 a fresh IP.

Everything else below is a plain constant with a working default — edit it
here if you need to.
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors and blocks (every request).
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, multiplied by the attempt number

BAYUT_PROXY = os.environ.get("BAYUT_PROXY") or None


def bayut_proxy():
    """The proxy for one curl session (None = direct)."""
    return os.environ.get("BAYUT_PROXY") or None
