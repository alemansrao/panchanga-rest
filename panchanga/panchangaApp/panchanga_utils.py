# Projects/panchanga-rest/panchanga/panchangaApp/panchanga_utils.py
"""
Utility helpers for Panchanga & Kundali computations using Swiss Ephemeris.
Focus: simplicity, readability, and safe timezone handling.

Additions:
- Robust date parsing (YYYY-MM-DD or DD/MM/YYYY)
- Planetary Nakshatra + Pada helpers
- Divisional chart helper + Navamsa (D9)
- DMS helpers (absolute and within sign)
- Sidereal conversions kept explicit and readable
"""

from __future__ import annotations

import math
from datetime import datetime
import pytz
import swisseph as swe

# ---------------------------------------------------------------------
# CONFIG: Sidereal mode (Lahiri) — commonly used in Indian astrology
# ---------------------------------------------------------------------
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

# ---------------------------------------------------------------------
# NAME MAPS
# ---------------------------------------------------------------------
RASHI_EN = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]
RASHI_SA = [
    "Mesha",
    "Vrishabha",
    "Mithuna",
    "Karka",
    "Simha",
    "Kanya",
    "Tula",
    "Vrishchika",
    "Dhanu",
    "Makara",
    "Kumbha",
    "Meena",
]
NAKSHATRA = [
    "Ashwini",
    "Bharani",
    "Krittika",
    "Rohini",
    "Mrigashirsha",
    "Ardra",
    "Punarvasu",
    "Pushya",
    "Ashlesha",
    "Magha",
    "Purva Phalguni",
    "Uttara Phalguni",
    "Hasta",
    "Chitra",
    "Swati",
    "Vishakha",
    "Anuradha",
    "Jyeshtha",
    "Mula",
    "Purva Ashadha",
    "Uttara Ashadha",
    "Shravana",
    "Dhanishtha",
    "Shatabhisha",
    "Purva Bhadrapada",
    "Uttara Bhadrapada",
    "Revati",
]
YOGA = [
    "Vishkambha",
    "Priti",
    "Ayushman",
    "Saubhagya",
    "Shobhana",
    "Atiganda",
    "Sukarma",
    "Dhriti",
    "Shula",
    "Ganda",
    "Vriddhi",
    "Dhruva",
    "Vyaghata",
    "Harshana",
    "Vajra",
    "Siddhi",
    "Vyatipata",
    "Variyan",
    "Parigha",
    "Shiva",
    "Siddha",
    "Sadhya",
    "Shubha",
    "Shukla",
    "Brahma",
    "Indra",
    "Vaidhriti",
]
# Tithis (1..30). 1..15 Shukla; 16..30 Krishna (15=Purnima, 30=Amavasya)
TITHI_BASE = [
    "Pratipada",
    "Dwitiya",
    "Tritiya",
    "Chaturthi",
    "Panchami",
    "Shashthi",
    "Saptami",
    "Ashtami",
    "Navami",
    "Dashami",
    "Ekadashi",
    "Dwadashi",
    "Trayodashi",
    "Chaturdashi",
    "Purnima",
    "Pratipada",
    "Dwitiya",
    "Tritiya",
    "Chaturthi",
    "Panchami",
    "Shashthi",
    "Saptami",
    "Ashtami",
    "Navami",
    "Dashami",
    "Ekadashi",
    "Dwadashi",
    "Trayodashi",
    "Chaturdashi",
    "Amavasya",
]
KARANA_MOVABLE = [
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Garaja",
    "Vanija",
    "Vishti (Bhadra)",
]

# Default TZ fallback
INDIA_TZ = pytz.timezone("Asia/Kolkata")


# ---------------------------------------------------------------------
# BASIC HELPERS
# ---------------------------------------------------------------------
def _ensure_tz(tz_str: str | None):
    """Return pytz timezone; fall back to Asia/Kolkata if invalid/missing."""
    if tz_str:
        try:
            return pytz.timezone(tz_str)
        except Exception:
            pass
    return INDIA_TZ


def _parse_date(date_str: str) -> datetime.date:  # type: ignore
    """
    Accepts:
    - YYYY-MM-DD (ISO)
    - DD/MM/YYYY (common local)
    - DD-MM-YYYY  # NEW
    Returns a date() (no time).
    """
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):  # added "%d-%m-%Y"
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(
        f"Unsupported date format: '{date_str}'. Use YYYY-MM-DD, DD/MM/YYYY, or DD-MM-YYYY."
    )


def _parse_time(time_str: str) -> tuple[int, int]:
    """Parse HH:MM (24h) → (hour, minute)."""
    try:
        hh, mm = time_str.strip().split(":")
        return int(hh), int(mm)
    except Exception:
        raise ValueError(f"Unsupported time format: '{time_str}'. Use HH:MM (24h).")


def normalize(deg: float) -> float:
    """Normalize angle to [0, 360)."""
    return deg % 360.0


def sign_index(deg_sidereal: float) -> int:
    """Return 0..11 for Aries..Pisces."""
    return int(math.floor(normalize(deg_sidereal) / 30.0))


def rashi_name_sa(idx: int) -> str:
    return RASHI_SA[idx]


def rashi_name_en(idx: int) -> str:
    return RASHI_EN[idx]


# ---------------------------------------------------------------------
# TIME ↔ JULIAN DAY HELPERS (TZ-AWARE)
# ---------------------------------------------------------------------
def to_utc_jd(date_str: str, time_str: str, tz_str: str | None = None):
    """
    Parse local date+time in tz_str and return (jd_ut, dt_local, dt_utc).
    Supported dates: YYYY-MM-DD or DD/MM/YYYY. Time: HH:MM (24h).
    """
    tz = _ensure_tz(tz_str)
    d = _parse_date(date_str)
    h, m = _parse_time(time_str)
    dt_local = tz.localize(datetime(d.year, d.month, d.day, h, m, 0))
    dt_utc = dt_local.astimezone(pytz.UTC)
    hfrac = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
    jd_ut = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hfrac)
    return jd_ut, dt_local, dt_utc


def jd_at_midnight_local(date_str: str, tz_str: str | None = None) -> float:
    """
    Given local calendar date (YYYY-MM-DD or DD/MM/YYYY), return UT Julian Day
    at local midnight (00:00).
    """
    tz = _ensure_tz(tz_str)
    d = _parse_date(date_str)
    dt_local = tz.localize(datetime(d.year, d.month, d.day, 0, 0, 0))
    dt_utc = dt_local.astimezone(pytz.UTC)
    jd_ut = swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0,
    )
    return jd_ut


def revjul_to_local(jd_ut: float, tz_str: str | None = None):
    """
    Convert Julian Day (UT) to timezone-aware local datetime.
    Safely handles various Swiss Ephemeris return shapes.
    """
    tz = _ensure_tz(tz_str)
    res = swe.revjul(jd_ut, swe.GREG_CAL)

    # Swiss Ephemeris may return:
    # (y, m, d, hh, mm, ss) OR (y, m, d, hour_float)
    if len(res) == 6:
        y, m, d, hh, mm, ss = res
    elif len(res) == 4:
        y, m, d, hour_float = res
        hh = int(hour_float)
        mm = int((hour_float - hh) * 60)
        ss = 0
    else:
        # Fallback: assume midnight of first day if incomplete
        y, m = res[:2]
        d = 1
        hh = mm = ss = 0

    dt_utc = pytz.UTC.localize(
        datetime(int(y), int(m), int(d), int(hh), int(mm), int(ss))
    )
    return dt_utc.astimezone(tz)


# ---------------------------------------------------------------------
# MOON LONGITUDE + SEARCH FOR NAKSHATRA BOUNDARIES
# ---------------------------------------------------------------------
def _moon_sidereal_lon(jd_ut: float) -> float:
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    xx, _ = swe.calc_ut(jd_ut, swe.MOON, flags)
    return normalize(xx[0])


def _angle_diff(a: float, b: float) -> float:
    """Circular difference in (-180, 180]."""
    d = (a - b) % 360.0
    if d > 180:
        d -= 360
    return d


def _jd_to_local_string(jd_ut: float, tz_str: str | None = None) -> str:
    """Format JD→Local time as 'DD-Mon-YYYY HH:MM'."""
    return revjul_to_local(jd_ut, tz_str).strftime("%d-%b-%Y %H:%M")


def _find_crossing(
    target_deg: float, jd_start: float, direction: int, step=0.5, max_days=45
):
    """
    Find JD where Moon longitude crosses target_deg near jd_start
    using sign-change detection + bisection. direction: +1 forward, -1 backward.
    """
    jd = jd_start
    prev_d = _angle_diff(_moon_sidereal_lon(jd), target_deg)

    for _ in range(int(max_days / step) + 2):
        jd += direction * step
        d = _angle_diff(_moon_sidereal_lon(jd), target_deg)

        # sign flip or exact hit
        if d == 0 or (prev_d <= 0 <= d) or (d <= 0 <= prev_d) or (d * prev_d < 0):
            left, right = jd - direction * step, jd
            dl = _angle_diff(_moon_sidereal_lon(left), target_deg)
            dr = _angle_diff(_moon_sidereal_lon(right), target_deg)
            for _ in range(60):
                mid = 0.5 * (left + right)
                dm = _angle_diff(_moon_sidereal_lon(mid), target_deg)
                if abs(dm) < 1e-8:
                    return mid
                if dl * dm <= 0:
                    right, dr = mid, dm
                else:
                    left, dl = mid, dm
            return 0.5 * (left + right)

        prev_d = d

    return None


# ---------------------------------------------------------------------
# PUBLIC: NAKSHATRA (MOON) WITH START/END IN LOCAL TZ
# ---------------------------------------------------------------------
def compute_nakshatra(jd_ut: float, tz_str: str | None = None):
    """
    Input: jd_ut (Julian Day UT), tz_str(optional)
    Output: dict { name, meta, times, progress }
    - 'times' shows start ↔ end in local timezone
    """
    seg = 360.0 / 27.0
    lon = _moon_sidereal_lon(jd_ut)
    n_float = lon / seg
    idx = int(math.floor(n_float))  # 0..26
    name = NAKSHATRA[idx]
    progress = (n_float - idx) * 100.0

    start_deg = (idx * seg) % 360
    end_deg = ((idx + 1) * seg) % 360

    start_jd = _find_crossing(start_deg, jd_ut, direction=-1)
    end_jd = _find_crossing(end_deg, jd_ut, direction=+1)

    start_str = _jd_to_local_string(start_jd, tz_str) if start_jd else "—"
    end_str = _jd_to_local_string(end_jd, tz_str) if end_jd else "—"

    return {
        "name": name,
        "meta": f"Nakshatra #{idx+1}/27 • {progress:.1f}%",
        "times": f"{start_str} ↔ {end_str}",
        "progress": float(f"{progress:.1f}"),
    }


# ---------------------------------------------------------------------
# PANCHANGA NAMES FROM LONGITUDES
# ---------------------------------------------------------------------


def nakshatra_pada(lon_sidereal: float):
    """Return (name, number 1..27, pada 1..4) for any sidereal longitude."""
    seg = 360.0 / 27.0
    idx = int(normalize(lon_sidereal) // seg)  # 0..26
    name = NAKSHATRA[idx]
    within = normalize(lon_sidereal) % seg
    pada = int(within // (seg / 4.0)) + 1  # 1..4
    return name, pada


def yoga_name(sun_lon_sidereal: float, moon_lon_sidereal: float):
    val = normalize(sun_lon_sidereal + moon_lon_sidereal)
    idx = int(math.floor(val / (360.0 / 27.0)))
    return YOGA[idx]


def tithi_name(sun_lon_sidereal: float, moon_lon_sidereal: float):
    tithi_float = normalize(moon_lon_sidereal - sun_lon_sidereal) / 12.0  # 0..30
    tithi_num = int(math.floor(tithi_float)) + 1  # 1..30
    phase = "Shukla" if tithi_num <= 15 else "Krishna"
    base = TITHI_BASE[tithi_num - 1]
    if tithi_num not in (15, 30):  # 15=Purnima, 30=Amavasya already standalone
        return f"{phase} Paksha {base}"
    return base


def karana_name(sun_lon_sidereal: float, moon_lon_sidereal: float):
    # Each Karana = 6° = half tithi
    kf = normalize(moon_lon_sidereal - sun_lon_sidereal) / 6.0  # 0..60
    ki = int(math.floor(kf)) + 1  # 1..60
    if ki == 1:
        return "Kimstughna"
    if 2 <= ki <= 57:
        return KARANA_MOVABLE[(ki - 2) % 7]
    if ki == 58:
        return "Shakuni"
    if ki == 59:
        return "Chatushpada"
    return "Naga"  # ki == 60


def ayana_name(sun_lon_sidereal: float):
    si = sign_index(sun_lon_sidereal)  # 0..11
    return "Uttarayana" if si in {9, 10, 11, 0, 1, 2} else "Dakshinayana"
