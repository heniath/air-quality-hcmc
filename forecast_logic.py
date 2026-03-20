# -*- coding: utf-8 -*-
"""
forecast_logic.py — Load model va predict 5 ngay tuong lai
Duoc import boi app_logic.py (tab Forecast)

Su dung:
    from forecast_logic import load_all_models, predict_station, TARGETS
"""

import os
import re
import json
import joblib
import numpy as np
import pandas as pd
import streamlit as st

TARGETS    = ["PM2.5", "PM10", "SO2", "O3", "CO", "NO2"]
LAGS       = [1, 2, 3, 7, 14]
ROLL_WINDOWS = [7, 14, 30]
MODELS_DIR = "models"
HORIZON    = 5   # so ngay du doan

# ──────────────────────────────────────────────
# AQI CALCULATION (EPA)
# ──────────────────────────────────────────────
def _linear_aqi(cp, bp_lo, bp_hi, aqi_lo, aqi_hi):
    return ((aqi_hi - aqi_lo) / (bp_hi - bp_lo)) * (cp - bp_lo) + aqi_lo

def _calc(c, bps):
    for lo, hi, alo, ahi in bps:
        if lo <= c <= hi:
            return round(_linear_aqi(c, lo, hi, alo, ahi))
    return 500

def pm25_to_aqi(c):
    c = round(max(0, c), 1)
    return _calc(c, [(0,12.0,0,50),(12.1,35.4,51,100),(35.5,55.4,101,150),
                     (55.5,150.4,151,200),(150.5,250.4,201,300),(250.5,350.4,301,400),(350.5,500.4,401,500)])

def pm10_to_aqi(c):
    c = int(max(0, c))
    return _calc(c, [(0,54,0,50),(55,154,51,100),(155,254,101,150),
                     (255,354,151,200),(355,424,201,300),(425,504,301,400),(505,604,401,500)])

def co_to_aqi(c_ugm3):
    c = round(max(0, c_ugm3) / 1145, 1)
    return _calc(c, [(0,4.4,0,50),(4.5,9.4,51,100),(9.5,12.4,101,150),
                     (12.5,15.4,151,200),(15.5,30.4,201,300),(30.5,40.4,301,400),(40.5,50.4,401,500)])

def so2_to_aqi(c):
    """SO2 (ppb) -> AQI — data da la ppb, khong can convert"""
    c = round(max(0, c))
    return _calc(c, [(0,35,0,50),(36,75,51,100),(76,185,101,150),
                     (186,304,151,200),(305,604,201,300),(605,804,301,400),(805,1004,401,500)])

def o3_to_aqi(c):
    """O3 (ppb) -> AQI — chia 1000 de ra ppm"""
    c_ppm = round(max(0, c) / 1000, 3)
    return _calc(c_ppm, [(0.000,0.054,0,50),(0.055,0.070,51,100),(0.071,0.085,101,150),
                         (0.086,0.105,151,200),(0.106,0.200,201,300),(0.205,0.404,301,400),(0.405,0.604,401,500)])

def no2_to_aqi(c):
    c = max(0, c)
    return _calc(c, [(0,53,0,50),(54,100,51,100),(101,360,101,150),
                     (361,649,151,200),(650,1249,201,300),(1250,1649,301,400),(1650,2049,401,500)])

def pollutants_to_aqi(pm25, pm10, co, so2, o3, no2):
    try:
        return float(max(
            pm25_to_aqi(pm25), pm10_to_aqi(pm10), co_to_aqi(co),
            so2_to_aqi(so2),   o3_to_aqi(o3),     no2_to_aqi(no2)
        ))
    except Exception:
        return float("nan")


# ──────────────────────────────────────────────
# FEATURE ENGINEERING (phai giong train_forecast.py)
# ──────────────────────────────────────────────
def _add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["day_of_week"]  = df["date"].dt.dayofweek
    df["day_of_year"]  = df["date"].dt.dayofyear
    df["month"]        = df["date"].dt.month
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["is_weekend"]   = (df["day_of_week"] >= 5).astype(int)
    return df

def _add_lag_roll(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in TARGETS:
        for lag in LAGS:
            df[f"{col}_lag{lag}"] = df[col].shift(lag)
        for w in ROLL_WINDOWS:
            df[f"{col}_rmean{w}"] = df[col].shift(1).rolling(w, min_periods=1).mean()
        df[f"{col}_rstd7"] = df[col].shift(1).rolling(7, min_periods=1).std().fillna(0)
    return df

def _make_feature_row(df_hist: pd.DataFrame, feat_cols: list) -> np.ndarray:
    """
    Lay hang cuoi cung cua df_hist (sau khi da add lag/roll)
    de tao vector feature cho ngay tiep theo.
    """
    df_hist = _add_time_features(df_hist)
    df_hist = _add_lag_roll(df_hist)
    last    = df_hist.iloc[[-1]][feat_cols]
    return last.values.astype(np.float32)


# ──────────────────────────────────────────────
# LOAD MODELS
# ──────────────────────────────────────────────
def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")

@st.cache_resource(show_spinner=False)
def load_all_models() -> dict:
    """
    Load tat ca model file tu MODELS_DIR.
    Tra ve dict: {station_name: {model, feat_cols, co_cap}}
    """
    meta_path = os.path.join(MODELS_DIR, "forecast_metadata.json")
    if not os.path.exists(meta_path):
        return {}

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    models = {}
    for stn, info in meta.items():
        path = info["path"]
        if os.path.exists(path):
            obj = joblib.load(path)
            obj["metrics"]  = info["metrics"]
            obj["n_train"]  = info["n_train"]
            obj["date_max"] = info["date_max"]
            models[stn]     = obj
    return models


def load_metadata() -> dict:
    meta_path = os.path.join(MODELS_DIR, "forecast_metadata.json")
    if not os.path.exists(meta_path):
        return {}
    with open(meta_path, encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────
# PREDICT
# ──────────────────────────────────────────────
def predict_station(
    station_name: str,
    df_full: pd.DataFrame,
    models: dict,
    horizon: int = HORIZON,
) -> pd.DataFrame | None:
    """
    Du doan `horizon` ngay ke tu ngay cuoi cung trong data.

    Parameters
    ----------
    station_name : ten tram
    df_full      : DataFrame chua tat ca du lieu cua tram do (da co PM2.5..NO2)
    models       : dict tu load_all_models()
    horizon      : so ngay du doan (default 5)

    Returns
    -------
    DataFrame voi columns: date, PM2.5, PM10, SO2, O3, CO, NO2, AQI
    """
    if station_name not in models:
        return None

    obj       = models[station_name]
    model     = obj["model"]
    feat_cols = obj["feat_cols"]
    co_cap    = obj.get("co_cap", 5000)

    # Chuan bi lich su — lay 60 ngay cuoi de tinh lag
    df_stn = df_full[df_full["station_name"] == station_name].copy()
    df_stn = df_stn.sort_values("date").reset_index(drop=True)

    # Normalize column name
    if "PM2,5" in df_stn.columns and "PM2.5" not in df_stn.columns:
        df_stn = df_stn.rename(columns={"PM2,5": "PM2.5"})

    # Lay window du de tinh lag14 + rolling30
    window = 60
    df_hist = df_stn[TARGETS + ["date"]].tail(window).copy().reset_index(drop=True)

    last_date = df_hist["date"].max()
    predictions = []

    for step in range(horizon):
        next_date = last_date + pd.Timedelta(days=step + 1)

        # Them dong gia tri cuoi (step truoc) de feature row dung lag
        x = _make_feature_row(df_hist, feat_cols)

        # Predict
        y_pred = model.predict(x)[0]           # shape (6,)
        y_pred = np.clip(y_pred, 0, None)
        y_pred[TARGETS.index("CO")] = min(y_pred[TARGETS.index("CO")], co_cap)

        pred_dict = {col: float(y_pred[i]) for i, col in enumerate(TARGETS)}
        pred_dict["date"] = next_date
        pred_dict["AQI"]  = pollutants_to_aqi(
            pred_dict["PM2.5"], pred_dict["PM10"],
            pred_dict["CO"],    pred_dict["SO2"],
            pred_dict["O3"],    pred_dict["NO2"],
        )
        predictions.append(pred_dict)

        # Append predicted row vao lich su cho buoc tiep theo (recursive)
        new_row = pd.DataFrame([{**{"date": next_date}, **{c: pred_dict[c] for c in TARGETS}}])
        df_hist = pd.concat([df_hist, new_row], ignore_index=True)

    return pd.DataFrame(predictions)


def get_history_for_chart(
    station_name: str,
    df_full: pd.DataFrame,
    days: int = 30,
) -> pd.DataFrame:
    """
    Tra ve `days` ngay gan nhat cua tram de ve chart lich su.
    """
    df_stn = df_full[df_full["station_name"] == station_name].copy()
    df_stn = df_stn.sort_values("date").tail(days).reset_index(drop=True)

    if "PM2,5" in df_stn.columns and "PM2.5" not in df_stn.columns:
        df_stn = df_stn.rename(columns={"PM2,5": "PM2.5"})

    # Tinh lai AQI tu pollutants
    df_stn["AQI"] = df_stn.apply(
        lambda r: pollutants_to_aqi(r["PM2.5"], r["PM10"], r["CO"], r["SO2"], r["O3"], r["NO2"]),
        axis=1
    )
    return df_stn[["date"] + TARGETS + ["AQI"]]