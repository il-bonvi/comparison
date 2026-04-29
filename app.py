"""
FIT TOOLS — FastAPI app unificata
Serve la single-page app con tab Comparison + Race Replay
"""

import logging
import os
import tempfile
from typing import Dict, Any

import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from utils.effort_analyzer import parse_fit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FIT Tools",
    description="Comparison & Race Replay for cycling FIT files",
    version="2.0.0"
)


# ─────────────────────────────────────────────
# UTILITY — parse FIT bytes → stream dict
# ─────────────────────────────────────────────

def _parse_fit_stream(file_bytes: bytes) -> Dict[str, Any]:
    with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        df = parse_fit(tmp_path)
    finally:
        os.unlink(tmp_path)

    lat = df["position_lat"].values
    lon = df["position_long"].values
    nan_mask  = (~np.isnan(lat)) & (~np.isnan(lon))
    range_mask = (np.abs(lat) <= 90) & (np.abs(lon) <= 180)
    zero_mask  = ~((np.abs(lat) < 1e-9) & (np.abs(lon) < 1e-9))
    valid = nan_mask & range_mask & zero_mask

    df_geo = df.loc[valid].copy().reset_index(drop=True)

    # Speed in km/h from distance + time
    dist_m  = df_geo["distance"].tolist()
    time_sec = df_geo["time_sec"].tolist()
    speed = [0.0]
    for i in range(1, len(dist_m)):
        dt = time_sec[i] - time_sec[i - 1]
        dd = dist_m[i] - dist_m[i - 1]
        speed.append((dd / 1000) / (dt / 3600) if dt > 0 else 0.0)

    return {
        "lat":        df_geo["position_lat"].tolist(),
        "lon":        df_geo["position_long"].tolist(),
        "alt":        df_geo["altitude"].tolist(),
        "distance_m": dist_m,
        "time_sec":   time_sec,
        "power":      df_geo["power"].tolist(),
        "hr":         df_geo["heartrate"].tolist(),
        "cadence":    df_geo["cadence"].tolist(),
        "speed":      speed,
        "n":          len(df_geo),
    }


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve la single-page app unificata"""
    template = os.path.join(
        os.path.dirname(__file__), "routes", "templates", "unified_app.html"
    )
    with open(template, encoding="utf-8") as f:
        html = f.read()
    try:
        from config import get_maptiler_key
        key = get_maptiler_key()
    except Exception:
        key = ""
    return HTMLResponse(content=html.replace("{maptiler_key}", key))


@app.post("/api/upload")
async def upload(file_a: UploadFile = File(...), file_b: UploadFile = File(...)):
    """Unico endpoint di upload — usato da entrambe le tab"""
    try:
        stream_a = _parse_fit_stream(await file_a.read())
        stream_b = _parse_fit_stream(await file_b.read())
        return JSONResponse({
            "success":    True,
            "stream_a":   stream_a,
            "stream_b":   stream_b,
            "filename_a": file_a.filename,
            "filename_b": file_b.filename,
        })
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("FIT Tools started — http://localhost:8002")


@app.on_event("shutdown")
async def shutdown():
    logger.info("FIT Tools shutdown")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
