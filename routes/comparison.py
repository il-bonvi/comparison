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
    
    # Prova a ottenere la MapTiler key da config.py
    try:
        from config import get_maptiler_key
        maptiler_key = get_maptiler_key()
    except Exception:
        maptiler_key = ""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Confronto Tracce FIT</title>
<meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no"/>
<script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
<link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0f172a; color:#e2e8f0; font-family:'Inter',system-ui,sans-serif; height:100vh; display:flex; flex-direction:column; overflow:hidden; }}

/* HEADER */
#header {{
  background:linear-gradient(135deg,#1e293b,#0f172a); padding:12px 20px;
  border-bottom:1px solid #334155; flex-shrink:0;
}}
#header h1 {{ color:#60a5fa; margin-bottom:4px; font-size:1.6rem; }}
#header p {{ color:#94a3b8; font-size:0.85rem; }}

/* TOP BAR */
#topbar {{
  display:flex; align-items:center; gap:12px; padding:10px 16px;
  background:#1e293b; border-bottom:1px solid #334155; flex-shrink:0; flex-wrap:wrap;
}}
#topbar label {{ font-size:0.78rem; color:#94a3b8; white-space:nowrap; }}
#topbar input[type=number] {{
  width:72px; padding:4px 8px; background:#0f172a; border:1px solid #475569;
  border-radius:5px; color:#e2e8f0; font-size:0.85rem;
}}
#topbar input[type=file] {{ display:none; }}
.btn {{
  padding:6px 14px; border:none; border-radius:6px; cursor:pointer;
  font-size:0.82rem; font-weight:600; transition:all .2s; white-space:nowrap;
}}
.btn-primary {{ background:linear-gradient(135deg,#3b82f6,#1d4ed8); color:#fff; }}
.btn-primary:hover {{ background:linear-gradient(135deg,#2563eb,#1e3a8a); transform:translateY(-1px); }}
.btn-success {{ background:linear-gradient(135deg,#10b981,#059669); color:#fff; }}
.btn-success:hover {{ transform:translateY(-1px); }}
.btn-warning {{ background:linear-gradient(135deg,#f59e0b,#d97706); color:#fff; }}
.btn-warning:hover {{ transform:translateY(-1px); }}
.btn-danger  {{ background:linear-gradient(135deg,#ef4444,#dc2626); color:#fff; }}
.badge {{
  display:inline-flex; align-items:center; gap:5px; padding:4px 10px;
  border-radius:20px; font-size:0.75rem; font-weight:600;
}}
.badge-a {{ background:rgba(59,130,246,.25); color:#60a5fa; border:1px solid #3b82f6; }}
.badge-b {{ background:rgba(249,115,22,.25); color:#fb923c; border:1px solid #f97316; }}
.badge-none {{ background:rgba(100,116,139,.2); color:#94a3b8; border:1px solid #475569; }}
#status-msg {{ font-size:0.78rem; color:#94a3b8; margin-left:auto; }}

/* UPLOAD AREA */
#upload-area {{
  padding:40px; text-align:center; background:rgba(0,0,0,.5);
  border:2px dashed #334155; border-radius:12px; margin:20px;
  flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center;
  min-height:0;
}}
#upload-area.ready {{ border-color:#22c55e; background:rgba(34,197,94,.05); }}
.upload-input {{ display:none; }}
.upload-label {{
  display:inline-block; padding:12px 24px; background:linear-gradient(135deg,#3b82f6,#2563eb);
  color:#fff; border-radius:8px; cursor:pointer; font-weight:600; margin:10px;
  transition:all .3s;
}}
.upload-label:hover {{ background:linear-gradient(135deg,#2563eb,#1d4ed8); transform:translateY(-2px); }}
.upload-info {{ color:#94a3b8; font-size:0.9rem; margin-top:10px; }}
.file-display {{ color:#22c55e; font-weight:600; margin-top:8px; }}

/* MAIN LAYOUT */
#main {{ flex:1; display:flex; flex-direction:column; overflow:hidden; display:none; }}
#map {{ flex:1; min-height:0; }}

/* CHART */
#chart-panel {{
  height:180px; background:#1e293b; border-top:2px solid #334155;
  flex-shrink:0; position:relative;
}}
#chart-resize {{
  position:absolute; top:0; left:0; right:0; height:6px;
  cursor:ns-resize; background:linear-gradient(#475569,transparent);
  z-index:10;
}}
#elevation-chart {{ width:100%; height:100%; padding-top:6px; }}

/* LEGEND */
#legend {{
  position:absolute; top:16px; right:16px; background:rgba(15,23,42,.9);
  border:1px solid #334155; border-radius:10px; padding:12px 16px; z-index:100;
  min-width:180px; backdrop-filter:blur(8px);
}}
#legend h4 {{ font-size:0.8rem; color:#94a3b8; margin-bottom:8px; text-transform:uppercase; letter-spacing:.05em; }}
.legend-item {{ display:flex; align-items:center; gap:8px; margin-bottom:5px; font-size:0.8rem; }}
.legend-line {{ width:30px; height:4px; border-radius:2px; flex-shrink:0; }}

/* CONTROLS */
#map-controls {{
  position:absolute; bottom:200px; left:16px; display:flex; flex-direction:column; gap:6px; z-index:100;
}}
#map-controls button {{
  padding:8px 12px; background:rgba(15,23,42,.9); border:1px solid #334155;
  border-radius:6px; color:#e2e8f0; cursor:pointer; font-size:0.8rem; transition:all .2s;
}}
#map-controls button:hover {{ background:rgba(30,41,59,.95); border-color:#60a5fa; }}
#style-select {{
  padding:6px 8px; background:rgba(15,23,42,.9); border:1px solid #334155;
  border-radius:6px; color:#e2e8f0; font-size:0.8rem; cursor:pointer;
}}

/* ARRIVAL MARKER tooltip */
#arrival-tip {{
  position:absolute; bottom:200px; right:16px; background:rgba(15,23,42,.92);
  border:1px solid #334155; border-radius:8px; padding:10px 14px; z-index:100;
  font-size:0.8rem; max-width:240px; display:none;
}}
#arrival-tip.visible {{ display:block; }}

/* LOADING */
#loading-overlay {{
  position:fixed; inset:0; background:rgba(15,23,42,.8); z-index:999;
  display:flex; align-items:center; justify-content:center; flex-direction:column; gap:12px;
  display:none;
}}
#loading-overlay.visible {{ display:flex; }}
.spinner {{
  width:48px; height:48px; border:4px solid #334155; border-top-color:#3b82f6;
  border-radius:50%; animation:spin .8s linear infinite;
}}
@keyframes spin {{ to {{ transform:rotate(360deg); }} }}

/* TOOLTIP */
#hover-tip {{
  position:absolute; background:rgba(15,23,42,.95); border:1px solid #475569;
  border-radius:6px; padding:8px 12px; font-size:0.75rem; pointer-events:none;
  z-index:200; display:none; line-height:1.6;
}}
</style>
</head>
<body>

<!-- HEADER -->
<div id="header">
  <h1>⚔️ Comparison FIT Traces</h1>
  <p>Confronta due tracce FIT con overlay interattivo su mappa 3D</p>
</div>

<!-- LOADING -->
<div id="loading-overlay">
  <div class="spinner"></div>
  <div id="loading-text" style="color:#94a3b8;font-size:.9rem;">Caricamento...</div>
</div>

<!-- UPLOAD SECTION -->
<div id="upload-area">
  <div style="font-size:3rem;margin-bottom:20px;">📁</div>
  <h2 style="color:#e2e8f0;margin-bottom:10px;">Carica due file FIT</h2>
  <p class="upload-info">Seleziona due tracce per confrontare performance e percorso</p>
  
  <input type="file" id="file-a-input" class="upload-input" accept=".fit"/>
  <input type="file" id="file-b-input" class="upload-input" accept=".fit"/>
  
  <label for="file-a-input" class="upload-label">📂 Seleziona FIT A</label>
  <label for="file-b-input" class="upload-label">📂 Seleziona FIT B</label>
  
  <div class="file-display" id="file-display" style="display:none;"></div>
  
  <button class="btn btn-success" onclick="uploadFiles()" id="btn-upload" disabled style="margin-top:20px;">
    🚀 Carica e Confronta
  </button>
</div>

<!-- MAIN APP (hidden until upload) -->
<div id="main">
  <div id="topbar">
    <span class="badge badge-a">🔵 <span id="label-a">Atleta A</span></span>
    <span class="badge badge-b">🟠 <span id="label-b">Atleta B</span></span>
    
    <div style="width:1px;height:24px;background:#334155;margin:0 4px;flex-shrink:0;"></div>

    <label>Ultimi km:</label>
    <input type="number" id="input-km" value="3" min="0.1" max="100" step="0.1"/>

    <label>Sezione (sec):</label>
    <input type="number" id="input-sec" value="20" min="5" max="300" step="5"/>

    <button class="btn btn-success" id="btn-set-arrival" onclick="startSetArrival()">
      🏁 Segna Arrivo
    </button>
    <button class="btn btn-warning" id="btn-analyze" onclick="runAnalysis()">
      🔍 Analizza Sezioni
    </button>
    <button class="btn btn-danger" onclick="resetApp()" style="margin-left:auto;">
      🔄 Reset
    </button>

    <span id="status-msg">Segna il punto di arrivo sulla mappa</span>
  </div>

  <div style="position:relative;flex:1;min-height:0;display:flex;flex-direction:column;">
    <div id="map" style="flex:1;min-height:0;"></div>

    <div id="legend">
      <h4>Legenda</h4>
      <div class="legend-item">
        <div class="legend-line" style="background:#3b82f6;"></div>
        <span id="legend-a">Atleta A</span>
      </div>
      <div class="legend-item">
        <div class="legend-line" style="background:#f97316;"></div>
        <span id="legend-b">Atleta B</span>
      </div>
    </div>

    <div id="map-controls">
      <select id="style-select" onchange="changeStyle(this.value)">
        <option value="outdoor">Outdoor</option>
        <option value="streets">Streets</option>
        <option value="topo">Topo</option>
        <option value="satellite">Satellite</option>
        <option value="dark">Dark</option>
      </select>
      <button onclick="resetView()">🎯 Reset View</button>
      <button onclick="toggle3D()">🏔️ 3D</button>
    </div>

    <div id="arrival-tip">
      🏁 Clicca sulla mappa per segnare il <strong>punto di arrivo</strong>
    </div>

    <div id="hover-tip"></div>

    <div id="chart-panel">
      <div id="chart-resize"></div>
      <div id="elevation-chart"></div>
    </div>
  </div>
</div>

<script>
// ============================================================================
// DATA & STATE
// ============================================================================
const MAPTILER_KEY = '{maptiler_key}';

let streamA = null;
let streamB = null;
let filenameA = 'Atleta A';
let filenameB = 'Atleta B';

let arrivalMode = false;
let arrivalA = null;
let arrivalB = null;
let map = null;
let elevationChart = null;
let analysisLayers = [];
let arrivalMarker = null;
let is3D = true;

const STYLES = {{
  outdoor:   `https://api.maptiler.com/maps/outdoor-v2/style.json?key=${{MAPTILER_KEY}}`,
  streets:   `https://api.maptiler.com/maps/streets-v2/style.json?key=${{MAPTILER_KEY}}`,
  topo:      `https://api.maptiler.com/maps/topo-v2/style.json?key=${{MAPTILER_KEY}}`,
  satellite: `https://api.maptiler.com/maps/satellite/style.json?key=${{MAPTILER_KEY}}`,
  dark:      `https://api.maptiler.com/maps/dataviz-dark/style.json?key=${{MAPTILER_KEY}}`,
}};

const SECTION_PALETTE = [
  '#ef4444','#f97316','#f59e0b','#eab308','#84cc16',
  '#22c55e','#10b981','#14b8a6','#06b6d4','#3b82f6',
  '#8b5cf6','#a855f7','#ec4899','#f43f5e','#fb923c',
  '#fbbf24','#a3e635','#34d399','#38bdf8','#818cf8',
];

// ============================================================================
// UPLOAD
// ============================================================================
const fileAInput = document.getElementById('file-a-input');
const fileBInput = document.getElementById('file-b-input');
const fileDisplay = document.getElementById('file-display');
const btnUpload = document.getElementById('btn-upload');

fileAInput.addEventListener('change', updateFileDisplay);
fileBInput.addEventListener('change', updateFileDisplay);

function updateFileDisplay() {{
  const fileA = fileAInput.files[0];
  const fileB = fileBInput.files[0];
  
  if (fileA && fileB) {{
    fileDisplay.textContent = `✅ ${{fileA.name}} + ${{fileB.name}}`;
    fileDisplay.style.display = 'block';
    btnUpload.disabled = false;
  }} else {{
    fileDisplay.style.display = 'none';
    btnUpload.disabled = true;
  }}
}}

async function uploadFiles() {{
  const fileA = fileAInput.files[0];
  const fileB = fileBInput.files[0];
  
  if (!fileA || !fileB) return;
  
  showLoading('Parsing file FIT...');
  
  try {{
    const fd = new FormData();
    fd.append('file_a', fileA);
    fd.append('file_b', fileB);
    
    const resp = await fetch('/api/upload', {{ method:'POST', body:fd }});
    const data = await resp.json();
    
    if (!data.success) throw new Error(data.detail || 'Errore');
    
    streamA = data.stream_a;
    streamB = data.stream_b;
    filenameA = data.filename_a || 'Atleta A';
    filenameB = data.filename_b || 'Atleta B';
    
    document.getElementById('file-a-input').disabled = true;
    document.getElementById('file-b-input').disabled = true;
    btnUpload.disabled = true;
    
    // Hide upload, show main
    document.getElementById('upload-area').style.display = 'none';
    document.getElementById('main').style.display = 'flex';
    
    document.getElementById('label-a').textContent = filenameA.slice(0,20);
    document.getElementById('label-b').textContent = filenameB.slice(0,20);
    document.getElementById('legend-a').textContent = filenameA.slice(0,18);
    document.getElementById('legend-b').textContent = filenameB.slice(0,18);
    
    initMap();
    hideLoading();
  }} catch(err) {{
    hideLoading();
    alert('Errore: ' + err.message);
  }}
}}

// ============================================================================
// MAP INIT
// ============================================================================
function initMap() {{
  const center = computeCenter(streamA);
  map = new maplibregl.Map({{
    container: 'map',
    style: STYLES.streets,
    center: [center.lon, center.lat],
    zoom: 13,
    pitch: 45,
    bearing: 0,
    antialias: true,
  }});

  map.addControl(new maplibregl.NavigationControl(), 'top-left');

  map.on('load', () => {{
    addTerrain();
    drawTraceA();
    drawTraceB();
    fitToBounds(streamA, streamB);
    initElevationChart();
  }});

  map.on('click', handleMapClick);
  map.on('mousemove', handleMapHover);
  map.on('mouseleave', () => {{ document.getElementById('hover-tip').style.display='none'; }});
}}

function computeCenter(stream) {{
  const n = stream.lat.length;
  let sumLat = 0, sumLon = 0;
  for (let i = 0; i < n; i++) {{ sumLat += stream.lat[i]; sumLon += stream.lon[i]; }}
  return {{ lat: sumLat/n, lon: sumLon/n }};
}}

function addTerrain() {{
  if (!MAPTILER_KEY) return;
  try {{
    if (!map.getSource('terrain-dem')) {{
      map.addSource('terrain-dem', {{
        type: 'raster-dem',
        url: `https://api.maptiler.com/tiles/terrain-rgb/tiles.json?key=${{MAPTILER_KEY}}`,
        tileSize: 256,
      }});
    }}
    map.setTerrain({{ source: 'terrain-dem', exaggeration: 1.5 }});
  }} catch(e) {{ console.warn('Terrain:', e); }}
}}

function streamToGeoJSON(stream, color) {{
  const coords = stream.lat.map((lat,i) => [stream.lon[i], lat, (stream.alt[i]||0)]);
  return {{
    type: 'FeatureCollection',
    features: [{{
      type: 'Feature',
      geometry: {{ type:'LineString', coordinates:coords }},
      properties: {{ color }}
    }}]
  }};
}}

function drawTraceA() {{
  const geojson = streamToGeoJSON(streamA, '#3b82f6');
  if (map.getSource('trace-a')) {{
    map.getSource('trace-a').setData(geojson);
  }} else {{
    map.addSource('trace-a', {{ type:'geojson', data:geojson }});
    map.addLayer({{
      id:'trace-a-line', type:'line', source:'trace-a',
      paint:{{ 'line-color':'#3b82f6', 'line-width':3, 'line-opacity':0.85 }}
    }});
  }}
}}

function drawTraceB() {{
  if (!streamB) return;
  const geojson = streamToGeoJSON(streamB, '#f97316');
  if (map.getSource('trace-b')) {{
    map.getSource('trace-b').setData(geojson);
  }} else {{
    map.addSource('trace-b', {{ type:'geojson', data:geojson }});
    map.addLayer({{
      id:'trace-b-line', type:'line', source:'trace-b',
      paint:{{ 'line-color':'#f97316', 'line-width':3, 'line-opacity':0.85 }}
    }});
  }}
}}

function fitToBounds(streamA_, streamB_) {{
  let lats = [...streamA_.lat];
  let lons = [...streamA_.lon];
  if (streamB_) {{ lats = lats.concat(streamB_.lat); lons = lons.concat(streamB_.lon); }}
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLon = Math.min(...lons), maxLon = Math.max(...lons);
  map.fitBounds([[minLon, minLat],[maxLon, maxLat]], {{ padding:60, duration:800 }});
}}

// ============================================================================
// ARRIVAL POINT
// ============================================================================
function startSetArrival() {{
  arrivalMode = true;
  document.getElementById('arrival-tip').classList.add('visible');
  document.getElementById('status-msg').textContent = 'Clicca sulla mappa...';
  map.getCanvas().style.cursor = 'crosshair';
}}

function handleMapClick(e) {{
  if (!arrivalMode) return;
  arrivalMode = false;
  map.getCanvas().style.cursor = '';
  document.getElementById('arrival-tip').classList.remove('visible');

  const clickLat = e.lngLat.lat;
  const clickLon = e.lngLat.lng;

  arrivalA = nearestIndex(streamA, clickLat, clickLon);
  arrivalB = nearestIndex(streamB, clickLat, clickLon);

  if (arrivalMarker) arrivalMarker.remove();
  const el = document.createElement('div');
  el.innerHTML = '🏁';
  el.style.cssText = 'font-size:28px;';
  arrivalMarker = new maplibregl.Marker({{ element:el }})
    .setLngLat([clickLon, clickLat])
    .addTo(map);

  document.getElementById('status-msg').textContent = 'Arrivo segnato! Clicca "Analizza Sezioni"';
}}

function nearestIndex(stream, lat, lon) {{
  // Find the LAST (latest in time) occurrence of a point near the clicked location
  // This is critical for multi-lap routes where the same area is visited multiple times
  
  const DISTANCE_THRESHOLD = 0.001; // ~100m in degrees
  let candidates = [];
  
  for (let i = 0; i < stream.lat.length; i++) {{
    const dlat = stream.lat[i] - lat;
    const dlon = stream.lon[i] - lon;
    const d = Math.sqrt(dlat*dlat + dlon*dlon);
    
    if (d < DISTANCE_THRESHOLD) {{
      candidates.push(i);
    }}
  }}
  
  // If found points within threshold, return the LAST one (highest index = latest in time)
  if (candidates.length > 0) {{
    return candidates[candidates.length - 1];
  }}
  
  // Fallback: find nearest point if none within threshold
  let best = 0, bestD = Infinity;
  for (let i = 0; i < stream.lat.length; i++) {{
    const dlat = stream.lat[i] - lat;
    const dlon = stream.lon[i] - lon;
    const d = dlat*dlat + dlon*dlon;
    if (d < bestD) {{ bestD = d; best = i; }}
  }}
  return best;
}}

// ============================================================================
// ANALYSIS
// ============================================================================
function runAnalysis() {{
  if (arrivalA === null || arrivalB === null) {{
    alert('Segna il punto di arrivo prima');
    return;
  }}
  
  const km = parseFloat(document.getElementById('input-km').value) || 3;
  const secInterval = parseInt(document.getElementById('input-sec').value) || 20;

  showLoading('Calcolo sezioni...');
  setTimeout(() => {{
    try {{
      clearAnalysisLayers();
      hideFullTraces();
      const sectionsA = buildSections(streamA, arrivalA, km * 1000, secInterval);
      const sectionsB = buildSections(streamB, arrivalB, km * 1000, secInterval);
      drawSections(sectionsA, sectionsB);
      drawElevationSections(sectionsA, sectionsB, secInterval);
      buildAndShowPowerComparison(km);
      document.getElementById('status-msg').textContent = `Analisi: ${{sectionsA.length}} sezioni da ${{secInterval}}s`;
    }} catch(err) {{
      console.error(err);
      alert('Errore: ' + err.message);
    }} finally {{
      hideLoading();
    }}
  }}, 50);
}}

function buildSections(stream, arrivalIdx, distanceM, secInterval) {{
  if (arrivalIdx === null || arrivalIdx === undefined) arrivalIdx = stream.lat.length - 1;

  const dist = stream.distance_m;
  const arrivalDist = dist[arrivalIdx];
  const startDist = Math.max(0, arrivalDist - distanceM);

  let startIdx = 0;
  for (let i = 0; i <= arrivalIdx; i++) {{
    if (dist[i] >= startDist) {{ startIdx = i; break; }}
  }}

  const time = stream.time_sec;
  const sections = [];
  let i = startIdx;
  let sectionIdx = 0;

  while (i <= arrivalIdx) {{
    const tStart = time[i];
    const tEnd = tStart + secInterval;

    const pts = [];
    let j = i;
    while (j <= arrivalIdx && time[j] < tEnd) {{
      pts.push(j);
      j++;
    }}

    if (pts.length < 2) {{ i = j; sectionIdx++; continue; }}

    let sumPow = 0, sumHr = 0;
    for (const p of pts) {{
      sumPow += (stream.power[p] || 0);
      sumHr  += (stream.hr[p] || 0);
    }}

    sections.push({{
      coords: pts.map(p => [stream.lon[p], stream.lat[p], stream.alt[p]||0]),
      sectionIdx,
      avgPower: sumPow / pts.length,
      avgHr: sumHr / pts.length,
      startDist: dist[pts[0]],
      endDist: dist[pts[pts.length-1]],
    }});

    i = j;
    sectionIdx++;
  }}

  return sections;
}}

function drawSections(sectionsA, sectionsB) {{
  const allSections = [
    ...sectionsA.map(s => ({{...s, athlete:'a'}})),
    ...sectionsB.map(s => ({{...s, athlete:'b'}})),
  ];

  allSections.forEach((sec, i) => {{
    const color = SECTION_PALETTE[sec.sectionIdx % SECTION_PALETTE.length];
    const layerId = `sec-${{sec.athlete}}-${{sec.sectionIdx}}-${{i}}`;
    const sourceId = `src-${{layerId}}`;

    const geojson = {{
      type: 'Feature',
      geometry: {{ type: 'LineString', coordinates: sec.coords }},
      properties: {{
        sectionIdx: sec.sectionIdx,
        athlete: sec.athlete,
        avgPower: Math.round(sec.avgPower),
        avgHr: Math.round(sec.avgHr),
        startDist: (sec.startDist/1000).toFixed(2),
        endDist: (sec.endDist/1000).toFixed(2),
      }}
    }};

    map.addSource(sourceId, {{ type:'geojson', data:geojson }});
    map.addLayer({{
      id: layerId,
      type: 'line',
      source: sourceId,
      paint: {{
        'line-color': color,
        'line-width': sec.athlete === 'a' ? 5 : 4,
        'line-opacity': sec.athlete === 'a' ? 0.95 : 0.85,
        'line-dasharray': sec.athlete === 'b' ? [3,1.5] : [1],
      }}
    }});

    analysisLayers.push({{ layerId, sourceId }});
  }});
}}

function clearAnalysisLayers() {{
  analysisLayers.forEach(({{ layerId, sourceId }}) => {{
    if (map.getLayer(layerId)) map.removeLayer(layerId);
    if (map.getSource(sourceId)) map.removeSource(sourceId);
  }});
  analysisLayers = [];
}}

function hideFullTraces() {{
  if (map.getLayer('trace-a-line')) map.setLayoutProperty('trace-a-line', 'visibility', 'none');
  if (map.getLayer('trace-b-line')) map.setLayoutProperty('trace-b-line', 'visibility', 'none');
}}

function showFullTraces() {{
  if (map.getLayer('trace-a-line')) map.setLayoutProperty('trace-a-line', 'visibility', 'visible');
  if (map.getLayer('trace-b-line')) map.setLayoutProperty('trace-b-line', 'visibility', 'visible');
}}

// ============================================================================
// ELEVATION CHART
// ============================================================================
function initElevationChart() {{
  const dom = document.getElementById('elevation-chart');
  elevationChart = echarts.init(dom, 'dark');
  updateElevationChart();

  const handle = document.getElementById('chart-resize');
  let dragging = false, startY = 0, startH = 0;
  handle.addEventListener('mousedown', e => {{
    dragging = true; startY = e.clientY;
    startH = document.getElementById('chart-panel').offsetHeight;
    e.preventDefault();
  }});
  document.addEventListener('mousemove', e => {{
    if (!dragging) return;
    const delta = startY - e.clientY;
    const newH = Math.max(100, Math.min(500, startH + delta));
    document.getElementById('chart-panel').style.height = newH + 'px';
    elevationChart.resize();
  }});
  document.addEventListener('mouseup', () => {{ dragging = false; }});
  window.addEventListener('resize', () => {{ if (elevationChart) elevationChart.resize(); }});
}}

function updateElevationChart() {{
  if (!elevationChart) return;

  const series = [];

  series.push({{
    name: filenameA.slice(0,15),
    type: 'line',
    data: streamA.distance_m.map((d,i) => [d/1000, streamA.alt[i]||0]),
    lineStyle: {{ color:'#3b82f6', width:2, opacity:0.9 }},
    areaStyle: {{ color:'rgba(59,130,246,.12)' }},
    showSymbol: false,
    smooth: true,
  }});

  series.push({{
    name: filenameB.slice(0,15),
    type: 'line',
    data: streamB.distance_m.map((d,i) => [d/1000, streamB.alt[i]||0]),
    lineStyle: {{ color:'#f97316', width:2, opacity:0.9 }},
    areaStyle: {{ color:'rgba(249,115,22,.1)' }},
    showSymbol: false,
    smooth: true,
  }});

  elevationChart.setOption({{
    backgroundColor: 'transparent',
    animation: false,
    legend: {{ show:true, textStyle:{{ color:'#94a3b8', fontSize:10 }}, top:4 }},
    grid: {{ left:50, right:20, top:30, bottom:30 }},
    xAxis: {{ type:'value', name:'km', nameTextStyle:{{ color:'#64748b' }}, axisLabel:{{ color:'#94a3b8', formatter: v => v.toFixed(1) }}, splitLine:{{ lineStyle:{{ color:'#1e293b' }} }} }},
    yAxis: {{ type:'value', name:'m', nameTextStyle:{{ color:'#64748b' }}, axisLabel:{{ color:'#94a3b8' }}, splitLine:{{ lineStyle:{{ color:'#1e293b' }} }} }},
    tooltip: {{
      trigger:'axis', backgroundColor:'rgba(15,23,42,.95)', borderColor:'#334155',
      textStyle:{{ color:'#e2e8f0', fontSize:11 }},
      formatter: params => {{
        let s = `<b>${{params[0].data[0].toFixed(2)}} km</b><br/>`;
        params.forEach(p => {{ s += `${{p.marker}} ${{p.seriesName}}: ${{Math.round(p.data[1])}}m<br/>`; }});
        return s;
      }}
    }},
    series,
  }}, true);
}}

function drawElevationSections(sectionsA, sectionsB, secInterval) {{
  const markAreaDataA = sectionsA.map(s => [
    {{ xAxis: s.startDist/1000, itemStyle:{{ color: SECTION_PALETTE[s.sectionIdx%SECTION_PALETTE.length], opacity:0.15 }} }},
    {{ xAxis: s.endDist/1000 }}
  ]);

  const opt = elevationChart.getOption();
  if (opt.series && opt.series[0]) {{
    opt.series[0].markArea = {{ silent:false, data: markAreaDataA }};
  }}
  if (opt.series && opt.series[1]) {{
    const markAreaDataB = sectionsB.map(s => [
      {{ xAxis: s.startDist/1000, itemStyle:{{ color: SECTION_PALETTE[s.sectionIdx%SECTION_PALETTE.length], opacity:0.08 }} }},
      {{ xAxis: s.endDist/1000 }}
    ]);
    opt.series[1].markArea = {{ silent:false, data: markAreaDataB }};
  }}
  elevationChart.setOption(opt, {{ lazyUpdate:true }});
}}

// ============================================================================
// POWER & HR ALIGNMENT & COMPARISON
// ============================================================================
function buildPowerAlignment(streamA, streamB, arrivalA, arrivalB, kmWindow) {{
  // Distance window: from (distance - kmWindow) to distance at arrival
  const distA = streamA.distance_m;
  const distB = streamB.distance_m;
  
  const arrivalDistA = distA[arrivalA];
  const arrivalDistB = distB[arrivalB];
  
  const startDistA = Math.max(0, arrivalDistA - kmWindow * 1000);
  const startDistB = Math.max(0, arrivalDistB - kmWindow * 1000);
  
  // Find index ranges
  let startIdxA = 0, endIdxA = arrivalA;
  let startIdxB = 0, endIdxB = arrivalB;
  
  for (let i = 0; i <= arrivalA; i++) {{
    if (distA[i] >= startDistA) {{ startIdxA = i; break; }}
  }}
  for (let i = 0; i <= arrivalB; i++) {{
    if (distB[i] >= startDistB) {{ startIdxB = i; break; }}
  }}
  
  // Build alignment data: distance-based matching
  // We'll create data points at 10m intervals
  const interval = 10; // 10 meters
  const alignedData = [];
  
  let maxDist = Math.max(
    distA[endIdxA] - distA[startIdxA],
    distB[endIdxB] - distB[startIdxB]
  );
  
  for (let d = 0; d <= maxDist; d += interval) {{
    const distFromStart_A = d;
    const distFromStart_B = d;
    
    // Find closest point in stream A
    let idxA = startIdxA;
    let bestDistDiffA = Math.abs(distA[idxA] - (distA[startIdxA] + distFromStart_A));
    for (let i = startIdxA; i <= endIdxA; i++) {{
      const diff = Math.abs(distA[i] - (distA[startIdxA] + distFromStart_A));
      if (diff < bestDistDiffA) {{ bestDistDiffA = diff; idxA = i; }}
    }}
    
    // Find closest point in stream B
    let idxB = startIdxB;
    let bestDistDiffB = Math.abs(distB[idxB] - (distB[startIdxB] + distFromStart_B));
    for (let i = startIdxB; i <= endIdxB; i++) {{
      const diff = Math.abs(distB[i] - (distB[startIdxB] + distFromStart_B));
      if (diff < bestDistDiffB) {{ bestDistDiffB = diff; idxB = i; }}
    }}
    
    alignedData.push({{
      distance: d,
      powerA: streamA.power[idxA] || 0,
      powerB: streamB.power[idxB] || 0,
      hrA: streamA.hr[idxA] || 0,
      hrB: streamB.hr[idxB] || 0,
    }});
  }}
  
  return alignedData;
}}

function buildAndShowPowerComparison(kmWindow) {{
  const alignment = buildPowerAlignment(streamA, streamB, arrivalA, arrivalB, kmWindow);
  
  if (!alignment || alignment.length === 0) {{
    console.warn('No alignment data');
    return;
  }}
  
  // Create separate charts for Power and HR
  const powerData = alignment.map(a => [a.distance/1000, a.powerA, a.powerB]);
  const hrData = alignment.map(a => [a.distance/1000, a.hrA, a.hrB]);
  
  const option = {{
    backgroundColor: 'transparent',
    animation: false,
    grid: [
      {{ left:50, right:20, top:20, bottom:20, height:'48%' }},
      {{ left:50, right:20, top:'58%', bottom:20, height:'40%' }}
    ],
    xAxis: [
      {{ type:'value', name:'km', gridIndex:0, position:'bottom', nameTextStyle:{{ color:'#64748b' }}, axisLabel:{{ color:'#94a3b8' }}, splitLine:{{ lineStyle:{{ color:'#1e293b' }} }} }},
      {{ type:'value', name:'km', gridIndex:1, nameTextStyle:{{ color:'#64748b' }}, axisLabel:{{ color:'#94a3b8' }}, splitLine:{{ lineStyle:{{ color:'#1e293b' }} }} }}
    ],
    yAxis: [
      {{ type:'value', name:'Watt', gridIndex:0, nameTextStyle:{{ color:'#64748b' }}, axisLabel:{{ color:'#94a3b8' }}, splitLine:{{ lineStyle:{{ color:'#1e293b' }} }} }},
      {{ type:'value', name:'bpm', gridIndex:1, nameTextStyle:{{ color:'#64748b' }}, axisLabel:{{ color:'#94a3b8' }}, splitLine:{{ lineStyle:{{ color:'#1e293b' }} }} }}
    ],
    legend: {{
      show: true,
      textStyle: {{ color:'#94a3b8', fontSize:9 }},
      top: 2,
      data: [`${{filenameA.slice(0,12)}} Power`, `${{filenameB.slice(0,12)}} Power`, `${{filenameA.slice(0,12)}} HR`, `${{filenameB.slice(0,12)}} HR`]
    }},
    series: [
      {{
        name: `${{filenameA.slice(0,12)}} Power`,
        type: 'line',
        data: alignment.map(a => [a.distance/1000, a.powerA]),
        xAxisIndex: 0, yAxisIndex: 0,
        lineStyle: {{ color:'#3b82f6', width:2 }},
        itemStyle: {{ color:'#3b82f6' }},
        showSymbol: false,
        smooth: 0.3,
      }},
      {{
        name: `${{filenameB.slice(0,12)}} Power`,
        type: 'line',
        data: alignment.map(a => [a.distance/1000, a.powerB]),
        xAxisIndex: 0, yAxisIndex: 0,
        lineStyle: {{ color:'#f97316', width:2, dashOffset: 0 }},
        itemStyle: {{ color:'#f97316' }},
        showSymbol: false,
        smooth: 0.3,
      }},
      {{
        name: `${{filenameA.slice(0,12)}} HR`,
        type: 'line',
        data: alignment.map(a => [a.distance/1000, a.hrA]),
        xAxisIndex: 1, yAxisIndex: 1,
        lineStyle: {{ color:'#60a5fa', width:1.5, dashArray: [4,2] }},
        itemStyle: {{ color:'#60a5fa' }},
        showSymbol: false,
        smooth: 0.3,
      }},
      {{
        name: `${{filenameB.slice(0,12)}} HR`,
        type: 'line',
        data: alignment.map(a => [a.distance/1000, a.hrB]),
        xAxisIndex: 1, yAxisIndex: 1,
        lineStyle: {{ color:'#fb923c', width:1.5, dashArray: [4,2] }},
        itemStyle: {{ color:'#fb923c' }},
        showSymbol: false,
        smooth: 0.3,
      }}
    ],
    tooltip: {{
      trigger: 'axis',
      backgroundColor: 'rgba(15,23,42,.95)',
      borderColor: '#334155',
      textStyle: {{ color:'#e2e8f0', fontSize:10 }},
      formatter: params => {{
        let html = `<b>${{params[0].data[0].toFixed(3)}} km</b><br/>`;
        params.forEach(p => {{
          const val = Math.round(p.data[1]);
          html += `<div style="color:${{p.color}}">■ ${{p.seriesName}}: <b>${{val}}</b></div>`;
        }});
        return html;
      }}
    }}
  }};
  
  elevationChart.setOption(option, true);
}}

// ============================================================================
// HOVER
// ============================================================================
function handleMapHover(e) {{
  const tip = document.getElementById('hover-tip');
  const features = map.queryRenderedFeatures(e.point, {{
    layers: analysisLayers.map(l => l.layerId)
  }});
  if (features.length > 0) {{
    const f = features[0].properties;
    const color = SECTION_PALETTE[f.sectionIdx % SECTION_PALETTE.length];
    tip.innerHTML = `
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
        <div style="width:12px;height:12px;border-radius:50%;background:${{color}};"></div>
        <b>Sezione ${{f.sectionIdx+1}}</b>
      </div>
      Potenza: <b>${{f.avgPower}}W</b><br/>
      HR: <b>${{f.avgHr}} bpm</b><br/>
      Km: ${{f.startDist}} → ${{f.endDist}}
    `;
    tip.style.display = 'block';
    tip.style.left = (e.point.x + 14) + 'px';
    tip.style.top  = (e.point.y - 20) + 'px';
    map.getCanvas().style.cursor = 'pointer';
  }} else {{
    tip.style.display = 'none';
    map.getCanvas().style.cursor = arrivalMode ? 'crosshair' : '';
  }}
}}

// ============================================================================
// CONTROLS
// ============================================================================
function changeStyle(key) {{
  const url = STYLES[key];
  if (!url) return;
  map.setStyle(url);
  map.once('styledata', () => {{
    addTerrain();
    drawTraceA();
    drawTraceB();
    const saved = [...analysisLayers];
    analysisLayers = [];
    saved.forEach(l => {{
      if (map.getLayer(l.layerId)) map.removeLayer(l.layerId);
      if (map.getSource(l.sourceId)) map.removeSource(l.sourceId);
    }});
  }});
}}

function resetView() {{
  fitToBounds(streamA, streamB);
  map.easeTo({{ pitch:45, bearing:0, duration:800 }});
}}

function toggle3D() {{
  is3D = !is3D;
  map.easeTo({{ pitch: is3D ? 45 : 0, duration:600 }});
}}

function resetApp() {{
  arrivalA = null; arrivalB = null;
  if (arrivalMarker) {{ arrivalMarker.remove(); arrivalMarker = null; }}
  clearAnalysisLayers();
  showFullTraces();
  document.getElementById('status-msg').textContent = 'Segna il punto di arrivo';
  updateElevationChart();
}}

// ============================================================================
// UTILITIES
// ============================================================================
function showLoading(msg) {{
  document.getElementById('loading-text').textContent = msg || 'Caricamento...';
  document.getElementById('loading-overlay').classList.add('visible');
}}

function hideLoading() {{
  document.getElementById('loading-overlay').classList.remove('visible');
}}
</script>
</body>
</html>
"""
