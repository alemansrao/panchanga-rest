#Projects\panchanga-rest\panchanga\panchangaApp\panchanga_utils.py
import math
import pytz
from datetime import datetime
import swisseph as swe

# ---------------- Constants & Name Maps ----------------
# Sidereal mode: Lahiri
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

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
# Shukla 1..15 (Purnima=15), Krishna 16..30 (Amavasya=30)
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
# Karanas: 60 half-tithis
KARANA_MOVABLE = [
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Garaja",
    "Vanija",
    "Vishti (Bhadra)",
]
PLANETS = [
    ("Sun", swe.SUN),
    ("Moon", swe.MOON),
    ("Mars", swe.MARS),
    ("Mercury", swe.MERCURY),
    ("Jupiter", swe.JUPITER),
    ("Venus", swe.VENUS),
    ("Saturn", swe.SATURN),
    # True Node for Rahu; Ketu computed as opposite point
    # ("Rahu", swe.TRUE_NODE),
    ("Rahu", swe.MEAN_NODE)
]

# Default timezone (used only as a fallback)
INDIA_TZ = pytz.timezone("Asia/Kolkata")


# ---------------- Utility Functions (timezone-aware) ----------------
def _ensure_tz(tz_str: str | None):
    """
    Return a pytz timezone. If tz_str is None/invalid, fall back to Asia/Kolkata.
    """
    if tz_str:
        try:
            return pytz.timezone(tz_str)
        except Exception:
            pass
    return INDIA_TZ


def jd_at_midnight_local(date_str: str, tz_str: str | None = None):
    """
    Given DD/MM/YYYY (local calendar date in given tz), return UT Julian Day at local midnight.
    """
    tz = _ensure_tz(tz_str)
    dt_local = tz.localize(datetime.strptime(f"{date_str} 00:00", "%d/%m/%Y %H:%M"))
    dt_utc = dt_local.astimezone(pytz.UTC)
    jd_ut = swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0,
    )
    return jd_ut


def to_utc_jd(date_str: str, time_str: str, tz_str: str | None = None):
    """
    Parse DD/MM/YYYY and HH:MM as local time in tz_str and return (jd_ut, dt_local, dt_utc).
    """
    tz = _ensure_tz(tz_str)
    dt_local = tz.localize(datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M"))
    dt_utc = dt_local.astimezone(pytz.UTC)
    hfrac = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
    jd_ut = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hfrac)
    return jd_ut, dt_local, dt_utc


def revjul_to_local(jd_ut: float, tz_str: str = None): # type: ignore
    """
    Convert Julian day (UT) to localized datetime, safely handling all Swiss Ephemeris return formats.
    """
    tz = _ensure_tz(tz_str)
    res = swe.revjul(jd_ut, swe.GREG_CAL)

    # Swiss Ephemeris may return:
    # (y, m, d, hh, mm, ss)
    # (y, m, d, hour_float)
    # (y, m) <-- observed error case

    if len(res) == 6:
        y, m, d, hh, mm, ss = res

    elif len(res) == 4:
        y, m, d, hour_float = res
        hh = int(hour_float)
        mm = int((hour_float - hh) * 60)
        ss = 0

    elif len(res) == 2:
        # Fallback: set time = 00:00:00
        y, m = res
        d = 1
        hh = mm = ss = 0

    else:
        raise ValueError(f"Unexpected swe.revjul format: {res}")

    dt_utc = pytz.UTC.localize(datetime(int(y), int(m), int(d), int(hh), int(mm), int(ss)))
    return dt_utc.astimezone(tz)

def dms(deg: float):
    d = int(math.floor(deg))
    m_float = (deg - d) * 60
    m = int(math.floor(m_float))
    s = int(round((m_float - m) * 60))
    return f"{d}°{m:02d}'{s:02d}\""


def normalize(deg: float):
    return deg % 360.0


def sign_index(deg_sidereal: float):
    return int(math.floor(normalize(deg_sidereal) / 30.0))  # 0..11


def rashi_name_sa(idx: int):
    return RASHI_SA[idx]


def rashi_name_en(idx: int):
    return RASHI_EN[idx]


def _angle_diff(a: float, b: float):
    """Circular angle difference in (-180, 180]"""
    d = (a - b) % 360.0
    if d > 180:
        d -= 360
    return d


def _moon_sidereal_lon(jd_ut: float):
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    xx, _ = swe.calc_ut(jd_ut, swe.MOON, flags)
    lon = xx[0]
    return lon % 360


def _jd_to_local_string(jd_ut: float, tz_str: str = None): # type: ignore
    tz = _ensure_tz(tz_str)
    res = swe.revjul(jd_ut, swe.GREG_CAL)

    if len(res) == 6:
        y, m, d, hh, mm, ss = res

    elif len(res) == 4:
        y, m, d, hour_float = res
        hh = int(hour_float)
        mm = int((hour_float - hh) * 60)
        ss = 0

    elif len(res) == 2:
        # Fallback: Year, month only
        y, m = res
        d = 1
        hh = mm = ss = 0

    else:
        raise ValueError(f"Unexpected swe.revjul return: {res}")

    dt_utc = pytz.UTC.localize(datetime(int(y), int(m), int(d), int(hh), int(mm), int(ss)))
    return dt_utc.astimezone(tz).strftime("%d-%b-%Y %H:%M")


def _find_crossing(target_deg: float, jd_start: float, direction: int, step=0.5, max_days=45):
    """
    Find Moon longitude crossing target_deg near jd_start using sign-change + bisection.
    direction: +1 forward, -1 backward.
    """
    jd0 = jd_start
    d0 = _angle_diff(_moon_sidereal_lon(jd0), target_deg)
    jd = jd0
    prev_d = d0
    for _ in range(int(max_days / step) + 2):
        jd += direction * step
        d = _angle_diff(_moon_sidereal_lon(jd), target_deg)
        # sign flip found
        if d == 0 or (prev_d <= 0 <= d) or (d <= 0 <= prev_d) or (d * prev_d < 0):
            # bisection refine
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


# ------------------------------------------------------------
# MAIN PUBLIC API (timezone-aware)
# ------------------------------------------------------------
def compute_nakshatra(jd_ut: float, tz_str: str | None = None):
    """
    Input: jd_ut (Julian Day UT), tz_str(optional)
    Output: { name, meta, times, progress } with start/end shown in local tz.
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

    start_str = _jd_to_local_string(start_jd, tz_str) if start_jd else "—" # type: ignore
    end_str = _jd_to_local_string(end_jd, tz_str) if end_jd else "—" # type: ignore

    return {
        "name": name,
        "meta": f"Nakshatra #{idx+1}/27 • {progress:.1f}%",
        "times": f"{start_str} ↔ {end_str}",
        "progress": float(f"{progress:.1f}"),
    }


def nakshatra_name(moon_lon_sidereal: float):
    idx = int(math.floor(normalize(moon_lon_sidereal) / (360.0 / 27.0)))  # 0..26
    return NAKSHATRA[idx], idx + 1


def yoga_name(sun_lon_sidereal: float, moon_lon_sidereal: float):
    val = normalize(sun_lon_sidereal + moon_lon_sidereal)
    idx = int(math.floor(val / (360.0 / 27.0)))
    return YOGA[idx], idx + 1


def tithi_name(sun_lon_sidereal: float, moon_lon_sidereal: float):
    tithi_float = normalize(moon_lon_sidereal - sun_lon_sidereal) / 12.0  # 0..30
    tithi_num = int(math.floor(tithi_float)) + 1  # 1..30
    phase = "Shukla" if tithi_num <= 15 else "Krishna"
    base = TITHI_BASE[tithi_num - 1]
    # Special cases already in base: Purnima (15), Amavasya (30)
    if tithi_num not in (15, 30):
        return f"{phase} Paksha {base}", tithi_num
    else:
        return base, tithi_num


def karana_name(sun_lon_sidereal: float, moon_lon_sidereal: float):
    # Each Karana = 6 degrees = half tithi
    kf = normalize(moon_lon_sidereal - sun_lon_sidereal) / 6.0  # 0..60
    ki = int(math.floor(kf)) + 1  # 1..60
    if ki == 1:
        return "Kimstughna", ki
    if 2 <= ki <= 57:
        return KARANA_MOVABLE[(ki - 2) % 7], ki
    if ki == 58:
        return "Shakuni", ki
    if ki == 59:
        return "Chatushpada", ki
    # ki == 60
    return "Naga", ki


def ayana_name(sun_lon_sidereal: float):
    si = sign_index(sun_lon_sidereal)  # 0..11 Aries..Pisces
    return "Uttarayana" if si in {9, 10, 11, 0, 1, 2} else "Dakshinayana"