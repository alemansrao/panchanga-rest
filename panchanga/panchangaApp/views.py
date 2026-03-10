#Projects\panchanga-rest\panchanga\panchangaApp\views.py
from rest_framework.views import APIView
from .panchanga_utils import compute_nakshatra, jd_at_midnight_local
from rest_framework.response import Response
from rest_framework import status
import swisseph as swe
from .serializers import PanchangaInputSerializer
from .panchanga_utils import (
    to_utc_jd,
    revjul_to_local,
    normalize,
    sign_index,
    rashi_name_sa,
    rashi_name_en,
    nakshatra_name,
    yoga_name,
    tithi_name,
    karana_name,
    dms,
    ayana_name,
)

# ---- City DB with coordinates and timezones (extend or plug real geocoding) ----
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

# ---- Swiss Ephemeris setup ----
swe.set_ephe_path("ephe")  # Path to ephemeris folder
FLAGS = swe.FLG_SWIEPH | swe.FLG_SIDEREAL  # For sidereal planetary longitudes


class PanchangaAPI(APIView):
    """
    POST /panchanga/

    Optional fields to match *any* external software exactly:

      "ayanamsa": "lahiri" | "raman" | "kp" | ...
      "ayanamsa_offset": 0.883   ← custom offset (degrees)

    If you provide ayanamsa_offset, it overrides everything else.
    """

    def post(self, request):
        ser = PanchangaInputSerializer(data=request.data)
        if not ser.is_valid():
            return Response({"error": ser.errors}, status=status.HTTP_400_BAD_REQUEST)

        date_str = ser.validated_data["date"]  # type: ignore
        time_str = ser.validated_data["time"]  # type: ignore
        city_key = ser.validated_data["location"].strip().lower()  # type: ignore

        if city_key not in CITY_DB:
            return Response(
                {"error": f"Unknown location '{city_key}'. Add it to CITY_DB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lat, lon, tz_guess = CITY_DB[city_key]
        tz_str = request.data.get("timezone") or tz_guess

        # -----------------------------
        # 1) Select AYANAMSA MODE
        # -----------------------------
        AYANAMSA_MAP = {
            "lahiri": swe.SIDM_LAHIRI,
            "chitrapaksha": swe.SIDM_LAHIRI,
            "raman": swe.SIDM_RAMAN,
            "kp": swe.SIDM_KRISHNAMURTI,
            "krishnamurti": swe.SIDM_KRISHNAMURTI,
            "fagan": swe.SIDM_FAGAN_BRADLEY,
            "fagan-bradley": swe.SIDM_FAGAN_BRADLEY,
            "yukteswar": swe.SIDM_YUKTESHWAR,
            "sassanian": swe.SIDM_SASSANIAN,
            "surya_siddhanta": swe.SIDM_SURYASIDDHANTA,
        }

        ayan_name = ("lahiri").lower()

        mode = swe.SIDM_LAHIRI
        swe.set_sid_mode(mode)
        effective_ayanamsa = ayan_name

        try:
            # -----------------------------
            # 2) Convert local → UT
            # -----------------------------
            jd_ut, dt_local, dt_utc = to_utc_jd(date_str, time_str, tz_str)

            # -----------------------------
            # 3) Sunrise / Sunset
            # -----------------------------
            jd_mid = jd_at_midnight_local(date_str, tz_str)

            sr = swe.rise_trans(
                jd_mid, swe.SUN, geopos=(lon, lat, 0), rsmi=swe.CALC_RISE
            )
            ss = swe.rise_trans(
                jd_mid, swe.SUN, geopos=(lon, lat, 0), rsmi=swe.CALC_SET
            )

            sunrise_jd = sr[1][0]
            sunset_jd = ss[1][0]

            sr_local = revjul_to_local(sunrise_jd, tz_str)
            ss_local = revjul_to_local(sunset_jd, tz_str)

            # -----------------------------
            # 4) Ayanamsa (numerical value)
            # -----------------------------
            ayan = swe.get_ayanamsa_ut(jd_ut)

            # -----------------------------
            # 5) ASCENDANT (correct way)
            # -----------------------------
            cusps, ascmc = swe.houses(jd_ut, lat, lon, b"E")
            asc_tropical = ascmc[0]
            asc_sidereal = normalize(asc_tropical - ayan)

            lagna_idx = sign_index(asc_sidereal)
            lagna_sa = rashi_name_sa(lagna_idx)
            lagna_en = rashi_name_en(lagna_idx)

            # -----------------------------
            # 6) PLANETS (sidereal)
            # -----------------------------
            planets = {}
            planet_list = [
                ("Sun", swe.SUN),
                ("Moon", swe.MOON),
                ("Mars", swe.MARS),
                ("Mercury", swe.MERCURY),
                ("Jupiter", swe.JUPITER),
                ("Venus", swe.VENUS),
                ("Saturn", swe.SATURN),
                ("Rahu", swe.MEAN_NODE),
            ]

            for name, p in planet_list:
                xx, ret = swe.calc_ut(jd_ut, p, FLAGS)
                lon_sid = normalize(xx[0])
                si = sign_index(lon_sid)

                planets[name] = {
                    "longitude_deg": round(lon_sid, 6),
                    "longitude_dms": dms(lon_sid),
                    "rashi_sa": rashi_name_sa(si),
                    "rashi_en": rashi_name_en(si),
                    "house": ((si - lagna_idx) % 12) + 1,
                }

            # Ketu = opposite Rahu
            rahu_lon = planets["Rahu"]["longitude_deg"]
            ketu_lon = normalize(rahu_lon + 180)
            ketu_si = sign_index(ketu_lon)
            planets["Ketu"] = {
                "longitude_deg": round(ketu_lon, 6),
                "longitude_dms": dms(ketu_lon),
                "rashi_sa": rashi_name_sa(ketu_si),
                "rashi_en": rashi_name_en(ketu_si),
                "house": ((ketu_si - lagna_idx) % 12) + 1,
            }

            # -----------------------------
            # 7) Panchanga parameters
            # -----------------------------
            sun_lon = planets["Sun"]["longitude_deg"]
            moon_lon = planets["Moon"]["longitude_deg"]

            tithi_str, tithi_num = tithi_name(sun_lon, moon_lon)
            nak_info = compute_nakshatra(jd_ut, tz_str)
            yoga_str, yoga_num = yoga_name(sun_lon, moon_lon)
            kar_str, kar_num = karana_name(sun_lon, moon_lon)

            ayana_val = ayana_name(sun_lon)
            sa_solar = rashi_name_sa(sign_index(sun_lon))
            sa_lunar = rashi_name_sa(sign_index(moon_lon))

            # -----------------------------
            # 8) Prepare Response
            # -----------------------------
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
                },
                "tithi": tithi_str,
                "nakshatra": {
                    "name": nak_info["name"],
                    "from": nak_info["times"].split(" ↔ ")[0],
                    "to": nak_info["times"].split(" ↔ ")[1],
                },
                "yoga": yoga_str,
                "karana": kar_str,
                "sauramana": sa_solar,
                "chandramana": sa_lunar,
                "sunrise": sr_local.strftime("%Y-%m-%d %H:%M"),
                "sunset": ss_local.strftime("%Y-%m-%d %H:%M"),
                "planets": planets,
            }

            return Response(resp, status=200)

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
