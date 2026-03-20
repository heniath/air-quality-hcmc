/**
 * core.js — Constants, utility functions, and shared state
 * Megacity AQI Dashboard
 */

// ====================== POLLUTANT DEFINITIONS ======================
const POLS = {
    aqi: { label: "AQI", unit: "", max: 300, t: [50, 100, 150, 200] },
    pm25: { label: "PM2.5", unit: "µg/m³", max: 250, t: [12, 35, 55, 150] },
    pm10: { label: "PM10", unit: "µg/m³", max: 400, t: [54, 154, 254, 354] },
    no2: { label: "NO₂", unit: "ppb", max: 200, t: [53, 100, 360, 649] },
    o3: { label: "O₃", unit: "ppb", max: 200, t: [54, 70, 85, 105] },
    co: { label: "CO", unit: "ppb", max: 500, t: [50, 100, 150, 300] },
    so2: { label: "SO₂", unit: "ppb", max: 200, t: [35, 75, 185, 304] },
};

// ====================== SHARED STATE ======================
let activePol = "aqi", currentLang = "vi", currentCtx = null;
let megaPoly = null, corePool = [], bufPool = [];
let userMarker = null, bufMarker = null, pulseCircle = null;
let showHeatmap = true, showWind = true;

// ====================== UTILITY FUNCTIONS ======================
const norm = s => (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
const getName = p => (p.shapeName || p.ADM1_EN || p.name || p.NAME_1 || "").toString().trim();

/**
 * Haversine distance in km between two lat/lng points
 */
function distKm(lat1, lng1, lat2, lng2) {
    const R = 6371, toR = x => x * Math.PI / 180;
    const dL = toR(lat2 - lat1), dN = toR(lng2 - lng1);
    const h = Math.sin(dL / 2) ** 2 + Math.cos(toR(lat1)) * Math.cos(toR(lat2)) * Math.sin(dN / 2) ** 2;
    return 2 * R * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

/**
 * Find k nearest stations to a point
 */
function nearestK(arr, lat, lng, k) {
    return [...arr].map(s => ({ ...s, _d: distKm(lat, lng, s.lat, s.lng) }))
        .sort((a, b) => a._d - b._d).slice(0, k)
        .map(({ _d, ...r }) => ({ ...r, dKm: _d }));
}

/**
 * Find nearest station within radius r (km)
 */
function nearestIn(arr, lat, lng, r) {
    const list = [...arr].map(s => ({ ...s, _d: distKm(lat, lng, s.lat, s.lng) }))
        .filter(x => x._d <= r).sort((a, b) => a._d - b._d);
    if (!list.length) return null;
    const { _d, ...rest } = list[0];
    return { ...rest, dKm: _d };
}

/**
 * IDW (Inverse Distance Weighting) interpolation
 * @param {Array} pts - Station points with pollutant values
 * @param {number} lat - Target latitude
 * @param {number} lng - Target longitude
 * @param {number} p - Power parameter (default 1.8)
 * @param {number} eps - Epsilon to avoid division by zero (default 0.08)
 */
function idwAll(pts, lat, lng, p = 1.8, eps = 0.08) {
    let sw = 0;
    const sums = { aqi: 0, pm25: 0, pm10: 0, co: 0, no2: 0, o3: 0, so2: 0 };
    for (const pt of pts) {
        const d = distKm(lat, lng, pt.lat, pt.lng);
        const w = (pt.penalty ?? 1) / Math.pow(d + eps, p);
        sw += w;
        for (const k of Object.keys(sums)) sums[k] += (Number(pt[k]) || 0) * w;
    }
    if (!sw) return sums;
    for (const k of Object.keys(sums)) sums[k] /= sw;
    return sums;
}

/**
 * Get color for pollutant value based on EPA breakpoints
 */
function polColor(v, p) {
    const t = POLS[p]?.t || [50, 100, 150, 200];
    if (v >= t[3]) return '#e11d48';
    if (v >= t[2]) return '#f97316';
    if (v >= t[1]) return '#fbbf24';
    if (v >= t[0]) return '#10b981';
    return '#38bdf8';
}

/**
 * Get text classification for pollutant value
 */
function polText(v, p) {
    const t = POLS[p]?.t || [50, 100, 150, 200];
    if (v >= t[3]) return 'Very Unhealthy';
    if (v >= t[2]) return 'Unhealthy';
    if (v >= t[1]) return 'Sensitive';
    if (v >= t[0]) return 'Moderate';
    return 'Good';
}

/**
 * Force certain provinces to buffer pool
 */
function forceBuffer(slug) {
    const s = (slug || "").toLowerCase();
    return s.includes("long-an") || s.includes("tay-ninh");
}
