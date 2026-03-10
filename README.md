# 🕉️ Panchanga REST API

Accurate, timezone-aware Vedic Panchanga calculations using **Django REST Framework** and **Swiss Ephemeris**.

This API computes:

- Tithi
- Nakshatra (with start/end times)
- Yoga
- Karana
- Lagna (Ascendant)
- Sidereal planetary positions (Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu)
- Sunrise & Sunset (Swiss Ephemeris precision)
- Ayanamsa (Lahiri mode by default)

---

## 🚀 Features

- Fully timezone‑aware (using `pytz`)
- Swiss Ephemeris–backed astronomical calculations
- Sidereal zodiac calculations
- Nakshatra boundary detection using bisection algorithm
- Clean API output with both Sanskrit & English rashi names
- Auto‑computed Rahu–Ketu positions
- Configurable city database with latitude, longitude & timezone

---

## 📌 API Endpoint

### `POST /panchanga/`

#### Example Request

```json
{
	"date": "10/03/2026",
	"time": "14:30",
	"location": "bangalore"
}
```

#### Optional fields

```json
{
	"ayanamsa": "lahiri | raman | kp | fagan | yukteswar",
	"ayanamsa_offset": 0.883,
	"timezone": "Asia/Kolkata"
}
```
#### Example Response

```json
{
  "date": "2026-03-10",
  "time": "14:30",
  "weekday": "Tuesday",
  "lagna": {
    "sign_sa": "Mithuna",
    "sign_en": "Gemini",
    "longitude_deg": 112.233344
  },
  "tithi": "Shukla Paksha Tritiya",
  "nakshatra": {
    "name": "Rohini",
    "from": "10-Mar-2026 08:15",
    "to": "11-Mar-2026 09:52"
  },
  "sunrise": "2026-03-10 06:27",
  "sunset": "2026-03-10 18:28",
  "planets": {
    "Sun": {
      "rashi_en": "Pisces",
      "longitude_deg": 356.22
    }
  }
}
```

#### Project Structure

```
panchangaApp/
│
├── views.py             # API endpoint logic
├── panchanga_utils.py   # Core computation engine
├── serializers.py       # Input validation
└── ephe/                # Swiss ephemeris files (.sef)
```

Installation
1. Clone the repository
JSONgit clone https://github.com/<your-username>/<repo-name>.gitcd <repo-name>
2. Create a virtual environment
Shellpython3 -m venv venvsource venv/bin/activate
3. Install Dependencies
Shellpip install -r requirements.txt
4. Run the server
Shellpython manage.py runserver

📦 Dependencies

Django
djangorestframework
swisseph
pytz
