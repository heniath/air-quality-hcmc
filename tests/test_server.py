"""
Unit Tests for Megacity AQI Server
Run: pytest tests/test_server.py -v
"""
import json
import os
import sys
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set required env vars before importing server
os.environ.setdefault("AUTH_TOKEN", "test_token_123")
os.environ.setdefault("GROQ_API_KEY", "test_groq_key")

import server


# ====================== FIXTURES ======================

@pytest.fixture
def client():
    """Flask test client."""
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


@pytest.fixture
def sample_station_response():
    """Mock aqi.in API response."""
    return {
        "status": "success",
        "data": [{
            "uid": 12345,
            "station": "Test Station",
            "city": "Ho Chi Minh City",
            "state": "Ho Chi Minh",
            "latitude": 10.783,
            "longitude": 106.701,
            "iaqi": {"aqi": 42, "pm25": 15, "pm10": 30, "co": 5, "no2": 10, "o3": 20, "so2": 3},
            "weather": {"temp_c": 32, "humidity": 60, "wind_kph": 9.4, "wind_dir": "NNW", "wind_degree": 329,
                        "pressure_mb": 1008, "condition": {"text": "Partly cloudy"}},
            "updated_at": "2026-02-21T06:00:00Z",
            "isOnline": True,
        }]
    }


@pytest.fixture
def sample_history_response():
    """Mock history API response."""
    return {
        "status": "success",
        "data": {
            "timeArray": ["2026-02-21T00:00:00Z", "2026-02-21T01:00:00Z"],
            "averageArray": [38, 42],
        }
    }


# ====================== SLUG READER TESTS ======================

class TestReadStationSlugs:
    """Tests for read_station_slugs() function."""

    def test_parse_api_url(self, tmp_path):
        """Should extract slug from apiserver.aqi.in URL."""
        url = "https://apiserver.aqi.in/aqi/v3/getLocationDetailsBySlug?slug=vietnam/ho-chi-minh/ho-chi-minh-city/test-station&type=4&source=web"
        f = tmp_path / "stations.txt"
        f.write_text(url)
        with patch.object(server, "STATIONS_URL_PATH", f):
            slugs = server.read_station_slugs()
        assert slugs == ["vietnam/ho-chi-minh/ho-chi-minh-city/test-station"]

    def test_parse_short_url(self, tmp_path):
        """Should extract slug from short aqi.in URL."""
        f = tmp_path / "stations.txt"
        f.write_text("https://www.aqi.in/vietnam/ho-chi-minh/test")
        with patch.object(server, "STATIONS_URL_PATH", f):
            slugs = server.read_station_slugs()
        assert slugs == ["vietnam/ho-chi-minh/test"]

    def test_deduplicate(self, tmp_path):
        """Should remove duplicate slugs."""
        f = tmp_path / "stations.txt"
        f.write_text("https://www.aqi.in/vietnam/test https://www.aqi.in/vietnam/test")
        with patch.object(server, "STATIONS_URL_PATH", f):
            slugs = server.read_station_slugs()
        assert len(slugs) == 1

    def test_strip_dashboard_prefix(self, tmp_path):
        """Should remove 'dashboard/' prefix from slug."""
        f = tmp_path / "stations.txt"
        f.write_text("https://www.aqi.in/dashboard/vietnam/test")
        with patch.object(server, "STATIONS_URL_PATH", f):
            slugs = server.read_station_slugs()
        assert slugs == ["vietnam/test"]

    def test_empty_file(self, tmp_path):
        """Should return empty list for empty file."""
        f = tmp_path / "stations.txt"
        f.write_text("")
        with patch.object(server, "STATIONS_URL_PATH", f):
            slugs = server.read_station_slugs()
        assert slugs == []

    def test_missing_file(self, tmp_path):
        """Should return empty list if file doesn't exist."""
        f = tmp_path / "nonexistent.txt"
        with patch.object(server, "STATIONS_URL_PATH", f):
            slugs = server.read_station_slugs()
        assert slugs == []


# ====================== FETCH TESTS ======================

class TestFetchNowBySlug:
    """Tests for fetch_now_by_slug() function."""

    @patch("server.requests.get")
    def test_success(self, mock_get, sample_station_response):
        """Should parse valid API response correctly."""
        mock_get.return_value = MagicMock(status_code=200, json=lambda: sample_station_response)
        result = server.fetch_now_by_slug("vietnam/test")
        assert result["name"] == "Test Station"
        assert result["aqi"] == 42
        assert result["pm25"] == 15
        assert result["lat"] == 10.783
        assert result["wind_kph"] == 9.4
        assert result["wind_degree"] == 329
        assert "error" not in result

    @patch("server.requests.get")
    def test_401_unauthorized(self, mock_get):
        """Should return auth_failed error on 401."""
        mock_get.return_value = MagicMock(status_code=401)
        result = server.fetch_now_by_slug("vietnam/test")
        assert "auth_failed" in result["error"]

    @patch("server.requests.get")
    def test_500_server_error(self, mock_get):
        """Should return http error on 500."""
        mock_get.return_value = MagicMock(status_code=500)
        result = server.fetch_now_by_slug("vietnam/test")
        assert "http_500" in result["error"]

    @patch("server.requests.get")
    def test_api_failed_status(self, mock_get):
        """Should return error when API returns failed status."""
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"status": "failed", "message": "Please Login"})
        result = server.fetch_now_by_slug("vietnam/test")
        assert result["error"] == "Please Login"

    @patch("server.requests.get")
    def test_empty_data(self, mock_get):
        """Should return empty_data error when data array is empty."""
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"status": "success", "data": []})
        result = server.fetch_now_by_slug("vietnam/test")
        assert result["error"] == "empty_data"

    @patch("server.requests.get")
    def test_network_error(self, mock_get):
        """Should catch network exceptions."""
        mock_get.side_effect = Exception("Connection refused")
        result = server.fetch_now_by_slug("vietnam/test")
        assert "Connection refused" in result["error"]


# ====================== API ENDPOINT TESTS ======================

class TestAPIEndpoints:
    """Tests for Flask API routes."""

    def test_root_serves_html(self, client):
        """GET / should serve map.html."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"<!doctype html>" in resp.data.lower() or b"<!DOCTYPE html>" in resp.data

    @patch("server.load_cache")
    def test_api_stations(self, mock_cache, client):
        """GET /api/stations should return cached data."""
        mock_cache.return_value = {"generatedAt": "2026-01-01", "stations": [{"name": "Test"}]}
        resp = client.get("/api/stations")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["stations"]) == 1

    @patch("server.refresh_cache")
    def test_api_refresh_cooldown(self, mock_refresh, client):
        """GET /api/refresh should enforce cooldown."""
        mock_refresh.return_value = {"generatedAt": "now", "stations": []}
        # First call
        server._last_refresh = time.time()
        resp = client.get("/api/refresh")
        assert resp.status_code == 429  # cooldown active

    @patch("server.refresh_cache")
    def test_api_refresh_allowed(self, mock_refresh, client):
        """GET /api/refresh should work after cooldown."""
        mock_refresh.return_value = {"generatedAt": "now", "stations": []}
        server._last_refresh = 0  # reset cooldown
        resp = client.get("/api/refresh")
        assert resp.status_code == 200

    def test_api_chat_no_groq_key(self, client):
        """POST /api/chat should return 503 if GROQ_API_KEY missing."""
        with patch.object(server, "GROQ_API_KEY", ""):
            resp = client.post("/api/chat", json={"message": "test"}, content_type="application/json")
            assert resp.status_code == 503

    @patch("server.requests.post")
    def test_api_poi(self, mock_post, client):
        """GET /api/poi should return POI data."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"elements": [{"tags": {"name": "School A", "amenity": "school"}, "lat": 10.78, "lon": 106.70}]}
        )
        resp = client.get("/api/poi?lat=10.78&lng=106.70&radius=2000")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["count"] == 1
        assert data["pois"][0]["name"] == "School A"


# ====================== CACHE TESTS ======================

class TestCache:
    """Tests for caching logic."""

    @patch("server.refresh_cache")
    def test_load_cache_missing_file(self, mock_refresh, tmp_path):
        """Should refresh if cache file missing."""
        mock_refresh.return_value = {"generatedAt": "now", "stations": []}
        with patch.object(server, "CACHE_PATH", tmp_path / "nonexistent.json"):
            server.load_cache()
        mock_refresh.assert_called_once()

    def test_cache_writes_json(self, tmp_path):
        """refresh_cache should write valid JSON to file."""
        cache_file = tmp_path / "test_cache.json"
        with patch.object(server, "CACHE_PATH", cache_file), \
             patch.object(server, "read_station_slugs", return_value=[]), \
             patch.object(server, "_last_refresh", 0):
            result = server.refresh_cache()
        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert "generatedAt" in data
        assert "stations" in data


# ====================== UTILITY TESTS ======================

class TestUtils:
    """Tests for utility functions and config."""

    def test_auth_token_loaded(self):
        """AUTH_TOKEN should be loaded from environment."""
        assert server.AUTH_TOKEN is not None

    def test_base_headers(self):
        """BASE_HEADERS should contain required fields."""
        assert "User-Agent" in server.BASE_HEADERS
        assert "Origin" in server.BASE_HEADERS
        assert "aqi.in" in server.BASE_HEADERS["Referer"]

    def test_details_url_format(self):
        """DETAILS_URL should accept slug parameter."""
        url = server.DETAILS_URL.format(slug="vietnam/test")
        assert "vietnam/test" in url
        assert "apiserver.aqi.in" in url


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
