# Projects/panchanga-rest/panchanga/panchangaApp/views.py
# -*- coding: utf-8 -*-
"""
Django REST API for Panchanga & Kundali basics using Swiss Ephemeris.

Additions:
- Per-planet: Nakshatra + Pada, Navamsa sign, DMS (absolute & within sign)
- Sidereal house cusps (1–12)
- Safer date parsing (YYYY-MM-DD or DD/MM/YYYY) via utils
- Clean, readable structure and comments
"""

from __future__ import annotations

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import swisseph as swe

from .serializers import PanchangaInputSerializer
from .panchanga_utils import (
    to_utc_jd,
    revjul_to_local,
    jd_at_midnight_local,
    normalize,
    sign_index,
    rashi_name_sa,
    rashi_name_en,
    dms,
    dms_in_sign,
    compute_nakshatra,
    nakshatra_name,
    nakshatra_pada,
    yoga_name,
    tithi_name,
    karana_name,
    ayana_name,
    navamsa,
)

# ---------------------------------------------------------------------
# City DB (latitude, longitude, timezone). Extend/replace with real DB.
# ---------------------------------------------------------------------
CITY_DB = {
    "chennai": (13.0827, 80.2707, "Asia/Kolkata"),
    "bangalore": (12.9716, 77.5946, "Asia/Kolkata"),
    "bengaluru": (12.9716, 77.5946, "Asia/Kolkata"),
    "mangalore": (12.849366, 74.845868, "Asia/Kolkata"),
    "mumbai": (19.0760, 72.8777, "Asia/Kolkata"),
    "hyderabad": (17.3850, 78.4867, "Asia/Kolkata"),
    "delhi": (28.6139, 77.2090, "Asia/Kolkata"),
    "kolkata": (22.5726, 88.3639, "Asia/Kolkata"),
    "pune": (18.5204, 73.8567, "Asia/Kolkata"),
}

# ---------------------------------------------------------------------
# Swiss Ephemeris setup
# ---------------------------------------------------------------------
swe.set_ephe_path("ephe")  # Ensure the 'ephe' directory is present and readable

FLAGS = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED  # Sidereal planetary longitudes


class PanchangaAPI(APIView):
    """
    Endpoints:
      GET  /panchanga/           -> health check { "status": "ok" }
      POST /panchanga/           -> compute panchanga + planets

    Request JSON (POST):
      Required:
        - date: "YYYY-MM-DD"  OR "DD/MM/YYYY"    (local calendar date)
        - time: "HH:MM"                          (local time 24h)
        - location: city key (e.g. "bangalore")  (see CITY_DB)
      Optional:
        - timezone: IANA TZ like "Asia/Kolkata"  (overrides CITY_DB default)
        - ayanamsa: string (currently fixed internally to Lahiri)

    NOTE: Ayanamsa selection currently defaults to Lahiri.
    """

    def get(self, request):
        """Health-check endpoint."""
        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    def post(self, request):
        # Validate input via serializer (assumed to expose 'date', 'time', 'location')
        ser = PanchangaInputSerializer(data=request.data)
        if not ser.is_valid():
            return Response({"error": ser.errors}, status=status.HTTP_400_BAD_REQUEST)

        date_str = ser.validated_data["date"]     # type: ignore
        time_str = ser.validated_data["time"]     # type: ignore
        city_key = ser.validated_data["location"].strip().lower()  # type: ignore

        if city_key not in CITY_DB:
            return Response(
                {"error": f"Unknown location '{city_key}'. Add it to CITY_DB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lat, lon, tz_guess = CITY_DB[city_key]
        tz_str = request.data.get("timezone") or tz_guess

        # Set ayanamsa mode (Lahiri)
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        effective_ayanamsa = "lahiri"

        try:
            # ---------------------------------------------------------
            # 1) Local → UT (Julian Day + sanity-checked datetimes)
            # ---------------------------------------------------------
            jd_ut, dt_local, dt_utc = to_utc_jd(date_str, time_str, tz_str)

            # ---------------------------------------------------------
            # 2) Sunrise / Sunset (compute using local midnight anchor)
            # ---------------------------------------------------------
            jd_mid = jd_at_midnight_local(date_str, tz_str)
            sr = swe.rise_trans(jd_mid, swe.SUN, geopos=(lon, lat, 0), rsmi=swe.CALC_RISE)
            ss = swe.rise_trans(jd_mid, swe.SUN, geopos=(lon, lat, 0), rsmi=swe.CALC_SET)
            sunrise_jd = sr[1][0]
            sunset_jd = ss[1][0]
            sr_local = revjul_to_local(sunrise_jd, tz_str)
            ss_local = revjul_to_local(sunset_jd, tz_str)

            # ---------------------------------------------------------
            # 3) Ayanamsa (numeric value at given UT)
            # ---------------------------------------------------------
            ayan = swe.get_ayanamsa_ut(jd_ut)  # degrees

            # ---------------------------------------------------------
            # 4) Houses & Ascendant (sidereal)
            # ---------------------------------------------------------
            # Swiss returns tropical cusps; convert to sidereal by subtracting ayanamsa.
            cusps_trop, ascmc = swe.houses(jd_ut, lat, lon, b"E")
            asc_tropical = ascmc[0]
            asc_sidereal = normalize(asc_tropical - ayan)
            lagna_idx = sign_index(asc_sidereal)
            lagna_sa = rashi_name_sa(lagna_idx)
            lagna_en = rashi_name_en(lagna_idx)

            # Sidereal house cusps (1..12)
            house_cusps_sid = [normalize(c - ayan) for c in cusps_trop]  # 12 values

            # ---------------------------------------------------------
            # 5) Planets (sidereal, with extras)
            # ---------------------------------------------------------
            planets = {}
            planet_list = [
                ("Sun", swe.SUN),
                ("Moon", swe.MOON),
                ("Mars", swe.MARS),
                ("Mercury", swe.MERCURY),
                ("Jupiter", swe.JUPITER),
                ("Venus", swe.VENUS),
                ("Saturn", swe.SATURN),
                ("Rahu", swe.MEAN_NODE),  # Ketu will be derived
            ]

            for name, p in planet_list:
                xx, ret = swe.calc_ut(jd_ut, p, FLAGS)
                lon_sid = normalize(xx[0])
                si = sign_index(lon_sid)

                # Nakshatra + Pada
                nak_name, nak_num, pada = nakshatra_pada(lon_sid)

                # Navamsa (D9) sign (0..11) and name
                d9_idx = navamsa(lon_sid)

                planets[name] = {
                    "longitude_deg": round(lon_sid, 6),
                    "longitude_dms": dms(lon_sid),
                    "in_sign_sa": rashi_name_sa(si),
                    "in_sign_en": rashi_name_en(si),
                    "deg_in_sign_dms": dms_in_sign(lon_sid),
                    # Whole-sign house from Lagna sign
                    "house": ((si - lagna_idx) % 12) + 1,
                    "retrograde": xx[3] < 0,
                    "nakshatra": {
                        "name": nak_name,
                        "number": nak_num,
                        "pada": pada,
                    },
                    "navamsa": {
                        "sign_index": d9_idx,
                        "sign_sa": rashi_name_sa(d9_idx),
                        "sign_en": rashi_name_en(d9_idx),
                    },
                }

            # Ketu = opposite Rahu
            rahu_lon = planets["Rahu"]["longitude_deg"]
            ketu_lon = normalize(rahu_lon + 180)
            ketu_si = sign_index(ketu_lon)
            ketu_nak_name, ketu_nak_num, ketu_pada = nakshatra_pada(ketu_lon)
            ketu_d9_idx = navamsa(ketu_lon)

            planets["Ketu"] = {
                "longitude_deg": round(ketu_lon, 6),
                "longitude_dms": dms(ketu_lon),
                "in_sign_sa": rashi_name_sa(ketu_si),
                "in_sign_en": rashi_name_en(ketu_si),
                "deg_in_sign_dms": dms_in_sign(ketu_lon),
                "house": ((ketu_si - lagna_idx) % 12) + 1,
                "retrograde": True,
                "nakshatra": {
                    "name": ketu_nak_name,
                    "number": ketu_nak_num,
                    "pada": ketu_pada,
                },
                "navamsa": {
                    "sign_index": ketu_d9_idx,
                    "sign_sa": rashi_name_sa(ketu_d9_idx),
                    "sign_en": rashi_name_en(ketu_d9_idx),
                },
            }

            # ---------------------------------------------------------
            # 6) Panchanga parameters
            # ---------------------------------------------------------
            sun_lon = planets["Sun"]["longitude_deg"]
            moon_lon = planets["Moon"]["longitude_deg"]

            tithi_str, tithi_num = tithi_name(sun_lon, moon_lon)
            nak_info = compute_nakshatra(jd_ut, tz_str)  # Moon's nakshatra with times
            yoga_str, yoga_num = yoga_name(sun_lon, moon_lon)
            kar_str, kar_num = karana_name(sun_lon, moon_lon)
            ayana_val = ayana_name(sun_lon)

            sauramana = rashi_name_sa(sign_index(sun_lon))
            chandramana = rashi_name_sa(sign_index(moon_lon))

            # ---------------------------------------------------------
            # 7) Response
            # ---------------------------------------------------------
            resp = {
                "date": dt_local.strftime("%Y-%m-%d"),
                "time": dt_local.strftime("%H:%M"),
                "weekday": dt_local.strftime("%A"),
                "timezone": tz_str,
                "ayanamsa_mode": effective_ayanamsa,
                "ayanamsa_value_deg": ayan,
                "lagna": {
                    "sign_sa": lagna_sa,
                    "sign_en": lagna_en,
                    "longitude_deg": round(asc_sidereal, 6),
                    "longitude_dms": dms(asc_sidereal),
                    "deg_in_sign_dms": dms_in_sign(asc_sidereal),
                },
                "tithi": {"name": tithi_str, "number": tithi_num},
                "nakshatra": {
                    "name": nak_info["name"],
                    "from": nak_info["times"].split(" ↔ ")[0],
                    "to": nak_info["times"].split(" ↔ ")[1],
                },
                "yoga": {"name": yoga_str, "number": yoga_num},
                "karana": {"name": kar_str, "number": kar_num},
                "ayana": ayana_val,
                "sauramana": sauramana,
                "chandramana": chandramana,
                "sunrise": sr_local.strftime("%Y-%m-%d %H:%M"),
                "sunset": ss_local.strftime("%Y-%m-%d %H:%M"),
                "planets": planets,
            }

            return Response(resp, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)