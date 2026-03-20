# -*- coding: utf-8 -*-
"""
train_forecast.py — Train XGBoost forecast models cho 12 tram
Chay 1 lan offline:
    python train_forecast.py

Output:
    models/forecast_<station_slug>.pkl   — model file
    models/forecast_metadata.json        — MAE/RMSE cua tung model
"""

import os
import json
import re
import warnings
import joblib
import numpy as np
import pandas as pd
from sklearn.multioutput import MultiOutputRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
IMPUTED_CSV  = "output_all_stations_2022_2026/hcmc_imputed_output_v2_20260318.csv"
MODELS_DIR   = "models"
TARGETS      = ["PM2.5", "PM10", "SO2", "O3", "CO", "NO2"]

# Lag features: so ngay truoc
LAGS         = [1, 2, 3, 7, 14]
# Rolling windows
ROLL_WINDOWS = [7, 14, 30]

# Train/val split ratio
VAL_RATIO    = 0.15   # 15% cuoi lam validation

# Sample weight: real data duoc cao hon imputed
W_REAL       = 2.0
W_IMPUTED_AB = 1.0    # short gap
W_IMPUTED_C  = 0.4    # long gap (fill tu nguon khac)

# XGBoost params
XGB_PARAMS = dict(
    n_estimators     = 300,
    max_depth        = 5,
    learning_rate    = 0.05,
    subsample        = 0.8,
    colsample_bytree = 0.8,
    min_child_weight = 3,
    reg_alpha        = 0.1,
    reg_lambda       = 1.0,
    random_state     = 42,
    n_jobs           = -1,
    verbosity        = 0,
)

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["day_of_week"]  = df["date"].dt.dayofweek
    df["day_of_year"]  = df["date"].dt.dayofyear
    df["month"]        = df["date"].dt.month
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["is_weekend"]   = (df["day_of_week"] >= 5).astype(int)
    return df


def add_lag_roll_features(df: pd.DataFrame, targets: list) -> pd.DataFrame:
    df = df.copy()
    for col in targets:
        # Lag features
        for lag in LAGS:
            df[f"{col}_lag{lag}"] = df[col].shift(lag)
        # Rolling mean & std
        for w in ROLL_WINDOWS:
            df[f"{col}_rmean{w}"] = df[col].shift(1).rolling(w, min_periods=1).mean()
        df[f"{col}_rstd7"]  = df[col].shift(1).rolling(7,  min_periods=1).std().fillna(0)
    return df


def compute_sample_weights(df: pd.DataFrame) -> np.ndarray:
    """
    Real data -> W_REAL
    Imputed type A/B -> W_IMPUTED_AB
    Imputed type C -> W_IMPUTED_C
    Average across all 6 targets.
    """
    weights = np.zeros(len(df))
    for col in TARGETS:
        imp_col  = f"imputed_{col}"
        gap_col  = f"gap_type_{col}"
        w = np.where(
            ~df[imp_col],
            W_REAL,
            np.where(df[gap_col].isin(["A", "B"]), W_IMPUTED_AB, W_IMPUTED_C)
        )
        weights += w
    return weights / len(TARGETS)


def build_features_labels(df: pd.DataFrame):
    """
    Tra ve X (features), y (targets), w (sample weights),
    va danh sach feature columns.
    """
    df = add_time_features(df)
    df = add_lag_roll_features(df, TARGETS)

    # Feature cols
    time_cols  = ["day_of_week", "day_of_year", "month", "week_of_year", "is_weekend"]
    lag_cols   = [c for c in df.columns
                  if any(f"{t}_lag" in c or f"{t}_rmean" in c or f"{t}_rstd7" in c
                         for t in TARGETS)]
    feat_cols  = time_cols + sorted(lag_cols)

    # Drop rows voi NaN trong features (do lag)
    mask = df[feat_cols].notna().all(axis=1)
    df   = df[mask].copy()

    X = df[feat_cols].values.astype(np.float32)
    y = df[TARGETS].values.astype(np.float32)
    w = compute_sample_weights(df)

    return X, y, w, feat_cols, df


# ──────────────────────────────────────────────
# AQI CALCULATION (EPA standard)
# ──────────────────────────────────────────────
def _linear_aqi(cp, bp_lo, bp_hi, aqi_lo, aqi_hi):
    return ((aqi_hi - aqi_lo) / (bp_hi - bp_lo)) * (cp - bp_lo) + aqi_lo

def pm25_to_aqi(c):
    """PM2.5 (ug/m3) -> AQI"""
    c = round(c, 1)
    bps = [(0,12.0,0,50),(12.1,35.4,51,100),(35.5,55.4,101,150),
           (55.5,150.4,151,200),(150.5,250.4,201,300),(250.5,350.4,301,400),(350.5,500.4,401,500)]
    for lo,hi,alo,ahi in bps:
        if lo <= c <= hi:
            return round(_linear_aqi(c, lo, hi, alo, ahi))
    return 500

def pm10_to_aqi(c):
    """PM10 (ug/m3) -> AQI"""
    c = int(c)
    bps = [(0,54,0,50),(55,154,51,100),(155,254,101,150),
           (255,354,151,200),(355,424,201,300),(425,504,301,400),(505,604,401,500)]
    for lo,hi,alo,ahi in bps:
        if lo <= c <= hi:
            return round(_linear_aqi(c, lo, hi, alo, ahi))
    return 500

def co_to_aqi(c_ugm3):
    """CO (ug/m3) -> AQI  (convert to ppm first: /1145)"""
    c = round(c_ugm3 / 1145, 1)
    bps = [(0,4.4,0,50),(4.5,9.4,51,100),(9.5,12.4,101,150),
           (12.5,15.4,151,200),(15.5,30.4,201,300),(30.5,40.4,301,400),(40.5,50.4,401,500)]
    for lo,hi,alo,ahi in bps:
        if lo <= c <= hi:
            return round(_linear_aqi(c, lo, hi, alo, ahi))
    return 500

def so2_to_aqi(c):
    """SO2 (ppb) -> AQI — data da la ppb"""
    c = round(max(0, c))
    bps = [(0,35,0,50),(36,75,51,100),(76,185,101,150),
           (186,304,151,200),(305,604,201,300),(605,804,301,400),(805,1004,401,500)]
    for lo,hi,alo,ahi in bps:
        if lo <= c <= hi:
            return round(_linear_aqi(c, lo, hi, alo, ahi))
    return 500

def o3_to_aqi(c):
    """O3 (ppb) -> AQI — chia 1000 de ra ppm"""
    c_ppm = round(max(0, c) / 1000, 3)
    bps = [(0.000,0.054,0,50),(0.055,0.070,51,100),(0.071,0.085,101,150),
           (0.086,0.105,151,200),(0.106,0.200,201,300),(0.205,0.404,301,400),(0.405,0.604,401,500)]
    for lo,hi,alo,ahi in bps:
        if lo <= c_ppm <= hi:
            return round(_linear_aqi(c_ppm, lo, hi, alo, ahi))
    return 500

def no2_to_aqi(c):
    """NO2 (ppb) -> AQI"""
    bps = [(0,53,0,50),(54,100,51,100),(101,360,101,150),
           (361,649,151,200),(650,1249,201,300),(1250,1649,301,400),(1650,2049,401,500)]
    for lo,hi,alo,ahi in bps:
        if lo <= c <= hi:
            return round(_linear_aqi(c, lo, hi, alo, ahi))
    return 500

def pollutants_to_aqi(pm25, pm10, co, so2, o3, no2):
    """Tinh AQI tong hop tu tat ca chi so — lay max theo EPA."""
    try:
        aqis = [
            pm25_to_aqi(max(0, pm25)),
            pm10_to_aqi(max(0, pm10)),
            co_to_aqi(max(0, co)),
            so2_to_aqi(max(0, so2)),
            o3_to_aqi(max(0, o3)),
            no2_to_aqi(max(0, no2)),
        ]
        return float(max(aqis))
    except Exception:
        return float("nan")


# ──────────────────────────────────────────────
# TRAIN ONE STATION
# ──────────────────────────────────────────────
def train_station(station_name: str, df_stn: pd.DataFrame) -> dict:
    print(f"\n  Training: {station_name}")

    # Sort by date
    df_stn = df_stn.sort_values("date").reset_index(drop=True)

    # Build features
    X, y, w, feat_cols, df_clean = build_features_labels(df_stn)

    n_total = len(X)
    n_val   = max(30, int(n_total * VAL_RATIO))
    n_train = n_total - n_val

    if n_train < 60:
        print(f"    SKIP — only {n_train} training rows after lag removal")
        return None

    X_train, X_val = X[:n_train], X[n_train:]
    y_train, y_val = y[:n_train], y[n_train:]
    w_train        = w[:n_train]

    # Clip CO outliers (>99th percentile) truoc khi train
    co_idx = TARGETS.index("CO")
    co_cap = np.percentile(y_train[:, co_idx], 99)
    y_train[:, co_idx] = np.clip(y_train[:, co_idx], 0, co_cap)
    y_val[:, co_idx]   = np.clip(y_val[:, co_idx],   0, co_cap)

    # Model
    base = XGBRegressor(**XGB_PARAMS)
    model = MultiOutputRegressor(base, n_jobs=1)
    model.fit(X_train, y_train, sample_weight=w_train)

    # Evaluate on val set
    y_pred = model.predict(X_val)
    y_pred = np.clip(y_pred, 0, None)

    metrics = {}
    for i, col in enumerate(TARGETS):
        mae  = mean_absolute_error(y_val[:, i], y_pred[:, i])
        rmse = mean_squared_error(y_val[:, i], y_pred[:, i]) ** 0.5
        metrics[col] = {"mae": round(mae, 3), "rmse": round(rmse, 3)}

    print(f"    n_train={n_train}  n_val={n_val}")
    for col, m in metrics.items():
        print(f"      {col:6s}: MAE={m['mae']:.2f}  RMSE={m['rmse']:.2f}")

    return {
        "model":      model,
        "feat_cols":  feat_cols,
        "co_cap":     float(co_cap),
        "metrics":    metrics,
        "n_train":    n_train,
        "n_val":      n_val,
        "station":    station_name,
        "date_min":   str(df_clean["date"].min().date()),
        "date_max":   str(df_clean["date"].max().date()),
    }


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    os.makedirs(MODELS_DIR, exist_ok=True)

    print("Loading imputed CSV...")
    df = pd.read_csv(IMPUTED_CSV)
    df["date"] = pd.to_datetime(df["date"])

    # Rename PM2.5 if needed (sometimes PM2,5)
    if "PM2,5" in df.columns and "PM2.5" not in df.columns:
        df = df.rename(columns={"PM2,5": "PM2.5"})
    if "imputed_PM2,5" in df.columns and "imputed_PM2.5" not in df.columns:
        df = df.rename(columns={"imputed_PM2,5": "imputed_PM2.5",
                                 "gap_type_PM2,5": "gap_type_PM2.5"})

    stations    = sorted(df["station_name"].unique())
    all_metadata = {}

    for stn in stations:
        df_stn = df[df["station_name"] == stn].copy()

        result = train_station(stn, df_stn)
        if result is None:
            continue

        slug = slugify(stn)
        path = os.path.join(MODELS_DIR, f"forecast_{slug}.pkl")

        # Save model + metadata together
        joblib.dump({
            "model":     result["model"],
            "feat_cols": result["feat_cols"],
            "co_cap":    result["co_cap"],
            "station":   stn,
        }, path)

        all_metadata[stn] = {
            "slug":     slug,
            "path":     path,
            "n_train":  result["n_train"],
            "n_val":    result["n_val"],
            "date_min": result["date_min"],
            "date_max": result["date_max"],
            "metrics":  result["metrics"],
        }
        print(f"    Saved -> {path}")

    # Save metadata JSON
    meta_path = os.path.join(MODELS_DIR, "forecast_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(all_metadata, f, ensure_ascii=False, indent=2)
    print(f"\nMetadata saved -> {meta_path}")
    print(f"\nDone! {len(all_metadata)} models trained.")


if __name__ == "__main__":
    main()