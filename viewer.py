#!/usr/bin/env python3
"""
Interactive GeoTIFF Viewer for SSL4EO-L Dataset
Flask server with Leaflet.js frontend for viewing satellite imagery on a map.
"""

import argparse
import json
import math
import os
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from flask import Flask, jsonify, request, send_file, Response
from PIL import Image

app = Flask(__name__)

# Configuration - will be set via command line
DATA_ROOT = None
SPLIT = "ssl4eo_l_oli_sr"

# Cache for sample list (avoid re-scanning filesystem)
_sample_cache = None

# Location index for nearest-sample queries
_location_index = None


def load_location_index():
    """Load pre-computed location index from JSON file."""
    global _location_index
    index_path = Path(DATA_ROOT) / "locations.json"
    if index_path.exists():
        with open(index_path) as f:
            _location_index = json.load(f)
        print(f"Loaded location index: {len(_location_index)} samples")
    else:
        print(f"Warning: Location index not found at {index_path}")
        print("Map click feature will be disabled. Run: python scripts/build_index.py")
        _location_index = {}


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in kilometers using Haversine formula."""
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def get_sample_ids():
    """Get list of all sample IDs from the data directory."""
    global _sample_cache
    if _sample_cache is None:
        data_dir = Path(DATA_ROOT) / SPLIT
        if data_dir.exists():
            _sample_cache = sorted([d.name for d in data_dir.iterdir() if d.is_dir()])
        else:
            _sample_cache = []
    return _sample_cache


def get_sample_info(sample_id):
    """Get metadata for a specific sample (timestamps with seasons and bounds)."""
    sample_dir = Path(DATA_ROOT) / SPLIT / sample_id
    if not sample_dir.exists():
        return None

    timestamps = []
    bounds_info = None

    for ts_dir in sorted(sample_dir.iterdir()):
        if ts_dir.is_dir():
            tif_path = ts_dir / "all_bands.tif"
            if tif_path.exists():
                ts_name = ts_dir.name
                # Extract date part (last 8 chars) for season calculation
                date_match_str = ts_name[-8:] if len(ts_name) >= 8 else ts_name
                season = get_season(date_match_str) if date_match_str.isdigit() else "Unknown"
                timestamps.append({
                    'name': ts_name,
                    'season': season
                })

                # Get bounds from first file
                if bounds_info is None:
                    with rasterio.open(tif_path) as src:
                        bounds = src.bounds
                        crs = src.crs
                        # Convert to lat/lon
                        lon_min, lat_min, lon_max, lat_max = transform_bounds(
                            crs, 'EPSG:4326',
                            bounds.left, bounds.bottom, bounds.right, bounds.top
                        )
                        bounds_info = {
                            'lat_min': lat_min,
                            'lat_max': lat_max,
                            'lon_min': lon_min,
                            'lon_max': lon_max,
                            'center_lat': (lat_min + lat_max) / 2,
                            'center_lon': (lon_min + lon_max) / 2
                        }

    return {
        'sample_id': sample_id,
        'timestamps': timestamps,
        'bounds': bounds_info
    }


@lru_cache(maxsize=256)
def generate_rgb_png_cached(tif_path_str):
    """Read GeoTIFF and generate RGB PNG with percentile normalization.

    Cached version - returns PNG bytes and bounds tuple for efficient re-requests.
    """
    with rasterio.open(tif_path_str) as src:
        # Read all bands
        data = src.read()

        # Extract RGB bands (Landsat: B4=Red, B3=Green, B2=Blue -> indices 3,2,1)
        rgb_indices = [3, 2, 1]
        rgb = np.stack([data[i] for i in rgb_indices], axis=0).astype(np.float32)

        # Percentile normalization
        p2, p98 = np.percentile(rgb, (2, 98))
        rgb_norm = np.clip((rgb - p2) / (p98 - p2 + 1e-8), 0, 1)
        rgb_norm = (rgb_norm * 255).astype(np.uint8)

        # Convert to PIL Image (H, W, C)
        img = Image.fromarray(np.transpose(rgb_norm, (1, 2, 0)))

        # Get bounds for the response
        bounds = src.bounds
        crs = src.crs
        lon_min, lat_min, lon_max, lat_max = transform_bounds(
            crs, 'EPSG:4326',
            bounds.left, bounds.bottom, bounds.right, bounds.top
        )

        # Convert to PNG bytes for caching
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        png_bytes = buffer.getvalue()

        # Return as tuple (hashable for cache key comparison)
        return png_bytes, (lat_min, lat_max, lon_min, lon_max)


def get_season(date_str):
    """Return season name from YYYYMMDD date string (Northern Hemisphere convention)."""
    month = int(date_str[4:6])
    if month in (12, 1, 2):
        return "Winter"
    elif month in (3, 4, 5):
        return "Spring"
    elif month in (6, 7, 8):
        return "Summer"
    else:
        return "Fall"


# ============== API Routes ==============

@app.route('/api/samples')
def api_samples():
    """Return list of all sample IDs."""
    samples = get_sample_ids()
    return jsonify({'samples': samples, 'count': len(samples)})


@app.route('/api/sample/<sample_id>')
def api_sample_info(sample_id):
    """Return metadata for a specific sample."""
    info = get_sample_info(sample_id)
    if info is None:
        return jsonify({'error': 'Sample not found'}), 404
    return jsonify(info)


@app.route('/api/tile/<sample_id>/<timestamp>')
def api_tile(sample_id, timestamp):
    """Return RGB PNG for a specific sample and timestamp."""
    tif_path = Path(DATA_ROOT) / SPLIT / sample_id / timestamp / "all_bands.tif"

    if not tif_path.exists():
        return jsonify({'error': 'File not found'}), 404

    try:
        # Use cached function (returns PNG bytes and bounds tuple)
        png_bytes, bounds_tuple = generate_rgb_png_cached(str(tif_path))
        lat_min, lat_max, lon_min, lon_max = bounds_tuple

        response = send_file(BytesIO(png_bytes), mimetype='image/png')
        # Add bounds as headers for the frontend
        response.headers['X-Bounds-LatMin'] = str(lat_min)
        response.headers['X-Bounds-LatMax'] = str(lat_max)
        response.headers['X-Bounds-LonMin'] = str(lon_min)
        response.headers['X-Bounds-LonMax'] = str(lon_max)
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/nearest')
def api_nearest():
    """Find the nearest sample to a given lat/lon coordinate."""
    if not _location_index:
        return jsonify({'error': 'Location index not loaded. Run: python scripts/build_index.py'}), 503

    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid lat/lon parameters'}), 400

    # Find nearest sample using Haversine distance
    nearest_id = None
    min_distance = float('inf')

    for sample_id, coords in _location_index.items():
        sample_lat, sample_lon = coords
        dist = haversine_distance(lat, lon, sample_lat, sample_lon)
        if dist < min_distance:
            min_distance = dist
            nearest_id = sample_id

    if nearest_id is None:
        return jsonify({'error': 'No samples in index'}), 404

    return jsonify({
        'sample_id': nearest_id,
        'distance_km': min_distance,
        'sample_lat': _location_index[nearest_id][0],
        'sample_lon': _location_index[nearest_id][1]
    })


# ============== HTML Frontend ==============

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSL4EO-L GeoTIFF Viewer</title>

    <!-- Leaflet CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />

    <!-- Select2 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet" />

    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        #header {
            background: #1a1a2e;
            color: white;
            padding: 12px 20px;
            display: flex;
            align-items: center;
            gap: 20px;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 1000;
            height: 60px;
        }

        #header h1 {
            font-size: 18px;
            font-weight: 500;
        }

        #sample-select-container {
            flex: 1;
            max-width: 400px;
        }

        #sample-select {
            width: 100%;
        }

        .select2-container--default .select2-selection--single {
            height: 36px;
            border-radius: 4px;
        }

        .select2-container--default .select2-selection--single .select2-selection__rendered {
            line-height: 36px;
        }

        .select2-container--default .select2-selection--single .select2-selection__arrow {
            height: 34px;
        }

        #info-panel {
            background: rgba(255,255,255,0.95);
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 13px;
            color: #333;
        }

        #opacity-control {
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(255,255,255,0.95);
            padding: 8px 12px;
            border-radius: 4px;
            color: #333;
        }

        #opacity-control label {
            font-size: 13px;
            white-space: nowrap;
        }

        #opacity-slider {
            width: 120px;
            cursor: pointer;
        }

        #opacity-value {
            font-size: 13px;
            min-width: 40px;
        }

        #map {
            position: fixed;
            top: 60px;
            left: 0;
            right: 0;
            bottom: 0;
        }

        .loading-overlay {
            position: fixed;
            top: 60px;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 999;
            color: white;
            font-size: 18px;
        }

        .hidden {
            display: none !important;
        }

        .leaflet-control-layers {
            max-height: calc(100vh - 100px);
            overflow-y: auto;
        }
    </style>
</head>
<body>
    <div id="header">
        <h1>SSL4EO-L Viewer</h1>
        <div id="sample-select-container">
            <select id="sample-select">
                <option value="">Select a sample...</option>
            </select>
        </div>
        <div id="opacity-control">
            <label for="opacity-slider">Opacity:</label>
            <input type="range" id="opacity-slider" min="0" max="100" value="90">
            <span id="opacity-value">90%</span>
        </div>
        <div id="info-panel">
            <span id="sample-count">Loading samples...</span>
        </div>
    </div>

    <div id="map"></div>
    <div id="loading" class="loading-overlay hidden">Loading...</div>

    <!-- jQuery (required for Select2) -->
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>

    <!-- Select2 JS -->
    <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>

    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

    <script>
        // Initialize map
        const map = L.map('map').setView([0, 0], 2);

        // Satellite basemap (Esri World Imagery)
        const satelliteLayer = L.tileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            {
                attribution: 'Esri, Maxar, Earthstar Geographics',
                maxZoom: 19
            }
        ).addTo(map);

        // OpenStreetMap as alternative
        const osmLayer = L.tileLayer(
            'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            {
                attribution: '&copy; OpenStreetMap contributors',
                maxZoom: 19
            }
        );

        // Layer control for base maps
        const baseMaps = {
            "Satellite": satelliteLayer,
            "OpenStreetMap": osmLayer
        };

        // Overlay layers (will be populated when sample is loaded)
        let overlayLayers = {};
        let layerControl = L.control.layers(baseMaps, overlayLayers).addTo(map);
        let currentOverlays = [];

        // Loading indicator
        function showLoading(show) {
            document.getElementById('loading').classList.toggle('hidden', !show);
        }

        // Load sample list
        async function loadSamples() {
            try {
                const response = await fetch('/api/samples');
                const data = await response.json();

                document.getElementById('sample-count').textContent =
                    `${data.count.toLocaleString()} samples`;

                // Populate select
                const select = document.getElementById('sample-select');
                data.samples.forEach(sample => {
                    const option = document.createElement('option');
                    option.value = sample;
                    option.textContent = sample;
                    select.appendChild(option);
                });

                // Initialize Select2 with search
                $('#sample-select').select2({
                    placeholder: 'Search or select a sample...',
                    allowClear: true,
                    width: '100%'
                });

            } catch (error) {
                console.error('Error loading samples:', error);
                document.getElementById('sample-count').textContent = 'Error loading samples';
            }
        }

        // Load and display sample
        async function loadSample(sampleId) {
            if (!sampleId) return;

            showLoading(true);

            try {
                // Clear existing overlays and revoke blob URLs to free memory
                currentOverlays.forEach(layer => {
                    if (layer._url) {
                        URL.revokeObjectURL(layer._url);
                    }
                    map.removeLayer(layer);
                });
                currentOverlays = [];

                // Remove old layer control and create new one
                map.removeControl(layerControl);
                overlayLayers = {};

                // Get sample info
                const infoResponse = await fetch(`/api/sample/${sampleId}`);
                const info = await infoResponse.json();

                if (info.error) {
                    alert('Sample not found: ' + info.error);
                    showLoading(false);
                    return;
                }

                // Zoom to sample bounds
                const bounds = info.bounds;
                map.fitBounds([
                    [bounds.lat_min, bounds.lon_min],
                    [bounds.lat_max, bounds.lon_max]
                ]);

                // Fetch all tiles in parallel for better performance
                const tilePromises = info.timestamps.map(ts =>
                    fetch(`/api/tile/${sampleId}/${ts.name}`)
                );
                const tileResponses = await Promise.all(tilePromises);

                // Process all responses
                const currentOpacity = document.getElementById('opacity-slider').value / 100;

                for (let i = 0; i < tileResponses.length; i++) {
                    const tileResponse = tileResponses[i];
                    const ts = info.timestamps[i];

                    const blob = await tileResponse.blob();
                    const imageUrl = URL.createObjectURL(blob);

                    // Get bounds from headers
                    const latMin = parseFloat(tileResponse.headers.get('X-Bounds-LatMin'));
                    const latMax = parseFloat(tileResponse.headers.get('X-Bounds-LatMax'));
                    const lonMin = parseFloat(tileResponse.headers.get('X-Bounds-LonMin'));
                    const lonMax = parseFloat(tileResponse.headers.get('X-Bounds-LonMax'));

                    // Create image overlay with current opacity
                    const overlay = L.imageOverlay(
                        imageUrl,
                        [[latMin, lonMin], [latMax, lonMax]],
                        { opacity: currentOpacity }
                    );

                    // Extract date from timestamp for label and include season
                    const tsName = ts.name;
                    const dateMatch = tsName.match(/\\d{8}$/);
                    const dateStr = dateMatch ? dateMatch[0] : tsName;
                    const formattedDate = dateStr.length === 8
                        ? `${dateStr.slice(0,4)}-${dateStr.slice(4,6)}-${dateStr.slice(6,8)}`
                        : dateStr;
                    const label = `${formattedDate} (${ts.season})`;

                    overlayLayers[label] = overlay;
                    currentOverlays.push(overlay);

                    // Show first layer by default
                    if (i === 0) {
                        overlay.addTo(map);
                    }
                }

                // Add new layer control
                layerControl = L.control.layers(baseMaps, overlayLayers).addTo(map);

            } catch (error) {
                console.error('Error loading sample:', error);
                alert('Error loading sample: ' + error.message);
            }

            showLoading(false);
        }

        // Event listener for sample selection
        $('#sample-select').on('change', function() {
            const sampleId = $(this).val();
            loadSample(sampleId);
        });

        // Opacity slider control
        document.getElementById('opacity-slider').addEventListener('input', function() {
            const opacity = this.value / 100;
            document.getElementById('opacity-value').textContent = this.value + '%';

            // Update opacity for all current overlays
            currentOverlays.forEach(overlay => {
                overlay.setOpacity(opacity);
            });
        });

        // Map click handler - find and load nearest sample
        map.on('click', async function(e) {
            const { lat, lng } = e.latlng;

            try {
                showLoading(true);
                document.getElementById('sample-count').textContent = 'Finding nearest sample...';

                const response = await fetch(`/api/nearest?lat=${lat}&lon=${lng}`);
                const data = await response.json();

                if (data.error) {
                    alert('Error finding nearest sample: ' + data.error);
                    document.getElementById('sample-count').textContent = `${$('#sample-select option').length - 1} samples`;
                    showLoading(false);
                    return;
                }

                // Update the selector to show the found sample
                $('#sample-select').val(data.sample_id).trigger('change.select2');

                // Load the sample
                await loadSample(data.sample_id);

                // Update info panel with distance
                const distKm = data.distance_km.toFixed(1);
                document.getElementById('sample-count').textContent =
                    `Sample ${data.sample_id} (${distKm} km away)`;

            } catch (error) {
                console.error('Error finding nearest sample:', error);
                alert('Error: ' + error.message);
                showLoading(false);
            }
        });

        // Initialize
        loadSamples();
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    """Serve the main HTML page."""
    return Response(HTML_TEMPLATE, mimetype='text/html')


# ============== Main ==============

def main():
    global DATA_ROOT, SPLIT

    parser = argparse.ArgumentParser(description='SSL4EO-L GeoTIFF Viewer')
    parser.add_argument('--root', type=str, default='./data',
                        help='Root directory containing the dataset')
    parser.add_argument('--split', type=str, default='ssl4eo_l_oli_sr',
                        help='Dataset split to use')
    parser.add_argument('--port', type=int, default=8080,
                        help='Port to run the server on')
    parser.add_argument('--host', type=str, default='127.0.0.1',
                        help='Host to bind to')

    args = parser.parse_args()

    DATA_ROOT = args.root
    SPLIT = args.split

    print(f"Starting SSL4EO-L GeoTIFF Viewer")
    print(f"  Data root: {DATA_ROOT}")
    print(f"  Split: {SPLIT}")
    print(f"  Server: http://{args.host}:{args.port}")
    print()

    # Load location index for map-click feature
    load_location_index()
    print()

    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == '__main__':
    main()
