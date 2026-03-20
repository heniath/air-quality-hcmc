/**
 * app.js — Main application logic, UI interactions, and Map initialization
 * Megacity AQI Dashboard
 */

// ====================== MAP & LAYERS ======================
const map = L.map("map", { zoomControl: false }).setView([10.7769, 106.7009], 9.8);
L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", { maxZoom: 19, attribution: '&copy; <a href="https://carto.com">CARTO</a>' }).addTo(map);

const heatmapGroup = L.layerGroup().addTo(map);
const markerGroup = L.layerGroup().addTo(map);
const windGroup = L.layerGroup().addTo(map); 

// ====================== DATA LOADING ======================
async function loadBoundary() {
    try {
        const res = await fetch("/geoBoundaries-VNM-ADM1.geojson");
        const data = await res.json();
        const megaNames = ["Ho Chi Minh", "Bình Dương", "Bà Rịa\u2013Vũng Tàu"];
        const matching = data.features.filter(f => megaNames.includes(getName(f.properties)));
        if (matching.length > 0) {
            megaPoly = matching.reduce((acc, f) => acc ? turf.union(acc, f) : f);
            L.geoJSON(megaPoly, { style: { color: "#10b981", weight: 2, fillOpacity: 0.03, dashArray: "5, 10" }, interactive: false }).addTo(map);
        }
    } catch (e) { console.error("Boundary error:", e); }
}

async function loadStations() {
    try {
        const res = await fetch("/api/stations").then(r => r.json());
        const valid = (res.stations || []).filter(x => !x.error && Number.isFinite(x.lat) && Number.isFinite(x.lng))
            .map(x => ({ ...x, lat: Number(x.lat), lng: Number(x.lng), aqi: Number(x.aqi) || 0, pm25: Number(x.pm25) || 0, pm10: Number(x.pm10) || 0, co: Number(x.co) || 0, no2: Number(x.no2) || 0, o3: Number(x.o3) || 0, so2: Number(x.so2) || 0 }));

        corePool = []; bufPool = [];
        valid.forEach(s => {
            let inside = true;
            if (megaPoly) { try { inside = turf.booleanPointInPolygon(turf.point([s.lng, s.lat]), megaPoly); } catch (e) { inside = true; } }
            if (!inside || forceBuffer(s.slug)) bufPool.push(s);
            else corePool.push(s);
        });

        document.getElementById("corePool").textContent = corePool.length;
        document.getElementById("bufPool").textContent = bufPool.length;
        drawMarkers(); drawStationList();
        if (typeof drawWindLayer === 'function') drawWindLayer();
        drawHeatmap();
    } catch (e) {
        console.error("Failed to load stations:", e);
        addAIMessage("❌ Không tải được dữ liệu trạm. Vui lòng thử lại.");
    }
}

// ====================== RENDERING ======================
function drawMarkers() {
    markerGroup.clearLayers();
    const p = activePol;
    corePool.forEach(s => {
        L.circleMarker([s.lat, s.lng], { radius: 7, weight: 1, color: "rgba(255,255,255,0.2)", fillColor: polColor(s[p], p), fillOpacity: .92 })
            .addTo(markerGroup)
            .bindPopup(stationPopupHTML(s), { maxWidth: 280 })
            .on("click", e => { L.DomEvent.stopPropagation(e); updateAt(s.lat, s.lng); });
    });
    bufPool.forEach(s => {
        L.circleMarker([s.lat, s.lng], { radius: 5, weight: 1, color: "rgba(239,68,68,0.5)", fillColor: "rgba(239,68,68,0.3)", fillOpacity: .7 }).addTo(markerGroup);
    });
}

// ====================== HEATMAP ======================
function drawHeatmap() {
    heatmapGroup.clearLayers();
    if (!showHeatmap || corePool.length === 0) return;
    const allStations = [...corePool, ...bufPool];
    const p = activePol;
    const bounds = map.getBounds();
    const zoom = map.getZoom();
    // Grid resolution — higher = denser but slower
    const gridSize = zoom >= 13 ? 25 : zoom >= 11 ? 20 : 16;
    const latStep = (bounds.getNorth() - bounds.getSouth()) / gridSize;
    const lngStep = (bounds.getEast() - bounds.getWest()) / gridSize;
    // Radius = ~70% of grid spacing (in meters) so circles overlap
    const radius = Math.round(latStep * 111000 * 0.7);

    for (let i = 0; i <= gridSize; i++) {
        for (let j = 0; j <= gridSize; j++) {
            const lat = bounds.getSouth() + i * latStep;
            const lng = bounds.getWest() + j * lngStep;
            // Only draw inside megaPoly if available
            if (megaPoly) {
                try {
                    if (!turf.booleanPointInPolygon(turf.point([lng, lat]), megaPoly)) continue;
                } catch (e) {
                    // megaPoly might be MultiPolygon — check each polygon individually
                    try {
                        const geom = megaPoly.geometry || (megaPoly.features && megaPoly.features[0]?.geometry);
                        if (geom?.type === 'MultiPolygon') {
                            const inside = geom.coordinates.some(coords =>
                                turf.booleanPointInPolygon(turf.point([lng, lat]), turf.polygon(coords))
                            );
                            if (!inside) continue;
                        }
                    } catch (e2) { /* draw anyway if all checks fail */ }
                }
            }
            const nearby = nearestK(allStations, lat, lng, 4);
            if (nearby.length === 0) continue;
            const val = idwAll(nearby.map(s => ({ ...s, type: "core", penalty: 1 })), lat, lng);
            const v = Math.round(val[p] || 0);
            L.circle([lat, lng], {
                radius: radius,
                stroke: false,
                fillColor: polColor(v, p),
                fillOpacity: 0.22
            }).addTo(heatmapGroup);
        }
    }
}

function toggleHeatmap() {
    showHeatmap = !showHeatmap;
    const dot = document.getElementById('heatDot');
    if (dot) dot.className = 'w-2 h-2 rounded-full ' + (showHeatmap ? 'bg-orange-400 animate-pulse' : 'bg-gray-600');
    drawHeatmap();
}

// Convert hex to rgba for proper alpha support
const hexToRgba = (hex, a) => {
    const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${a})`;
};

function switchPol(p) {
    activePol = p;
    const sel = document.getElementById('polSelect');
    if (sel) sel.value = p;
    drawMarkers(); drawStationList(); drawHeatmap();
    if (currentCtx) {
        const est = currentCtx.est, mv = est[p];
        document.getElementById("mainLabel").textContent = POLS[p].label;
        document.getElementById("mainVal").textContent = Math.round(mv);
        document.getElementById("mainVal").style.color = polColor(mv, p);
        const st = document.getElementById("mainStatus");
        st.textContent = polText(mv, p);
        st.style.background = hexToRgba(polColor(mv, p), 0.13);
        st.style.color = polColor(mv, p);
        ['pm25', 'pm10', 'no2', 'o3', 'co', 'so2'].forEach(k => {
            const v = Math.round(est[k]);
            const el = document.getElementById(k + "Val"), bar = document.getElementById(k + "Bar");
            if (el) { el.textContent = v; el.style.color = polColor(v, k); }
            if (bar) { bar.style.width = Math.min(100, (v / POLS[k].max) * 100) + "%"; bar.style.backgroundColor = polColor(v, k); }
        });
    }
}

function toggleWind() {
    showWind = !showWind;
    const dot = document.getElementById('windDot');
    if (dot) dot.className = 'w-2 h-2 rounded-full ' + (showWind ? 'bg-sky-400 animate-pulse' : 'bg-gray-600');
    drawWindLayer();
}

function stationPopupHTML(s) {
    const aq = s.aqi || 0, c = polColor(aq, "aqi"), pm25C = polColor(s.pm25 || 0, "pm25");
    return `<div style="padding:16px;min-width:240px;font-family:Outfit">
    <div style="font-size:10px;color:#6b7280;text-transform:uppercase;font-weight:700;margin-bottom:4px">${s.city || 'Station'}</div>
    <div style="font-size:16px;font-weight:900;color:#f3f4f6">${s.name}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px">
      <div style="background:${hexToRgba(c, 0.08)};padding:10px;border-radius:14px;text-align:center;border:1px solid ${hexToRgba(c, 0.2)}">
        <div style="font-size:24px;font-weight:900;color:${c}">${aq}</div>
        <div style="font-size:9px;color:${c};font-weight:700">AQI</div>
      </div>
      <div style="background:rgba(255,255,255,0.05);padding:10px;border-radius:14px;text-align:center">
        <div style="font-size:24px;font-weight:900;color:${pm25C}">${s.pm25 || '--'}</div>
        <div style="font-size:9px;color:#6b7280">PM2.5</div>
      </div>
    </div>
  </div>`;
}

function drawStationList() {
    const p = activePol;
    document.getElementById("stList").innerHTML = [...corePool, ...bufPool].map(s => `
    <div class="flex items-center justify-between p-2 rounded-2xl bg-white/5 hover:bg-white/10 transition cursor-pointer" onclick="goTo(${s.lat},${s.lng})">
      <div class="flex items-center gap-2 truncate">
        <div class="shrink-0 w-1.5 h-4 rounded-full" style="background:${polColor(s[p], p)}"></div>
        <div class="truncate text-[11px] font-bold">${s.name}</div>
      </div>
      <div class="text-[11px] font-bold" style="color:${polColor(s[p], p)}">${s[p]}</div>
    </div>`).join("");
}

// ====================== ANALYSIS ======================
function dBorderKm(lat, lng) {
    if (!megaPoly) return 999;
    try {
        const pt = turf.point([lng, lat]);
        const line = turf.polygonToLine(megaPoly);
        const geometry = line.type === "FeatureCollection" ? line.features[0] : line;
        return turf.pointToLineDistance(pt, geometry, { units: "kilometers" });
    } catch (e) { return 999; }
}

function updateAt(lat, lng) {
    if (typeof handleCompareClick === 'function' && handleCompareClick(lat, lng)) return;

    // Remove previous click marker & radius
    if (userMarker) { map.removeLayer(userMarker); userMarker = null; }
    if (pulseCircle) { map.removeLayer(pulseCircle); pulseCircle = null; }
    if (bufMarker) { map.removeLayer(bufMarker); bufMarker = null; }

    let inside = true;
    if (megaPoly) { try { inside = turf.booleanPointInPolygon(turf.point([lng, lat]), megaPoly); } catch (e) { inside = true; } }
    const db = dBorderKm(lat, lng);
    const core3 = nearestK(corePool, lat, lng, 3).map(x => ({ ...x, type: "core", penalty: 1 }));
    let buf1 = null;
    if (db <= 20) { buf1 = nearestIn(bufPool, lat, lng, 30) || nearestIn(bufPool, lat, lng, 45); }

    const used = [...core3];
    if (buf1) used.push({ ...buf1, type: "buffer", penalty: .55 });

    const est = idwAll(used, lat, lng), p = activePol, mv = est[p];
    currentCtx = { lat, lng, inside, est, nearest: nearestK([...corePool, ...bufPool], lat, lng, 1)[0] };

    // Update UI Elements
    document.getElementById("locName").textContent = inside ? "Inside Megacity" : "Outside";
    document.getElementById("latlng").textContent = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    document.getElementById("mainLabel").textContent = POLS[p].label;
    document.getElementById("mainVal").textContent = Math.round(mv);
    document.getElementById("mainVal").style.color = polColor(mv, p);

    const st = document.getElementById("mainStatus");
    st.textContent = polText(mv, p);
    st.style.background = hexToRgba(polColor(mv, p), 0.13);
    st.style.color = polColor(mv, p);

    ['pm25', 'pm10', 'no2', 'o3', 'co', 'so2'].forEach(k => {
        const v = Math.round(est[k]);
        const el = document.getElementById(k + "Val"), bar = document.getElementById(k + "Bar");
        if (el) { el.textContent = v; el.style.color = polColor(v, k); }
        if (bar) { bar.style.width = Math.min(100, (v / POLS[k].max) * 100) + "%"; bar.style.backgroundColor = polColor(v, k); }
    });

    if (currentCtx.nearest) {
        const n = currentCtx.nearest;
        document.getElementById("wTemp").textContent = (n.temp_c ?? "--") + "°C";
        document.getElementById("wHum").textContent = (n.humidity ?? "--") + "%";
        document.getElementById("wWind").textContent = (n.wind_kph ?? "--") + " km/h";
    }

    // Draw click marker (pulsing dot)
    const mc = polColor(mv, p);
    userMarker = L.circleMarker([lat, lng], {
        radius: 8, weight: 2, color: mc, fillColor: mc, fillOpacity: 0.9,
        className: 'click-marker-pulse'
    }).addTo(map);

    // Draw IDW radius circle (~3km)
    pulseCircle = L.circle([lat, lng], {
        radius: 3000, weight: 1.5, color: mc, fillColor: mc,
        fillOpacity: 0.06, dashArray: '6, 8'
    }).addTo(map);

    // Draw line to nearest station
    if (currentCtx.nearest) {
        const n = currentCtx.nearest;
        bufMarker = L.polyline([[lat, lng], [n.lat, n.lng]], {
            color: 'rgba(255,255,255,0.12)', weight: 1, dashArray: '4, 6'
        }).addTo(map);
    }

    aiAutoAnalyze(currentCtx);
    loadChart();
    if (typeof fetchPOI === 'function') fetchPOI(lat, lng, est.aqi);
}

// ====================== AI & UI ======================
function addAIMessage(text) {
    const el = document.getElementById("chatMessages");
    const msg = document.createElement("div");
    msg.className = "chat-bubble chat-ai";
    msg.innerHTML = text.replace(/\n/g, '<br>');
    el.appendChild(msg); el.scrollTop = el.scrollHeight;
}

function addUserMessage(text) {
    const el = document.getElementById("chatMessages");
    const msg = document.createElement("div");
    msg.className = "chat-bubble chat-user";
    msg.textContent = text;
    el.appendChild(msg); el.scrollTop = el.scrollHeight;
}

function aiAutoAnalyze(ctx) {
    const aqi = Math.round(ctx.est.aqi);
    let status = polText(aqi, 'aqi');
    let msg = `📍 <b>Phân tích:</b> AQI ${aqi} (${status}).<br>`;
    if (aqi <= 50) msg += "✨ Không khí tuyệt vời!";
    else if (aqi <= 100) msg += "🌿 Bình thường, nhóm nhạy cảm lưu ý.";
    else msg += "⚠️ Ô nhiễm, hạn chế ra ngoài.";
    addAIMessage(msg);
}

async function sendChat() {
    const inp = document.getElementById("chatInput");
    const msg = inp.value.trim();
    if (!msg) return;
    if (!currentCtx) {
        addAIMessage("📍 Vui lòng click vào bản đồ trước để AI có dữ liệu phân tích.");
        return;
    }
    addUserMessage(msg); inp.value = "";
    // Show typing indicator
    const chatEl = document.getElementById("chatMessages");
    const typing = document.createElement("div");
    typing.className = "chat-bubble chat-ai";
    typing.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
    chatEl.appendChild(typing); chatEl.scrollTop = chatEl.scrollHeight;
    try {
        const res = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: msg, context: currentCtx }) });
        const data = await res.json();
        typing.remove();
        if (data.error) {
            addAIMessage(`⚠️ AI Error: ${data.error}`);
        } else {
            addAIMessage(data.reply || "🤖 Không có phản hồi.");
        }
    } catch (e) {
        typing.remove();
        addAIMessage("❌ Không thể kết nối AI. Kiểm tra mạng và thử lại.");
    }
}

let _searchTimer = null;
function debouncedSearch() { clearTimeout(_searchTimer); _searchTimer = setTimeout(searchLocation, 400); }

async function searchLocation() {
    const q = document.getElementById("searchInp").value.trim();
    const box = document.getElementById("searchBox");
    if (q.length < 3) { box.style.display = "none"; return; }
    try {
        const results = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}&viewbox=105.5,11.5,107.5,10.0&bounded=1`).then(resp => resp.json());
        box.innerHTML = '';
        if (results.length === 0) {
            box.innerHTML = '<div class="search-result" style="color:#6b7280;cursor:default">Không tìm thấy kết quả</div>';
        } else {
            results.forEach(item => {
                const div = document.createElement('div');
                div.className = 'search-result';
                div.textContent = item.display_name;
                div.onclick = () => goTo(Number(item.lat), Number(item.lon));
                box.appendChild(div);
            });
        }
        box.style.display = "block";
    } catch (e) {
        box.innerHTML = '<div class="search-result" style="color:#ef4444;cursor:default">⚠️ Lỗi tìm kiếm. Thử lại sau.</div>';
        box.style.display = "block";
    }
}

function goTo(lat, lng) {
    map.setView([lat, lng], 13);
    document.getElementById("searchBox").style.display = "none";
    document.getElementById("searchInp").value = "";
    updateAt(lat, lng);
}

let trendChart = null;
async function loadChart() {
    if (!currentCtx?.nearest) return;
    const slug = currentCtx.nearest.slug, pol = document.getElementById("chartPol").value;
    try {
        const res = await fetch(`/api/history/${slug}?sensor=${pol}`).then(r => r.json());
        if (res.status !== "success") return;
        const ctx = document.getElementById('trendCanvas').getContext('2d');
        if (trendChart) trendChart.destroy();
        trendChart = new Chart(ctx, {
            type: 'line', data: { labels: res.data.timeArray.map(t => new Date(t).getHours() + "h"), datasets: [{ data: res.data.averageArray, borderColor: polColor(res.data.averageArray.slice(-1)[0], pol), fill: false, tension: 0.4, pointRadius: 0 }] },
            options: { plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { display: false } } }
        });
    } catch (e) { console.error("Chart load error:", e); }
}

// ====================== INIT ======================
async function main() {
    await loadBoundary();
    await loadStations();
    updateAt(10.7769, 106.7009);
    map.on("click", e => updateAt(e.latlng.lat, e.latlng.lng));
    let _heatTimer = null;
    map.on("moveend", () => { clearTimeout(_heatTimer); _heatTimer = setTimeout(drawHeatmap, 300); });

    // Enter key handler for chat input
    document.getElementById("chatInput").addEventListener("keydown", e => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
    });
    document.addEventListener("click", e => {
        if (!e.target.closest("#searchInp") && !e.target.closest("#searchBox")) document.getElementById("searchBox").style.display = "none";
    });
}
main();
