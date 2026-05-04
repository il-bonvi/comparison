"""
FIT TOOLS — FastAPI app unificata
Serve la single-page app con tab Comparison + Race Replay
"""

import logging
import os
import tempfile
from contextlib import asynccontextmanager
from typing import Any, Dict

import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse

from utils.fit_parser import parse_fit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# LIFESPAN  (sostituisce @app.on_event deprecato)
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FIT Tools avviato — http://localhost:8002")
    yield
    logger.info("FIT Tools shutdown")


app = FastAPI(
    title="FIT Tools",
    description="Comparison & Race Replay for cycling FIT files",
    version="2.1.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────
# UTILITY — unico parser FIT → stream dict
# ─────────────────────────────────────────────

def _parse_fit_stream(file_bytes: bytes) -> Dict[str, Any]:
    """
    Converte bytes di un file FIT in un dizionario stream pronto per il frontend.

    Questa è l'unica implementazione del parsing FIT nell'applicazione.
    Tutti gli endpoint che necessitano di dati GPS/power/hr usano questa funzione.

    Returns:
        dict con chiavi: lat, lon, alt, distance_m, time_sec,
                         power, hr, cadence, speed, n
    """
    with tempfile.NamedTemporaryFile(suffix=".fit", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        df = parse_fit(tmp_path)
    finally:
        # Il finally garantisce la rimozione anche in caso di eccezione
        os.unlink(tmp_path)

    # Filtra punti GPS non validi
    lat = df["position_lat"].values
    lon = df["position_long"].values
    nan_mask   = (~np.isnan(lat)) & (~np.isnan(lon))
    range_mask = (np.abs(lat) <= 90) & (np.abs(lon) <= 180)
    zero_mask  = ~((np.abs(lat) < 1e-9) & (np.abs(lon) < 1e-9))
    valid = nan_mask & range_mask & zero_mask

    df_geo = df.loc[valid].copy().reset_index(drop=True)

    if df_geo.empty:
        logger.warning("Nessun punto GPS valido trovato nel file FIT")

    # Speed in km/h ricavata da distance + time (delta campione)
    dist_m   = df_geo["distance"].tolist()
    time_sec = df_geo["time_sec"].tolist()
    speed = [0.0]
    for i in range(1, len(dist_m)):
        dt = time_sec[i] - time_sec[i - 1]
        dd = dist_m[i] - dist_m[i - 1]
        speed.append((dd / 1000.0) / (dt / 3600.0) if dt > 0 else 0.0)

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
    """Serve la single-page app unificata."""
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
async def upload(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
):
    """
    Unico endpoint di upload — usato da entrambe le tab (Comparison e Race Replay).

    Accetta due file FIT, li parsa e restituisce gli stream JSON pronti per il frontend.
    """
    try:
        stream_a = _parse_fit_stream(await file_a.read())
        stream_b = _parse_fit_stream(await file_b.read())
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Errore imprevisto nel parsing FIT: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Errore interno nel parsing del file")

    return JSONResponse({
        "success":    True,
        "stream_a":   stream_a,
        "stream_b":   stream_b,
        "filename_a": file_a.filename,
        "filename_b": file_b.filename,
    })


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)