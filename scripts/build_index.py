#!/usr/bin/env python3
"""
Generate location index for SSL4EO-L dataset.
Scans all samples and creates a JSON file mapping sample_id -> [lat, lon].
Run this once after downloading to enable the map-click-to-nearest-sample feature.

Uses thread pool for speed (~20 workers).
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import rasterio
from rasterio.warp import transform_bounds


def get_sample_center(sample_dir_str):
    """Get center coordinates for a sample by reading its first GeoTIFF."""
    sample_dir = Path(sample_dir_str)
    sample_id = sample_dir.name

    for ts_dir in sample_dir.iterdir():
        if ts_dir.is_dir():
            tif_path = ts_dir / "all_bands.tif"
            if tif_path.exists():
                try:
                    with rasterio.open(tif_path) as src:
                        bounds = src.bounds
                        crs = src.crs
                        lon_min, lat_min, lon_max, lat_max = transform_bounds(
                            crs, 'EPSG:4326',
                            bounds.left, bounds.bottom, bounds.right, bounds.top
                        )
                        center_lat = (lat_min + lat_max) / 2
                        center_lon = (lon_min + lon_max) / 2
                        return sample_id, [center_lat, center_lon], None
                except Exception as e:
                    return sample_id, None, str(e)

    return sample_id, None, "No valid GeoTIFF"


def main():
    parser = argparse.ArgumentParser(description='Generate location index for SSL4EO-L')
    parser.add_argument('--root', type=str, default='./data',
                        help='Root directory containing the dataset')
    parser.add_argument('--split', type=str, default='ssl4eo_l_oli_sr',
                        help='Dataset split to use')
    parser.add_argument('--output', type=str, default=None,
                        help='Output JSON file path (default: <root>/locations.json)')
    parser.add_argument('--workers', type=int, default=20,
                        help='Number of parallel workers')

    args = parser.parse_args()

    data_dir = Path(args.root) / args.split
    output_path = Path(args.output) if args.output else Path(args.root) / "locations.json"

    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        sys.exit(1)

    # Get all sample directories
    sample_dirs = [str(d) for d in data_dir.iterdir() if d.is_dir()]
    total = len(sample_dirs)
    print(f"Found {total} samples. Processing with {args.workers} workers...")

    # Build location index in parallel
    location_index = {}
    errors = []
    completed = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(get_sample_center, d): d for d in sample_dirs}

        for future in as_completed(futures):
            sample_id, coords, error = future.result()
            completed += 1

            if coords:
                location_index[sample_id] = coords
            elif error:
                errors.append(f"{sample_id}: {error}")

            # Print progress every 5000 samples
            if completed % 5000 == 0 or completed == total:
                print(f"Progress: {completed}/{total} ({100*completed//total}%)")

    # Save to JSON
    with open(output_path, 'w') as f:
        json.dump(location_index, f)

    print(f"Done! Indexed {len(location_index)} samples -> {output_path}")

    if errors:
        print(f"Warnings: {len(errors)} samples had issues")


if __name__ == '__main__':
    main()
