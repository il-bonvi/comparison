# ==============================================================================
# Copyright (c) 2026 Andrea Bonvicin - bFactor Project
# PROPRIETARY LICENSE - TUTTI I DIRITTI RISERVATI
# ==============================================================================

"""
Comparison route - Confronto due tracce FIT su mappa 3D con sezioni temporali
"""

import json
import logging
import uuid
import numpy as np
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse

from utils.effort_analyzer import parse_fit

logger = logging.getLogger(__name__)

# Shared sessions dict - set by setup_comparison_router()
_shared_sessions: Dict[str, Any] = {}

router = APIRouter()


def setup_comparison_router(sessions_dict: Dict[str, Any]):
    """Setup router with shared sessions"""
    global _shared_sessions
    _shared_sessions = sessions_dict


# ============================================================================
# UTILITY - Parse FIT to lightweight GPS+stream dict
# ============================================================================

def _parse_fit_for_comparison(file_bytes: bytes) -> Dict[str, Any]:
    """
    Parse FIT bytes -> dict con lat, lon, alt, distance_m, time_sec, power, hr, cadence.
    Riusa parse_fit della webapp ma accetta bytes direttamente.
    """
    import tempfile, os

    with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        df = parse_fit(tmp_path)
    finally:
        os.unlink(tmp_path)

    # Filter valid GPS
    lat = df["position_lat"].values
    lon = df["position_long"].values
    nan_mask = (~np.isnan(lat)) & (~np.isnan(lon))
    range_mask = (np.abs(lat) <= 90) & (np.abs(lon) <= 180)
    zero_mask = ~((np.abs(lat) < 1e-9) & (np.abs(lon) < 1e-9))
    valid = nan_mask & range_mask & zero_mask

    df_geo = df.loc[valid].copy().reset_index(drop=True)

    # Calculate speed in km/h from distance and time
    speed = []
    dist_m = df_geo["distance"].tolist()
    time_sec = df_geo["time_sec"].tolist()
    for i in range(len(dist_m)):
        if i == 0:
            speed.append(0)
        else:
            dt = time_sec[i] - time_sec[i-1]
            dd = dist_m[i] - dist_m[i-1]
            if dt > 0:
                speed.append((dd / 1000) / (dt / 3600))  # Convert to km/h
            else:
                speed.append(0)

    return {
        "lat": df_geo["position_lat"].tolist(),
        "lon": df_geo["position_long"].tolist(),
        "alt": df_geo["altitude"].tolist(),
        "distance_m": dist_m,
        "time_sec": time_sec,
        "power": df_geo["power"].tolist(),
        "hr": df_geo["heartrate"].tolist(),
        "cadence": df_geo["cadence"].tolist(),
        "speed": speed,
        "n": len(df_geo),
    }


def _session_to_stream(session: Dict[str, Any]) -> Dict[str, Any]:
    """Convert existing session df to stream dict"""
    df = session["df"]

    lat = df["position_lat"].values
    lon = df["position_long"].values
    nan_mask = (~np.isnan(lat)) & (~np.isnan(lon))
    range_mask = (np.abs(lat) <= 90) & (np.abs(lon) <= 180)
    zero_mask = ~((np.abs(lat) < 1e-9) & (np.abs(lon) < 1e-9))
    valid = nan_mask & range_mask & zero_mask

    df_geo = df.loc[valid].copy().reset_index(drop=True)

    return {
        "lat": df_geo["position_lat"].tolist(),
        "lon": df_geo["position_long"].tolist(),
        "alt": df_geo["altitude"].tolist(),
        "distance_m": df_geo["distance"].tolist(),
        "time_sec": df_geo["time_sec"].tolist(),
        "power": df_geo["power"].tolist(),
        "hr": df_geo["heartrate"].tolist(),
        "cadence": df_geo["cadence"].tolist(),
        "n": len(df_geo),
    }


# ============================================================================
# ENDPOINT - Upload file and generate comparison page
# ============================================================================

@router.get("/", response_class=HTMLResponse)
async def comparison_page():
    """Serve la pagina comparison con due file FIT da caricare"""
    html = _generate_comparison_html()
    return HTMLResponse(content=html)


@router.post("/api/upload")
async def upload_fit_files(file_a: UploadFile = File(...), file_b: UploadFile = File(...)):
    """Riceve due file FIT e restituisce gli stream JSON"""
    try:
        bytes_a = await file_a.read()
        bytes_b = await file_b.read()
        
        stream_a = _parse_fit_for_comparison(bytes_a)
        stream_b = _parse_fit_for_comparison(bytes_b)
        
        return JSONResponse({
            "success": True,
            "stream_a": stream_a,
            "stream_b": stream_b,
            "filename_a": file_a.filename,
            "filename_b": file_b.filename,
        })
    except Exception as e:
        logger.error(f"Error parsing FIT files: {e}")
        raise HTTPException(status_code=400, detail=f"Errore parsing file FIT: {str(e)}")


# ============================================================================
# HTML GENERATOR
# ============================================================================

def _generate_comparison_html() -> str:
    """Genera HTML completo per la app comparison standalone"""
    
    import os
    
    # Prova a ottenere la MapTiler key da config.py
    try:
        from config import get_maptiler_key
        maptiler_key = get_maptiler_key()
    except Exception:
        maptiler_key = ""

    # Leggi il template HTML da file
    template_path = os.path.join(os.path.dirname(__file__), "templates", "comparison.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html_template = f.read()
    
    # Sostituisci il placeholder con il valore reale della MapTiler key
    html = html_template.replace("{maptiler_key}", maptiler_key)
    
    return html



