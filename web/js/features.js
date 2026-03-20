/**
 * features.js — Timeline Playback, Comparison Mode, Nearby POI
 * Megacity AQI Dashboard
 */

// ====================== TIMELINE PLAYBACK ======================
let tlData = {}, tlPlaying = false, tlInterval = null, tlActive = false;

async function loadTimeline() {
    const slugs = corePool.map(s => s.slug);
    const results = await Promise.allSettled(slugs.map(slug => fetch(`/api/history/${slug}?sensor=aqi`).then(r => r.json())));
    tlData = {};
    results.forEach((r, i) => {
        if (r.status === 'fulfilled' && r.value.status === 'success' && r.value.data) {
            const d = r.value.data;
            if (!d.timeArray || !d.averageArray) return;
            d.timeArray.forEach((t, j) => {
                const key = j;
                if (!tlData[key]) tlData[key] = {};
                tlData[key][corePool[i].slug] = { aqi: d.averageArray[j], time: t };
            });
        }
    });
    const keys = Object.keys(tlData).map(Number);
    const maxIdx = keys.length > 0 ? Math.max(...keys) : 23;
    document.getElementById('timeRange').max = maxIdx;
    document.getElementById('timeRange').value = maxIdx;
}

function applyTimeIndex(idx) {
    const snap = tlData[idx] || {};
    markerGroup.clearLayers();
    corePool.forEach(s => {
        const hv = snap[s.slug];
        const val = hv ? hv.aqi : s[activePol];
        L.circleMarker([s.lat, s.lng], { radius: 7, weight: 1, color: 'rgba(255,255,255,0.2)', fillColor: polColor(val, 'aqi'), fillOpacity: .92 })
            .addTo(markerGroup).bindPopup(`<div style="padding:12px;font-family:Outfit"><b>${s.name}</b><br>AQI: <b style="color:${polColor(val, 'aqi')}">${Math.round(val)}</b>${hv ? '<br><span style="font-size:10px;color:#6b7280">' + new Date(hv.time).toLocaleTimeString('vi') + '</span>' : ''}</div>`, { maxWidth: 250 });
    });
    bufPool.forEach(s => { L.circleMarker([s.lat, s.lng], { radius: 5, weight: 1, color: 'rgba(239,68,68,0.5)', fillColor: 'rgba(239,68,68,0.3)', fillOpacity: .7 }).addTo(markerGroup); });
    const first = Object.values(snap)[0];
    document.getElementById('timeLabel').textContent = first ? new Date(first.time).toLocaleTimeString('vi', { hour: '2-digit', minute: '2-digit' }) : 'Now';
}

function toggleTimeline() {
    tlActive = !tlActive;
    document.getElementById('timeSliderBox').style.display = tlActive ? 'block' : 'none';
    document.getElementById('tlDot').className = tlActive ? 'w-2 h-2 rounded-full bg-orange-500 animate-pulse' : 'w-2 h-2 rounded-full bg-gray-600';
    if (tlActive && !Object.keys(tlData).length) loadTimeline().then(() => addAIMessage('⏱ Timeline loaded! Drag slider or press ▶️'));
    if (!tlActive) { stopPlayback(); drawMarkers(); document.getElementById('timeLabel').textContent = 'Now'; }
}

function startPlayback() {
    if (tlPlaying) { stopPlayback(); return; }
    tlPlaying = true; document.getElementById('btnPlay').textContent = '⏸️';
    const range = document.getElementById('timeRange'), max = parseInt(range.max);
    let idx = 0; range.value = 0;
    tlInterval = setInterval(() => {
        applyTimeIndex(idx); range.value = idx;
        idx++; if (idx > max) { stopPlayback(); }
    }, 400);
}

function stopPlayback() {
    tlPlaying = false; document.getElementById('btnPlay').textContent = '▶️';
    if (tlInterval) { clearInterval(tlInterval); tlInterval = null; }
}

// ====================== COMPARISON MODE ======================
let cmpMode = false, cmpPoints = [];

function toggleCompare() {
    cmpMode = !cmpMode;
    document.getElementById('comparePanel').style.display = cmpMode ? 'flex' : 'none';
    document.getElementById('cmpDot').className = cmpMode ? 'w-2 h-2 rounded-full bg-violet-500 animate-pulse' : 'w-2 h-2 rounded-full bg-gray-600';
    if (cmpMode) {
        cmpPoints = [];
        document.getElementById('cmpA').innerHTML = '<div class="text-[10px] text-orange-400 font-bold mb-2">📍 POINT A</div><div class="text-xs text-gray-500">Click map...</div>';
        document.getElementById('cmpB').innerHTML = '<div class="text-[10px] text-sky-400 font-bold mb-2">📍 POINT B</div><div class="text-xs text-gray-500">Click map...</div>';
    } else {
        cmpPoints = [];
        drawMarkers();
    }
}

function cmpCardHTML(tag, color, lat, lng, est, nearest) {
    return `<div class="text-[10px] text-${color}-400 font-bold mb-2">${tag}</div>
    <div class="text-[10px] text-gray-500 mb-2">${lat.toFixed(4)}, ${lng.toFixed(4)}</div>
    <div class="text-2xl font-black mb-1" style="color:${polColor(est.aqi, 'aqi')}">${Math.round(est.aqi)}</div>
    <div class="text-[9px] font-bold mb-2" style="color:${polColor(est.aqi, 'aqi')}">${polText(est.aqi, 'aqi')}</div>
    <div class="grid grid-cols-2 gap-1 text-[10px]">
      <div>PM2.5: <b style="color:${polColor(est.pm25, 'pm25')}">${Math.round(est.pm25)}</b></div>
      <div>PM10: <b>${Math.round(est.pm10)}</b></div>
      <div>NO₂: <b>${Math.round(est.no2)}</b></div>
      <div>O₃: <b>${Math.round(est.o3)}</b></div>
    </div>
    ${nearest ? `<div class="text-[9px] text-gray-500 mt-2">🌡${nearest.temp_c || '--'}°C 💧${nearest.humidity || '--'}% 💨${nearest.wind_kph || '--'}</div>` : ''}`;
}

function handleCompareClick(lat, lng) {
    if (!cmpMode) return false;
    const core3 = nearestK(corePool, lat, lng, 3).map(x => ({ ...x, type: 'core', penalty: 1 }));
    const est = idwAll(core3, lat, lng);
    const nearest = nearestK([...corePool, ...bufPool], lat, lng, 1)[0];
    if (cmpPoints.length === 0) {
        cmpPoints.push({ lat, lng, est, nearest });
        document.getElementById('cmpA').innerHTML = cmpCardHTML('📍 POINT A', 'orange', lat, lng, est, nearest);
        L.circleMarker([lat, lng], { radius: 10, weight: 2, color: '#f97316', fillColor: '#f97316', fillOpacity: .4 }).addTo(markerGroup);
    } else if (cmpPoints.length === 1) {
        cmpPoints.push({ lat, lng, est, nearest });
        document.getElementById('cmpB').innerHTML = cmpCardHTML('📍 POINT B', 'sky', lat, lng, est, nearest);
        L.circleMarker([lat, lng], { radius: 10, weight: 2, color: '#38bdf8', fillColor: '#38bdf8', fillOpacity: .4 }).addTo(markerGroup);
        const a = cmpPoints[0].est, b = cmpPoints[1].est;
        const diff = Math.round(b.aqi - a.aqi);
        addAIMessage(`🔀 <b>So sánh:</b> A(AQI ${Math.round(a.aqi)}) vs B(AQI ${Math.round(b.aqi)}) → Chênh <b>${diff > 0 ? '+' : ''}${diff}</b>. ${Math.abs(diff) > 20 ? '⚠️ Chênh lệch lớn!' : '✅ Tương đương'}`);
    } else {
        cmpPoints = [];
        document.getElementById('cmpA').innerHTML = '<div class="text-[10px] text-orange-400 font-bold mb-2">📍 POINT A</div><div class="text-xs text-gray-500">Click map...</div>';
        document.getElementById('cmpB').innerHTML = '<div class="text-[10px] text-sky-400 font-bold mb-2">📍 POINT B</div><div class="text-xs text-gray-500">Click map...</div>';
        handleCompareClick(lat, lng);
    }
    return true;
}

// ====================== NEARBY POI ======================
const poiGroup = L.layerGroup();
let poiVisible = false, _poiTimer = null;

async function fetchPOI(lat, lng, aqi) {
    if (_poiTimer) clearTimeout(_poiTimer);
    _poiTimer = setTimeout(async () => {
        poiGroup.clearLayers();
        if (aqi < 80) { if (poiVisible) { map.removeLayer(poiGroup); poiVisible = false; } return; }
        try {
            const r = await fetch(`/api/poi?lat=${lat}&lng=${lng}&radius=3000`).then(res => res.json());
            if (!r.pois || !r.pois.length) return;
            const icons = { school: '🏫', hospital: '🏥', kindergarten: '👶' };
            r.pois.forEach(p => {
                const emoji = icons[p.type] || '📍';
                const icon = L.divIcon({ className: '', html: `<div class="poi-icon">${emoji}</div>`, iconSize: [20, 20], iconAnchor: [10, 10] });
                L.marker([p.lat, p.lng], { icon }).bindPopup(`<div style="padding:8px;font-family:Outfit;background:#0d111e;color:#f3f4f6;border-radius:12px"><b>${emoji} ${p.name}</b><br><span style="font-size:10px;color:#6b7280">${p.type}</span></div>`, { maxWidth: 200 }).addTo(poiGroup);
            });
            if (!poiVisible) { poiGroup.addTo(map); poiVisible = true; }
            addAIMessage(`🚨 <b>AQI ${Math.round(aqi)}</b> — Tìm thấy <b>${r.pois.length}</b> trường học/bệnh viện trong 3km! Nhóm nhạy cảm cần cẩn thận.`);
        } catch (e) { console.error('POI error:', e); }
    }, 2000);
}
