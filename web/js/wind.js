/**
 * wind.js — Wind visualization: arrows, trails, and animated flow field
 * Megacity AQI Dashboard
 */

// ====================== WIND LAYER (Arrows + Trails) ======================
function windColor(spd) {
    if (spd >= 25) return '#ef4444';
    if (spd >= 15) return '#f97316';
    if (spd >= 8) return '#10b981';
    return '#38bdf8';
}

function windSpeedText(spd) {
    if (spd >= 25) return 'Rất mạnh';
    if (spd >= 15) return 'Mạnh';
    if (spd >= 8) return 'Nhẹ';
    return 'Lặng';
}

function drawWindLayer() {
    windGroup.clearLayers();
    if (!showWind) return;
    const all = [...corePool, ...bufPool];
    all.forEach(s => {
        if (s.wind_degree == null || s.wind_kph == null || !s.wind_kph) return;
        const spd = s.wind_kph, deg = s.wind_degree, color = windColor(spd);
        const sz = Math.min(40, 22 + spd * 0.7);
        const rot = (deg + 180) % 360;
        const arrow = `<div style="transform:rotate(${rot}deg);width:${sz}px;height:${sz}px;filter:drop-shadow(0 0 6px ${color}80)" class="wind-pulse">
      <svg viewBox="0 0 32 32" width="${sz}" height="${sz}">
        <path d="M16 2 L22 16 L16 11 L10 16 Z" fill="${color}" opacity=".9"/>
        <line x1="16" y1="11" x2="16" y2="28" stroke="${color}" stroke-width="1.5" opacity=".3" stroke-dasharray="2,2"/>
      </svg>
    </div>`;
        const icon = L.divIcon({ className: 'wind-arrow', html: arrow, iconSize: [sz, sz], iconAnchor: [sz / 2, sz / 2] });
        L.marker([s.lat, s.lng], { icon, interactive: false, zIndexOffset: 500 }).addTo(windGroup);

        const lbl = `<div class="wind-speed-lbl" style="color:${color};white-space:nowrap">${spd}<span style="opacity:.5;font-size:7px">km/h</span></div>`;
        const lblIcon = L.divIcon({ className: '', html: lbl, iconSize: [50, 14], iconAnchor: [-sz / 2 - 2, 7] });
        L.marker([s.lat, s.lng], { icon: lblIcon, interactive: false, zIndexOffset: 500 }).addTo(windGroup);

        const rad = rot * Math.PI / 180;
        for (let i = 1; i <= 3; i++) {
            const dist = 0.012 * i;
            const dlat = Math.cos(rad) * dist, dlng = Math.sin(rad) * dist;
            const dotSz = Math.max(3, 6 - i);
            const tx = Math.round(Math.sin(rad) * 30), ty = Math.round(-Math.cos(rad) * 30);
            const delay = (i * 0.6).toFixed(1);
            const dotHtml = `<div class="wind-trail" style="width:${dotSz}px;height:${dotSz}px;background:${color};--tx:${tx}px;--ty:${ty}px;animation-delay:${delay}s;box-shadow:0 0 4px ${color}"></div>`;
            const dotIcon = L.divIcon({ className: '', html: dotHtml, iconSize: [dotSz, dotSz], iconAnchor: [dotSz / 2, dotSz / 2] });
            L.marker([s.lat + dlat, s.lng + dlng], { icon: dotIcon, interactive: false, zIndexOffset: 400 }).addTo(windGroup);
        }
    });
}

// ====================== FLOW FIELD (Canvas particle system) ======================
let flowActive = false, flowAnimId = null, particles = [];
let windGrid = null, windGridBounds = null;
const PARTICLE_COUNT = 300, PARTICLE_LIFE = 80, GRID_RES = 20;

/**
 * Interpolate wind at any point using IDW from station data
 */
function interpWind(lat, lng) {
    const all = [...corePool, ...bufPool].filter(s => s.wind_degree != null && s.wind_kph > 0);
    if (!all.length) return { u: 0, v: 0, spd: 0 };
    let sw = 0, su = 0, sv = 0;
    for (const s of all) {
        const rad = (s.wind_degree + 180) * Math.PI / 180;
        const u = s.wind_kph * Math.sin(rad), v = s.wind_kph * Math.cos(rad);
        const d = distKm(lat, lng, s.lat, s.lng);
        const w = 1 / Math.pow(d + 0.5, 2); sw += w; su += u * w; sv += v * w;
    }
    return { u: su / sw, v: sv / sw, spd: Math.sqrt((su / sw) ** 2 + (sv / sw) ** 2) };
}

/**
 * Pre-compute wind grid for O(1) lookups during animation
 */
function buildWindGrid() {
    const b = map.getBounds();
    windGridBounds = { s: b.getSouth(), n: b.getNorth(), w: b.getWest(), e: b.getEast() };
    const dlat = (windGridBounds.n - windGridBounds.s) / GRID_RES;
    const dlng = (windGridBounds.e - windGridBounds.w) / GRID_RES;
    windGrid = [];
    for (let i = 0; i <= GRID_RES; i++) {
        windGrid[i] = [];
        for (let j = 0; j <= GRID_RES; j++) {
            windGrid[i][j] = interpWind(windGridBounds.s + i * dlat, windGridBounds.w + j * dlng);
        }
    }
}

/**
 * Bilinear interpolation from pre-computed wind grid — O(1)
 */
function gridWind(lat, lng) {
    if (!windGrid || !windGridBounds) return { u: 0, v: 0, spd: 0 };
    const fi = (lat - windGridBounds.s) / (windGridBounds.n - windGridBounds.s) * GRID_RES;
    const fj = (lng - windGridBounds.w) / (windGridBounds.e - windGridBounds.w) * GRID_RES;
    const i0 = Math.max(0, Math.min(GRID_RES - 1, Math.floor(fi)));
    const j0 = Math.max(0, Math.min(GRID_RES - 1, Math.floor(fj)));
    const di = fi - i0, dj = fj - j0;
    const g00 = windGrid[i0][j0], g01 = windGrid[i0][j0 + 1] || g00;
    const g10 = windGrid[i0 + 1] ? windGrid[i0 + 1][j0] : g00;
    const g11 = windGrid[i0 + 1] ? (windGrid[i0 + 1][j0 + 1] || g10) : g01;
    return {
        u: g00.u * (1 - di) * (1 - dj) + g10.u * di * (1 - dj) + g01.u * (1 - di) * dj + g11.u * di * dj,
        v: g00.v * (1 - di) * (1 - dj) + g10.v * di * (1 - dj) + g01.v * (1 - di) * dj + g11.v * di * dj,
        spd: g00.spd * (1 - di) * (1 - dj) + g10.spd * di * (1 - dj) + g01.spd * (1 - di) * dj + g11.spd * di * dj,
    };
}

function initFlowField() {
    const canvas = document.getElementById('flowCanvas');
    const mapEl = document.getElementById('map');
    canvas.width = mapEl.offsetWidth; canvas.height = mapEl.offsetHeight;
    particles = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) particles.push(spawnParticle());
    buildWindGrid();
}

function spawnParticle() {
    const b = map.getBounds();
    return {
        lat: b.getSouth() + Math.random() * (b.getNorth() - b.getSouth()),
        lng: b.getWest() + Math.random() * (b.getEast() - b.getWest()),
        age: Math.floor(Math.random() * PARTICLE_LIFE)
    };
}

function animateFlow() {
    if (!flowActive) return;
    const canvas = document.getElementById('flowCanvas'), ctx = canvas.getContext('2d');
    ctx.fillStyle = 'rgba(240,244,248,0.20)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    const b = map.getBounds();
    const viewSpan = b.getNorth() - b.getSouth();
    const speedScale = viewSpan / 80000;
    const cosLat = Math.cos(map.getCenter().lat * Math.PI / 180);
    for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        const w = gridWind(p.lat, p.lng);
        p.lat += w.v * speedScale;
        p.lng += w.u * speedScale / cosLat;
        p.age++;
        if (p.age > PARTICLE_LIFE || !map.getBounds().contains([p.lat, p.lng])) { particles[i] = spawnParticle(); continue; }
        const pt = map.latLngToContainerPoint([p.lat, p.lng]);
        const alpha = Math.min(1, (1 - p.age / PARTICLE_LIFE) * 1.5);
        const spd = w.spd;
        const r = spd > 15 ? 255 : spd > 8 ? 16 : 56;
        const g = spd > 15 ? 115 : spd > 8 ? 185 : 189;
        const bl = spd > 15 ? 22 : spd > 8 ? 129 : 248;
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, spd > 15 ? 2.5 : spd > 8 ? 2 : 1.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r},${g},${bl},${alpha * 0.8})`;
        ctx.fill();
    }
    flowAnimId = requestAnimationFrame(animateFlow);
}

function toggleFlow() {
    flowActive = !flowActive;
    const canvas = document.getElementById('flowCanvas');
    document.getElementById('flowDot').className = flowActive ? 'w-2 h-2 rounded-full bg-cyan-400 animate-pulse' : 'w-2 h-2 rounded-full bg-gray-600';
    if (flowActive) {
        canvas.style.display = 'block'; initFlowField(); animateFlow();
        map.on('moveend', initFlowField); map.on('zoomend', initFlowField);
    } else {
        canvas.style.display = 'none';
        if (flowAnimId) { cancelAnimationFrame(flowAnimId); flowAnimId = null; }
        const ctx = canvas.getContext('2d'); ctx.clearRect(0, 0, canvas.width, canvas.height);
        map.off('moveend', initFlowField); map.off('zoomend', initFlowField);
    }
}