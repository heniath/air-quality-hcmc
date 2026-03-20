# import json
# import os
# import sys
# import time
# from pathlib import Path
# from datetime import datetime, timezone
# from urllib.parse import urlparse, parse_qs

# import requests
# from flask import Flask, jsonify, send_from_directory, request
# from flask_cors import CORS

# # Load environment variables from .env file if exists
# try:
#     from dotenv import load_dotenv
#     load_dotenv()
# except ImportError:
#     print("⚠️  Warning: python-dotenv not installed. Install with: pip install python-dotenv")

# # ================= CONFIG =================
# BASE = Path(__file__).resolve().parent
# WEB_DIR = BASE / "web"
# DATA_DIR = BASE / "data"
# DATA_DIR.mkdir(exist_ok=True)

# CACHE_PATH = DATA_DIR / "latest_now.json"

# STATIONS_URL_PATH = BASE / "stations_url.txt"
# GEO_NAME = "geoBoundaries-VNM-ADM1.geojson"

# # ================= SECURITY: Load from environment variables =================
# AUTH_TOKEN = os.environ.get("AUTH_TOKEN")
# GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# # Validate required environment variables
# if not AUTH_TOKEN:
#     print("❌ ERROR: AUTH_TOKEN environment variable is not set!")
#     print("   Please create a .env file with: AUTH_TOKEN=your_token_here")
#     sys.exit(1)

# if not GROQ_API_KEY:
#     print("⚠️  WARNING: GROQ_API_KEY not set. AI chat will not work!")

# # API URLs
# DETAILS_URL = "https://apiserver.aqi.in/aqi/v3/getLocationDetailsBySlug?slug={slug}&type=4&source=web"
# HISTORY_API = "https://apiserver.aqi.in/aqi/v3/getLast24HourHistory?slug={slug}&sensorname={sensor}&slugType=locationId&source=web"
# GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# # Server configuration
# REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "12"))
# FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() == "true"

# BASE_HEADERS = {
#     "Accept": "*/*",
#     "Accept-Language": "en-US,en;q=0.9",
#     "Origin": "https://www.aqi.in",
#     "Referer": "https://www.aqi.in/",
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
# }

# # ================= SLUG READER =================
# def read_station_slugs():
#     if not STATIONS_URL_PATH.exists():
#         return []
#     lines = STATIONS_URL_PATH.read_text(encoding="utf-8").splitlines()
#     slugs = []
#     for line in lines:
#         line = line.strip()
#         if not line or line.startswith("#"):
#             continue
#         for u in line.split():
#             u = u.strip()
#             if not u or u.startswith("#"):
#                 continue
#             s = None
#             if "apiserver.aqi.in" in u and "slug=" in u:
#                 try:
#                     q = parse_qs(urlparse(u).query)
#                     s = (q.get("slug") or [None])[0]
#                 except Exception:
#                     pass
#             if not s and "aqi.in/" in u:
#                 s = u.split("aqi.in/")[-1].strip("/")
#             if not s:
#                 s = u.strip("/")
#             if s and s.startswith("dashboard/"):
#                 s = s[10:]
#             if s:
#                 slugs.append(s.strip("/"))
#     return list(dict.fromkeys(slugs))

# # ================= FETCH =================
# def fetch_now_by_slug(slug):
#     url = DETAILS_URL.format(slug=slug)
#     headers = {**BASE_HEADERS, "Authorization": f"Bearer {AUTH_TOKEN}"}
#     try:
#         r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
#         if r.status_code == 401:
#             return {"slug": slug, "error": "auth_failed (401) - token expired or invalid"}
#         if r.status_code != 200:
#             return {"slug": slug, "error": f"http_{r.status_code}"}
#         payload = r.json()
#         if payload.get("status") == "failed":
#             return {"slug": slug, "error": payload.get("message", "API failed")}
#         item = (payload.get("data") or [None])[0]
#         if not item:
#             return {"slug": slug, "error": "empty_data"}
#         iaqi = item.get("iaqi") or {}
#         weather = item.get("weather") or {}
#         return {
#             "id": str(item.get("uid") or item.get("locationId") or slug.split("/")[-1]),
#             "slug": item.get("location_slug") or item.get("slug") or slug,
#             "name": item.get("station") or item.get("location"),
#             "city": item.get("city"), "state": item.get("state"),
#             "lat": item.get("latitude"), "lng": item.get("longitude"),
#             "aqi": iaqi.get("aqi"), "pm25": iaqi.get("pm25"),
#             "pm10": iaqi.get("pm10"), "co": iaqi.get("co"),
#             "no2": iaqi.get("no2"), "o3": iaqi.get("o3"), "so2": iaqi.get("so2"),
#             "temp_c": weather.get("temp_c"), "humidity": weather.get("humidity"),
#             "wind_kph": weather.get("wind_kph"), "wind_dir": weather.get("wind_dir"),
#             "wind_degree": weather.get("wind_degree"), "pressure_mb": weather.get("pressure_mb"),
#             "weather_text": (weather.get("condition") or {}).get("text"),
#             "updated_at": item.get("updated_at"), "isOnline": item.get("isOnline"),
#         }
#     except Exception as e:
#         return {"slug": slug, "error": str(e)}

# # ================= CACHE =================
# _last_refresh = 0
# CACHE_TTL = 900  # 15 minutes
# REFRESH_COOLDOWN = 60  # seconds between manual refreshes

# def refresh_cache():
#     global _last_refresh
#     slugs = read_station_slugs()
#     data = {"generatedAt": datetime.now(timezone.utc).isoformat(),
#             "stations": [fetch_now_by_slug(s) for s in slugs]}
#     try:
#         CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
#     except Exception:
#         pass
#     _last_refresh = time.time()
#     return data

# def load_cache():
#     if CACHE_PATH.exists():
#         try:
#             data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
#             # Check if cache is stale
#             generated = data.get("generatedAt", "")
#             if generated:
#                 age = (datetime.now(timezone.utc) - datetime.fromisoformat(generated)).total_seconds()
#                 if age > CACHE_TTL:
#                     return refresh_cache()
#             return data
#         except Exception:
#             pass
#     return refresh_cache()

# # ================= FLASK =================
# app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path='')

# # Enable CORS for all routes
# CORS(app, resources={
#     r"/api/*": {
#         "origins": [r"http://localhost:\d+", r"http://127.0.0.1:\d+"],
#         "methods": ["GET", "POST"],
#         "allow_headers": ["Content-Type"]
#     }
# })

# @app.route("/")
# def root():
#     return send_from_directory(WEB_DIR, "map.html")

# @app.route(f"/{GEO_NAME}")
# def geo():
#     return send_from_directory(str(BASE), GEO_NAME)

# @app.route("/<path:path>")
# def static_files(path):
#     return send_from_directory(WEB_DIR, path)

# @app.route("/api/stations")
# def api_stations():
#     return jsonify(load_cache())

# @app.route("/api/refresh")
# def api_refresh():
#     global _last_refresh
#     elapsed = time.time() - _last_refresh
#     if elapsed < REFRESH_COOLDOWN:
#         return jsonify({"error": f"Cooldown: wait {int(REFRESH_COOLDOWN - elapsed)}s", "cached": load_cache()}), 429
#     return jsonify(refresh_cache())

# @app.route("/api/health")
# def api_health():
#     return jsonify({
#         "status": "ok",
#         "timestamp": datetime.now(timezone.utc).isoformat(),
#         "auth_token": bool(AUTH_TOKEN),
#         "groq_api_key": bool(GROQ_API_KEY),
#         "stations_count": len(read_station_slugs()),
#         "cache_exists": CACHE_PATH.exists(),
#     })

# VALID_SENSORS = {"aqi", "pm25", "pm10", "no2", "o3", "co", "so2"}

# @app.route("/api/history/<path:slug>")
# def api_history_station(slug):
#     sensor = request.args.get("sensor", "aqi")
#     if sensor not in VALID_SENSORS:
#         return jsonify({"status": "error", "message": f"Invalid sensor: {sensor}"}), 400
#     url = HISTORY_API.format(slug=slug, sensor=sensor)
#     headers = {**BASE_HEADERS, "Authorization": f"Bearer {AUTH_TOKEN}"}
#     try:
#         r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
#         return jsonify(r.json())
#     except requests.exceptions.Timeout:
#         return jsonify({"status": "error", "message": "Request timeout"}), 504
#     except requests.exceptions.RequestException as e:
#         return jsonify({"status": "error", "message": str(e)}), 502

# @app.route("/api/poi")
# def api_poi():
#     lat = request.args.get("lat", type=float)
#     lng = request.args.get("lng", type=float)
#     radius = request.args.get("radius", 3000, type=int)
#     types = request.args.get("types", "school,hospital,kindergarten")
#     amenity_filter = "|".join(types.split(","))
#     query = f'[out:json][timeout:10];(node["amenity"~"{amenity_filter}"](around:{radius},{lat},{lng});way["amenity"~"{amenity_filter}"](around:{radius},{lat},{lng}););out center 20;'
#     overpass_urls = [
#         "https://overpass-api.de/api/interpreter",
#         "https://overpass.kumi.systems/api/interpreter",
#     ]
#     for api_url in overpass_urls:
#         try:
#             r = requests.post(api_url, data={"data": query}, timeout=15)
#             if r.status_code != 200:
#                 continue
#             elements = r.json().get("elements", [])
#             pois = []
#             for el in elements:
#                 tags = el.get("tags", {})
#                 plat = el.get("lat") or (el.get("center") or {}).get("lat")
#                 plng = el.get("lon") or (el.get("center") or {}).get("lon")
#                 if plat and plng:
#                     pois.append({"name": tags.get("name", "Unknown"), "type": tags.get("amenity", ""),
#                                  "lat": plat, "lng": plng})
#             return jsonify({"pois": pois, "count": len(pois)})
#         except Exception:
#             continue
#     return jsonify({"pois": [], "error": "All Overpass mirrors failed"}), 502

# @app.route("/api/chat", methods=["POST"])
# def api_chat():
#     if not GROQ_API_KEY:
#         return jsonify({"reply": None, "error": "GROQ_API_KEY not configured"}), 503

#     body = request.json or {}
#     user_msg = body.get("message", "")
#     ctx = body.get("context") or {}
#     est = ctx.get("est") or {}
#     nearest = ctx.get("nearest") or {}
#     stations_summary = body.get("stationsSummary", "")
#     lat = ctx.get('lat') or 0
#     lng = ctx.get('lng') or 0

#     system_prompt = f"""Bạn là AI chuyên gia chất lượng không khí của hệ thống Megacity AQI (TP.HCM, Bình Dương, Bà Rịa-Vũng Tàu).

# DỮ LIỆU THỰC TẾ HIỆN TẠI:
# - Vị trí: {lat:.4f}, {lng:.4f} ({'Trong Megacity' if ctx.get('inside') else 'Ngoài Megacity'})
# - AQI: {round(est.get('aqi') or 0)} | PM2.5: {round(est.get('pm25') or 0)} µg/m³ | PM10: {round(est.get('pm10') or 0)}
# - NO₂: {round(est.get('no2') or 0)} | O₃: {round(est.get('o3') or 0)} | CO: {round(est.get('co') or 0)} | SO₂: {round(est.get('so2') or 0)}
# - Thời tiết: {nearest.get('temp_c','?')}°C | Ẩm {nearest.get('humidity','?')}% | Gió {nearest.get('wind_kph','?')}km/h {nearest.get('wind_dir','')}
# - Trạm gần nhất: {nearest.get('name','?')}
# {stations_summary}

# QUY TẮC TRẢ LỜI:
# 1. Trả lời ngắn gọn, dễ hiểu, thân thiện (dùng emoji)
# 2. Dùng ngôn ngữ của người hỏi (Việt thì Việt, English thì English)
# 3. Tham chiếu WHO/EPA khi cần
# 4. Nếu không liên quan không khí/sức khỏe → khéo léo từ chối
# 5. Khuyến nghị cụ thể dựa trên số liệu thực tế
# 6. Không dài hơn 200 chữ trừ khi hỏi chi tiết"""

#     payload = {
#         "model": "llama-3.1-8b-instant",
#         "messages": [
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_msg}
#         ],
#         "max_tokens": 512,
#         "temperature": 0.7
#     }
#     headers = {
#         "Authorization": f"Bearer {GROQ_API_KEY}",
#         "Content-Type": "application/json"
#     }

#     try:
#         r = requests.post(GROQ_URL, json=payload, headers=headers, timeout=15)
#         r.raise_for_status()
#         data = r.json()
#         if "choices" not in data:
#             err = data.get('error', {}).get('message', 'unknown')
#             return jsonify({"reply": None, "error": err}), 500
#         reply = data["choices"][0]["message"]["content"]
#         return jsonify({"reply": reply})
#     except requests.exceptions.Timeout:
#         return jsonify({"reply": None, "error": "Groq API timeout"}), 504
#     except requests.exceptions.HTTPError as e:
#         return jsonify({"reply": None, "error": f"Groq API error: {e.response.status_code}"}), 502
#     except Exception as e:
#         return jsonify({"reply": None, "error": str(e)}), 500

# if __name__ == "__main__":
#     # Get configuration from environment
#     host = os.environ.get("FLASK_HOST", "0.0.0.0")
#     port = int(os.environ.get("FLASK_PORT", "5501"))

#     print(f"🚀 Starting Megacity AQI Server...")
#     print(f"   Host: {host}:{port}")
#     print(f"   Debug: {FLASK_DEBUG}")
#     print(f"   AUTH_TOKEN: {'✅ Set' if AUTH_TOKEN else '❌ Missing'}")
#     print(f"   GROQ_API_KEY: {'✅ Set' if GROQ_API_KEY else '⚠️  Missing (AI chat disabled)'}")

#     app.run(host=host, port=port, debug=FLASK_DEBUG)

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

import requests
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS

# Load environment variables from .env file if exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  Warning: python-dotenv not installed. Install with: pip install python-dotenv")

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent
WEB_DIR = BASE / "web"
DATA_DIR = BASE / "data"
DATA_DIR.mkdir(exist_ok=True)

CACHE_PATH = DATA_DIR / "latest_now.json"

STATIONS_URL_PATH = BASE / "stations_url.txt"
GEO_NAME = "geoBoundaries-VNM-ADM1.geojson"

# ================= SECURITY: Load from environment variables =================
AUTH_TOKEN = os.environ.get("AUTH_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Validate required environment variables
if not AUTH_TOKEN:
    print("❌ ERROR: AUTH_TOKEN environment variable is not set!")
    print("   Please create a .env file with: AUTH_TOKEN=your_token_here")
    sys.exit(1)

if not GROQ_API_KEY:
    print("⚠️  WARNING: GROQ_API_KEY not set. AI chat will not work!")

# API URLs
DETAILS_URL = "https://apiserver.aqi.in/aqi/v3/getLocationDetailsBySlug?slug={slug}&type=4&source=web"
HISTORY_API = "https://apiserver.aqi.in/aqi/v3/getLast24HourHistory?slug={slug}&sensorname={sensor}&slugType=locationId&source=web"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Server configuration
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "12"))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() == "true"

BASE_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.aqi.in",
    "Referer": "https://www.aqi.in/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
}

# ================= SLUG READER =================
def read_station_slugs():
    if not STATIONS_URL_PATH.exists():
        return []
    lines = STATIONS_URL_PATH.read_text(encoding="utf-8").splitlines()
    slugs = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for u in line.split():
            u = u.strip()
            if not u or u.startswith("#"):
                continue
            s = None
            if "apiserver.aqi.in" in u and "slug=" in u:
                try:
                    q = parse_qs(urlparse(u).query)
                    s = (q.get("slug") or [None])[0]
                except Exception:
                    pass
            if not s and "aqi.in/" in u:
                s = u.split("aqi.in/")[-1].strip("/")
            if not s:
                s = u.strip("/")
            if s and s.startswith("dashboard/"):
                s = s[10:]
            if s:
                slugs.append(s.strip("/"))
    return list(dict.fromkeys(slugs))

# ================= FETCH =================
def fetch_now_by_slug(slug):
    url = DETAILS_URL.format(slug=slug)
    headers = {**BASE_HEADERS, "Authorization": f"Bearer {AUTH_TOKEN}"}
    try:
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code == 401:
            return {"slug": slug, "error": "auth_failed (401) - token expired or invalid"}
        if r.status_code != 200:
            return {"slug": slug, "error": f"http_{r.status_code}"}
        payload = r.json()
        if payload.get("status") == "failed":
            return {"slug": slug, "error": payload.get("message", "API failed")}
        item = (payload.get("data") or [None])[0]
        if not item:
            return {"slug": slug, "error": "empty_data"}
        iaqi = item.get("iaqi") or {}
        weather = item.get("weather") or {}
        return {
            "id": str(item.get("uid") or item.get("locationId") or slug.split("/")[-1]),
            "slug": item.get("location_slug") or item.get("slug") or slug,
            "name": item.get("station") or item.get("location"),
            "city": item.get("city"), "state": item.get("state"),
            "lat": item.get("latitude"), "lng": item.get("longitude"),
            "aqi": iaqi.get("aqi"), "pm25": iaqi.get("pm25"),
            "pm10": iaqi.get("pm10"), "co": iaqi.get("co"),
            "no2": iaqi.get("no2"), "o3": iaqi.get("o3"), "so2": iaqi.get("so2"),
            "temp_c": weather.get("temp_c"), "humidity": weather.get("humidity"),
            "wind_kph": weather.get("wind_kph"), "wind_dir": weather.get("wind_dir"),
            "wind_degree": weather.get("wind_degree"), "pressure_mb": weather.get("pressure_mb"),
            "weather_text": (weather.get("condition") or {}).get("text"),
            "updated_at": item.get("updated_at"), "isOnline": item.get("isOnline"),
        }
    except Exception as e:
        return {"slug": slug, "error": str(e)}

# ================= CACHE =================
_last_refresh = 0
CACHE_TTL = 900  # 15 minutes
REFRESH_COOLDOWN = 60  # seconds between manual refreshes

def refresh_cache():
    global _last_refresh
    slugs = read_station_slugs()
    data = {"generatedAt": datetime.now(timezone.utc).isoformat(),
            "stations": [fetch_now_by_slug(s) for s in slugs]}
    try:
        CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    _last_refresh = time.time()
    return data

def load_cache():
    if CACHE_PATH.exists():
        try:
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            # Check if cache is stale
            generated = data.get("generatedAt", "")
            if generated:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(generated)).total_seconds()
                if age > CACHE_TTL:
                    return refresh_cache()
            return data
        except Exception:
            pass
    return refresh_cache()

# ================= FLASK =================
app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path='')

# Enable CORS for all routes
# Streamlit chạy ở port 8501 (mặc định), Flask ở 5501
# Thêm origins cho cả 2 để gọi API qua nhau
_ALLOWED_ORIGINS = [
    r"http://localhost:\d+",
    r"http://127\.0\.0\.1:\d+",
]
# Nếu có STREAMLIT_URL trong env (production/Docker), thêm vào
import re as _re
_extra = os.environ.get("STREAMLIT_ORIGIN", "")
if _extra:
    _ALLOWED_ORIGINS.append(_re.escape(_extra))

CORS(app, resources={
    r"/api/*": {
        "origins": _ALLOWED_ORIGINS,
        "methods": ["GET", "POST"],
        "allow_headers": ["Content-Type"],
        "supports_credentials": False,
    }
})

@app.route("/")
def root():
    return send_from_directory(WEB_DIR, "map.html")

@app.route(f"/{GEO_NAME}")
def geo():
    return send_from_directory(str(BASE), GEO_NAME)

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(WEB_DIR, path)

@app.route("/api/stations")
def api_stations():
    return jsonify(load_cache())

@app.route("/api/refresh")
def api_refresh():
    global _last_refresh
    elapsed = time.time() - _last_refresh
    if elapsed < REFRESH_COOLDOWN:
        return jsonify({"error": f"Cooldown: wait {int(REFRESH_COOLDOWN - elapsed)}s", "cached": load_cache()}), 429
    return jsonify(refresh_cache())

@app.route("/api/health")
def api_health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "auth_token": bool(AUTH_TOKEN),
        "groq_api_key": bool(GROQ_API_KEY),
        "stations_count": len(read_station_slugs()),
        "cache_exists": CACHE_PATH.exists(),
    })

VALID_SENSORS = {"aqi", "pm25", "pm10", "no2", "o3", "co", "so2"}

@app.route("/api/history/<path:slug>")
def api_history_station(slug):
    sensor = request.args.get("sensor", "aqi")
    if sensor not in VALID_SENSORS:
        return jsonify({"status": "error", "message": f"Invalid sensor: {sensor}"}), 400
    url = HISTORY_API.format(slug=slug, sensor=sensor)
    headers = {**BASE_HEADERS, "Authorization": f"Bearer {AUTH_TOKEN}"}
    try:
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        return jsonify(r.json())
    except requests.exceptions.Timeout:
        return jsonify({"status": "error", "message": "Request timeout"}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": str(e)}), 502

@app.route("/api/poi")
def api_poi():
    lat = request.args.get("lat", type=float)
    lng = request.args.get("lng", type=float)
    radius = request.args.get("radius", 3000, type=int)
    types = request.args.get("types", "school,hospital,kindergarten")
    amenity_filter = "|".join(types.split(","))
    query = f'[out:json][timeout:10];(node["amenity"~"{amenity_filter}"](around:{radius},{lat},{lng});way["amenity"~"{amenity_filter}"](around:{radius},{lat},{lng}););out center 20;'
    overpass_urls = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    for api_url in overpass_urls:
        try:
            r = requests.post(api_url, data={"data": query}, timeout=15)
            if r.status_code != 200:
                continue
            elements = r.json().get("elements", [])
            pois = []
            for el in elements:
                tags = el.get("tags", {})
                plat = el.get("lat") or (el.get("center") or {}).get("lat")
                plng = el.get("lon") or (el.get("center") or {}).get("lon")
                if plat and plng:
                    pois.append({"name": tags.get("name", "Unknown"), "type": tags.get("amenity", ""),
                                 "lat": plat, "lng": plng})
            return jsonify({"pois": pois, "count": len(pois)})
        except Exception:
            continue
    return jsonify({"pois": [], "error": "All Overpass mirrors failed"}), 502

@app.route("/api/chat", methods=["POST"])
def api_chat():
    if not GROQ_API_KEY:
        return jsonify({"reply": None, "error": "GROQ_API_KEY not configured"}), 503

    body = request.json or {}
    user_msg = body.get("message", "")
    ctx = body.get("context") or {}
    est = ctx.get("est") or {}
    nearest = ctx.get("nearest") or {}
    stations_summary = body.get("stationsSummary", "")
    lat = ctx.get('lat') or 0
    lng = ctx.get('lng') or 0

    system_prompt = f"""Bạn là AI chuyên gia chất lượng không khí của hệ thống Megacity AQI (TP.HCM, Bình Dương, Bà Rịa-Vũng Tàu).

DỮ LIỆU THỰC TẾ HIỆN TẠI:
- Vị trí: {lat:.4f}, {lng:.4f} ({'Trong Megacity' if ctx.get('inside') else 'Ngoài Megacity'})
- AQI: {round(est.get('aqi') or 0)} | PM2.5: {round(est.get('pm25') or 0)} µg/m³ | PM10: {round(est.get('pm10') or 0)}
- NO₂: {round(est.get('no2') or 0)} | O₃: {round(est.get('o3') or 0)} | CO: {round(est.get('co') or 0)} | SO₂: {round(est.get('so2') or 0)}
- Thời tiết: {nearest.get('temp_c','?')}°C | Ẩm {nearest.get('humidity','?')}% | Gió {nearest.get('wind_kph','?')}km/h {nearest.get('wind_dir','')}
- Trạm gần nhất: {nearest.get('name','?')}
{stations_summary}

QUY TẮC TRẢ LỜI:
1. Trả lời ngắn gọn, dễ hiểu, thân thiện (dùng emoji)
2. Dùng ngôn ngữ của người hỏi (Việt thì Việt, English thì English)
3. Tham chiếu WHO/EPA khi cần
4. Nếu không liên quan không khí/sức khỏe → khéo léo từ chối
5. Khuyến nghị cụ thể dựa trên số liệu thực tế
6. Không dài hơn 200 chữ trừ khi hỏi chi tiết"""

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ],
        "max_tokens": 512,
        "temperature": 0.7
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(GROQ_URL, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        if "choices" not in data:
            err = data.get('error', {}).get('message', 'unknown')
            return jsonify({"reply": None, "error": err}), 500
        reply = data["choices"][0]["message"]["content"]
        return jsonify({"reply": reply})
    except requests.exceptions.Timeout:
        return jsonify({"reply": None, "error": "Groq API timeout"}), 504
    except requests.exceptions.HTTPError as e:
        return jsonify({"reply": None, "error": f"Groq API error: {e.response.status_code}"}), 502
    except Exception as e:
        return jsonify({"reply": None, "error": str(e)}), 500

if __name__ == "__main__":
    # Get configuration from environment
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", "5501"))

    print(f"🚀 Starting Megacity AQI Server...")
    print(f"   Host: {host}:{port}")
    print(f"   Debug: {FLASK_DEBUG}")
    print(f"   AUTH_TOKEN: {'✅ Set' if AUTH_TOKEN else '❌ Missing'}")
    print(f"   GROQ_API_KEY: {'✅ Set' if GROQ_API_KEY else '⚠️  Missing (AI chat disabled)'}")

    app.run(host=host, port=port, debug=FLASK_DEBUG)