import streamlit as st
import geopandas as gpd
import pandas as pd
import rasterio
from rasterio.warp import transform_bounds
from rasterio.mask import mask as rasterio_mask
from rasterio.crs import CRS
import numpy as np
from shapely.geometry import Polygon, shape, mapping
from shapely import affinity
from pyproj import Transformer
import os
import subprocess
import json
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import leafmap.foliumap as leafmap
import base64
import io
from PIL import Image
import webbrowser
import threading
import http.server
import urllib.parse

# --- 1. APP CONFIGURATION ---
st.set_page_config(layout="wide", page_title="DPIRD Field Mapping Tool")
st.title("DPIRD Field Mapping Tool")


# --- File/Folder browser: ASYNC subprocess approach ---
# Launches dialog in a background process, polls for result.
# Streamlit stays responsive while dialog is open.

import sys as _sys
import tempfile as _tempfile

def _launch_dialog(dialog_type, result_key, title="Select", filetypes=None):
    """Launch a file/folder dialog in a background process.
    Writes selected path to a temp file. Streamlit polls for it."""
    tmp = os.path.join(_tempfile.gettempdir(), f"_dpird_dialog_{result_key}.txt")
    # Clear any previous result
    if os.path.exists(tmp):
        os.remove(tmp)

    if dialog_type == "folder":
        code = (
            "import tkinter as tk\n"
            "from tkinter import filedialog\n"
            "root = tk.Tk()\n"
            "root.withdraw()\n"
            "root.attributes('-topmost', True)\n"
            "root.focus_force()\n"
            "path = filedialog.askdirectory(parent=root)\n"
            "root.destroy()\n"
            f"open(r'{tmp}', 'w').write(path if path else '')\n"
        )
    else:
        ft_str = repr(filetypes) if filetypes else repr([("All files", "*.*")])
        code = (
            "import tkinter as tk\n"
            "from tkinter import filedialog\n"
            "root = tk.Tk()\n"
            "root.withdraw()\n"
            "root.attributes('-topmost', True)\n"
            "root.focus_force()\n"
            f"path = filedialog.askopenfilename(title={repr(title)}, filetypes={ft_str}, parent=root)\n"
            "root.destroy()\n"
            f"open(r'{tmp}', 'w').write(path if path else '')\n"
        )

    # Launch as a detached background process
    subprocess.Popen(
        [_sys.executable, "-c", code],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    # Store the temp file path so we can poll for it
    st.session_state[f'_dialog_pending_{result_key}'] = tmp


def _check_dialog_result(result_key):
    """Check if a background dialog has completed. Returns path or None."""
    pending_key = f'_dialog_pending_{result_key}'
    if pending_key not in st.session_state:
        return None
    tmp = st.session_state[pending_key]
    if os.path.exists(tmp):
        try:
            with open(tmp, 'r') as f:
                path = f.read().strip()
            os.remove(tmp)
            del st.session_state[pending_key]
            return path if path else None
        except Exception:
            return None
    return None  # Dialog still open


def browse_folder_async(result_key, session_key):
    """Non-blocking folder browse. Call from a button, polls on rerun."""
    # Check if a previous dialog completed
    path = _check_dialog_result(result_key)
    if path:
        st.session_state[session_key] = os.path.normpath(path)
        return True  # Signal that we got a result

    return False


def browse_file_async(result_key, session_key, title="Select file",
                      filetypes=None):
    """Non-blocking file browse. Call from a button, polls on rerun."""
    path = _check_dialog_result(result_key)
    if path:
        st.session_state[session_key] = path
        return True

    return False




# ============================================================
# HELPER: GeoJSON → Shapefile  (in-memory, no temp .geojson)
# ============================================================
def geojson_to_shapefile(geojson_data, output_shp_path, target_crs="EPSG:4326"):
    if isinstance(geojson_data, str):
        geojson_data = json.loads(geojson_data)
    gdf = gpd.GeoDataFrame.from_features(
        geojson_data["features"], crs="EPSG:4326"
    )
    if target_crs and target_crs != "EPSG:4326":
        gdf = gdf.to_crs(target_crs)
    gdf.to_file(output_shp_path)
    return gdf


# ============================================================
# MINI HTTP SERVER  –  receives edited GeoJSON from the browser
# and writes a shapefile directly. Runs in a background thread.
# ============================================================
_server_instance = None
_server_port = None


class _ShapefileSaveHandler(http.server.BaseHTTPRequestHandler):
    """Handles POST /save  from the editing HTML page."""

    save_directory = "."

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            geojson_data = json.loads(body)
            shp_path = os.path.join(
                self.__class__.save_directory, "edited_grid.shp"
            )
            geojson_to_shapefile(geojson_data, shp_path)
            resp = json.dumps({"success": True, "path": shp_path})
            self.send_response(200)
        except Exception as e:
            resp = json.dumps({"success": False, "error": str(e)})
            self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(resp.encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, fmt, *args):
        pass  # silence console spam


def _ensure_save_server(save_directory):
    """Start the background HTTP server (once) and return its port."""
    global _server_instance, _server_port
    if _server_instance is not None:
        _ShapefileSaveHandler.save_directory = save_directory
        return _server_port

    _ShapefileSaveHandler.save_directory = save_directory

    # Find a free port
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    server = http.server.HTTPServer(("127.0.0.1", port), _ShapefileSaveHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    _server_instance = server
    _server_port = port
    return port


# --- 2. GRID LOGIC ---
def generate_plots(pts, nbanks, nrows, buffer_m, plot_size_str, df=None):
    tl, tr, br, bl = pts
    pw, ph = map(float, plot_size_str.split(','))
    angle = np.degrees(np.arctan2(tr[1] - tl[1], tr[0] - tl[0]))
    polys = []
    rows_list = []

    for b in range(nbanks):
        for r in range(nrows):
            u, v = (b + 0.5) / nbanks, (r + 0.5) / nrows
            center = (1 - v) * ((1 - u) * tl + u * tr) + v * ((1 - u) * bl + u * br)
            w, h = (pw / 2) - buffer_m, (ph / 2) - buffer_m
            rect = Polygon([
                (center[0] - w, center[1] - h),
                (center[0] + w, center[1] - h),
                (center[0] + w, center[1] + h),
                (center[0] - w, center[1] + h),
            ])
            polys.append(affinity.rotate(rect, angle, origin=(center[0], center[1])))

            plot_num = b * nrows + r
            row_data = {
                'Plot_ID': (b + 1) * 1000 + (r + 1),
                'B/R': f"B{b+1}R{r+1}",
                'Bank': b + 1,
                'Row': r + 1,
            }

            if df is not None and plot_num < len(df):
                for col_name in df.columns:
                    if col_name not in row_data:
                        row_data[col_name] = df.iloc[plot_num][col_name]

            rows_list.append(row_data)

    return polys, rows_list


# ============================================================
# EDITABLE HTML MAP  –  fully custom drag / delete / draw / undo
# No dependency on leaflet-path-drag (unreliable with L.geoJSON).
# Drag is implemented with mousedown → mousemove offset tracking.
# ============================================================
def create_editable_html(gdf, output_path, ortho_path=None,
                         save_directory=None, server_port=None):

    centroid = gdf.geometry.centroid.iloc[0]
    center = [centroid.y, centroid.x]

    if save_directory is None:
        save_directory = os.path.dirname(output_path) or os.getcwd()

    # --- ortho overlay ---
    ortho_layer_js = ""
    if ortho_path and os.path.exists(ortho_path):
        try:
            with rasterio.open(ortho_path) as src:
                r = src.read(1)
                g = src.read(2) if src.count >= 2 else src.read(1)
                b = src.read(3) if src.count >= 3 else src.read(1)
                rgb = np.dstack([r, g, b])
                rgb = ((rgb - rgb.min()) / (rgb.max() - rgb.min()) * 255).astype(np.uint8)
                img = Image.fromarray(rgb)
                max_size = 4096
                if max(img.size) > max_size:
                    ratio = max_size / max(img.size)
                    img = img.resize(
                        (int(img.size[0] * ratio), int(img.size[1] * ratio)),
                        Image.Resampling.LANCZOS,
                    )
                buffered = io.BytesIO()
                img.save(buffered, format="PNG", optimize=True)
                img_str = base64.b64encode(buffered.getvalue()).decode()
                bounds_latlon = transform_bounds(src.crs, 'EPSG:4326', *src.bounds)
                ortho_layer_js = (
                    f"var imageBounds = [[{bounds_latlon[1]}, {bounds_latlon[0]}],"
                    f"[{bounds_latlon[3]}, {bounds_latlon[2]}]];\n"
                    f"L.imageOverlay('data:image/png;base64,{img_str}', imageBounds,"
                    "{opacity: 0.8}).addTo(map);\n"
                )
        except Exception as e:
            ortho_layer_js = f"// ortho error: {e}"

    geojson_str = json.dumps(json.loads(gdf.to_json()))
    save_dir_escaped = save_directory.replace("\\", "\\\\")
    port_str = str(server_port) if server_port else ""

    # ---------------------------------------------------------------
    # Instead of embedding JS in the f-string (which causes escaping
    # nightmares with {x:…} etc.), we build the JS as a plain string
    # and only inject the dynamic values via .replace().
    # ---------------------------------------------------------------
    js_template = r"""
// ========== CONFIG ==========
var SAVE_PORT = "%%PORT%%";
var SAVE_DIR  = "%%SAVEDIR%%";

// ========== MAP INIT ==========
var map = L.map('map', {maxZoom:25, minZoom:3, doubleClickZoom:false})
             .setView([%%CENTERLAT%%, %%CENTERLNG%%], 19);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom:25, maxNativeZoom:19
}).addTo(map);

%%ORTHO%%

// ========== STYLES ==========
var S_DEFAULT  = {color:'red',    weight:2, fillColor:'yellow', fillOpacity:0.2};
var S_HOVER    = {color:'red',    weight:3, fillColor:'yellow', fillOpacity:0.35};
var S_SELECTED = {color:'#0066ff',weight:3, fillColor:'#80b3ff',fillOpacity:0.35};
var S_DRAGGING = {color:'#00cc44',weight:3, fillColor:'#66ff99',fillOpacity:0.30};
var S_DELETE   = {color:'#dc3545',weight:3, fillColor:'#ff6b6b',fillOpacity:0.40};

// ========== STATE ==========
var currentMode = 'navigate';
var editableLayer = new L.FeatureGroup().addTo(map);
var mapEl = map.getContainer();
var undoHistory = [];

var isDragging = false;
var dragTarget = null;
var dragStartPx = null;

var drawPoints = [];
var drawMarkers = [];
var drawLine = null;

// Multi-select
var selectedPolys = [];

// Copy/paste
var clipboard = null; // {latlngs:[[lat,lng],...], props:{...}}

// Measurements
var showMeasurements = false;
var measureLabels = [];

// ========== TOAST ==========
function showToast(msg, isError) {
  var t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (isError ? ' error' : '');
  setTimeout(function(){ t.className = 'toast'; }, 2500);
}

// ========== HELPERS ==========
function getLatLngsFlat(layer) {
  var raw = layer.getLatLngs();
  while (raw.length > 0 && Array.isArray(raw[0])) raw = raw[0];
  return raw;
}

function saveState() {
  try {
    undoHistory.push(JSON.stringify(buildGeoJSON()));
    if (undoHistory.length > 50) undoHistory.shift();
  } catch(e) {}
}

function pxToLatLng(cx, cy) {
  var rect = mapEl.getBoundingClientRect();
  return map.containerPointToLatLng(L.point(cx - rect.left, cy - rect.top));
}

// Haversine distance in metres between two LatLng
function distMetres(a, b) {
  var R = 6371000;
  var dLat = (b.lat - a.lat) * Math.PI / 180;
  var dLng = (b.lng - a.lng) * Math.PI / 180;
  var s = Math.sin(dLat/2)*Math.sin(dLat/2) +
          Math.cos(a.lat*Math.PI/180)*Math.cos(b.lat*Math.PI/180)*
          Math.sin(dLng/2)*Math.sin(dLng/2);
  return R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1-s));
}

// ========== BUILD GEOJSON ==========
function buildGeoJSON() {
  var features = [];
  editableLayer.eachLayer(function(layer) {
    var latlngs = getLatLngsFlat(layer);
    var coords = latlngs.map(function(ll) { return [ll.lng, ll.lat]; });
    if (coords.length > 0) {
      var f = coords[0], la = coords[coords.length-1];
      if (f[0] !== la[0] || f[1] !== la[1]) coords.push([f[0], f[1]]);
    }
    features.push({
      type:'Feature',
      properties: layer._props || {},
      geometry: {type:'Polygon', coordinates:[coords]}
    });
  });
  return {type:'FeatureCollection', features:features};
}

// ========== SELECTION ==========
function isSelected(poly) {
  return selectedPolys.indexOf(poly) !== -1;
}

function selectPoly(poly) {
  if (isSelected(poly)) return;
  selectedPolys.push(poly);
  poly.setStyle(S_SELECTED);
  updateSelCount();
}

function deselectPoly(poly) {
  var idx = selectedPolys.indexOf(poly);
  if (idx !== -1) selectedPolys.splice(idx, 1);
  poly.setStyle(S_DEFAULT);
  updateSelCount();
}

function toggleSelect(poly) {
  if (isSelected(poly)) deselectPoly(poly);
  else selectPoly(poly);
}

function clearSelection() {
  selectedPolys.forEach(function(p) {
    if (editableLayer.hasLayer(p)) p.setStyle(S_DEFAULT);
  });
  selectedPolys = [];
  updateSelCount();
}

function selectAll() {
  clearSelection();
  editableLayer.eachLayer(function(l) { selectPoly(l); });
}

function updateSelCount() {
  var el = document.getElementById('selCount');
  if (el) el.textContent = selectedPolys.length;
}

// ========== MEASUREMENTS ==========
function clearMeasureLabels() {
  measureLabels.forEach(function(l) { map.removeLayer(l); });
  measureLabels = [];
}

function updateMeasurements() {
  clearMeasureLabels();
  if (!showMeasurements) return;

  editableLayer.eachLayer(function(layer) {
    var pts = getLatLngsFlat(layer);
    if (pts.length < 2) return;
    for (var i = 0; i < pts.length; i++) {
      var a = pts[i];
      var b = pts[(i + 1) % pts.length];
      var d = distMetres(a, b);
      var mid = L.latLng((a.lat + b.lat) / 2, (a.lng + b.lng) / 2);
      var label = L.tooltip({permanent: true, direction: 'center', className: 'measure-label'})
        .setLatLng(mid)
        .setContent(d.toFixed(2) + 'm');
      label.addTo(map);
      measureLabels.push(label);
    }
  });
}

function toggleMeasurements() {
  showMeasurements = !showMeasurements;
  var btn = document.getElementById('btnMeasure');
  if (btn) btn.classList.toggle('active', showMeasurements);
  updateMeasurements();
}

// ========== ADD POLYGON ==========
function addPoly(latlngs, properties) {
  var poly = L.polygon(latlngs, S_DEFAULT);
  poly._props = properties || {};

  var popup = '<b>Plot Info</b><br>';
  for (var k in poly._props) popup += k + ': ' + poly._props[k] + '<br>';
  poly.bindPopup(popup);

  var label = poly._props.Plot_ID || poly._props.Plot || '';
  if (label) poly.bindTooltip(String(label), {permanent:false, direction:'center'});

  // Click: select / delete depending on mode
  poly.on('click', function(e) {
    if (currentMode === 'delete') {
      // Delete: if polygon is selected, delete all selected; else just this one
      saveState();
      if (isSelected(this) && selectedPolys.length > 1) {
        var toDelete = selectedPolys.slice();
        selectedPolys = [];
        toDelete.forEach(function(p) { editableLayer.removeLayer(p); });
        showToast(toDelete.length + ' plots deleted');
      } else {
        deselectPoly(this);
        editableLayer.removeLayer(this);
        showToast('Plot deleted');
      }
      updateCount();
      updateMeasurements();
      return;
    }
    if (currentMode === 'navigate' || currentMode === 'drag' || currentMode === 'vertex') {
      // Ctrl+click or Shift+click to toggle selection
      if (e.originalEvent.ctrlKey || e.originalEvent.shiftKey) {
        toggleSelect(this);
      } else {
        // Single click without modifier: select only this
        clearSelection();
        selectPoly(this);
      }
    }
  });

  // Mousedown: drag (single or multi)
  poly.on('mousedown', function(e) {
    if (currentMode !== 'drag') return;
    saveState();
    isDragging = true;
    // If this poly is selected and we have multi-select, drag all selected
    if (isSelected(this) && selectedPolys.length > 0) {
      dragTarget = selectedPolys.slice(); // array of polys
    } else {
      clearSelection();
      selectPoly(this);
      dragTarget = [this];
    }
    dragTarget.forEach(function(p) { p.setStyle(S_DRAGGING); p.closePopup(); p.closeTooltip(); });
    dragStartPx = {x: e.originalEvent.clientX, y: e.originalEvent.clientY};
  });

  // Hover
  poly.on('mouseover', function() {
    if (isDragging) return;
    if (isSelected(this)) return; // keep selected style
    if (currentMode === 'navigate') this.setStyle(S_HOVER);
    if (currentMode === 'drag')     this.setStyle(S_DRAGGING);
    if (currentMode === 'delete')   this.setStyle(S_DELETE);
  });
  poly.on('mouseout', function() {
    if (isDragging) return;
    if (isSelected(this)) { this.setStyle(S_SELECTED); return; }
    this.setStyle(S_DEFAULT);
  });

  editableLayer.addLayer(poly);
  return poly;
}

// ========== LOAD DATA ==========
var plotData = %%GEOJSON%%;
plotData.features.forEach(function(f) {
  var rings = f.geometry.coordinates[0].map(function(c) { return [c[1], c[0]]; });
  addPoly(rings, f.properties);
});
map.fitBounds(editableLayer.getBounds(), {padding:[50,50]});
updateCount();

// ========== DRAG: document-level mousemove/mouseup ==========
document.addEventListener('mousemove', function(e) {
  if (!isDragging || !dragTarget || !dragStartPx) return;
  try {
    var oldLL = pxToLatLng(dragStartPx.x, dragStartPx.y);
    var newLL = pxToLatLng(e.clientX, e.clientY);
    var dlat = newLL.lat - oldLL.lat;
    var dlng = newLL.lng - oldLL.lng;
    dragTarget.forEach(function(poly) {
      var latlngs = getLatLngsFlat(poly);
      var shifted = latlngs.map(function(ll) {
        return L.latLng(ll.lat + dlat, ll.lng + dlng);
      });
      poly.setLatLngs([shifted]);
    });
    dragStartPx = {x: e.clientX, y: e.clientY};
  } catch(err) { isDragging = false; }
});

document.addEventListener('mouseup', function() {
  if (!isDragging) return;
  if (dragTarget) {
    dragTarget.forEach(function(poly) {
      var coords = getLatLngsFlat(poly).map(function(ll) { return [ll.lat, ll.lng]; });
      var props = poly._props;
      var wasSel = isSelected(poly);
      editableLayer.removeLayer(poly);
      var idx = selectedPolys.indexOf(poly);
      if (idx !== -1) selectedPolys.splice(idx, 1);
      var np = addPoly(coords, props);
      if (wasSel) selectPoly(np);
    });
  }
  isDragging = false;
  dragTarget = null;
  dragStartPx = null;
  updateMeasurements();
});

// ========== DRAW: map click + dblclick ==========
map.on('click', function(e) {
  if (currentMode !== 'draw') return;
  var pt = e.latlng;
  if (drawPoints.length >= 3) {
    var fp = map.latLngToContainerPoint(drawPoints[0]);
    var cp = map.latLngToContainerPoint(pt);
    if (fp.distanceTo(cp) < 20) { finishDraw(); return; }
  }
  drawPoints.push(pt);
  drawMarkers.push(
    L.circleMarker(pt, {radius:6, color:'#007bff', fillColor:'#007bff', fillOpacity:1}).addTo(map)
  );
  updateDrawLine();
});

map.on('dblclick', function() {
  if (currentMode === 'draw' && drawPoints.length >= 3) finishDraw();
});

function updateDrawLine() {
  if (drawLine) map.removeLayer(drawLine);
  if (drawPoints.length >= 2)
    drawLine = L.polyline(drawPoints, {color:'#007bff', weight:2, dashArray:'6,4'}).addTo(map);
}

function finishDraw() {
  if (drawPoints.length < 3) return;
  saveState();
  addPoly(drawPoints.slice(), {Plot_ID: 'new_' + Date.now()});
  clearDrawHelpers();
  drawPoints = [];
  updateCount();
  updateMeasurements();
  showToast('New plot added');
}

function clearDrawHelpers() {
  if (drawLine) { map.removeLayer(drawLine); drawLine = null; }
  drawMarkers.forEach(function(m){ map.removeLayer(m); });
  drawMarkers = [];
}

// ========== COPY / PASTE ==========
function copySelected() {
  if (selectedPolys.length === 0) { showToast('Select a polygon first', true); return; }
  var src = selectedPolys[0]; // copy the first selected
  clipboard = {
    latlngs: getLatLngsFlat(src).map(function(ll) { return [ll.lat, ll.lng]; }),
    props: JSON.parse(JSON.stringify(src._props))
  };
  showToast('Copied polygon shape');
}

function pastePolygon() {
  if (!clipboard) { showToast('Nothing to paste', true); return; }
  saveState();
  // Offset by a small amount (roughly 1-2 metres) so pasted polygon is visible but close
  var offset = 0.00002;
  var shifted = clipboard.latlngs.map(function(c) { return [c[0] + offset, c[1] + offset]; });
  var newProps = JSON.parse(JSON.stringify(clipboard.props));
  // Generate a new Plot_ID based on count
  var count = 0;
  editableLayer.eachLayer(function(){ count++; });
  newProps.Plot_ID = 'Plot_' + (count + 1);
  var np = addPoly(shifted, newProps);
  clearSelection();
  selectPoly(np);
  updateCount();
  updateMeasurements();
  showToast('Polygon pasted');
}

// Apply shape of first selected polygon to all other selected polygons
function applyShapeToSelected() {
  if (selectedPolys.length < 2) { showToast('Select 2+ polygons (first = source)', true); return; }
  saveState();
  var src = selectedPolys[0];
  var srcPts = getLatLngsFlat(src);

  // Compute source centroid
  var sLat = 0, sLng = 0;
  srcPts.forEach(function(ll) { sLat += ll.lat; sLng += ll.lng; });
  sLat /= srcPts.length; sLng /= srcPts.length;

  // Collect targets (all selected except the source) before modifying anything
  var targets = [];
  for (var i = 1; i < selectedPolys.length; i++) {
    var tgt = selectedPolys[i];
    var tgtPts = getLatLngsFlat(tgt);
    var tLat = 0, tLng = 0;
    tgtPts.forEach(function(ll) { tLat += ll.lat; tLng += ll.lng; });
    tLat /= tgtPts.length; tLng /= tgtPts.length;
    targets.push({layer: tgt, centroidLat: tLat, centroidLng: tLng, props: tgt._props});
  }

  // Now remove old layers and create new ones
  var newSelection = [src];
  targets.forEach(function(t) {
    var newCoords = srcPts.map(function(ll) {
      return [ll.lat - sLat + t.centroidLat, ll.lng - sLng + t.centroidLng];
    });
    editableLayer.removeLayer(t.layer);
    var np = addPoly(newCoords, t.props);
    newSelection.push(np);
  });

  // Rebuild selection cleanly
  selectedPolys = [];
  newSelection.forEach(function(p) { selectPoly(p); });

  updateCount();
  updateMeasurements();
  showToast('Shape applied to ' + targets.length + ' polygon(s)');
}

// Apply shape of first selected polygon to ALL other polygons
function applyShapeToAll() {
  if (selectedPolys.length < 1) { showToast('Select a source polygon first', true); return; }
  saveState();
  var src = selectedPolys[0];
  var srcPts = getLatLngsFlat(src);

  var sLat = 0, sLng = 0;
  srcPts.forEach(function(ll) { sLat += ll.lat; sLng += ll.lng; });
  sLat /= srcPts.length; sLng /= srcPts.length;

  // Collect all non-source polygons
  var targets = [];
  editableLayer.eachLayer(function(layer) {
    if (layer === src) return;
    var tgtPts = getLatLngsFlat(layer);
    var tLat = 0, tLng = 0;
    tgtPts.forEach(function(ll) { tLat += ll.lat; tLng += ll.lng; });
    tLat /= tgtPts.length; tLng /= tgtPts.length;
    targets.push({layer: layer, centroidLat: tLat, centroidLng: tLng, props: layer._props});
  });

  if (targets.length === 0) { showToast('No other polygons to apply to', true); return; }

  targets.forEach(function(t) {
    var newCoords = srcPts.map(function(ll) {
      return [ll.lat - sLat + t.centroidLat, ll.lng - sLng + t.centroidLng];
    });
    editableLayer.removeLayer(t.layer);
    addPoly(newCoords, t.props);
  });

  clearSelection();
  selectPoly(src);
  updateCount();
  updateMeasurements();
  showToast('Shape applied to all ' + targets.length + ' polygon(s)');
}

// ========== MODE MANAGEMENT ==========
function setMode(mode) {
  if (currentMode === 'vertex') {
    editableLayer.eachLayer(function(l) {
      if (l.editing && l.editing.enabled()) l.editing.disable();
    });
    updateMeasurements();
  }
  if (currentMode === 'draw') { clearDrawHelpers(); drawPoints = []; }

  // Reset non-selected styles
  editableLayer.eachLayer(function(l) {
    if (!isSelected(l)) l.setStyle(S_DEFAULT);
    else l.setStyle(S_SELECTED);
  });
  isDragging = false; dragTarget = null; dragStartPx = null;

  currentMode = mode;

  ['btnNavigate','btnDrag','btnVertex','btnDelete','btnDraw'].forEach(function(id) {
    document.getElementById(id).classList.remove('active');
  });
  var btnMap = {navigate:'btnNavigate', drag:'btnDrag', vertex:'btnVertex',
                delete:'btnDelete', draw:'btnDraw'};
  if (btnMap[mode]) document.getElementById(btnMap[mode]).classList.add('active');

  var labels = {navigate:'Navigate', drag:'Drag Plots', vertex:'Edit Vertices',
                delete:'Delete Plot', draw:'Draw New'};
  document.getElementById('modeLabel').textContent = labels[mode] || mode;

  var cursors = {navigate:'', drag:'move', vertex:'crosshair',
                 delete:'not-allowed', draw:'crosshair'};
  mapEl.style.cursor = cursors[mode] || '';

  if (mode === 'drag' || mode === 'delete') {
    map.dragging.disable();
  } else {
    map.dragging.enable();
  }

  if (mode === 'vertex') {
    saveState();
    // If polygons are selected, edit only those; else edit all
    var targets = selectedPolys.length > 0 ? selectedPolys.slice() : [];
    if (targets.length === 0) {
      editableLayer.eachLayer(function(l) { targets.push(l); });
    }
    targets.forEach(function(l) {
      if (l.editing) {
        l.editing.enable();
        // Real-time measurement update while dragging vertices
        l.on('editdrag', function() { if (showMeasurements) updateMeasurements(); });
      }
    });
  }
}

// ========== UNDO ==========
function undoLast() {
  if (undoHistory.length === 0) { showToast('Nothing to undo', true); return; }
  var prev = JSON.parse(undoHistory.pop());
  editableLayer.clearLayers();
  selectedPolys = [];
  prev.features.forEach(function(f) {
    var rings = f.geometry.coordinates[0].map(function(c) { return [c[1], c[0]]; });
    addPoly(rings, f.properties);
  });
  updateCount();
  updateSelCount();
  var m = currentMode;
  currentMode = 'navigate';
  setMode(m);
  updateMeasurements();
  showToast('Undo successful');
}

// ========== COUNT ==========
function updateCount() {
  var n = 0;
  editableLayer.eachLayer(function(){ n++; });
  document.getElementById('plotCount').textContent = n;
}

// ========== EXPORT GEOJSON ==========
function exportGeoJSON() {
  if (currentMode === 'vertex') {
    editableLayer.eachLayer(function(l) {
      if (l.editing && l.editing.enabled()) l.editing.disable();
    });
  }
  var data = buildGeoJSON();
  var blob = new Blob([JSON.stringify(data,null,2)], {type:'application/json'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url; a.download = 'edited_grid.geojson'; a.click();
  URL.revokeObjectURL(url);
  showToast('GeoJSON downloaded');
  if (currentMode === 'vertex') {
    editableLayer.eachLayer(function(l) { if (l.editing) l.editing.enable(); });
  }
}

// ========== SAVE SHAPEFILE ==========
function saveShapefile() {
  if (!SAVE_PORT) {
    showToast('No save server – exporting GeoJSON instead', true);
    exportGeoJSON();
    return;
  }
  if (currentMode === 'vertex') {
    editableLayer.eachLayer(function(l) {
      if (l.editing && l.editing.enabled()) l.editing.disable();
    });
  }
  var data = buildGeoJSON();
  document.getElementById('modeLabel').textContent = 'Saving...';
  fetch('http://127.0.0.1:' + SAVE_PORT + '/save', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(data)
  })
  .then(function(r){ return r.json(); })
  .then(function(d){
    if(d.success) showToast('Shapefile saved: '+d.path);
    else showToast('Error: '+d.error, true);
    setModeLabel();
    if (currentMode === 'vertex') {
      editableLayer.eachLayer(function(l) { if (l.editing) l.editing.enable(); });
    }
  })
  .catch(function(){
    showToast('Server unreachable – downloading GeoJSON', true);
    exportGeoJSON();
    setModeLabel();
  });
}

function setModeLabel() {
  var labels = {navigate:'Navigate', drag:'Drag Plots', vertex:'Edit Vertices',
                delete:'Delete Plot', draw:'Draw New'};
  document.getElementById('modeLabel').textContent = labels[currentMode] || currentMode;
}

// ========== KEYBOARD ==========
document.addEventListener('keydown', function(e) {
  if (e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA') return;
  if (e.key==='Escape') { clearSelection(); setMode('navigate'); }
  if (e.ctrlKey && e.key==='z') { e.preventDefault(); undoLast(); }
  if (e.ctrlKey && e.key==='a') { e.preventDefault(); selectAll(); }
  if (e.ctrlKey && e.key==='c') { e.preventDefault(); copySelected(); }
  if (e.ctrlKey && e.key==='v') { e.preventDefault(); pastePolygon(); }
  if (!e.ctrlKey && !e.altKey) {
    if (e.key==='d'||e.key==='D') setMode('drag');
    if (e.key==='v'||e.key==='V') setMode('vertex');
    if (e.key==='x'||e.key==='X') setMode('delete');
    if (e.key==='n'||e.key==='N') setMode('draw');
    if (e.key==='m'||e.key==='M') toggleMeasurements();
  }
});

setMode('navigate');
"""

    # Inject dynamic values into the JS template (no f-string escaping issues)
    js_code = (js_template
        .replace("%%PORT%%", port_str)
        .replace("%%SAVEDIR%%", save_dir_escaped)
        .replace("%%CENTERLAT%%", str(center[0]))
        .replace("%%CENTERLNG%%", str(center[1]))
        .replace("%%ORTHO%%", ortho_layer_js)
        .replace("%%GEOJSON%%", geojson_str)
    )

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Edit Plot Grid</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;}}
  #map{{position:absolute;top:0;bottom:0;width:100%;z-index:1;}}
  .toolbar{{
    position:fixed;top:12px;right:12px;z-index:1000;
    display:flex;flex-direction:column;gap:6px;
    background:rgba(255,255,255,.94);backdrop-filter:blur(8px);
    padding:12px;border-radius:10px;
    box-shadow:0 4px 20px rgba(0,0,0,.18);width:220px;
  }}
  .toolbar h3{{font-size:13px;margin-bottom:4px;color:#333;}}
  .tb-btn{{
    display:flex;align-items:center;gap:6px;
    padding:9px 12px;border:2px solid #bbb;border-radius:6px;
    font-size:13px;font-weight:600;cursor:pointer;
    background:#fff;color:#333;transition:all .15s;user-select:none;
  }}
  .tb-btn:hover{{background:#f0f0f0;}}
  .tb-btn.active{{border-color:#007bff;background:#e7f1ff;color:#007bff;}}
  .tb-sep{{border:none;border-top:1px solid #ddd;margin:2px 0;}}
  .btn-green{{background:#28a745!important;color:#fff!important;border-color:#28a745!important;}}
  .btn-green:hover{{background:#218838!important;}}
  .btn-blue{{background:#007bff!important;color:#fff!important;border-color:#007bff!important;}}
  .btn-blue:hover{{background:#0069d9!important;}}
  .btn-orange{{background:#fd7e14!important;color:#fff!important;border-color:#fd7e14!important;}}
  .btn-orange:hover{{background:#e8690b!important;}}
  .status-bar{{
    position:fixed;bottom:12px;left:50%;transform:translateX(-50%);z-index:1000;
    background:rgba(255,255,255,.94);backdrop-filter:blur(8px);
    padding:6px 20px;border-radius:20px;font-size:12px;color:#555;
    box-shadow:0 2px 12px rgba(0,0,0,.1);
  }}
  .status-bar .mode{{font-weight:700;color:#007bff;}}
  .info-panel{{
    position:fixed;bottom:12px;left:12px;z-index:1000;
    background:rgba(255,255,255,.94);backdrop-filter:blur(8px);
    padding:10px 14px;border-radius:10px;font-size:12px;color:#444;
    box-shadow:0 2px 12px rgba(0,0,0,.1);line-height:1.7;max-width:250px;
  }}
  .toast{{
    position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:9999;
    background:#28a745;color:#fff;padding:12px 24px;border-radius:8px;
    font-size:14px;font-weight:600;box-shadow:0 4px 16px rgba(0,0,0,.2);
    opacity:0;transition:opacity .3s;pointer-events:none;
  }}
  .toast.show{{opacity:1;}}
  .toast.error{{background:#dc3545;}}
  .measure-label{{background:rgba(0,0,0,0.7);color:#fff;border:none;
    font-size:11px;padding:2px 5px;border-radius:3px;font-weight:600;
    box-shadow:none;white-space:nowrap;}}
  .tb-row{{display:flex;gap:4px;}}
  .tb-row .tb-btn{{flex:1;justify-content:center;padding:7px 4px;font-size:11px;}}
</style>
</head>
<body>
<div id="map"></div>
<div class="toast" id="toast"></div>
<div class="toolbar">
  <h3>Editing Tools</h3>
  <button class="tb-btn" id="btnNavigate" onclick="setMode('navigate')">🗺️ Navigate</button>
  <button class="tb-btn" id="btnDrag"     onclick="setMode('drag')">🖐️ Drag Plots</button>
  <button class="tb-btn" id="btnVertex"   onclick="setMode('vertex')">✏️ Edit Vertices</button>
  <button class="tb-btn" id="btnDelete"   onclick="setMode('delete')">🗑️ Delete Plot</button>
  <button class="tb-btn" id="btnDraw"     onclick="setMode('draw')">➕ Draw New</button>
  <hr class="tb-sep">
  <h3>Selection</h3>
  <div class="tb-row">
    <button class="tb-btn" onclick="selectAll()">Select All</button>
    <button class="tb-btn" onclick="clearSelection()">Clear Sel</button>
  </div>
  <button class="tb-btn" onclick="applyShapeToSelected()">📋 Apply Shape to Selected</button>
  <button class="tb-btn" onclick="applyShapeToAll()">📋 Apply Shape to All</button>
  <hr class="tb-sep">
  <h3>Copy / Paste</h3>
  <div class="tb-row">
    <button class="tb-btn" onclick="copySelected()">📋 Copy</button>
    <button class="tb-btn" onclick="pastePolygon()">📄 Paste</button>
  </div>
  <hr class="tb-sep">
  <button class="tb-btn" id="btnMeasure" onclick="toggleMeasurements()">📏 Measurements</button>
  <button class="tb-btn btn-blue"   onclick="undoLast()">↩️ Undo</button>
  <button class="tb-btn btn-green"  onclick="saveShapefile()">💾 Save Shapefile</button>
  <button class="tb-btn btn-orange" onclick="exportGeoJSON()">📥 Export GeoJSON</button>
</div>
<div class="status-bar">
  Mode: <span class="mode" id="modeLabel">Navigate</span> &nbsp;|&nbsp;
  Plots: <span id="plotCount">0</span> &nbsp;|&nbsp;
  Selected: <span id="selCount">0</span>
</div>
<div class="info-panel">
  <b>Shortcuts</b><br>
  <b>D</b> Drag &nbsp; <b>V</b> Vertices &nbsp; <b>X</b> Delete<br>
  <b>N</b> Draw &nbsp; <b>M</b> Measurements<br>
  <b>Ctrl+A</b> Select all &nbsp; <b>Esc</b> Deselect<br>
  <b>Ctrl+C</b> Copy &nbsp; <b>Ctrl+V</b> Paste<br>
  <b>Ctrl+Z</b> Undo<br>
  <b>Click</b> Select &nbsp; <b>Ctrl+Click</b> Multi-select
</div>
<script>
{js_code}
</script>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


# ============================================================
# STREAMLIT APP  –  SIDEBAR NAV + TABS
# ============================================================

# --- Sticky footer + layout CSS ---
st.markdown("""
<style>
.sticky-footer {
    position: fixed; bottom: 0; left: 0; right: 0; z-index: 9999;
    background: #f8f9fa; border-top: 1px solid #ddd;
    padding: 8px 0; text-align: center;
    font-size: 14px; color: #555;
}
.sticky-footer a { color: #007bff; text-decoration: none; }
.sticky-footer a:hover { text-decoration: underline; }
/* Add bottom padding to main content so footer doesn't overlap */
.main .block-container { padding-bottom: 60px; padding-top: 1rem; }
/* Minimize top spacing above title */
.main .block-container h1:first-of-type { margin-top: 0; padding-top: 0; }
header[data-testid="stHeader"] { height: 2rem; }
/* Larger sidebar collapse button */
button[data-testid="stSidebarCollapseButton"],
button[kind="headerNoPadding"] {
    transform: scale(1.5);
    margin: 4px;
}
</style>
<div class="sticky-footer">
    Developed by Bipul Neupane, PhD (Research Scientist, DPIRD Node, APPN).
    Contact: <a href="mailto:bipul.neupane@dpird.wa.gov.au">bipul.neupane@dpird.wa.gov.au</a>
</div>
""", unsafe_allow_html=True)

# --- Sidebar: Logo + How to use + Documentation ---
with st.sidebar:
    # === LOGO ===
    _logo_path = os.path.join(".", "bin", "logo.png")  # <-- LINE 1006: ./bin/logo.png
    if os.path.exists(_logo_path):
        st.image(_logo_path, width='stretch')
    else:
        st.caption("⚠️ Logo not found. Place your logo at `./bin/logo.png`.")
    st.divider()

    st.title("📖 How to use")
    st.markdown("Select a tab in the main area to get started.")
    st.divider()

    st.markdown("**Available Tools:**")
    st.markdown("""
    1. 📐 **Generate Grid** — Create plot grids from orthomosaics
    2. ✏️ **Edit Grid** — Edit existing grids in browser
    3. 🔄 **Convert File** — Convert vector file formats
    4. ✂️ **Cropping Tool** — Crop rasters by polygon boundaries
    """)

    st.divider()
    st.subheader("📖 Documentation")

    with st.expander("📐 Generate Grid", expanded=False):
        st.markdown("""
**Purpose:** Generate a regular grid of plot polygons over an orthomosaic within a user-drawn boundary.

**Workflow:**
1. Select your project folder containing the orthomosaic (.tif) and optional CSV with plot metadata.
2. Set grid parameters (see below).
3. Draw a boundary polygon on the map by clicking the four corners in order: **top-left (B1R1) → top-right (BXR1) → bottom-right (BXRY) → bottom-left (B1RY)**.
4. Click **Generate Grid** to create the plot polygons.
5. Use **Edit Grid** to open the browser-based editor, or **Save** directly.

**Parameters:**
- **Banks**: Number of banks (columns) in the grid (X direction).
- **Rows**: Number of rows in the grid (Y direction).
- **Buffer (m)**: Gap between adjacent plots in metres. A buffer of 0.1m leaves a small gap; 0 means plots touch edge-to-edge.
- **Plot Size (W,H)**: Width and height of each plot in metres, comma-separated. E.g. `4,1` creates plots 4m wide by 1m tall.

**Plot ID Convention:**
- `Plot_ID`: Bank × 1000 + Row. B1R1 = 1001, B1R2 = 1002, B2R1 = 2001, etc.
- `B/R`: Bank-Row label (e.g. B1R1, B2R3).

**Coordinate Order:**
The four boundary vertices define how banks and rows are oriented. B1R1 will be nearest to the first vertex you draw (top-left).
        """)

    with st.expander("✏️ Edit Grid", expanded=False):
        st.markdown("""
**Purpose:** Load an existing grid shapefile and orthomosaic, then edit polygons interactively in a browser-based map editor.

**Browser Editor Tools:**
- 🖐️ **Drag** (D): Click and drag polygons to reposition. Multi-select with Ctrl+Click, then drag all selected.
- ✏️ **Vertices** (V): Drag individual vertices to reshape polygons. Toggle **Measurements** (M) to see edge lengths in real-time.
- 🗑️ **Delete** (X): Click a polygon to remove it. If multiple are selected, deletes all selected.
- ➕ **Draw** (N): Click to place vertices, double-click or click first vertex to close.
- 📋 **Copy/Paste** (Ctrl+C / Ctrl+V): Duplicate polygons.
- 📋 **Apply Shape to Selected/All**: Copy one polygon's shape to others, centered on each polygon's centroid.
- 📏 **Measurements** (M): Toggle edge length labels in metres.
- ↩️ **Undo** (Ctrl+Z): Revert last action.
- **Ctrl+A**: Select all polygons. **Esc**: Clear selection.

**Saving:**
- 💾 **Save Shapefile**: Writes directly to the grid directory.
- 📥 **Export GeoJSON**: Downloads a GeoJSON file.
        """)

    with st.expander("🔄 Convert File", expanded=False):
        st.markdown("""
**Purpose:** Convert vector files between formats with optional CRS reprojection.

**Supported Input Formats:** Shapefile (.shp), GeoJSON (.geojson/.json), GeoPackage (.gpkg), KML (.kml), HDF5 (.h5/.hdf5)

**Supported Output Formats:** Shapefile, GeoJSON, GeoPackage, KML

**CRS Options:**
- **Source file CRS**: No reprojection.
- **WGS 84 (EPSG:4326)**: Global standard.
- **GDA2020 / MGA Zones 49–56**: Australian map grid zones.
- **GDA94 / MGA Zones 49–56**: Older Australian datum.
- **Custom EPSG**: Enter any EPSG code manually.

**Note:** KML output is always reprojected to WGS 84 (required by the format).
        """)

    with st.expander("✂️ Cropping Tool", expanded=False):
        st.markdown("""
**Purpose:** Crop raster data (orthophotos, DSMs, etc.) using polygon boundaries.

**Two modes:**
- **Single polygon** (e.g. trial boundary): Saves one cropped raster with user-defined filename.
- **Multiple polygons** (e.g. plot grid): Saves one raster per polygon, named `filename_PlotID.tif`.

**Workflow:**
1. Load a vector boundary file (shapefile, GeoJSON, or GPKG).
2. Load a raster file (.tif).
3. Choose a save folder and base filename.
4. Click **Crop and Save**.

The tool automatically reprojects the vector to match the raster's CRS if needed. NoData pixels are set to 0.
        """)

    # --- Close Tool button ---
    st.divider()
    if st.button("🛑 Close Tool", type="secondary", width='stretch'):
        st.warning("Shutting down the application...")
        # Give Streamlit a moment to render the message
        import time
        time.sleep(1)
        os._exit(0)


# --- Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(["📐 Generate Grid", "✏️ Edit Grid", "🔄 Convert File", "✂️ Cropping Tool"])

# ========================  TAB 1  ========================
with tab1:
    st.header("Generate Initial Grid")

    # --- File Selection ---
    st.subheader("1. File Selection")
    if 'folder_path' not in st.session_state:
        st.session_state.folder_path = ""

    # Check if browse dialog completed
    browse_folder_async("gen_folder", "folder_path")

    def _on_folder_input():
        st.session_state.folder_path = st.session_state._folder_input_val

    col_f1, col_f2 = st.columns([4, 1])
    with col_f1:
        st.text_input("Project Folder:", value=st.session_state.folder_path,
                       key="_folder_input_val", on_change=_on_folder_input)
    with col_f2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📂 Browse", key="browse_folder"):
            _launch_dialog("folder", "gen_folder")
            st.toast("📂 Folder picker opened — select a folder then click back here")
    
    # Auto-refresh to pick up dialog result
    if f'_dialog_pending_gen_folder' in st.session_state:
        import time; time.sleep(1)
        st.rerun()

    ortho_path, csv_path = "", ""
    if st.session_state.folder_path and os.path.isdir(st.session_state.folder_path):
        f_p = st.session_state.folder_path
        tifs = [f for f in os.listdir(f_p) if f.lower().endswith('.tif')]
        csvs = [f for f in os.listdir(f_p) if f.lower().endswith('.csv')]
        col_t, col_c = st.columns(2)
        with col_t:
            sel_tif = st.selectbox("Select Orthomosaic:", [""] + tifs)
        with col_c:
            sel_csv = st.selectbox("Select CSV (optional — for additional plot metadata):", [""] + csvs)
        if sel_tif:
            ortho_path = os.path.join(f_p, sel_tif)
        if sel_csv:
            csv_path = os.path.join(f_p, sel_csv)

    # --- Grid Parameters ---
    st.subheader("2. Grid Parameters")
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1:
        nc = st.number_input("Banks", min_value=1, value=12, key="gen_cols")
    with col_p2:
        nr = st.number_input("Rows", min_value=1, value=6, key="gen_rows")
    with col_p3:
        buff = st.number_input("Buffer (m)", value=0.1, key="gen_buff")
    with col_p4:
        plot_dim = st.text_input("Plot Size (W,H)", value="4,1", key="gen_plotdim")

    st.divider()

    # --- Main area: Map ---
    if ortho_path and os.path.exists(ortho_path):
        if 'current_gdf' not in st.session_state:
            st.info("👇 Draw a boundary polygon on the map below")
            st.warning("📐 **Please plot the four coordinates of the trial in the order: "
                       "top-left (B1R1) → top-right (BXR1) → bottom-right (BXRY) → bottom-left (B1RY).** "
                       "B and R refer to Banks and Rows. The first point you select will be adjacent to the "
                       "first plot i.e., B1R1 on the top-left of the trial design.")
            with rasterio.open(ortho_path) as src:
                bounds = src.bounds
                center_lon = (bounds.left + bounds.right) / 2
                center_lat = (bounds.bottom + bounds.top) / 2

            boundary_map = leafmap.Map(center=[center_lat, center_lon], zoom=19, draw_export=True)
            boundary_map.add_raster(ortho_path, layer_name="Orthomosaic", bands=[1, 2, 3])
            draw_control = Draw(
                export=True,
                draw_options={
                    'polyline': False, 'rectangle': True, 'polygon': True,
                    'circle': False, 'marker': False, 'circlemarker': False,
                },
                edit_options={'edit': True, 'remove': True},
            )
            boundary_map.add_child(draw_control)
            map_output = st_folium(boundary_map, height=600, width=1200, key="boundary_map")
        else:
            gdf = st.session_state['current_gdf']
            st.success(f"✅ Grid generated: {len(gdf)} plots")

            # Check if grid parameters changed since last generation
            current_params = (nc, nr, buff, plot_dim)
            last_params = st.session_state.get('last_grid_params', None)
            if (last_params is not None and current_params != last_params
                    and 'gen_boundary_coords' in st.session_state):
                stored_coords = st.session_state['gen_boundary_coords']
                with rasterio.open(ortho_path) as src:
                    lon, lat = src.lnglat()
                    zone = int((lon + 180) / 6) + 1
                    dst_crs = f"EPSG:327{zone}"
                transformer = Transformer.from_crs("EPSG:4326", dst_crs, always_xy=True)
                pts_utm = [np.array(transformer.transform(c[0], c[1])) for c in stored_coords]
                df = pd.read_csv(csv_path) if csv_path and os.path.exists(csv_path) else None
                try:
                    polys, rows_data = generate_plots(pts_utm, nc, nr, buff, plot_dim, df)
                    new_gdf = gpd.GeoDataFrame(rows_data, crs=dst_crs, geometry=polys)
                    st.session_state['current_gdf'] = new_gdf.to_crs("EPSG:4326")
                    st.session_state['last_grid_params'] = current_params
                    gdf = st.session_state['current_gdf']
                except Exception:
                    pass

            centroid = gdf.geometry.centroid.iloc[0]
            preview_map = leafmap.Map(center=[centroid.y, centroid.x], zoom=19)
            preview_map.add_raster(ortho_path, layer_name="Orthomosaic", bands=[1, 2, 3])
            preview_map.add_gdf(
                gdf, layer_name="Generated Plots",
                style={'color': 'red', 'fillOpacity': 0.1, 'weight': 2},
                info_mode='on_hover',
            )
            st_folium(preview_map, height=600, width=1200, key="preview_map")

            st.dataframe(gdf.drop(columns=['geometry']).head(10), width='stretch')
    else:
        st.warning("⚠️ Please select your project folder and orthomosaic file")

    # --- Action buttons (below the map) ---
    st.subheader("3. Actions")
    col_gen, col_clear, col_edit, col_save, col_bnd = st.columns(5)
    with col_gen:
        generate_btn = st.button("📐 Generate Grid", type="primary", width='stretch')
    with col_clear:
        clear_btn = st.button("🗑️ Clear Grid", width='stretch',
                              disabled='current_gdf' not in st.session_state)
    with col_edit:
        edit_grid_btn = st.button("✏️ Edit Grid", width='stretch',
                                  disabled='current_gdf' not in st.session_state)
    with col_save:
        save_grid_btn = st.button("💾 Save Initial Grid", width='stretch',
                                  disabled='current_gdf' not in st.session_state)
    with col_bnd:
        save_boundary_btn = st.button("💾 Save Trial Boundary", width='stretch',
                                      disabled='boundary_gdf' not in st.session_state)

    # --- Handle Clear Grid button ---
    if clear_btn:
        for k in ('boundary_gdf', 'current_gdf', 'gen_boundary_coords'):
            st.session_state.pop(k, None)
        st.rerun()

    # --- Generate grid logic ---
    if generate_btn:
        if 'map_output' in locals() and map_output and map_output.get("all_drawings"):
            draw_data = map_output.get("all_drawings")
            if draw_data:
                coords = []
                last_drawing = draw_data[-1]
                if last_drawing['geometry']['type'] == 'Polygon':
                    coords = last_drawing['geometry']['coordinates'][0][:4]
                if len(coords) >= 4:
                    boundary_poly = Polygon(coords)
                    st.session_state['boundary_gdf'] = gpd.GeoDataFrame(
                        {'id': [1], 'type': ['trial_boundary']},
                        crs="EPSG:4326", geometry=[boundary_poly],
                    )
                    st.session_state['gen_boundary_coords'] = coords[:4]

                    with rasterio.open(ortho_path) as src:
                        lon, lat = src.lnglat()
                        zone = int((lon + 180) / 6) + 1
                        dst_crs = f"EPSG:327{zone}"
                    transformer = Transformer.from_crs("EPSG:4326", dst_crs, always_xy=True)
                    pts_utm = [np.array(transformer.transform(c[0], c[1])) for c in coords[:4]]
                    df = pd.read_csv(csv_path) if csv_path and os.path.exists(csv_path) else None
                    polys, rows_data = generate_plots(pts_utm, nc, nr, buff, plot_dim, df)
                    gdf = gpd.GeoDataFrame(rows_data, crs=dst_crs, geometry=polys)
                    st.session_state['current_gdf'] = gdf.to_crs("EPSG:4326")
                    st.session_state['gen_ortho_path'] = ortho_path
                    st.session_state['last_grid_params'] = (nc, nr, buff, plot_dim)
                    st.success(f"✅ Generated {len(gdf)} plots!")
                    st.rerun()
                else:
                    st.error("Need at least 4 corners")
            else:
                st.error("Please draw a boundary polygon first")
        elif 'current_gdf' in st.session_state:
            st.warning("Grid already generated. Clear it first to regenerate.")
        else:
            st.error("Please draw a boundary polygon on the map first")

    # --- Edit Grid button ---
    if edit_grid_btn and 'current_gdf' in st.session_state:
        grid_directory = os.path.dirname(ortho_path) if ortho_path else os.getcwd()
        port = _ensure_save_server(grid_directory)
        html_out = os.path.abspath("editable_grid_map.html")
        with st.spinner("Creating editable map…"):
            create_editable_html(
                st.session_state['current_gdf'], html_out,
                st.session_state.get('gen_ortho_path', ortho_path),
                save_directory=grid_directory,
                server_port=port,
            )
        st.session_state['html_map_path'] = html_out
        st.session_state['grid_directory'] = grid_directory
        st.session_state['save_server_port'] = port
        webbrowser.open('file://' + html_out)
        st.success("✅ Editable map opened in browser!")
        st.info(f"""
**Editing tools in the browser:**
- 🖐️ **Drag Plots** (D) – click and drag any plot to reposition
- ✏️ **Edit Vertices** (V) – reshape plot corners
- 🗑️ **Delete** (X) – click any plot to remove it
- ➕ **Draw New** (N) – click to place vertices, double-click or click first vertex to close
- ↩️ **Undo** (Ctrl+Z)
- **Esc** = Navigate mode

**💾 Save Shapefile** writes directly to:
`{grid_directory}/edited_grid.shp`
(no GeoJSON import step needed)
        """)

    # Save initial grid
    if save_grid_btn and 'current_gdf' in st.session_state and ortho_path:
        out_shp = ortho_path.replace(".tif", "_initial_grid.shp")
        st.session_state['current_gdf'].to_file(out_shp)
        st.success(f"✅ Initial grid saved: {out_shp}")

    # Save trial boundary
    if save_boundary_btn and 'boundary_gdf' in st.session_state and ortho_path:
        out_boundary = ortho_path.replace(".tif", "_trial_boundary.shp")
        st.session_state['boundary_gdf'].to_file(out_boundary)
        st.success(f"✅ Trial boundary saved: {out_boundary}")


# ========================  TAB 2  ========================
with tab2:
    st.header("Edit Existing Grid")

    st.markdown("""
    **Workflow:** Load grid + orthomosaic → open editable map → drag / edit / delete →
    click **💾 Save Shapefile** in the browser → done. Shapefile is written directly.
    """)
    st.divider()

    # --- Step 1: Load files ---
    st.subheader("Step 1 – Load Files")

    # Check for completed dialogs
    if browse_file_async("edit_grid", "edit_grid_path"):
        grid_path = st.session_state['edit_grid_path']
        if grid_path and os.path.exists(grid_path):
            st.session_state['edit_gdf'] = gpd.read_file(grid_path).to_crs("EPSG:4326")
            st.rerun()
    if browse_file_async("edit_ortho", "edit_ortho_path"):
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📂 Load Grid Shapefile", width='stretch'):
            _launch_dialog("file", "edit_grid", title="Select grid shapefile",
                          filetypes=[("Shapefiles", "*.shp"), ("All files", "*.*")])
            st.toast("📂 File picker opened...")
    with col2:
        if st.button("🗺️ Load Orthomosaic", width='stretch'):
            _launch_dialog("file", "edit_ortho", title="Select orthomosaic TIF",
                          filetypes=[("GeoTIFF", "*.tif"), ("All files", "*.*")])
            st.toast("📂 File picker opened...")

    # Auto-refresh to pick up dialog results
    if (f'_dialog_pending_edit_grid' in st.session_state or
        f'_dialog_pending_edit_ortho' in st.session_state):
        import time; time.sleep(1)
        st.rerun()

    status_cols = st.columns(2)
    with status_cols[0]:
        if 'edit_gdf' in st.session_state:
            st.info(f"✅ Grid: {len(st.session_state['edit_gdf'])} plots loaded")
        else:
            st.warning("⚠️ Grid not loaded")
    with status_cols[1]:
        if 'edit_ortho_path' in st.session_state:
            st.info(f"✅ Ortho: {os.path.basename(st.session_state['edit_ortho_path'])}")
        else:
            st.warning("⚠️ Orthomosaic not loaded")

    st.divider()

    # --- Step 2: Create editable map ---
    st.subheader("Step 2 – Open Editable Map")
    files_ready = 'edit_gdf' in st.session_state and 'edit_ortho_path' in st.session_state

    if not files_ready:
        st.warning("⚠️ Please load both grid shapefile and orthomosaic first")

    if st.button("🗺️ Create & Open Editable Map", type="primary",
                 width='stretch', disabled=not files_ready):
        grid_directory = os.path.dirname(st.session_state['edit_ortho_path'])
        port = _ensure_save_server(grid_directory)
        html_out = os.path.abspath("editable_grid_map.html")
        with st.spinner("Creating editable map with orthomosaic…"):
            create_editable_html(
                st.session_state['edit_gdf'], html_out,
                st.session_state['edit_ortho_path'],
                save_directory=grid_directory,
                server_port=port,
            )
        st.session_state['html_map_path'] = html_out
        st.session_state['grid_directory'] = grid_directory
        st.session_state['save_server_port'] = port
        webbrowser.open('file://' + html_out)
        st.success(f"""✅ Map opened in browser!

**💾 Save Shapefile** in the browser writes directly to:
`{grid_directory}/edited_grid.shp`
        """)

    if 'html_map_path' in st.session_state and os.path.exists(st.session_state['html_map_path']):
        if st.button("🔄 Re-open Map in Browser", width='stretch'):
            webbrowser.open('file://' + st.session_state['html_map_path'])

    # --- Current grid stats + viewer ---
    if 'edit_gdf' in st.session_state:
        st.divider()
        st.subheader("Current Grid Data")
        gdf = st.session_state['edit_gdf']
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Plots", len(gdf))
        with col2:
            bounds = gdf.total_bounds
            st.metric("Coverage", f"{(bounds[2]-bounds[0]):.4f}° × {(bounds[3]-bounds[1]):.4f}°")

        # Viewer map
        st.divider()
        st.subheader("Grid Preview")
        st.info("ℹ️ This is a read-only preview. To edit the polygons, open the editable map from **Step 2** above.")
        if 'edit_ortho_path' in st.session_state and os.path.exists(st.session_state['edit_ortho_path']):
            centroid = gdf.geometry.centroid.iloc[0]
            viewer_map = leafmap.Map(center=[centroid.y, centroid.x], zoom=19)
            viewer_map.add_raster(
                st.session_state['edit_ortho_path'],
                layer_name="Orthomosaic", bands=[1, 2, 3],
            )
            viewer_map.add_gdf(
                gdf, layer_name="Edited Plots",
                style={'color': 'red', 'fillOpacity': 0.1, 'weight': 2},
                info_mode='on_hover',
            )
            st_folium(viewer_map, height=600, width=1200, key="edit_viewer_map")
        else:
            st.warning("⚠️ Load an orthomosaic in Step 1 to see the grid preview.")

        st.dataframe(gdf.drop(columns=['geometry']).head(20), width='stretch')
    else:
        st.info("👆 Load a grid shapefile to begin editing")

# ========================  TAB 3 – CONVERT FILE  ========================
with tab3:
    st.header("Convert Vector File")
    st.markdown("Convert between **Shapefile**, **GeoJSON**, **KML**, **GeoPackage (GPKG)**, and **HDF5** formats with optional CRS reprojection.")

    # --- Australian UTM zones ---
    aus_crs_options = {
        "Source file CRS (no reprojection)": None,
        "WGS 84 (EPSG:4326)": "EPSG:4326",
        "GDA2020 / MGA Zone 49 (EPSG:7849)": "EPSG:7849",
        "GDA2020 / MGA Zone 50 (EPSG:7850)": "EPSG:7850",
        "GDA2020 / MGA Zone 51 (EPSG:7851)": "EPSG:7851",
        "GDA2020 / MGA Zone 52 (EPSG:7852)": "EPSG:7852",
        "GDA2020 / MGA Zone 53 (EPSG:7853)": "EPSG:7853",
        "GDA2020 / MGA Zone 54 (EPSG:7854)": "EPSG:7854",
        "GDA2020 / MGA Zone 55 (EPSG:7855)": "EPSG:7855",
        "GDA2020 / MGA Zone 56 (EPSG:7856)": "EPSG:7856",
        "GDA94 / MGA Zone 49 (EPSG:28349)": "EPSG:28349",
        "GDA94 / MGA Zone 50 (EPSG:28350)": "EPSG:28350",
        "GDA94 / MGA Zone 51 (EPSG:28351)": "EPSG:28351",
        "GDA94 / MGA Zone 52 (EPSG:28352)": "EPSG:28352",
        "GDA94 / MGA Zone 53 (EPSG:28353)": "EPSG:28353",
        "GDA94 / MGA Zone 54 (EPSG:28354)": "EPSG:28354",
        "GDA94 / MGA Zone 55 (EPSG:28355)": "EPSG:28355",
        "GDA94 / MGA Zone 56 (EPSG:28356)": "EPSG:28356",
    }

    output_formats = {
        "Shapefile (.shp)": "shp",
        "GeoJSON (.geojson)": "geojson",
        "GeoPackage (.gpkg)": "gpkg",
        "KML (.kml)": "kml",
    }

    col_in, col_out = st.columns(2)

    with col_in:
        st.subheader("Input File")

        # Check for completed dialog
        if browse_file_async("conv_in", "conv_input_path"):
            st.rerun()

        if st.button("📂 Browse Input File", key="conv_browse_in", width='stretch'):
            _launch_dialog("file", "conv_in", title="Select vector file",
                          filetypes=[("All supported", "*.shp *.geojson *.json *.gpkg *.kml *.h5 *.hdf5"),
                                     ("Shapefiles", "*.shp"), ("GeoJSON", "*.geojson *.json"),
                                     ("GeoPackage", "*.gpkg"), ("KML", "*.kml"), ("HDF5", "*.h5 *.hdf5"),
                                     ("All files", "*.*")])
            st.toast("📂 File picker opened...")

        if 'conv_input_path' in st.session_state:
            in_path = st.session_state['conv_input_path']
            st.info(f"📄 `{os.path.basename(in_path)}`")
            try:
                ext = os.path.splitext(in_path)[1].lower()
                if ext in ('.h5', '.hdf5'):
                    conv_gdf = gpd.read_file(in_path, engine="pyopenscience" if ext == '.h5' else None)
                else:
                    conv_gdf = gpd.read_file(in_path)
                st.success(f"✅ {len(conv_gdf)} features loaded | CRS: `{conv_gdf.crs}`")
                st.dataframe(conv_gdf.drop(columns=['geometry']).head(10), width='stretch')
                st.session_state['conv_gdf'] = conv_gdf
            except Exception as e:
                st.error(f"❌ Failed to read file: {e}")

    with col_out:
        st.subheader("Output Settings")
        sel_format = st.selectbox("Output Format", list(output_formats.keys()), key="conv_format")
        sel_crs = st.selectbox("Coordinate System", list(aus_crs_options.keys()), key="conv_crs")

        custom_crs = st.text_input("Or enter custom EPSG code (e.g. EPSG:32750):", key="conv_custom_crs")

        st.subheader("Save Location")

        # Check for completed dialog
        if browse_folder_async("conv_save", "conv_save_folder"):
            st.rerun()

        if st.button("📂 Choose Save Folder", key="conv_browse_out", width='stretch'):
            _launch_dialog("folder", "conv_save")
            st.toast("📂 Folder picker opened...")

        if 'conv_save_folder' in st.session_state:
            st.info(f"📁 `{st.session_state['conv_save_folder']}`")

        conv_filename = st.text_input("Output filename (without extension):", value="converted", key="conv_filename")

    st.divider()

    conv_ready = ('conv_gdf' in st.session_state and 'conv_save_folder' in st.session_state and conv_filename)
    if st.button("🔄 Convert & Save", type="primary", width='stretch', disabled=not conv_ready):
        gdf_out = st.session_state['conv_gdf'].copy()

        # Determine target CRS
        target_crs = None
        if custom_crs.strip():
            target_crs = custom_crs.strip()
        else:
            target_crs = aus_crs_options[sel_crs]

        if target_crs is not None:
            try:
                gdf_out = gdf_out.to_crs(target_crs)
                st.info(f"Reprojected to `{target_crs}`")
            except Exception as e:
                st.error(f"❌ CRS reprojection failed: {e}")
                st.stop()

        out_ext = output_formats[sel_format]
        out_path = os.path.join(st.session_state['conv_save_folder'], f"{conv_filename}.{out_ext}")

        try:
            if out_ext == "shp":
                gdf_out.to_file(out_path)
            elif out_ext == "geojson":
                gdf_out.to_file(out_path, driver="GeoJSON")
            elif out_ext == "gpkg":
                gdf_out.to_file(out_path, driver="GPKG")
            elif out_ext == "kml":
                # KML requires WGS84
                if gdf_out.crs and str(gdf_out.crs) != "EPSG:4326":
                    gdf_out = gdf_out.to_crs("EPSG:4326")
                import fiona
                fiona.supported_drivers['KML'] = 'rw'
                gdf_out.to_file(out_path, driver="KML")

            st.success(f"✅ File saved: `{out_path}` ({len(gdf_out)} features)")
        except Exception as e:
            st.error(f"❌ Save failed: {e}")

    if not conv_ready:
        st.warning("⚠️ Load an input file, choose a save folder, and provide a filename to convert.")


# ========================  TAB 4 – CROPPING TOOL  ========================
with tab4:
    st.header("Crop Raster by Vector Boundaries")
    st.markdown("""
    Crop an orthophoto, DSM, or any raster file using polygon boundaries.
    - **Single polygon** (e.g. trial boundary) → saves one cropped raster.
    - **Multiple polygons** (e.g. plot grid) → saves one raster per polygon, named with the Plot_ID.
    """)

    col_vec, col_ras = st.columns(2)

    with col_vec:
        st.subheader("1. Vector Boundaries")

        # Check for completed dialog
        if browse_file_async("crop_vec", "crop_vec_path"):
            st.rerun()

        if st.button("📂 Load Shapefile / Vector", key="crop_browse_vec", width='stretch'):
            _launch_dialog("file", "crop_vec", title="Select vector boundary file",
                          filetypes=[("Shapefiles", "*.shp"), ("GeoJSON", "*.geojson"),
                                     ("GeoPackage", "*.gpkg"), ("All files", "*.*")])
            st.toast("📂 File picker opened...")

        if 'crop_vec_path' in st.session_state:
            vec_path = st.session_state['crop_vec_path']
            st.info(f"📄 `{os.path.basename(vec_path)}`")
            try:
                crop_gdf = gpd.read_file(vec_path)
                st.session_state['crop_gdf'] = crop_gdf
                st.success(f"✅ {len(crop_gdf)} polygon(s) loaded | CRS: `{crop_gdf.crs}`")
                if len(crop_gdf) == 1:
                    st.info("📌 Single polygon detected → will crop one raster.")
                else:
                    st.info(f"📌 {len(crop_gdf)} polygons detected → will crop one raster per polygon.")
            except Exception as e:
                st.error(f"❌ Failed to read: {e}")

    with col_ras:
        st.subheader("2. Raster Data")

        # Check for completed dialog
        if browse_file_async("crop_ras", "crop_ras_path"):
            st.rerun()

        if st.button("📂 Load Raster (TIF)", key="crop_browse_ras", width='stretch'):
            _launch_dialog("file", "crop_ras", title="Select raster file",
                          filetypes=[("GeoTIFF", "*.tif *.tiff"), ("All rasters", "*.tif *.tiff *.img *.vrt"),
                                     ("All files", "*.*")])
            st.toast("📂 File picker opened...")

        if 'crop_ras_path' in st.session_state:
            ras_path = st.session_state['crop_ras_path']
            st.info(f"🗺️ `{os.path.basename(ras_path)}`")
            try:
                with rasterio.open(ras_path) as src:
                    st.success(f"✅ Raster: {src.width}×{src.height}px, {src.count} band(s), CRS: `{src.crs}`")
            except Exception as e:
                st.error(f"❌ Failed to read: {e}")

    st.divider()

    st.subheader("3. Output Settings")
    col_save, col_name = st.columns(2)
    with col_save:
        # Check for completed dialog
        if browse_folder_async("crop_save", "crop_save_dir"):
            st.rerun()

        if st.button("📂 Choose Save Folder", key="crop_browse_save", width='stretch'):
            _launch_dialog("folder", "crop_save")
            st.toast("📂 Folder picker opened...")
        if 'crop_save_dir' in st.session_state:
            st.info(f"📁 `{st.session_state['crop_save_dir']}`")

    with col_name:
        crop_filename = st.text_input("Base filename (without extension):", value="cropped", key="crop_filename")

    st.divider()

    crop_ready = (
        'crop_gdf' in st.session_state
        and 'crop_ras_path' in st.session_state
        and 'crop_save_dir' in st.session_state
        and crop_filename
    )

    if st.button("✂️ Crop and Save", type="primary", width='stretch', disabled=not crop_ready):
        crop_gdf = st.session_state['crop_gdf']
        ras_path = st.session_state['crop_ras_path']
        save_dir = st.session_state['crop_save_dir']

        with rasterio.open(ras_path) as src:
            ras_crs = src.crs

            # Reproject vector to match raster CRS if needed
            if crop_gdf.crs != ras_crs:
                crop_gdf_proj = crop_gdf.to_crs(ras_crs)
                st.info(f"Reprojected vector from `{crop_gdf.crs}` to `{ras_crs}`")
            else:
                crop_gdf_proj = crop_gdf

            n_polys = len(crop_gdf_proj)
            progress = st.progress(0, text="Cropping...")
            saved_files = []
            errors = []

            for idx, row in crop_gdf_proj.iterrows():
                geom = row.geometry
                if geom is None or geom.is_empty:
                    continue

                # Determine filename
                if n_polys == 1:
                    out_name = f"{crop_filename}.tif"
                else:
                    # Try to get Plot_ID
                    plot_id = row.get('Plot_ID', None)
                    if plot_id is None:
                        plot_id = row.get('Plot', None)
                    if plot_id is None:
                        plot_id = idx
                    out_name = f"{crop_filename}_{plot_id}.tif"

                out_path = os.path.join(save_dir, out_name)

                try:
                    shapes = [mapping(geom)]
                    # Determine a safe nodata value that won't collide with real pixel data
                    src_nodata = src.nodata
                    dtype = src.dtypes[0]
                    if src_nodata is not None:
                        fill_nodata = src_nodata
                    elif dtype in ('uint8',):
                        fill_nodata = 255
                    elif dtype in ('uint16',):
                        fill_nodata = 65535
                    elif dtype in ('int16',):
                        fill_nodata = -9999
                    elif dtype in ('float32', 'float64'):
                        fill_nodata = float('nan')
                    else:
                        fill_nodata = 0

                    out_image, out_transform = rasterio_mask(
                        src, shapes, crop=True, all_touched=True,
                        nodata=fill_nodata)

                    out_meta = src.meta.copy()
                    out_meta.update({
                        "driver": "GTiff",
                        "height": out_image.shape[1],
                        "width": out_image.shape[2],
                        "transform": out_transform,
                        "nodata": fill_nodata,
                    })

                    with rasterio.open(out_path, "w", **out_meta) as dest:
                        dest.write(out_image)

                    saved_files.append(out_name)
                except Exception as e:
                    errors.append(f"{out_name}: {e}")

                progress.progress((idx + 1) / n_polys, text=f"Cropping {idx + 1}/{n_polys}...")

            progress.empty()

            if saved_files:
                st.success(f"✅ Successfully saved {len(saved_files)} cropped raster(s) to `{save_dir}`")
                with st.expander("Saved files", expanded=False):
                    for f in saved_files:
                        st.text(f"  📄 {f}")

            if errors:
                st.error(f"❌ {len(errors)} error(s) occurred:")
                for e in errors:
                    st.text(f"  ⚠️ {e}")

    if not crop_ready:
        st.warning("⚠️ Load a vector boundary, a raster file, choose a save folder, and provide a base filename.")

# --- Global polling for any pending file dialogs ---
_any_pending = any(k.startswith('_dialog_pending_') for k in st.session_state)
if _any_pending:
    import time
    time.sleep(1)
    st.rerun()