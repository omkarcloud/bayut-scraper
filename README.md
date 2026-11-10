# 🏙️ Bayut Scraper

Bayut Scraper is a **free and open-source** scraper that gets you **unlimited** detailed Bayut property data for free.

## ✨ What Can I Get?

- 🏠 **Full details on 600K+ UAE listings** — price, size, every photo, amenities, payment plans & the agent's email
- 🔍 **Search the whole UAE your way** — any city, community or tower, 20+ filters, sale or rent
- 👤 **20K+ agents & 13K+ agencies** — emails, phones, WhatsApp, RERA licences, languages & listing counts
- 🏗️ **3,000+ new projects** — developer, starting price, unit mix, handover date & payment plan

## 🎥 Example: A Full Bayut Listing

```json
{
  "id": 15783263,
  "link": "https://www.bayut.com/property/details-15783263.html",
  "title": "Stunning Views | Luxury Living | Vacant | Premium 3 B/R",
  "purpose": "for-sale",
  "price": { "amount": 8500000.0, "currency": "AED", "period": null, "is_hidden": false },
  "bedrooms": 3,
  "bathrooms": 5,
  "area": { "sqm": 216.74, "sqft": 2332.97 },
  "location": { "name": "Burj Khalifa", "city": "Dubai", "community": "Downtown Dubai", "building": "Burj Khalifa" },
  "coordinates": { "latitude": 25.197159, "longitude": 55.274491 },
  "is_verified": true,
  "verification": { "status": "verified", "verified_at": "2026-10-28T14:05:24Z" },
  "photos": { "count": 27, "cover": "https://images.bayut.com/thumbnails/851541762-800x600.jpeg" },
  "description": "Boville Real Estate LLC is proud to present this exceptional 3-bedroom apartment in the iconic Burj Khalifa, located in the heart of Downtown Dubai...",
  "amenities": [
    { "group": "Health and Fitness", "amenities": [{ "name": "Gym or Health Club" }, { "name": "Swimming Pool" }] }
  ],
  "agent": {
    "id": 2556879,
    "name": "Mohamad Kraidly",
    "email": "m.kraidly@boville.ae",
    "phone": { "mobile": "+971562403464", "whatsapp": "+971562403464" },
    "languages": ["English", "Arabic"],
    "is_trubroker": true
  },
  "agency": { "id": 9734, "name": "Boville Real Estate", "licenses": [{ "authority": "RERA", "number": "20871" }] }
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free Bayut Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/bayut-scraper
cd bayut-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

Bayut only serves connections from the UAE — everywhere else its bot protection answers a "Security check" page. Outside the UAE? Start it on a UAE residential proxy instead:
```bash
BAYUT_PROXY=http://user:pass@host:port python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/properties/details?property=15783263"
```

```json
{
  "id": 15783263,
  "title": "Stunning Views | Luxury Living | Vacant | Premium 3 B/R",
  "purpose": "for-sale",
  "price": { "amount": 8500000.0, "currency": "AED", "period": null, "is_hidden": false },
  "bedrooms": 3,
  "bathrooms": 5,
  "area": { "sqm": 216.74, "sqft": 2332.97 },
  "location": { "name": "Burj Khalifa", "city": "Dubai", "community": "Downtown Dubai", "building": "Burj Khalifa" },
  "coordinates": { "latitude": 25.197159, "longitude": 55.274491 },
  "is_verified": true,
  "photos": { "count": 27, "cover": "https://images.bayut.com/thumbnails/851541762-800x600.jpeg" },
  "agent": { "id": 2556879, "name": "Mohamad Kraidly", "email": "m.kraidly@boville.ae", "is_trubroker": true },
  "agency": { "id": 9734, "name": "Boville Real Estate", "licenses": [{ "authority": "RERA", "number": "20871" }] }
}
```

All 11 endpoints are now live at `http://localhost:8000`.

## 📚 Endpoints

11 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Property Details | `/properties/details` | Everything about one listing, plus the agent's email and phones |
| Autocomplete Locations | `/locations/autocomplete` | Location IDs and slugs for any city, community or tower |
| Search Properties | `/properties/search` | 25 listings per page with 20+ filters and 5 sort orders |
| Search Agents | `/agents/search` | Agents by name, area or language, with emails and phones |
| Agent Details | `/agents/details` | Full agent profile: email, WhatsApp, BRN, languages, badges |
| Agent Listings | `/agents/listings` | Every live listing of one agent, 25 per page |
| Search Agencies | `/agencies/search` | Agencies or developers by name or area, with licences |
| Agency Details | `/agencies/details` | Profile, RERA licences, phones, agent and listing counts |
| Agency Agents | `/agencies/agents` | Every agent at one agency with contacts, 25 per page |
| Search New Projects | `/projects/search` | Off-plan projects with starting prices and payment plans |
| New Project Details | `/projects/details` | Developer, unit mix, handover date, payment plan and brochure |

## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-bayut-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-bayut-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-bayut-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/properties/details",
    params={"property": "15783263"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about Bayut Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://www.omkar.cloud/l/bayut-scraper-github-whatsapp)

[![Ask Us by Email about Bayut Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=Help%20with%20Bayut%20Scraper%20API&body=I%20need%20help%20using%20the%20Bayut%20Scraper%20API.)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website
- [**AliExpress Scraper**](https://www.omkar.cloud/tools/aliexpress-scraper-api) — live product details, SKU variants, stock & shipping
- [**Booking Scraper**](https://www.omkar.cloud/tools/booking-scraper) — Booking.com hotels: prices, ratings, rooms & amenities
- [**Etsy Scraper**](https://www.omkar.cloud/tools/etsy-scraper) — Etsy products: prices, discounts, shops & variations

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/bayut-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/bayut-scraper)
