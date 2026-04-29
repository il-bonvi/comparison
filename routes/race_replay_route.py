"""
Race Replay route — confronto animato gap tra due atleti
Nuova funzionalità indipendente dalla Comparison esistente
"""

import logging
import os
from typing import Dict, Any

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/replay", tags=["race_replay"])


def setup_race_replay_router():
    """Nothing to setup — route is stateless"""
    pass


@router.get("/", response_class=HTMLResponse)
async def race_replay_page():
    """Serve la pagina Race Replay"""
    html = _load_html()
    return HTMLResponse(content=html)


@router.post("/api/upload")
async def upload_replay_files(file_a: UploadFile = File(...), file_b: UploadFile = File(...)):
    """Shared upload endpoint — reuses the same logic as comparison"""
    from routes.comparison import _parse_fit_for_comparison
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
        logger.error(f"Race replay upload error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


def _load_html() -> str:
    try:
        from config import get_maptiler_key
        key = get_maptiler_key()
    except Exception:
        key = ""

    template_path = os.path.join(os.path.dirname(__file__), "templates", "race_replay.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
    return html.replace("{maptiler_key}", key)
