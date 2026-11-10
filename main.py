"""Use the scraper straight from Python — no server needed.

    python main.py

Every function returns the same JSON the API does (paged endpoints carry a
`pagination` block instead of next / previous links); results are written
to output/*.json. The schemas fill in every default, exactly as the API does.
Outside the UAE, set BAYUT_PROXY to a UAE residential proxy first (config.py).
"""
import json
import os

from bayut import api, schemas

os.makedirs("output", exist_ok=True)


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


def params(schema_cls, **query):
    """Validate a query exactly like the API: defaults filled, links resolved."""
    return schema_cls().load(query)


if __name__ == "__main__":
    # a listing id or any bayut.com listing link: a 3-bedroom in Burj Khalifa
    save("property_15783263.json", api.property_details(
        **params(schemas.PropertySchema, property="15783263")))

    # 25 listings per page; a place name, location id, slug path or search link
    save("search_palm_jumeirah_villas.json", api.properties_search(
        **params(schemas.PropertiesSearchSchema, location="Palm Jumeirah", purpose="for-sale", category="villas")))

    # an agent id, slug or any bayut.com agent link
    save("agent_2512279.json", api.agent_details(
        **params(schemas.AgentSchema, agent="2512279")))
