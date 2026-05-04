"""
FIT parser — unica funzione usata dal backend.
"""

import logging
import os

import numpy as np
import pandas as pd
from fitparse import FitFile

logger = logging.getLogger(__name__)

# Specifica FIT/Garmin: divisore intero 2**31
SEMICIRCLES_TO_DEGREES = 180.0 / (2 ** 31)


def parse_fit(file_path: str) -> pd.DataFrame:
    """
    Legge un file FIT e restituisce un DataFrame con i record di telemetria.

    Colonne restituite:
        time, time_sec, power, altitude, distance, distance_km,
        heartrate, grade, cadence, position_lat, position_long

    Raises:
        FileNotFoundError: file non trovato
        ValueError: file corrotto, vuoto o senza timestamp validi
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File FIT non trovato: {file_path}")

    try:
        fit = FitFile(file_path)
    except Exception as e:
        raise ValueError(f"Errore apertura file FIT: {e}")

    rows = []
    try:
        for record in fit.get_messages("record"):
            v = {f.name: f.value for f in record}
            rows.append({
                "time":         v.get("timestamp"),
                "power":        v.get("power"),
                "altitude":     v.get("enhanced_altitude"),
                "distance":     v.get("distance"),
                "heartrate":    v.get("heart_rate"),
                "grade":        v.get("grade"),
                "cadence":      v.get("cadence"),
                "position_lat": v.get("position_lat"),
                "position_long":v.get("position_long"),
            })
    except Exception as e:
        raise ValueError(f"Errore durante parsing record: {e}")

    if not rows:
        raise ValueError("Nessun record trovato nel file FIT")

    df = pd.DataFrame(rows)

    # Timestamp
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    if df["time"].isna().all():
        raise ValueError("Nessun timestamp valido trovato")

    # Numerici semplici
    df["power"]     = pd.to_numeric(df["power"],     errors="coerce").fillna(0).astype(int)
    df["heartrate"] = pd.to_numeric(df["heartrate"], errors="coerce").fillna(0).astype(int)
    df["cadence"]   = pd.to_numeric(df["cadence"],   errors="coerce").fillna(0).astype(int)
    df["grade"]     = pd.to_numeric(df["grade"],     errors="coerce").fillna(0)

    # Distance — ffill con warning se ci sono gap
    df["distance"] = pd.to_numeric(df["distance"], errors="coerce")
    if df["distance"].isna().all():
        logger.warning("distance: tutti NaN, impostato a 0")
        df["distance"] = 0.0
    else:
        n_nan = int(df["distance"].isna().sum())
        if n_nan:
            logger.warning(f"distance: {n_nan}/{len(df)} campioni NaN interpolati via ffill")
        df["distance"] = df["distance"].ffill().fillna(0)

    # Altitude — stessa logica
    df["altitude"] = pd.to_numeric(df["altitude"], errors="coerce")
    if df["altitude"].isna().all():
        logger.warning("altitude: tutti NaN, impostato a 0")
        df["altitude"] = 0.0
    else:
        n_nan = int(df["altitude"].isna().sum())
        if n_nan:
            logger.warning(f"altitude: {n_nan}/{len(df)} campioni NaN interpolati via ffill")
        df["altitude"] = df["altitude"].ffill().fillna(0)

    # GPS — conversione semicircles se necessario
    df["position_lat"]  = pd.to_numeric(df["position_lat"],  errors="coerce")
    df["position_long"] = pd.to_numeric(df["position_long"], errors="coerce")
    if df["position_lat"].abs().max() > 180:
        df["position_lat"]  *= SEMICIRCLES_TO_DEGREES
        df["position_long"] *= SEMICIRCLES_TO_DEGREES
        logger.info("Coordinate GPS convertite da semicircles a gradi")

    df["time_sec"]    = (df["time"] - df["time"].iloc[0]).dt.total_seconds()
    df["distance_km"] = df["distance"] / 1000

    logger.info(f"parse_fit: {len(df)} record da {file_path}")
    return df