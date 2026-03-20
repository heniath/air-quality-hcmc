# -*- coding: utf-8 -*-
"""
streamlit_app.py — Entry point 3 tab
  🗺️  Live Map   — iframe nhúng Flask/Leaflet
  📊  Dashboard  — KPI + station cards + trend (CSV historical)
  🔬  EDA        — Phân tích sâu (CSV historical)

Chạy:
  # Terminal 1 — Flask backend
  python server.py

  # Terminal 2 — Streamlit
  streamlit run streamlit_app.py

Tuỳ chọn môi trường:
  FLASK_URL=http://localhost:5501   (default)
"""

import os
import streamlit as st
import streamlit.components.v1 as components

# ── PHẢI là lệnh đầu tiên ──
st.set_page_config(
    page_title="Megacity AQI – HCMC",
    page_icon="🌫️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

FLASK_URL = os.environ.get("FLASK_URL", "http://localhost:5501")

# ══════════════════════════════════════════════════════════════════
#  GLOBAL CSS — light theme toàn app
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

/* ── Base ── */
html, body, [data-testid="stApp"] {
    background: #f0f4f8 !important;
    font-family: 'Inter', sans-serif !important;
    color: #1a202c !important;
}
#MainMenu, footer, header          { visibility: hidden; }
[data-testid="stToolbar"]          { display: none !important; }
[data-testid="stMainBlockContainer"]   { padding: 0 2rem !important; max-width: 100% !important; }
[data-testid="stAppViewContainer"]     { padding: 0 !important; }
[data-testid="stAppViewBlockContainer"]{ padding-bottom: 0 !important; }
[data-testid="stBottomBlockContainer"] { display: none !important; }
section[data-testid="stSidebar"]       { display: none !important; }
.block-container                       { padding: 0.5rem 0 2rem !important; }

/* ── Dashboard/EDA padding wrapper ── */
.dash-wrap { padding: 0 2rem 2rem; }

/* ── Section headers (Dashboard) ── */
.db-section-hdr {
    display: flex; align-items: center; gap: 10px;
    margin: 24px 0 14px;
}
.db-section-icon  { font-size: 20px; }
.db-section-title {
    font-size: 19px; font-weight: 800; color: #1a202c;
    letter-spacing: -0.3px;
}

/* ── Spacing ── */
[data-testid="stVerticalBlock"]  { gap: 0.2rem !important; }
[data-testid="stHorizontalBlock"]{ gap: 12px !important; padding: 0 !important; }
[data-testid="stVerticalBlock"] > div:empty { display: none !important; }

/* ── Tab switcher (radio) compact ── */
[data-testid="stRadio"]                          { margin: 0 !important; padding: 0 !important; }
[data-testid="stRadio"] > div                    { margin: 0 !important; padding: 0 !important; min-height: 0 !important; }
[data-testid="stRadio"] > div > div              { margin: 0 !important; padding: 0 !important; }
[data-testid="stRadio"] > label                  { display: none !important; }
div[role="radiogroup"]                           { gap: 0 !important; padding: 6px 0 4px !important; }
div[role="radiogroup"] label                     { padding: 2px 12px 2px 0 !important; margin: 0 !important; }

/* ── Divider compact ── */
[data-testid="stDivider"]                        { margin: 0 !important; }

/* ── Container borders ── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffffff !important;
    border-radius: 12px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
}
/* Top-level wrapper → transparent */
[data-testid="stAppViewBlockContainer"] > div > [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stMainBlockContainer"]    > div > [data-testid="stVerticalBlockBorderWrapper"] {
    background: transparent !important; border: none !important; box-shadow: none !important;
}
/* Column layout wrappers → transparent */
[data-testid="stHorizontalBlock"] > div > [data-testid="stVerticalBlockBorderWrapper"] {
    background: transparent !important; border: none !important;
    box-shadow: none !important; border-radius: 0 !important; padding: 0 !important;
}

/* ── Widgets ── */
div[data-baseweb="select"], div[data-baseweb="select"] > div,
div[data-baseweb="input"],  div[data-baseweb="base-input"],
[data-testid="stDateInput"] div, input, textarea {
    background: #ffffff !important; background-color: #ffffff !important;
    border-color: #e2e8f0 !important; color: #1a202c !important;
}
ul[data-baseweb="menu"], li[data-baseweb="menu-item"],
div[role="listbox"], div[role="option"] {
    background: #ffffff !important; color: #1a202c !important;
}
li[data-baseweb="menu-item"]:hover       { background: #eff6ff !important; }
div[data-baseweb="select"] span,
div[data-baseweb="select"] p             { color: #1a202c !important; }
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
.stSelectbox label, .stDateInput label,
.stRadio label, div[role="radiogroup"] label,
div[role="radiogroup"] span,
div[role="radiogroup"] p                 { color: #1a202c !important; font-weight: 600 !important; }
div[role="radiogroup"] label:has(input:checked) span { color: #2563eb !important; }
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"]      { color: #1a202c !important; }

/* ══ NAVBAR ══ */
.app-navbar {
    position: sticky; top: 0; z-index: 9999;
    background: #ffffff; border-bottom: 1px solid #e2e8f0;
    padding: 0 28px; height: 56px;
    display: flex; align-items: center; gap: 14px;
    box-shadow: 0 1px 8px rgba(0,0,0,0.06);
}
.nb-logo {
    font-size: 17px; font-weight: 800; letter-spacing: -0.5px;
    color: #1a202c !important; white-space: nowrap;
}
.nb-logo span { color: #f97316; }
.nb-sep  { width: 1px; height: 22px; background: #e2e8f0; flex-shrink: 0; }
.nb-title{ font-size: 13px; font-weight: 600; color: #64748b !important; white-space: nowrap; }
.nb-live {
    display: flex; align-items: center; gap: 5px;
    background: #f0fdf4; border: 1px solid #bbf7d0;
    padding: 3px 10px; border-radius: 20px;
}
.nb-dot {
    width: 6px; height: 6px; border-radius: 50%; background: #16a34a;
    animation: nbpulse 1.8s ease-in-out infinite;
}
.nb-live-txt { font-size: 9px; font-weight: 700; color: #16a34a !important;
               text-transform: uppercase; letter-spacing: 0.8px; }
@keyframes nbpulse { 0%,100%{opacity:.35} 50%{opacity:1} }

/* ══ MAP TAB ══ */
.map-banner {
    background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 10px;
    padding: 10px 16px; margin-bottom: 10px;
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.map-banner-txt  { font-size: 12px; font-weight: 600; color: #1d4ed8 !important; }
.map-badge  {
    background: #dbeafe; color: #1d4ed8; border: 1px solid #93c5fd;
    font-size: 10px; font-weight: 700; padding: 2px 9px; border-radius: 20px;
}
.map-hint { font-size: 11px; color: #64748b !important; margin-left: auto; }
.map-wrap {
    border-radius: 16px; overflow: hidden;
    border: 1px solid #e2e8f0; box-shadow: 0 2px 12px rgba(0,0,0,0.07);
}
.map-legend {
    display: flex; gap: 18px; flex-wrap: wrap;
    padding: 8px 2px 2px; font-size: 11px; color: #64748b !important;
}
iframe { border: none !important; }

/* ══ SHARED Dashboard/EDA ══ */
.hero   { padding: 2px 0 8px; }
.hero h1{ font-size: 26px; font-weight: 800; color: #1a202c !important; margin: 0 0 4px; }
.hero p { font-size: 13px; color: #718096 !important; margin: 0; }

.sec-head { font-size: 17px; font-weight: 700; color: #1a202c !important; margin: 16px 0 10px; }
.cp-title { font-size: 14px; font-weight: 700; color: #1a202c !important; margin: 4px 0 4px; }
.cp-sub   { font-size: 11px; color: #718096 !important; margin: 0 0 10px; }

/* ── Container inner padding ── */
[data-testid="stVerticalBlockBorderWrapper"] > div > div {
    padding: 4px 2px !important;
}

.kpi-row  { display: grid; grid-template-columns: repeat(3,1fr); gap: 12px; margin-bottom: 16px; }
.kpi-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
            padding: 16px 20px; display: flex; justify-content: space-between;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
.kpi-lbl  { font-size: 10px; font-weight: 700; letter-spacing: 1px;
            color: #718096 !important; text-transform: uppercase; margin-bottom: 8px; }
.kpi-val  { font-size: 36px; font-weight: 800; font-family: 'JetBrains Mono', monospace;
            color: #1a202c !important; line-height: 1; }
.kpi-bdg  { display: inline-block; font-size: 11px; font-weight: 600;
            padding: 2px 9px; border-radius: 20px; margin-top: 6px; border: 1px solid; }
.kpi-ico  { font-size: 20px; opacity: 0.4; }

.stn-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
            padding: 16px 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            transition: box-shadow .2s, border-color .2s; }
.stn-card:hover { box-shadow: 0 4px 14px rgba(37,99,235,0.1); border-color: #bfdbfe; }
.stn-hdr  { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2px; }
.stn-name { font-size: 13px; font-weight: 700; color: #1a202c !important; }
.stn-addr { font-size: 11px; color: #a0aec0 !important; margin-bottom: 10px; }
.stn-aqi  { font-size: 40px; font-weight: 800; font-family: 'JetBrains Mono', monospace;
            color: #1a202c !important; line-height: 1; margin-bottom: 4px; }
.stn-bdg  { display: inline-block; font-size: 10px; font-weight: 700;
            padding: 2px 9px; border-radius: 20px; margin-bottom: 10px; border: 1px solid; }
.stn-div  { height: 1px; background: #e2e8f0; margin-bottom: 10px; }
.stn-row  { display: flex; gap: 18px; }
.stn-plbl { font-size: 10px; color: #a0aec0 !important; text-transform: uppercase; margin-bottom: 2px; }
.stn-pval { font-size: 14px; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: #2d3748 !important; }
.live-bdg { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0;
            font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 4px; }
.nd-bdg   { background: #f7fafc; color: #a0aec0; border: 1px solid #e2e8f0;
            font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 4px; }

.ref-bar  { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
.ref-ttl  { font-size: 10px; font-weight: 700; color: #718096 !important;
            text-transform: uppercase; letter-spacing: 0.8px; }
.ref-chip { display: inline-flex; align-items: center; gap: 5px; font-size: 11px;
            font-weight: 600; padding: 3px 10px; border-radius: 20px; border: 1px solid; }
.ref-dot  { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }

.stn-sel-bar   { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 10px;
                 padding: 10px 16px; margin-bottom: 14px;
                 display: flex; align-items: center; gap: 10px; }
.stn-sel-label { font-size: 12px; font-weight: 600; color: #1d4ed8 !important; }
.stn-sel-name  { font-size: 13px; font-weight: 700; color: #1a202c !important; }

/* ── Footer ── */
.app-footer { text-align: center; padding: 6px 0 4px;
              font-family: 'JetBrains Mono', monospace; font-size: 10px;
              color: #cbd5e0; letter-spacing: 2px; border-top: 1px solid #e2e8f0; }

::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #f0f4f8; }
::-webkit-scrollbar-thumb { background: #cbd5e0; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  NAVBAR
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-navbar">
  <div class="nb-logo">MEGA<span>AQI</span></div>
  <div class="nb-sep"></div>
  <div class="nb-title">Air Quality Monitoring – HCMC</div>
  <div class="nb-live">
    <span class="nb-dot"></span>
    <span class="nb-live-txt">Live</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  TAB SWITCHER
# ══════════════════════════════════════════════════════════════════
# Neu co flag chuyen tab tu ben trong (vi du: nut map o Dashboard)
# phai set truoc khi render radio
TAB_OPTIONS = ["🗺️ Live Map", "📊 Dashboard", "🔬 EDA", "🔮 Forecast"]
if st.session_state.get("_switch_tab"):
    st.session_state["main_tab"] = st.session_state.pop("_switch_tab")

tab = st.radio(
    "",
    TAB_OPTIONS,
    horizontal=True,
    label_visibility="collapsed",
    key="main_tab",
)
st.markdown('<hr style="margin:2px 0 0;border:none;border-top:1px solid #e2e8f0">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  TAB 1 — LIVE MAP
# ══════════════════════════════════════════════════════════════════
if tab == "🗺️ Live Map":

    # Kiểm tra Flask có online không
    import requests as _req
    _ok = False
    try:
        _ok = _req.get(f"{FLASK_URL}/api/health", timeout=3).status_code == 200
    except Exception:
        pass

    if not _ok:
        st.error(
            f"⚠️ **Flask backend chưa chạy!**\n\n"
            f"Vui lòng mở terminal và chạy:\n```\npython server.py\n```\n"
            f"Sau đó reload trang này. URL hiện tại: `{FLASK_URL}`\n\n"
            f"Để đổi URL: `export FLASK_URL=http://your-host:5501`"
        )
        st.stop()

    st.markdown('<div style="margin: -0.5rem -2rem 0">', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="map-banner">
      <span class="map-banner-txt">🌍 Bản đồ giám sát AQI thời gian thực</span>
      <span class="map-badge">⚡ Live · aqi.in</span>
      <span class="map-badge">📐 IDW Nội suy</span>
      <span class="map-badge">12 Trạm quan trắc</span>
      <span class="map-badge">3 Tỉnh Megacity</span>
      <span class="map-hint">💡 Click bất kỳ điểm nào trên bản đồ để xem AQI nội suy</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="map-wrap">', unsafe_allow_html=True)
    components.iframe(src=FLASK_URL, height=1650, scrolling=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="map-legend">
      <span>🗺️ <b>Nền bản đồ:</b> CartoDB Dark Matter</span>
      <span>📐 <b>Nội suy:</b> IDW power=1.8, ε=0.08</span>
      <span>🔥 <b>Heatmap:</b> Grid AQI overlay</span>
      <span>💨 <b>Gió:</b> Arrow + Particle Flow canvas</span>
      <span>⏱️ <b>Timeline:</b> Playback 24h lịch sử</span>
      <span>🤖 <b>AI Chat:</b> Groq / Llama 3.1 8B</span>
      <span>🔄 <b>Cache:</b> 15 phút / TTL 60s cooldown</span>
    </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  TAB 2 — DASHBOARD
# ══════════════════════════════════════════════════════════════════
elif tab == "📊 Dashboard":
    from app_logic import render_dashboard
    render_dashboard()


# ══════════════════════════════════════════════════════════════════
#  TAB 3 — EDA
# ══════════════════════════════════════════════════════════════════
elif tab == "🔬 EDA":
    from app_logic import render_eda
    render_eda()


# ══════════════════════════════════════════════════════════════════
#  TAB 4 — FORECAST
# ══════════════════════════════════════════════════════════════════
elif tab == "🔮 Forecast":
    from app_logic import render_forecast
    render_forecast()


# ══════════════════════════════════════════════════════════════
#  FOOTER
# ══════════════════════════════════════════════════════════════════
# st.markdown("""
# <div class="app-footer">
#   MEGACITY AQI · HCMC · 2022–2026 · AQICN DATA + CSV HISTORICAL
# </div>
# """, unsafe_allow_html=True)