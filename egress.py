"""The one network helper the bayut module needs: the Accept-Language its
sessions send. bayut.com only serves UAE connections, so every session
announces the list a desktop Chrome in the UAE sends — on your own
connection or on BAYUT_PROXY alike."""

UAE = "ar-AE,ar;q=0.9,en-US;q=0.8,en;q=0.7"


def site_accept_language(site=None):
    return UAE


def accept_language(proxy=None, country=None):
    return UAE
