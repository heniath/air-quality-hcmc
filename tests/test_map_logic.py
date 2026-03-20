"""
Tests for map.html JavaScript logic
Run: pytest tests/test_map_logic.py -v
Tests the core science functions (IDW, distance, color mapping) by running them in a simulated environment.
"""
import math
import pytest


# ====================== PYTHON REIMPLEMENTATION OF JS FUNCTIONS ======================
# These mirror the JS functions in map.html for validation

POLS = {
    "aqi": {"label": "AQI", "unit": "", "max": 300, "t": [50, 100, 150, 200]},
    "pm25": {"label": "PM2.5", "unit": "µg/m³", "max": 250, "t": [12, 35, 55, 150]},
    "pm10": {"label": "PM10", "unit": "µg/m³", "max": 400, "t": [54, 154, 254, 354]},
    "no2": {"label": "NO₂", "unit": "ppb", "max": 200, "t": [53, 100, 360, 649]},
    "o3": {"label": "O₃", "unit": "ppb", "max": 200, "t": [54, 70, 85, 105]},
    "co": {"label": "CO", "unit": "ppb", "max": 500, "t": [50, 100, 150, 300]},
    "so2": {"label": "SO₂", "unit": "ppb", "max": 200, "t": [35, 75, 185, 304]},
}


def dist_km(lat1, lng1, lat2, lng2):
    """Haversine distance in km — mirrors distKm() in map.html."""
    R = 6371
    to_rad = lambda x: x * math.pi / 180
    dL = to_rad(lat2 - lat1)
    dN = to_rad(lng2 - lng1)
    h = math.sin(dL / 2) ** 2 + math.cos(to_rad(lat1)) * math.cos(to_rad(lat2)) * math.sin(dN / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def nearest_k(stations, lat, lng, k):
    """Find k nearest stations — mirrors nearestK()."""
    with_dist = [({**s, "dKm": dist_km(lat, lng, s["lat"], s["lng"])}) for s in stations]
    with_dist.sort(key=lambda x: x["dKm"])
    return with_dist[:k]


def idw_all(pts, lat, lng, p=1.8, eps=0.08):
    """IDW interpolation — mirrors idwAll()."""
    sw = 0
    sums = {"aqi": 0, "pm25": 0, "pm10": 0, "co": 0, "no2": 0, "o3": 0, "so2": 0}
    for pt in pts:
        d = dist_km(lat, lng, pt["lat"], pt["lng"])
        w = pt.get("penalty", 1) / ((d + eps) ** p)
        sw += w
        for k in sums:
            sums[k] += (pt.get(k, 0) or 0) * w
    if sw == 0:
        return sums
    return {k: v / sw for k, v in sums.items()}


def pol_color(v, p):
    """AQI color mapping — mirrors polColor()."""
    t = POLS.get(p, {}).get("t", [50, 100, 150, 200])
    if v >= t[3]: return "#e11d48"
    if v >= t[2]: return "#f97316"
    if v >= t[1]: return "#fbbf24"
    if v >= t[0]: return "#10b981"
    return "#38bdf8"


def pol_text(v, p):
    """AQI text classification — mirrors polText()."""
    t = POLS.get(p, {}).get("t", [50, 100, 150, 200])
    if v >= t[3]: return "Very Unhealthy"
    if v >= t[2]: return "Unhealthy"
    if v >= t[1]: return "Sensitive"
    if v >= t[0]: return "Moderate"
    return "Good"


def wind_color(spd):
    """Wind speed color — mirrors windColor()."""
    if spd >= 25: return "#ef4444"
    if spd >= 15: return "#f97316"
    if spd >= 8: return "#10b981"
    return "#38bdf8"


# ====================== TESTS ======================

class TestDistKm:
    """Tests for Haversine distance calculation."""

    def test_same_point(self):
        assert dist_km(10.78, 106.70, 10.78, 106.70) == pytest.approx(0, abs=0.001)

    def test_known_distance(self):
        """HCM (10.78, 106.70) to Vung Tau (10.35, 107.08) ≈ 64km."""
        d = dist_km(10.78, 106.70, 10.35, 107.08)
        assert 55 < d < 75

    def test_symmetry(self):
        """dist(A,B) == dist(B,A)."""
        d1 = dist_km(10.78, 106.70, 10.35, 107.08)
        d2 = dist_km(10.35, 107.08, 10.78, 106.70)
        assert d1 == pytest.approx(d2, abs=0.0001)

    def test_short_distance(self):
        """~1km apart."""
        d = dist_km(10.78, 106.70, 10.789, 106.70)
        assert 0.5 < d < 1.5


class TestNearestK:
    """Tests for nearest station finder."""

    STATIONS = [
        {"lat": 10.78, "lng": 106.70, "name": "S1", "aqi": 50},
        {"lat": 10.90, "lng": 106.80, "name": "S2", "aqi": 80},
        {"lat": 11.00, "lng": 106.90, "name": "S3", "aqi": 120},
    ]

    def test_returns_k(self):
        result = nearest_k(self.STATIONS, 10.78, 106.70, 2)
        assert len(result) == 2

    def test_closest_first(self):
        result = nearest_k(self.STATIONS, 10.78, 106.70, 3)
        assert result[0]["name"] == "S1"  # same point

    def test_k_larger_than_list(self):
        result = nearest_k(self.STATIONS, 10.78, 106.70, 10)
        assert len(result) == 3


class TestIDW:
    """Tests for IDW interpolation."""

    def test_single_station(self):
        """IDW with 1 station should return that station's values."""
        pts = [{"lat": 10.78, "lng": 106.70, "aqi": 50, "pm25": 20, "pm10": 30, "co": 0, "no2": 0, "o3": 0, "so2": 0}]
        result = idw_all(pts, 10.78, 106.70)
        assert result["aqi"] == pytest.approx(50, abs=1)
        assert result["pm25"] == pytest.approx(20, abs=1)

    def test_two_equal_distance(self):
        """Two stations equidistant → should return average."""
        pts = [
            {"lat": 10.79, "lng": 106.70, "aqi": 40, "pm25": 10, "pm10": 0, "co": 0, "no2": 0, "o3": 0, "so2": 0},
            {"lat": 10.77, "lng": 106.70, "aqi": 60, "pm25": 30, "pm10": 0, "co": 0, "no2": 0, "o3": 0, "so2": 0},
        ]
        result = idw_all(pts, 10.78, 106.70)
        assert result["aqi"] == pytest.approx(50, abs=2)

    def test_closer_station_dominates(self):
        """Closer station should have more influence."""
        pts = [
            {"lat": 10.781, "lng": 106.70, "aqi": 100, "pm25": 0, "pm10": 0, "co": 0, "no2": 0, "o3": 0, "so2": 0},
            {"lat": 11.00, "lng": 107.00, "aqi": 0, "pm25": 0, "pm10": 0, "co": 0, "no2": 0, "o3": 0, "so2": 0},
        ]
        result = idw_all(pts, 10.78, 106.70)
        assert result["aqi"] > 80  # should be much closer to 100

    def test_penalty_reduces_weight(self):
        """Buffer station with penalty should have less influence."""
        pts_no_pen = [
            {"lat": 10.79, "lng": 106.70, "aqi": 100, "pm25": 0, "pm10": 0, "co": 0, "no2": 0, "o3": 0, "so2": 0},
            {"lat": 10.77, "lng": 106.70, "aqi": 0, "pm25": 0, "pm10": 0, "co": 0, "no2": 0, "o3": 0, "so2": 0},
        ]
        pts_pen = [
            {"lat": 10.79, "lng": 106.70, "aqi": 100, "pm25": 0, "pm10": 0, "co": 0, "no2": 0, "o3": 0, "so2": 0, "penalty": 0.55},
            {"lat": 10.77, "lng": 106.70, "aqi": 0, "pm25": 0, "pm10": 0, "co": 0, "no2": 0, "o3": 0, "so2": 0},
        ]
        r1 = idw_all(pts_no_pen, 10.78, 106.70)
        r2 = idw_all(pts_pen, 10.78, 106.70)
        assert r2["aqi"] < r1["aqi"]  # penalized station has less influence

    def test_no_stations(self):
        """Empty list should return zeros."""
        result = idw_all([], 10.78, 106.70)
        assert all(v == 0 for v in result.values())


class TestPolColor:
    """Tests for AQI color mapping."""

    def test_good_aqi(self):
        assert pol_color(30, "aqi") == "#38bdf8"  # blue

    def test_moderate_aqi(self):
        assert pol_color(75, "aqi") == "#10b981"  # green

    def test_sensitive_aqi(self):
        assert pol_color(120, "aqi") == "#fbbf24"  # yellow

    def test_unhealthy_aqi(self):
        assert pol_color(165, "aqi") == "#f97316"  # orange

    def test_very_unhealthy_aqi(self):
        assert pol_color(250, "aqi") == "#e11d48"  # red

    def test_pm25_boundaries(self):
        assert pol_color(10, "pm25") == "#38bdf8"
        assert pol_color(12, "pm25") == "#10b981"
        assert pol_color(35, "pm25") == "#fbbf24"
        assert pol_color(55, "pm25") == "#f97316"
        assert pol_color(150, "pm25") == "#e11d48"


class TestPolText:
    """Tests for AQI text classification."""

    def test_good(self):
        assert pol_text(30, "aqi") == "Good"

    def test_moderate(self):
        assert pol_text(75, "aqi") == "Moderate"

    def test_sensitive(self):
        assert pol_text(120, "aqi") == "Sensitive"

    def test_unhealthy(self):
        assert pol_text(180, "aqi") == "Unhealthy"

    def test_very_unhealthy(self):
        assert pol_text(300, "aqi") == "Very Unhealthy"

    def test_boundary_exact(self):
        """Exact boundary value should be the higher category."""
        assert pol_text(50, "aqi") == "Moderate"
        assert pol_text(100, "aqi") == "Sensitive"
        assert pol_text(200, "aqi") == "Very Unhealthy"


class TestWindColor:
    """Tests for wind speed color."""

    def test_light(self):
        assert wind_color(5) == "#38bdf8"

    def test_moderate(self):
        assert wind_color(10) == "#10b981"

    def test_strong(self):
        assert wind_color(18) == "#f97316"

    def test_very_strong(self):
        assert wind_color(30) == "#ef4444"


class TestScientificValidation:
    """Validation tests for scientific accuracy."""

    def test_idw_is_within_range(self):
        """IDW should never extrapolate beyond input values."""
        pts = [
            {"lat": 10.78, "lng": 106.70, "aqi": 30, "pm25": 10, "pm10": 20, "co": 0, "no2": 0, "o3": 0, "so2": 0},
            {"lat": 10.90, "lng": 106.80, "aqi": 80, "pm25": 40, "pm10": 60, "co": 0, "no2": 0, "o3": 0, "so2": 0},
        ]
        # Test many random points
        import random
        random.seed(42)
        for _ in range(50):
            lat = 10.7 + random.random() * 0.3
            lng = 106.6 + random.random() * 0.3
            result = idw_all(pts, lat, lng)
            assert 30 <= result["aqi"] <= 80, f"IDW extrapolated: {result['aqi']} at ({lat},{lng})"
            assert 10 <= result["pm25"] <= 40

    def test_idw_monotonic_with_distance(self):
        """As we move towards station B, IDW should shift towards B's values."""
        s_a = {"lat": 10.70, "lng": 106.70, "aqi": 0, "pm25": 0, "pm10": 0, "co": 0, "no2": 0, "o3": 0, "so2": 0}
        s_b = {"lat": 10.90, "lng": 106.70, "aqi": 100, "pm25": 0, "pm10": 0, "co": 0, "no2": 0, "o3": 0, "so2": 0}
        pts = [s_a, s_b]
        prev = 0
        for step in range(1, 10):
            lat = 10.70 + step * 0.02
            result = idw_all(pts, lat, 106.70)
            assert result["aqi"] >= prev, f"IDW not monotonic at step {step}"
            prev = result["aqi"]

    def test_haversine_accuracy(self):
        """Test against known distance: HN to HCM ≈ 1,140km."""
        d = dist_km(21.028, 105.854, 10.823, 106.630)
        assert 1100 < d < 1180


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
