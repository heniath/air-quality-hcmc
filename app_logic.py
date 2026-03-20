# -*- coding: utf-8 -*-
"""
app_logic.py — Pure logic module (data, charts, render functions)
Duoc import boi streamlit_app.py — KHONG chay truc tiep.
"""
from datetime import date
import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

CITY_CSV     = "output_city_hcmc/hcmc_city_2022_2026_comma.csv"
STATIONS_CSV = "output_all_stations_2022_2026/aqi_daily_allstations_2022_2026.csv"

NON_AQI = ["PM2,5", "PM10", "CO", "SO2", "O3", "NO2"]
ALL_COL = ["AQI"] + NON_AQI
_DISP   = {"PM2,5":"PM2.5","PM10":"PM10","CO":"CO","SO2":"SO2","O3":"O3","NO2":"NO2","AQI":"AQI"}

AQI_BANDS = [
    (0,   50,  "#16a34a", "Good"),
    (51,  100, "#ca8a04", "Moderate"),
    (101, 150, "#ea580c", "USG"),
    (151, 200, "#dc2626", "Unhealthy"),
    (201, 300, "#7e22ce", "Very Unhealthy"),
    (301, 999, "#7f1d1d", "Hazardous"),
]

_CFG = dict(displayModeBar=False)
_PL  = dict(
    paper_bgcolor="#ffffff", plot_bgcolor="#f8fafc",
    font=dict(family="Inter, sans-serif", color="#4a5568", size=11),
    margin=dict(l=8, r=8, t=8, b=8),
    legend=dict(bgcolor="rgba(255,255,255,0.95)", bordercolor="#e2e8f0",
                borderwidth=1, font=dict(size=10, color="#1a202c")),
)
_AX = dict(gridcolor="#e2e8f0", zeroline=False, linecolor="#cbd5e0",
           tickfont=dict(size=9, color="#718096"))

def _theme(fig):
    fig.update_layout(**_PL); fig.update_xaxes(**_AX); fig.update_yaxes(**_AX)
    return fig

def _num(df, cols):
    for c in cols:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def _normalize_pm(df):
    """CSV co the dung PM2.5 (cham) thay vi PM2,5 (phay) — chuan hoa ve dau phay."""
    if "PM2.5" in df.columns and "PM2,5" not in df.columns:
        df = df.rename(columns={"PM2.5": "PM2,5"})
    return df

def aqi_info(v):
    try:
        val = float(v)
        if np.isnan(val): return "N/A", "#a0aec0"
    except: return "N/A", "#a0aec0"
    for lo, hi, color, label in AQI_BANDS:
        if lo <= val <= hi: return label, color
    return "N/A", "#a0aec0"

def _fmt(v, dec=1):
    try:
        f = float(v); return f"{f:.{dec}f}" if not np.isnan(f) else "—"
    except: return "—"

def _rgba(h, a=0.15):
    hx = h.lstrip("#")
    r, g, b = int(hx[0:2],16), int(hx[2:4],16), int(hx[4:6],16)
    return f"rgba({r},{g},{b},{a})"

def _corr(df, x, y):
    t = df[[x,y]].dropna()
    return float(t[x].corr(t[y])) if len(t) >= 3 else float("nan")

@st.cache_data(ttl=600)
def get_city():
    df = pd.read_csv(CITY_CSV)
    df = _normalize_pm(df)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return _num(df.dropna(subset=["date"]), ALL_COL).sort_values("date").reset_index(drop=True)

@st.cache_data(ttl=600)
def get_stations():
    df = pd.read_csv(STATIONS_CSV)
    df = _normalize_pm(df)
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    if "station_name" not in df.columns: df["station_name"] = df["station_slug"]
    return _num(df.dropna(subset=["date"]), ALL_COL).sort_values(["station_name","date"]).reset_index(drop=True)

def _aqi_bands(fig):
    for lo, hi, c, _ in AQI_BANDS:
        fig.add_hrect(y0=lo, y1=hi, fillcolor=c, opacity=0.06, layer="below", line_width=0)

def chart_trend(df, col="AQI", ylab="AQI"):
    v = df[["date", col]].dropna().sort_values("date")
    r = v.set_index("date")[col].rolling(7, min_periods=1).mean().reset_index()
    fig = go.Figure()
    if col == "AQI": _aqi_bands(fig)
    fig.add_trace(go.Scatter(x=v["date"], y=v[col], name=_DISP.get(col,col),
        mode="lines", line=dict(color="#ef4444", width=1.2), opacity=0.6))
    fig.add_trace(go.Scatter(x=r["date"], y=r[col], name="7-day MA",
        mode="lines", line=dict(color="#2563eb", width=2.5)))
    _theme(fig)
    fig.update_layout(hovermode="x unified", yaxis_title=ylab,
        legend=dict(orientation="h", y=1.12, x=1, xanchor="right"))
    return fig

def chart_radar(df, station):
    avail = [c for c in NON_AQI if c in df.columns and df[c].notna().sum() > 5]
    if len(avail) < 3: return go.Figure()
    sub   = df[df["station_name"]==station][avail].mean()
    all_m = df[avail].mean()
    scale = all_m.replace(0, np.nan)
    ns = (sub/scale).fillna(0).clip(0,2)
    nc = (all_m/scale).fillna(0).clip(0,2)
    lbl  = [_DISP.get(c,c) for c in avail]
    cats = lbl + [lbl[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=nc.tolist()+[nc.iloc[0]], theta=cats,
        name="City Avg", fill="toself", opacity=0.4,
        line=dict(color="#94a3b8", width=1.5), fillcolor="rgba(148,163,184,0.15)"))
    fig.add_trace(go.Scatterpolar(r=ns.tolist()+[ns.iloc[0]], theta=cats,
        name=station[:22], fill="toself", opacity=0.7,
        line=dict(color="#2563eb", width=2), fillcolor="rgba(37,99,235,0.18)"))
    _theme(fig)
    fig.update_layout(
        polar=dict(bgcolor="#f8fafc",
            radialaxis=dict(visible=True, range=[0,2],
                tickfont=dict(size=8, color="#94a3b8"), gridcolor="#e2e8f0", linecolor="#e2e8f0"),
            angularaxis=dict(tickfont=dict(size=9, color="#4a5568"), gridcolor="#e2e8f0")),
        legend=dict(font=dict(size=10, color="#1a202c")))
    return fig

def chart_aqi_freq(df):
    order = [l for _,_,_,l in AQI_BANDS]
    cats  = df["AQI"].dropna().apply(lambda x: aqi_info(x)[0]).value_counts()
    cats  = cats.reindex([c for c in order if c in cats.index])
    cols  = [next((c for _,_,c,l in AQI_BANDS if l==k), "#94a3b8") for k in cats.index]
    fig   = go.Figure(go.Bar(
        x=cats.values, y=cats.index, orientation="h",
        marker=dict(color=cols, line=dict(width=0)),
        text=cats.values, textposition="outside",
        textfont=dict(color="#1a202c", size=10),
        hovertemplate="%{y}: %{x} ngay<extra></extra>"))
    _theme(fig)
    fig.update_layout(showlegend=False, yaxis=dict(autorange="reversed"))
    return fig

# ════════════════════════════════════════
# FIX 1: Correlation Matrix (thay the scatter don le)
# ════════════════════════════════════════
def chart_corr_matrix(df):
    cols = ["AQI"] + [c for c in NON_AQI if c in df.columns and df[c].notna().sum() > 10]
    if len(cols) < 3: return go.Figure()
    corr = df[cols].corr(method="pearson", numeric_only=True)
    cols = [c for c in cols if c in corr.columns]
    corr = corr.loc[cols, cols]
    z    = corr.values
    lbl  = [_DISP.get(c,c) for c in cols]
    txt  = [[f"{v:.2f}" for v in row] for row in z]
    colorscale = [[0.0,"#dc2626"],[0.25,"#fca5a5"],[0.5,"#f8fafc"],[0.75,"#93c5fd"],[1.0,"#1d4ed8"]]
    fig = go.Figure(go.Heatmap(
        z=z, x=lbl, y=lbl, text=txt, texttemplate="%{text}",
        textfont=dict(size=11, color="#1a202c"),
        colorscale=colorscale, zmin=-1, zmax=1,
        hovertemplate="%{y} x %{x}: r = %{z:.3f}<extra></extra>",
        showscale=True,
        colorbar=dict(thickness=12, len=0.9,
            tickvals=[-1,-0.5,0,0.5,1], ticktext=["-1","-0.5","0","0.5","1"],
            tickfont=dict(size=9, color="#4a5568"),
            title=dict(text="r", font=dict(color="#4a5568", size=10)))))
    _theme(fig)
    fig.update_layout(
        xaxis=dict(tickfont=dict(size=10, color="#1a202c"), side="bottom"),
        yaxis=dict(tickfont=dict(size=10, color="#1a202c"), autorange="reversed"),
        margin=dict(l=60, r=20, t=10, b=60))
    return fig

# ════════════════════════════════════════
# FIX 2: Normalized overlay (tong hop)
# ════════════════════════════════════════
def chart_all_pollutants(df):
    colors = {"PM2,5":"#ef4444","PM10":"#f97316","CO":"#eab308",
              "SO2":"#22c55e","O3":"#3b82f6","NO2":"#8b5cf6"}
    avail  = [c for c in NON_AQI if c in df.columns and df[c].notna().sum() > 5]
    if not avail: return go.Figure()
    fig = go.Figure()
    for col in avail:
        tmp = df[["date",col]].dropna().sort_values("date")
        if tmp.empty: continue
        s = tmp[col]; mn, mx = s.min(), s.max()
        norm = (s-mn)/(mx-mn) if mx>mn else s*0
        fig.add_trace(go.Scatter(
            x=tmp["date"], y=norm, name=_DISP.get(col,col), mode="lines",
            line=dict(color=colors.get(col,"#94a3b8"), width=1.6), opacity=0.85,
            hovertemplate=f"<b>{_DISP.get(col,col)}</b>: %{{customdata:.1f}}<extra></extra>",
            customdata=s.values))
    _theme(fig)
    fig.update_layout(hovermode="x unified", yaxis_title="Normalized (0-1)",
        legend=dict(orientation="h", y=1.14, x=1, xanchor="right", font=dict(size=10)))
    return fig

def chart_scatter(df, x_col, y_col, tl=True):
    if x_col not in df.columns or y_col not in df.columns: return go.Figure()
    tmp = df[[x_col, y_col, "AQI"]].dropna().copy()
    if tmp.empty: return go.Figure()
    tmp["cat"] = tmp["AQI"].apply(lambda v: aqi_info(v)[0])
    clr = {l: c for _,_,c,l in AQI_BANDS}
    r   = _corr(tmp, x_col, y_col)
    fig = px.scatter(tmp, x=x_col, y=y_col, color="cat",
        category_orders={"cat": [l for _,_,_,l in AQI_BANDS]},
        color_discrete_map=clr, opacity=0.7,
        trendline="ols" if tl else None,
        labels={x_col: _DISP.get(x_col,x_col), y_col: _DISP.get(y_col,y_col)})
    fig.update_traces(marker=dict(size=5, line=dict(width=0)))
    _theme(fig)
    fig.update_layout(legend=dict(title=None, font=dict(size=10)),
        annotations=[dict(x=0.02, y=0.97, xref="paper", yref="paper",
            text=f"r = {r:.3f}" if not np.isnan(r) else "r = N/A",
            showarrow=False, font=dict(size=12, color="#1d4ed8", family="JetBrains Mono"),
            bgcolor="rgba(219,234,254,0.95)", bordercolor="#3b82f6", borderwidth=1, borderpad=6)])
    return fig

def chart_pollutant_ts(df, col):
    if col not in df.columns: return go.Figure()
    tmp = df[["date", col]].dropna().sort_values("date")
    if tmp.empty: return go.Figure()
    r = tmp.set_index("date")[col].rolling(7, min_periods=1).mean().reset_index()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tmp["date"], y=tmp[col], name=_DISP.get(col,col),
        mode="lines", line=dict(color="#ef4444", width=1), opacity=0.6))
    fig.add_trace(go.Scatter(x=r["date"], y=r[col], name="7-day MA",
        mode="lines", line=dict(color="#2563eb", width=2.2)))
    _theme(fig)
    fig.update_layout(hovermode="x unified", yaxis_title=_DISP.get(col,col),
        legend=dict(orientation="h", y=1.12, x=1, xanchor="right"))
    return fig

def chart_heatmap(df):
    tmp = df.copy()
    tmp["month"] = tmp["date"].dt.month
    tmp["year"]  = tmp["date"].dt.year
    pivot = tmp.pivot_table(index="year", columns="month", values="AQI", aggfunc="mean")
    ml  = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    xl  = [ml[m-1] for m in pivot.columns]
    zv  = pivot.values.astype(float)
    txt = np.where(np.isnan(zv), "", np.round(zv,0).astype("int").astype("str"))
    fig = go.Figure(go.Heatmap(z=zv, x=xl, y=[str(y) for y in pivot.index],
        colorscale=[[0,"#22c55e"],[.25,"#eab308"],[.5,"#f97316"],[.75,"#ef4444"],[1,"#7f1d1d"]],
        zmin=0, zmax=150, text=txt, texttemplate="%{text}",
        textfont=dict(size=10, color="#1a202c"),
        hovertemplate="Nam %{y} - %{x}: AQI %{z:.1f}<extra></extra>",
        showscale=True,
        colorbar=dict(thickness=10, len=.85, tickfont=dict(size=9, color="#4a5568"),
            title=dict(text="AQI", font=dict(color="#4a5568", size=10)))))
    _theme(fig)
    return fig

# ════════════════════════════════════════
# FIX 3: Boxplot height scale theo so tram
# ════════════════════════════════════════
def chart_boxplot(df):
    order = df.groupby("station_name")["AQI"].median().dropna().sort_values(ascending=False).index.tolist()
    n     = len(order)
    pal   = ["#2563eb","#16a34a","#ca8a04","#dc2626","#7e22ce",
             "#0891b2","#059669","#ea580c","#c026d3","#d97706"]
    fig   = go.Figure()
    for i, stn in enumerate(order):
        vals  = df[df["station_name"]==stn]["AQI"].dropna()
        if len(vals) < 2: continue
        c     = pal[i % len(pal)]
        short = stn[:26]+"…" if len(stn)>26 else stn
        fig.add_trace(go.Box(x=vals, y=[short]*len(vals), name=short,
            orientation="h", boxmean=True,
            marker=dict(size=3, opacity=0.4, color=c),
            line=dict(color=c, width=1.5), showlegend=False,
            hovertemplate=f"<b>{stn}</b><br>AQI: %{{x:.0f}}<extra></extra>"))
    _theme(fig)
    fig.update_layout(
        showlegend=False, hovermode="closest",
        xaxis_title="AQI",
        yaxis=dict(autorange="reversed", tickfont=dict(size=9, color="#1a202c")),
        height=max(320, n * 46),          # 46px moi tram, toi thieu 320px
        margin=dict(l=180, r=20, t=10, b=40))
    return fig

def chart_yearly(df_city, df_st):
    pal = ["#2563eb","#16a34a","#ca8a04","#dc2626","#7e22ce",
           "#0891b2","#059669","#ea580c","#c026d3"]
    fig = go.Figure()
    cg  = df_city.copy(); cg["year"] = cg["date"].dt.year
    cy  = cg.groupby("year")["AQI"].mean().reset_index()
    fig.add_trace(go.Scatter(x=cy["year"], y=cy["AQI"], name="City (AQICN)",
        mode="lines+markers", line=dict(color="#1a202c", width=3),
        marker=dict(size=7, color="#1a202c")))
    sg = df_st.copy(); sg["year"] = sg["date"].dt.year
    for i, stn in enumerate(sg["station_name"].unique()):
        sub = sg[sg["station_name"]==stn].groupby("year")["AQI"].mean().reset_index()
        if sub["AQI"].notna().sum() < 2: continue
        short = stn[:20]+"…" if len(stn)>20 else stn
        fig.add_trace(go.Scatter(x=sub["year"], y=sub["AQI"], name=short,
            mode="lines+markers",
            line=dict(color=pal[i%len(pal)], width=1.5, dash="dot"),
            marker=dict(size=5)))
    _theme(fig)
    fig.update_layout(hovermode="x unified", xaxis=dict(dtick=1),
        yaxis_title="AQI TB theo nam", legend=dict(font=dict(size=10)))
    return fig

def chart_missing(df):
    poll = [c for c in ALL_COL if c in df.columns]
    miss = df.groupby("station_name")[poll].apply(lambda g: g.isna().mean()*100)
    col_lbl = [_DISP.get(c,c) for c in miss.columns.tolist()]
    fig  = go.Figure(go.Heatmap(z=miss.values, x=col_lbl,
        y=[s[:22]+"…" if len(s)>22 else s for s in miss.index],
        colorscale=[[0,"#22c55e"],[.5,"#eab308"],[1,"#dc2626"]],
        zmin=0, zmax=100,
        text=np.round(miss.values,0).astype("int").astype("str"),
        texttemplate="%{text}%", textfont=dict(size=9, color="#1a202c"),
        hovertemplate="%{y} - %{x}: %{z:.1f}% missing<extra></extra>",
        showscale=True, colorbar=dict(thickness=10, ticksuffix="%",
            tickfont=dict(size=9, color="#4a5568"))))
    _theme(fig)
    fig.update_layout(margin=dict(l=160, r=20, t=10, b=40))
    return fig

# ══════════════════════════════════════════════
# STATION EDA — da sua 3 loi
# ══════════════════════════════════════════════
def render_station_eda(df_st_full, station_name, df_city_full):
    df_s = df_st_full[df_st_full["station_name"] == station_name].copy()
    # Dam bao PM2,5 duoc normalize ngay ca sau khi slice
    df_s = _normalize_pm(df_s)

    ref_chips = "".join([
        f'<span class="ref-chip" style="color:{c};border-color:{c};background:{_rgba(c,.12)}">'
        f'<span class="ref-dot" style="background:{c}"></span>{l}</span>'
        for _,_,c,l in AQI_BANDS])
    st.markdown(f'<div class="ref-bar"><span class="ref-ttl">AQI Reference:</span>{ref_chips}</div>',
                unsafe_allow_html=True)

    # ROW 1: AQI trend + Radar
    c1, c2 = st.columns([2, 1])
    with c1:
        with st.container(border=True):
            st.markdown(f'<p class="cp-title">📈 AQI Trend – {station_name}</p>', unsafe_allow_html=True)
            st.markdown('<p class="cp-sub">Daily AQI + 7-day rolling average</p>', unsafe_allow_html=True)
            fig_t = chart_trend(df_s)
            if fig_t.data: st.plotly_chart(fig_t, use_container_width=True, config=_CFG,
                                            key=f"trend_{station_name}")
            else: st.info("Khong co du lieu AQI.")
    with c2:
        with st.container(border=True):
            st.markdown('<p class="cp-title">🕸️ Pollutant Profile vs City Avg</p>', unsafe_allow_html=True)
            st.markdown('<p class="cp-sub">Chuan hoa theo trung binh toan mang luoi</p>', unsafe_allow_html=True)
            fig_r = chart_radar(df_st_full, station_name)
            if fig_r.data: st.plotly_chart(fig_r, use_container_width=True, config=_CFG,
                                            key=f"radar_{station_name}")
            else: st.info("Khong du du lieu.")

    # ROW 2: AQI Freq + Correlation Matrix (FIX 1)
    c3, c4 = st.columns([1, 1.6])
    with c3:
        with st.container(border=True):
            st.markdown('<p class="cp-title">🎯 AQI Frequency</p>', unsafe_allow_html=True)
            st.markdown('<p class="cp-sub">Phan bo so ngay theo muc AQI</p>', unsafe_allow_html=True)
            fig_fr = chart_aqi_freq(df_s)
            if fig_fr.data: st.plotly_chart(fig_fr, use_container_width=True, config=_CFG,
                                             key=f"freq_{station_name}")
            else: st.info("Khong co du lieu.")
    with c4:
        with st.container(border=True):
            st.markdown('<p class="cp-title">🔗 Correlation Matrix</p>', unsafe_allow_html=True)
            st.markdown('<p class="cp-sub">Pearson r — xanh = tuong quan thuan · do = nghich chieu</p>',
                        unsafe_allow_html=True)
            fig_cm = chart_corr_matrix(df_s)
            if fig_cm.data: st.plotly_chart(fig_cm, use_container_width=True, config=_CFG,
                                             key=f"corr_{station_name}")
            else: st.info("Can >= 3 chi so co >= 10 ngay du lieu.")

    # ROW 3: Tabs tung chi so
    # Lay tat ca cot co du lieu — check ca 2 dang ten PM2,5 va PM2.5
    def _avail_cols(df):
        result = []
        for c in ["AQI"] + NON_AQI:
            if c in df.columns and df[c].notna().sum() > 3:
                result.append(c)
        return result

    all_avail = _avail_cols(df_s)
    st.markdown('<p class="sec-head">📊 Dien bien tung chi so theo thoi gian</p>', unsafe_allow_html=True)
    if len(all_avail) > 0:
        tabs = st.tabs([_DISP.get(c, c) for c in all_avail])
        for tab_obj, col_name in zip(tabs, all_avail):
            with tab_obj:
                with st.container(border=True):
                    st.markdown(
                        f'<p class="cp-sub">{_DISP.get(col_name, col_name)} daily + 7-day MA</p>',
                        unsafe_allow_html=True)
                    if col_name == "AQI":
                        fig_p = chart_trend(df_s, col="AQI", ylab="AQI")
                    else:
                        fig_p = chart_pollutant_ts(df_s, col_name)
                    if fig_p.data:
                        st.plotly_chart(fig_p, use_container_width=True, config=_CFG,
                                        key=f"ts_{station_name}_{col_name}")
                    else:
                        actual_cols = [c for c in df_s.columns if df_s[c].notna().sum() > 3]
                        st.info(f"Khong co du lieu cho {_DISP.get(col_name, col_name)}. "
                                f"Cac cot co du lieu: {actual_cols}")
    else:
        st.info("Khong du du lieu chi so.")

    # ROW 5: Normalized overlay
    with st.container(border=True):
        st.markdown('<p class="cp-title">📉 Tong hop tat ca chi so (normalized 0–1)</p>', unsafe_allow_html=True)
        st.markdown('<p class="cp-sub">Chuan hoa de so sanh bien thien tuong doi — hover de xem gia tri goc</p>',
                    unsafe_allow_html=True)
        fig_all = chart_all_pollutants(df_s)
        if fig_all.data: st.plotly_chart(fig_all, use_container_width=True, config=_CFG,
                                          key=f"overlay_{station_name}")
        else: st.info("Khong du du lieu.")


# ══════════════════════════════════════════════
# CITY EDA
# ══════════════════════════════════════════════
def render_city_eda(df_city, df_st):
    ref_chips = "".join([
        f'<span class="ref-chip" style="color:{c};border-color:{c};background:{_rgba(c,.12)}">'
        f'<span class="ref-dot" style="background:{c}"></span>{l}</span>'
        for _,_,c,l in AQI_BANDS])
    st.markdown(f'<div class="ref-bar"><span class="ref-ttl">AQI Reference:</span>{ref_chips}</div>',
                unsafe_allow_html=True)

    c1, c2 = st.columns([1.6, 1])
    with c1:
        with st.container(border=True):
            st.markdown('<p class="cp-title">📈 City AQI Trend</p>', unsafe_allow_html=True)
            st.markdown('<p class="cp-sub">Daily AQI + 7-day rolling average · Nguon: AQICN</p>', unsafe_allow_html=True)
            fig_t = chart_trend(df_city)
            if fig_t.data: st.plotly_chart(fig_t, use_container_width=True, config=_CFG, key="eda_city_trend")
            else: st.info("Khong co du lieu.")
    with c2:
        with st.container(border=True):
            st.markdown('<p class="cp-title">🎯 AQI Frequency</p>', unsafe_allow_html=True)
            st.markdown('<p class="cp-sub">Phan bo so ngay theo muc AQI</p>', unsafe_allow_html=True)
            fig_fr = chart_aqi_freq(df_city)
            if fig_fr.data: st.plotly_chart(fig_fr, use_container_width=True, config=_CFG, key="eda_city_freq")
            else: st.info("Khong co du lieu.")

    c3, c4 = st.columns([1, 1])
    with c3:
        with st.container(border=True):
            st.markdown('<p class="cp-title">🗓️ AQI Heatmap – Month x Year</p>', unsafe_allow_html=True)
            st.markdown('<p class="cp-sub">City-level monthly average AQI</p>', unsafe_allow_html=True)
            if not df_city.empty and df_city["AQI"].notna().sum() > 0:
                st.plotly_chart(chart_heatmap(df_city), use_container_width=True, config=_CFG, key="eda_city_heatmap")
            else: st.info("Khong co du lieu.")
    with c4:
        with st.container(border=True):
            st.markdown('<p class="cp-title">📅 Yearly Mean AQI Trend</p>', unsafe_allow_html=True)
            st.markdown('<p class="cp-sub">City index vs individual stations year-over-year</p>', unsafe_allow_html=True)
            if not df_city.empty:
                st.plotly_chart(chart_yearly(df_city, df_st), use_container_width=True, config=_CFG, key="eda_city_yearly")
            else: st.info("Khong co du lieu.")

    # FIX 3: Boxplot full-width (khong nam trong column) de du chieu cao cho 12 tram
    with st.container(border=True):
        st.markdown('<p class="cp-title">📦 AQI Distribution by Station</p>', unsafe_allow_html=True)
        st.markdown('<p class="cp-sub">Median, IQR and outliers per station — sap xep theo median giam dan</p>',
                    unsafe_allow_html=True)
        if not df_st.empty and df_st["AQI"].notna().sum() > 0:
            st.plotly_chart(chart_boxplot(df_st), use_container_width=True, config=_CFG, key="eda_city_boxplot")
        else: st.info("Khong co du lieu.")

    with st.container(border=True):
        st.markdown('<p class="cp-title">🔍 Data Completeness (% Missing)</p>', unsafe_allow_html=True)
        st.markdown('<p class="cp-sub">Green = complete · Yellow = partial · Red = mostly missing</p>',
                    unsafe_allow_html=True)
        if not df_st.empty:
            st.plotly_chart(chart_missing(df_st), use_container_width=True, config=_CFG, key="eda_city_missing")
        else: st.info("Khong co du lieu.")

    poll_choice = st.selectbox("Chi so theo thoi gian", ["AQI"] + NON_AQI,
                               format_func=lambda c: _DISP.get(c,c), key="city_poll")
    with st.container(border=True):
        st.markdown(f'<p class="cp-title">{_DISP.get(poll_choice,poll_choice)} Time Series – City Level</p>',
                    unsafe_allow_html=True)
        fig_p = chart_trend(df_city, col=poll_choice, ylab=_DISP.get(poll_choice,poll_choice)) \
                if poll_choice == "AQI" else chart_pollutant_ts(df_city, poll_choice)
        if fig_p.data: st.plotly_chart(fig_p, use_container_width=True, config=_CFG, key=f"eda_city_ts_{poll_choice}")
        else: st.info(f"Khong co du lieu {_DISP.get(poll_choice,poll_choice)}.")


# ══════════════════════════════════════════════
# PUBLIC RENDER FUNCTIONS
# ══════════════════════════════════════════════
def render_dashboard():
    with st.spinner("Loading data..."):
        try:    df_city = get_city()
        except Exception as e: st.error(f"Cannot load City CSV: {e}"); st.stop()
        try:    df_st   = get_stations()
        except Exception as e: st.error(f"Cannot load Stations CSV: {e}"); st.stop()

    if "eda_station" not in st.session_state:
        st.session_state["eda_station"] = None

    st.markdown("""<div class="hero">
      <h1>Ho Chi Minh City — Dashboard</h1>
      <p>Dữ liệu AQI 2022–2026 · Nguồn: AQICN · CSV</p>
    </div>""", unsafe_allow_html=True)

    st.markdown('<p class="sec-head" style="margin-top:0">Bộ lọc thời gian</p>', unsafe_allow_html=True)
    fd1, fd2 = st.columns([1, 1])
    with fd1:
        ts0 = pd.Timestamp(st.date_input("Từ ngày", value=date(2024,1,1),
            min_value=df_city["date"].min().date(), max_value=df_city["date"].max().date(), key="dash_d0"))
    with fd2:
        ts1 = pd.Timestamp(st.date_input("Đến ngày", value=date.today(),
            min_value=df_city["date"].min().date(), max_value=df_city["date"].max().date(), key="dash_d1"))
    if ts0 > ts1: ts0, ts1 = ts1, ts0

    df_cf = df_city[(df_city["date"] >= ts0) & (df_city["date"] <= ts1)].copy()
    df_sf = df_st  [(df_st["date"]   >= ts0) & (df_st["date"]   <= ts1)].copy()

    cq   = df_cf["AQI"].dropna(); cavg = cq.mean() if len(cq) else None
    ccat, ccol = aqi_info(cavg)
    n_stn = df_sf["station_name"].nunique()
    n_bad = int((df_sf.groupby("station_name")["AQI"].mean().dropna() > 50).sum())

    st.markdown(f"""<div class="kpi-row">
      <div class="kpi-card"><div>
        <div class="kpi-lbl">City Average AQI</div>
        <div class="kpi-val">{_fmt(cavg,0)}</div>
        <span class="kpi-bdg" style="color:{ccol};border-color:{ccol};background:{_rgba(ccol,.1)}">{ccat}</span>
      </div><div class="kpi-ico">📈</div></div>
      <div class="kpi-card"><div>
        <div class="kpi-lbl">Active Stations</div>
        <div class="kpi-val">{n_stn}</div>
        <span class="kpi-bdg" style="color:#16a34a;border-color:#16a34a;background:rgba(22,163,74,.1)">Online</span>
      </div><div class="kpi-ico">📍</div></div>
      <div class="kpi-card"><div>
        <div class="kpi-lbl">Unhealthy Areas</div>
        <div class="kpi-val">{n_bad}</div>
        <span class="kpi-bdg" style="color:#dc2626;border-color:#dc2626;background:rgba(220,38,38,.1)">AQI &gt; 50</span>
      </div><div class="kpi-ico">⚠️</div></div>
    </div>""", unsafe_allow_html=True)

    col_trend, col_map = st.columns([1.6, 1])
    with col_trend:
        with st.container(border=True):
            st.markdown('<p class="cp-title">📈 City-level AQI Trend</p>', unsafe_allow_html=True)
            st.markdown('<p class="cp-sub">Daily AQI + 7-day rolling average · Nguồn: AQICN city index</p>', unsafe_allow_html=True)
            if not df_cf.empty and df_cf["AQI"].notna().sum() > 0:
                fig_trend = chart_trend(df_cf)
                fig_trend.update_layout(height=380)
                st.plotly_chart(fig_trend, use_container_width=True, config=_CFG, key="dash_city_trend")
            else:
                st.info("Khong co du lieu trong khoang thoi gian da chon.")
    with col_map:
        with st.container(border=True):
            st.markdown("""
            <p class="cp-title">🗺️ Live Map</p>
            <p class="cp-sub">Bản đồ AQI realtime · 12 trạm quan trắc</p>
            """, unsafe_allow_html=True)
            import base64 as _b64, os as _os
            map_preview_path = "map_preview.png"
            if _os.path.exists(map_preview_path):
                with open(map_preview_path, "rb") as f:
                    b64 = _b64.b64encode(f.read()).decode()
                bg_css = f"background:url('data:image/png;base64,{b64}') center/cover no-repeat"
            else:
                bg_css = "background:linear-gradient(160deg,#bfdbfe 0%,#dbeafe 40%,#e0f2fe 100%)"

            st.markdown(f"""
            <div style="width:100%;height:290px;border-radius:10px;overflow:hidden;
                 {bg_css};position:relative;border:1px solid #e2e8f0;margin-bottom:8px">
              <div style="position:absolute;inset:0;
                   background:linear-gradient(to top,rgba(0,0,0,0.35) 0%,transparent 55%)"></div>
              <div style="position:absolute;top:50%;left:50%;
                   transform:translate(-50%,-60%);
                   display:flex;flex-direction:column;align-items:center;gap:6px">
                <div style="font-size:48px;filter:drop-shadow(0 2px 6px rgba(0,0,0,0.2))">📍</div>
                <div style="font-size:15px;font-weight:700;color:#1e3a8a;
                     background:rgba(255,255,255,0.92);padding:4px 16px;border-radius:20px;
                     box-shadow:0 2px 8px rgba(0,0,0,0.12);
                     font-family:Georgia,serif;letter-spacing:0.5px;font-style:italic">
                  TP. Hồ Chí Minh
                </div>
                <div style="display:flex;gap:5px">
                  <span style="font-size:9px;font-weight:700;padding:2px 9px;border-radius:10px;color:#fff;background:#16a34a">● Good</span>
                  <span style="font-size:9px;font-weight:700;padding:2px 9px;border-radius:10px;color:#fff;background:#ca8a04">● Moderate</span>
                  <span style="font-size:9px;font-weight:700;padding:2px 9px;border-radius:10px;color:#fff;background:#ea580c">● USG</span>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <a href="/" target="_self" onclick="
              fetch('/_stcore/health').then(()=>{
                window.location.href='/?main_tab=live';
              });
            " style="display:block;text-align:center;background:#2563eb;color:#fff;
              font-size:13px;font-weight:700;padding:10px 20px;border-radius:20px;
              text-decoration:none;margin-top:4px;
              box-shadow:0 2px 8px rgba(37,99,235,0.3)">
              🗺️ Xem bản đồ đầy đủ →
            </a>
            """, unsafe_allow_html=True)

            # if st.button("🗺️ Xem bản đồ đầy đủ →",
            #              use_container_width=True,
            #              key="goto_livemap"):
            #     st.session_state["_switch_tab"] = "🗺️ Live Map"
            #     st.rerun()

    st.markdown('<p class="sec-head">Monitoring Stations</p>', unsafe_allow_html=True)
    stations = df_sf["station_name"].unique().tolist()

    def _stn_card(name):
        sub  = df_sf[df_sf["station_name"] == name].sort_values("date")
        last = sub.dropna(subset=["AQI"]).tail(1)
        av   = float(last["AQI"].iloc[0]) if not last.empty else None
        cat, col = aqi_info(av)
        badge = '<span class="live-bdg">LIVE</span>' if av is not None else '<span class="nd-bdg">NO DATA</span>'
        def _p(c):
            if last.empty or c not in last.columns: return "—"
            v = last[c].iloc[0]; return _fmt(v, 0) if pd.notna(v) else "—"
        return f"""<div class="stn-card">
  <div class="stn-hdr"><div class="stn-name">{name}</div>{badge}</div>
  <div class="stn-addr">Ho Chi Minh City</div>
  <div class="stn-aqi">{_fmt(av,0) if av else "—"}</div>
  <span class="stn-bdg" style="color:{col};border-color:{col};background:{_rgba(col,.1)}">{cat}</span>
  <div class="stn-div"></div>
  <div class="stn-row">
    <div><div class="stn-plbl">PM2.5</div><div class="stn-pval">{_p("PM2,5")}</div></div>
    <div><div class="stn-plbl">PM10</div><div class="stn-pval">{_p("PM10")}</div></div>
    <div><div class="stn-plbl">O3</div><div class="stn-pval">{_p("O3")}</div></div>
  </div>
</div>"""

    for i in range(0, len(stations), 3):
        batch = stations[i:i+3]
        cols  = st.columns(len(batch))
        for co, stn in zip(cols, batch):
            with co: st.markdown(_stn_card(stn), unsafe_allow_html=True)

    st.divider()
    st.markdown('<p class="sec-head">Station Detail View</p>', unsafe_allow_html=True)
    sel = st.selectbox("Chọn trạm", stations, key="det_stn")
    if sel:
        d1, d2 = st.columns([2, 1])
        with d1:
            with st.container(border=True):
                st.markdown(f'<p class="cp-title">📈 AQI Trend – {sel}</p>', unsafe_allow_html=True)
                sub_s = df_sf[df_sf["station_name"]==sel][["date","AQI"]].dropna().sort_values("date")
                if not sub_s.empty:
                    roll = sub_s.set_index("date")["AQI"].rolling(7, min_periods=1).mean().reset_index()
                    fig2 = go.Figure(); _aqi_bands(fig2)
                    fig2.add_trace(go.Scatter(x=sub_s["date"], y=sub_s["AQI"], name="AQI Daily",
                        mode="lines", line=dict(color="#ef4444", width=1.2), opacity=0.6))
                    fig2.add_trace(go.Scatter(x=roll["date"], y=roll["AQI"], name="7-day MA",
                        mode="lines", line=dict(color="#2563eb", width=2.5)))
                    _theme(fig2)
                    fig2.update_layout(hovermode="x unified", yaxis_title="AQI",
                        legend=dict(orientation="h", y=1.12, x=1, xanchor="right"))
                    st.plotly_chart(fig2, use_container_width=True, config=_CFG)
                else: st.info("Khong co du lieu AQI.")
        with d2:
            with st.container(border=True):
                st.markdown('<p class="cp-title">🕸️ Pollutant Profile</p>', unsafe_allow_html=True)
                fig_r = chart_radar(df_sf, sel)
                if fig_r.data: st.plotly_chart(fig_r, use_container_width=True, config=_CFG)
                else: st.info("Khong du du lieu.")


    # ══════════════════════════════════════════════
    # SECTION: STATIONS INFO
    # ══════════════════════════════════════════════
    st.markdown("""
    <div class="db-section-hdr">
      
      <span class="db-section-title">Mạng lưới trạm quan trắc TP.HCM</span>
    </div>
    """, unsafe_allow_html=True)

    STATION_INFO = [
        # ── CORE: HCM nội thành / ngoại thành ──
        {"name": "Hem 108 Tran Van Quang",               "area": "Quận Tân Bình, TP.HCM",            "lat": "10.7799", "lng": "106.6470", "type": "Nội thành"},
        {"name": "Ho Chi Minh City US Consulate",        "area": "Quận 1, TP.HCM",                   "lat": "10.7830", "lng": "106.7010", "type": "Nội thành"},
        {"name": "Duong Ngo Quang Tham",                 "area": "TP. Thủ Đức, TP.HCM",             "lat": "10.6580", "lng": "106.7240", "type": "Nội thành"},
        {"name": "Tp Ho Chi Minh Duong Nguyen Van Tao",  "area": "Huyện Nhà Bè, TP.HCM",             "lat": "10.6596", "lng": "106.7280", "type": "Ngoại thành"},
        # ── CORE: Bình Dương ──
        {"name": "Hiep Thanh",                           "area": "TP. Thủ Dầu Một, Bình Dương",      "lat": "10.9923", "lng": "106.6580", "type": "Ngoại thành"},
        # ── CORE: Bà Rịa – Vũng Tàu ──
        {"name": "Phuoc Hiep",                           "area": "TP. Bà Rịa, BR-VT",                "lat": "10.5024", "lng": "107.1690", "type": "Ngoại thành"},
        {"name": "phuong 7",                             "area": "TP. Vũng Tàu, BR-VT",              "lat": "10.3680", "lng": "107.0840", "type": "Ngoại thành"},
        # ── BUFFER: Long An ──
        {"name": "Long An xa Duc Lap Ha",                "area": "Tỉnh Long An",                     "lat": "10.9127", "lng": "106.4310", "type": "Vùng lân cận"},
        {"name": "Long An tt van hoa huyen Ben Luc",     "area": "Huyện Bến Lức, Long An",           "lat": "10.6400", "lng": "106.4800", "type": "Vùng lân cận"},
        {"name": "Long An TT van hoa huyen Can Giuoc",   "area": "Huyện Cần Giuộc, Long An",         "lat": "10.6056", "lng": "106.6660", "type": "Vùng lân cận"},
        # ── BUFFER: Tây Ninh ──
        {"name": "Tay Ninh thi xa Trang Bang",           "area": "TX. Trảng Bàng, Tây Ninh",         "lat": "11.0340", "lng": "106.3730", "type": "Vùng lân cận"},
        {"name": "Tay Ninh phuong 3 tp Tay Ninh",        "area": "TP. Tây Ninh, Tây Ninh",           "lat": "11.3100", "lng": "106.0984", "type": "Vùng lân cận"},
    ]

    type_colors = {
        "Nội thành":    ("#2563eb", "#dbeafe"),
        "Ngoại thành":  ("#16a34a", "#dcfce7"),
        "Vùng lân cận": ("#f97316", "#ffedd5"),
    }

    cards_html = '<div class="stn-info-grid">'
    for i, s in enumerate(STATION_INFO):
        tc, bg = type_colors.get(s["type"], ("#64748b","#f1f5f9"))
        cards_html += f"""
        <div class="stn-info-card" style="animation-delay:{i*0.05:.2f}s">
          <div class="stn-info-top">
            <div class="stn-info-num">{i+1:02d}</div>
            <span class="stn-info-type" style="color:{tc};background:{bg};border:1px solid {tc}33">{s["type"]}</span>
          </div>
          <div class="stn-info-name">{s["name"]}</div>
          <div class="stn-info-area">📍 {s["area"]}</div>
          <div class="stn-info-coord">{s["lat"]}°N · {s["lng"]}°E</div>
        </div>"""
    cards_html += '</div>'

    st.markdown(f"""
    <style>
    .db-section-hdr {{
        display: flex; align-items: center; gap: 10px;
        margin: 32px 0 16px;
    }}
    .db-section-icon {{ font-size: 22px; }}
    .db-section-title {{
        font-size: 20px; font-weight: 800; color: #1a202c;
        letter-spacing: -0.3px;
    }}
    .stn-info-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 12px; margin-bottom: 8px;
    }}
    .stn-info-card {{
        background: #ffffff; border: 1px solid #e2e8f0;
        border-radius: 14px; padding: 16px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        transition: transform .18s, box-shadow .18s;
        animation: fadeUp .4s ease both;
    }}
    .stn-info-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(37,99,235,0.10);
        border-color: #93c5fd;
    }}
    @keyframes fadeUp {{
        from {{ opacity:0; transform:translateY(12px); }}
        to   {{ opacity:1; transform:translateY(0); }}
    }}
    .stn-info-top {{
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 10px;
    }}
    .stn-info-num {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px; font-weight: 700; color: #94a3b8;
    }}
    .stn-info-type {{
        font-size: 9px; font-weight: 700;
        padding: 2px 8px; border-radius: 20px;
        letter-spacing: 0.3px;
    }}
    .stn-info-name {{
        font-size: 15px; font-weight: 800; color: #1a202c;
        margin-bottom: 4px; line-height: 1.2;
    }}
    .stn-info-area {{
        font-size: 11px; color: #64748b; margin-bottom: 6px;
    }}
    .stn-info-coord {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px; color: #94a3b8;
    }}
    </style>
    {cards_html}
    """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════
    # SECTION: AQI GUIDE
    # ══════════════════════════════════════════════
    st.markdown("""
    <div class="db-section-hdr">
      
      <span class="db-section-title">Thang đo chất lượng không khí (AQI)</span>
    </div>
    """, unsafe_allow_html=True)

    AQI_GUIDE = [
        (0,   50,  "#16a34a", "#f0fdf4", "#bbf7d0", "Tốt",                    "😊", "Không khí trong lành, lý tưởng cho mọi hoạt động ngoài trời."),
        (51,  100, "#ca8a04", "#fefce8", "#fde68a", "Trung bình",              "😐", "Chấp nhận được. Người nhạy cảm nên hạn chế hoạt động kéo dài."),
        (101, 150, "#ea580c", "#fff7ed", "#fed7aa", "Không tốt cho nhóm nhạy cảm", "😷", "Người già, trẻ em, người bệnh hô hấp cần hạn chế ra ngoài."),
        (151, 200, "#dc2626", "#fef2f2", "#fecaca", "Không lành mạnh",         "🤢", "Mọi người có thể bị ảnh hưởng. Hạn chế mọi hoạt động ngoài trời."),
        (201, 300, "#7e22ce", "#faf5ff", "#e9d5ff", "Rất không lành mạnh",     "🚨", "Cảnh báo sức khỏe nghiêm trọng. Tránh hoàn toàn hoạt động ngoài trời."),
        (301, 500, "#7f1d1d", "#fff1f2", "#fecaca", "Nguy hiểm",               "☠️", "Khẩn cấp sức khỏe. Ở trong nhà, đóng kín cửa sổ, dùng máy lọc không khí."),
    ]

    guide_html = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:4px">'
    for lo, hi, color, bg, border, label, emoji, desc in AQI_GUIDE:
        guide_html += f"""<div style="background:{bg};border:1.5px solid {border};border-radius:14px;padding:16px 18px">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
            <div style="width:5px;height:44px;border-radius:4px;background:{color};flex-shrink:0"></div>
            <div style="flex:1">
              <div style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:800;color:{color};line-height:1">{lo}–{hi}</div>
              <div style="font-size:12px;font-weight:700;color:{color};margin-top:3px">{label}</div>
            </div>
            <div style="font-size:28px">{emoji}</div>
          </div>
          <div style="font-size:12px;color:#374151;line-height:1.6">{desc}</div>
        </div>"""
    guide_html += '</div>'
    st.markdown(guide_html, unsafe_allow_html=True)

    # ══════════════════════════════════════════════
    # SECTION: NEWS — tin tuc that
    # ══════════════════════════════════════════════
    st.markdown("""
    <div class="db-section-hdr" style="margin-top:8px">
      
      <span class="db-section-title">Tin tức môi trường TP.HCM</span>
    </div>
    """, unsafe_allow_html=True)

    NEWS = [
        {
            "title": "Chất lượng không khí TP.HCM suy giảm năm 2025",
            "source": "VnExpress",
            "date": "18/12/2025",
            "summary": "Báo cáo quan trắc tại 118 điểm cho thấy nồng độ bụi TSP và PM10 tại TP.HCM có xu hướng tăng. Thành phố đề xuất lắp đặt thêm 157 điểm quan trắc để cảnh báo sớm.",
            "tag": "Cảnh báo",
            "tag_color": "#dc2626",
            "url": "https://vnexpress.net/chat-luong-khong-khi-o-tp-hcm-suy-giam-4995159.html",
        },
        {
            "title": "Giải cứu không khí TP.HCM: PM2.5 vượt ngưỡng WHO 7 lần",
            "source": "Người Lao Động",
            "date": "22/12/2025",
            "summary": "Cuối năm 2025, AQI tại TP.HCM thường xuyên vượt 150, thậm chí có thời điểm trên 200. Giao thông chiếm 63% lượng phát thải PM2.5 với gần 13 triệu phương tiện cá nhân.",
            "tag": "Phân tích",
            "tag_color": "#7e22ce",
            "url": "https://nld.com.vn/giai-cuu-khong-khi-tp-hcm-196251222205928762.htm",
        },
        {
            "title": "Sở TN&MT nói về hướng giải quyết ô nhiễm không khí TP.HCM",
            "source": "Tuổi Trẻ",
            "date": "07/04/2025",
            "summary": "Trạm tại 200 Lý Chính Thắng ghi nhận 4 ngày AQI ở mức kém trong đầu năm. TP.HCM triển khai kế hoạch 5 mục tiêu giảm phát thải bụi khí thải giai đoạn 2024–2025.",
            "tag": "Chính sách",
            "tag_color": "#2563eb",
            "url": "https://tuoitre.vn/so-tai-nguyen-moi-truong-noi-ve-huong-giai-quyet-o-nhiem-khong-khi-o-tp-hcm-20250407180646582.htm",
        },
        {
            "title": "TP.HCM lọt top 5 thành phố ô nhiễm nhất thế giới",
            "source": "IQAir",
            "date": "11/09/2025",
            "summary": "Ngày 11/9/2025 TP.HCM xếp hạng thứ 5 toàn cầu về ô nhiễm, AQI vượt 130. Mức PM2.5 ngày đó gần gấp đôi trung bình năm 2024 (69 AQI), đẩy không khí vào vùng nguy hiểm cho nhóm nhạy cảm.",
            "tag": "Quốc tế",
            "tag_color": "#0891b2",
            "url": "https://www.iqair.com/vi/newsroom/ho-chi-minh-city-among-the-most-polluted-cities-in-the-world-09-11-2025",
        },
        {
            "title": "Ô nhiễm không khí TP.HCM 2025: AQI = 194, top 4 thế giới",
            "source": "Osakar",
            "date": "16/10/2025",
            "summary": "Ngày 14/1/2025, TP.HCM đạt AQI = 194, xếp top 4 thành phố ô nhiễm nhất thế giới. PM2.5 cao gấp 4,2 lần tiêu chuẩn WHO. Gò Vấp, An Sương, Bình Phước là các điểm nóng.",
            "tag": "Dữ liệu",
            "tag_color": "#ea580c",
            "url": "https://osakar.com.vn/tin-tuc/o-nhiem-moi-truong-khong-khi-o-tp-hcm/",
        },
        {
            "title": "AQI TP.HCM đầu năm 2025 dao động 150–200, mức nguy hiểm",
            "source": "Chính sách & Cuộc sống",
            "date": "2025",
            "summary": "Theo Bộ TN&MT, chỉ số AQI tại TP.HCM những tháng đầu năm 2025 dao động 150–200. Xe máy chiếm 90% phát thải CO và 31% PM2.5 toàn thành phố.",
            "tag": "Nghiên cứu",
            "tag_color": "#16a34a",
            "url": "https://chinhsachcuocsong.vnanet.vn/o-nhiem-khong-khi-tang-cao-nhung-ngay-dau-nam-2025/54400.html",
        },
    ]

    news_cards = ""
    for i, n in enumerate(NEWS):
        tc = n["tag_color"]
        news_cards += f"""<a href="{n['url']}" target="_blank" style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;padding:18px;text-decoration:none;display:block;box-shadow:0 1px 4px rgba(0,0,0,0.05)">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
            <span style="font-size:10px;font-weight:700;padding:2px 9px;border-radius:20px;color:{tc};background:{tc}18;border:1px solid {tc}40">{n['tag']}</span>
            <span style="font-size:10px;color:#94a3b8;font-family:monospace">{n['date']}</span>
          </div>
          <div style="font-size:14px;font-weight:700;color:#1a202c;line-height:1.4;margin-bottom:8px">{n['title']}</div>
          <div style="font-size:12px;color:#64748b;line-height:1.6;margin-bottom:10px">{n['summary']}</div>
          <div style="font-size:11px;color:#94a3b8;font-style:italic">— {n['source']}</div>
        </a>"""

    news_html = f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:4px">{news_cards}</div>'
    st.markdown(news_html, unsafe_allow_html=True)

    # ══════════════════════════════════════════════
    # SECTION: TEAM
    # ══════════════════════════════════════════════
    st.markdown("""
    <div class="db-section-hdr" style="margin-top:8px">
      
      <span class="db-section-title">Nhóm phát triển</span>
    </div>
    """, unsafe_allow_html=True)

    TEAM = [
        {"name": "Dương Tiến Thành",       "role": "CEO & Data Lead",        "color": "#2563eb", "bg": "#dbeafe", "photo": "Thanh.jpg"},
        {"name": "Đinh Khắc Nhật Trường",  "role": "CEO & Backend Engineer",  "color": "#16a34a", "bg": "#dcfce7", "photo": "Truong.jpg"},
        {"name": "Lê Thị Anh Thương",      "role": "CEO & Frontend Dev",      "color": "#ea580c", "bg": "#ffedd5", "photo": "Thuong.jpg"},
        {"name": "Trần Công Vinh",          "role": "CEO & GIS Specialist",    "color": "#7e22ce", "bg": "#ede9fe", "photo": "Vinh.jpg"},
        {"name": "Đặng Quang Nhật",         "role": "CEO & AI Engineer",       "color": "#0891b2", "bg": "#cffafe", "photo": "Nhat.jpg"},
    ]

    def _initials(name):
        parts = name.strip().split()
        return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else parts[0][:2].upper()

    def _photo_src(path):
        """Doc anh tu file local, tra ve data URI base64. Neu loi tra ve None."""
        import base64, mimetypes
        try:
            mime = mimetypes.guess_type(path)[0] or "image/jpeg"
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return f"data:{mime};base64,{b64}"
        except Exception:
            return None

    team_cards = ""
    for m in TEAM:
        src = _photo_src(m["photo"]) if m["photo"] else None
        if src:
            avatar = (f'<img src="{src}" '
                      f'style="width:72px;height:72px;border-radius:50%;object-fit:cover;'
                      f'border:3px solid {m["color"]}50;display:block;margin:0 auto 12px">')
        else:
            ini = _initials(m["name"])
            avatar = (f'<div style="width:72px;height:72px;border-radius:50%;'
                      f'background:linear-gradient(135deg,{m["bg"]},{m["color"]}35);'
                      f'border:2.5px solid {m["color"]}50;'
                      f'display:flex;align-items:center;justify-content:center;'
                      f'margin:0 auto 12px;font-size:22px;font-weight:800;'
                      f'color:{m["color"]};font-family:Inter,sans-serif;'
                      f'letter-spacing:-0.5px">{ini}</div>')

        display_name = m["name"] if len(m["name"]) <= 20 else m["name"][:18] + "…"

        team_cards += (f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;'
                       f'padding:20px 12px 18px;text-align:center;'
                       f'box-shadow:0 1px 4px rgba(0,0,0,0.05);'
                       f'transition:transform .2s,box-shadow .2s"'
                       f' onmouseover="this.style.transform=\'translateY(-4px)\';'
                       f'this.style.boxShadow=\'0 10px 28px rgba(0,0,0,0.10)\'"'
                       f' onmouseout="this.style.transform=\'\';'
                       f'this.style.boxShadow=\'0 1px 4px rgba(0,0,0,0.05)\'">'
                       f'{avatar}'
                       f'<div style="font-size:13px;font-weight:800;color:#1a202c;'
                       f'margin-bottom:3px;line-height:1.3">{display_name}</div>'
                       f'<div style="font-size:11px;font-weight:600;color:{m["color"]};'
                       f'margin-bottom:10px">{m["role"]}</div>'
                       f'<span style="font-size:9px;font-weight:700;padding:2px 10px;'
                       f'border-radius:20px;background:{m["bg"]};color:{m["color"]};'
                       f'border:1px solid {m["color"]}40;text-transform:uppercase;'
                       f'letter-spacing:0.5px">MegaAQI Team</span>'
                       f'</div>')

    team_html = f'<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:32px">{team_cards}</div>'
    st.markdown(team_html, unsafe_allow_html=True)


def render_eda():
    with st.spinner("Loading data..."):
        try:    df_city = get_city()
        except Exception as e: st.error(f"Cannot load City CSV: {e}"); st.stop()
        try:    df_st   = get_stations()
        except Exception as e: st.error(f"Cannot load Stations CSV: {e}"); st.stop()

    if "eda_station" not in st.session_state:
        st.session_state["eda_station"] = None

    st.markdown("""<div class="hero">
      <h1>Exploratory Data Analysis</h1>
      <p>Phân tích dữ liệu khám phá - mối quan hệ giữa các chỉ số ô nhiễm, phân bố AQI và biến thiên theo trạm quan trắc</p>
    </div>""", unsafe_allow_html=True)

    eda_mode = st.radio("Nguồn dữ liệu EDA", ["🏙️ Toàn thành phố", "📍 Theo trạm"],
                        horizontal=True, label_visibility="visible", key="eda_mode")

    fe1, fe2 = st.columns([1, 1])
    with fe1:
        ta = pd.Timestamp(st.date_input("Từ ngày", value=date(2022,1,1),
            min_value=df_city["date"].min().date(), max_value=df_city["date"].max().date(), key="eda_d0"))
    with fe2:
        tb = pd.Timestamp(st.date_input("Đến ngày", value=date.today(),
            min_value=df_city["date"].min().date(), max_value=df_city["date"].max().date(), key="eda_d1"))
    if ta > tb: ta, tb = tb, ta

    df_ca = df_city[(df_city["date"] >= ta) & (df_city["date"] <= tb)].copy()
    df_sa = df_st  [(df_st["date"]   >= ta) & (df_st["date"]   <= tb)].copy()

    if eda_mode == "🏙️ Toàn thành phố":
        st.session_state["eda_station"] = None
        render_city_eda(df_ca, df_sa)
    else:
        all_stns = df_sa["station_name"].unique().tolist()
        default_idx = 0
        if st.session_state["eda_station"] and st.session_state["eda_station"] in all_stns:
            default_idx = all_stns.index(st.session_state["eda_station"])
        chosen = st.selectbox("Chọn Trạm", all_stns, index=default_idx, key="eda_stn_pick")
        st.session_state["eda_station"] = chosen
        st.markdown(f"""<div class="stn-sel-bar">
          <span class="stn-sel-label">📍 Đang xem EDA của trạm:</span>
          <span class="stn-sel-name">{chosen}</span>
        </div>""", unsafe_allow_html=True)
        render_station_eda(df_sa, chosen, df_ca)

# ══════════════════════════════════════════════════════════════════
#  FORECAST TAB
# ══════════════════════════════════════════════════════════════════
FORECAST_CSV = "output_all_stations_2022_2026/hcmc_imputed_output_v2_20260318.csv"
FORECAST_HORIZON = 5

AQI_BANDS_FC = [
    (0,   50,  "#16a34a", "Tốt"),
    (51,  100, "#ca8a04", "Trung bình"),
    (101, 150, "#ea580c", "Không tốt"),
    (151, 200, "#dc2626", "Không lành mạnh"),
    (201, 300, "#7e22ce", "Rất không lành mạnh"),
    (301, 999, "#7f1d1d", "Nguy hiểm"),
]

def _aqi_color_fc(v):
    try:
        val = float(v)
    except Exception:
        return "#a0aec0", "N/A"
    for lo, hi, c, l in AQI_BANDS_FC:
        if lo <= val <= hi:
            return c, l
    return "#7f1d1d", "Nguy hiểm"


@st.cache_data(ttl=3600)
def _load_imputed_csv():
    df = pd.read_csv(FORECAST_CSV)
    df["date"] = pd.to_datetime(df["date"])
    if "PM2,5" in df.columns and "PM2.5" not in df.columns:
        df = df.rename(columns={"PM2,5": "PM2.5"})
    return df


def render_forecast():
    from forecast_logic import load_all_models, predict_station, get_history_for_chart, TARGETS, load_metadata
    import plotly.graph_objects as go

    st.markdown("""<div class="hero">
      <h1>🔮 Dự báo chất lượng không khí</h1>
      <p>XGBoost · Multi-output · Dự báo 5 ngày tới cho 12 trạm quan trắc</p>
    </div>""", unsafe_allow_html=True)

    with st.spinner("Đang tải model..."):
        models = load_all_models()

    if not models:
        st.error("Chưa có model. Vui lòng chạy: `python train_forecast.py`")
        return

    with st.spinner("Đang tải dữ liệu..."):
        try:
            df_full = _load_imputed_csv()
        except Exception as e:
            st.error(f"Không tải được dữ liệu: {e}")
            return

    sel_stn = st.selectbox("📍 Chọn trạm quan trắc", sorted(models.keys()), key="fc_station")

    with st.spinner("Đang tính dự báo..."):
        df_hist = get_history_for_chart(sel_stn, df_full, days=30)
        df_pred = predict_station(sel_stn, df_full, models, horizon=FORECAST_HORIZON)

    if df_pred is None or df_pred.empty:
        st.warning("Không có dữ liệu dự báo.")
        return

    # Chuẩn hoá df_hist
    df_hist = df_hist.copy()
    df_hist["AQI"] = df_hist["AQI"].ffill().bfill().fillna(0)
    for col in TARGETS:
        if col in df_hist.columns:
            df_hist[col] = df_hist[col].ffill().bfill().fillna(0)

    # ── KPI cards ──
    st.markdown('<p class="sec-head" style="margin-top:8px">📅 Dự báo 5 ngày tới</p>',
                unsafe_allow_html=True)
    kpi_html = '<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:16px">'
    for _, row in df_pred.iterrows():
        aqi_val = float(row["AQI"])
        color, label = _aqi_color_fc(aqi_val)
        date_str = pd.Timestamp(row["date"]).strftime("%a\n%d/%m")
        kpi_html += f"""
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;
             padding:14px 10px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.05)">
          <div style="font-size:11px;font-weight:700;color:#64748b;white-space:pre-line;margin-bottom:6px">{date_str}</div>
          <div style="font-size:32px;font-weight:800;font-family:'JetBrains Mono',monospace;color:#1a202c;line-height:1">{aqi_val:.0f}</div>
          <div style="font-size:10px;font-weight:700;color:{color};margin-top:4px;padding:2px 8px;border-radius:10px;
               background:{color}18;border:1px solid {color}30;display:inline-block">{label}</div>
          <div style="font-size:10px;color:#94a3b8;margin-top:8px">PM2.5: <b>{float(row['PM2.5']):.1f}</b></div>
        </div>"""
    kpi_html += '</div>'
    st.markdown(kpi_html, unsafe_allow_html=True)

    # ── Chuẩn bị dữ liệu chart ──
    connect_date = df_hist["date"].iloc[-1]
    connect_aqi  = float(df_hist["AQI"].iloc[-1])
    today_str    = pd.Timestamp(connect_date).strftime("%Y-%m-%d")

    pred_dates = [connect_date] + df_pred["date"].tolist()
    pred_aqi   = [connect_aqi]  + [float(v) for v in df_pred["AQI"]]

    # ── Chart AQI ──
    fig = go.Figure()
    for lo, hi, c, _ in AQI_BANDS_FC:
        fig.add_hrect(y0=lo, y1=min(hi, 300), fillcolor=c, opacity=0.05, layer="below", line_width=0)

    fig.add_trace(go.Scatter(
        x=df_hist["date"], y=df_hist["AQI"],
        name="Lịch sử", mode="lines", line=dict(color="#2563eb", width=2)))

    fig.add_trace(go.Scatter(
        x=pred_dates, y=pred_aqi,
        name="Dự báo", mode="lines+markers",
        line=dict(color="#f97316", width=2.5, dash="dot"),
        marker=dict(size=8, color="#f97316", line=dict(color="#fff", width=2))))

    # Uncertainty band ±15%
    upper = [v * 1.15 for v in pred_aqi]
    lower = [max(0, v * 0.85) for v in pred_aqi]
    fig.add_trace(go.Scatter(
        x=pred_dates + pred_dates[::-1], y=upper + lower[::-1],
        fill="toself", fillcolor="rgba(249,115,22,0.10)",
        line=dict(width=0), showlegend=False, hoverinfo="skip"))

    # Đường "Hôm nay" dùng add_shape thay vi add_vline
    fig.add_shape(type="line",
        x0=today_str, x1=today_str, y0=0, y1=1, xref="x", yref="paper",
        line=dict(dash="dash", color="#94a3b8", width=1.5))
    fig.add_annotation(x=today_str, y=1, xref="x", yref="paper",
        text="Hôm nay", showarrow=False, yanchor="bottom",
        font=dict(size=10, color="#64748b"))

    fig.update_layout(
        paper_bgcolor="#ffffff", plot_bgcolor="#f8fafc",
        font=dict(family="Inter,sans-serif", color="#4a5568", size=11),
        margin=dict(l=8, r=8, t=24, b=8),
        hovermode="x unified", yaxis_title="AQI", height=380,
        xaxis=dict(gridcolor="#e2e8f0", zeroline=False, tickfont=dict(size=9, color="#718096")),
        yaxis=dict(gridcolor="#e2e8f0", zeroline=False, tickfont=dict(size=9, color="#718096")),
        legend=dict(bgcolor="rgba(255,255,255,0.95)", bordercolor="#e2e8f0", borderwidth=1, font=dict(size=10)))

    with st.container(border=True):
        st.markdown('<p class="cp-title">📈 AQI — 30 ngày qua + dự báo 5 ngày tới</p>', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True, config=dict(displayModeBar=False), key="fc_aqi_chart")

    # ── Pollutant charts ──
    st.markdown('<p class="sec-head">🧪 Chi tiết từng chỉ số</p>', unsafe_allow_html=True)
    POLL_COLORS = {"PM2.5":"#ef4444","PM10":"#f97316","CO":"#eab308","SO2":"#22c55e","O3":"#3b82f6","NO2":"#8b5cf6"}
    POLL_UNITS  = {"PM2.5":"µg/m³","PM10":"µg/m³","CO":"µg/m³","SO2":"ppb","O3":"ppb","NO2":"ppb"}

    for row_i in range(0, len(TARGETS), 2):
        cols = st.columns(2)
        for ci, col_name in enumerate(TARGETS[row_i:row_i+2]):
            with cols[ci]:
                with st.container(border=True):
                    color = POLL_COLORS[col_name]
                    unit  = POLL_UNITS[col_name]
                    st.markdown(
                        f'<p class="cp-title" style="color:{color}">{col_name} '
                        f'<span style="font-weight:400;color:#94a3b8;font-size:11px">({unit})</span></p>',
                        unsafe_allow_html=True)

                    hist_y = df_hist[col_name].ffill().bfill().fillna(0)
                    last_v = float(hist_y.iloc[-1])
                    pred_y = [float(v) for v in df_pred[col_name]]
                    px_    = [connect_date] + df_pred["date"].tolist()
                    py_    = [last_v] + pred_y

                    fig2 = go.Figure()
                    fig2.add_trace(go.Scatter(
                        x=df_hist["date"], y=hist_y, mode="lines",
                        line=dict(color=color, width=1.8), showlegend=False))
                    fig2.add_trace(go.Scatter(
                        x=px_, y=py_, mode="lines+markers",
                        line=dict(color=color, width=2, dash="dot"),
                        marker=dict(size=6, color=color, line=dict(color="#fff", width=1.5)),
                        showlegend=False))
                    fig2.add_shape(type="line",
                        x0=today_str, x1=today_str, y0=0, y1=1, xref="x", yref="paper",
                        line=dict(dash="dash", color="#cbd5e0", width=1))
                    fig2.update_layout(
                        paper_bgcolor="#ffffff", plot_bgcolor="#f8fafc",
                        margin=dict(l=4, r=4, t=4, b=4), height=200,
                        showlegend=False, hovermode="x unified",
                        xaxis=dict(gridcolor="#e2e8f0", zeroline=False, tickfont=dict(size=8, color="#718096")),
                        yaxis=dict(gridcolor="#e2e8f0", zeroline=False,
                                   tickfont=dict(size=8, color="#718096"), title=unit))
                    st.plotly_chart(fig2, use_container_width=True,
                                    config=dict(displayModeBar=False),
                                    key=f"fc_{col_name}_{sel_stn}")

    # ── Model metrics ──
    with st.expander("📊 Độ chính xác model (Validation set)"):
        meta = load_metadata()
        if sel_stn in meta:
            m_info = meta[sel_stn]
            st.markdown(f'<p class="cp-sub">Train: {m_info["n_train"]} ngày · Data đến {m_info["date_max"]}</p>',
                        unsafe_allow_html=True)
            rows = [{"Chỉ số": col, "MAE": round(m["mae"], 2), "RMSE": round(m["rmse"], 2)}
                    for col, m in m_info["metrics"].items()]
            st.dataframe(pd.DataFrame(rows).set_index("Chỉ số"), use_container_width=True)
        st.caption("Đơn vị: µg/m³ cho PM2.5/PM10/CO, ppb cho SO2/O3/NO2")