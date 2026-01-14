#!/usr/bin/env python3
"""
Export SSL4EO-L samples as PNG images.
Generates RGB composites from GeoTIFF files for local viewing.

Usage:
    python scripts/export_samples.py --sample 0029460
    python scripts/export_samples.py --random 5
    python scripts/export_samples.py --sample 0029460 --output ./previews
"""

import argparse
import random
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image


def generate_rgb_png(tif_path: Path) -> Image.Image:
    """Read GeoTIFF and generate RGB image with percentile normalization."""
    with rasterio.open(tif_path) as src:
        data = src.read()

        # RGB bands (Landsat OLI: B4=Red, B3=Green, B2=Blue -> indices 3,2,1)
        rgb_indices = [3, 2, 1]
        rgb = np.stack([data[i] for i in rgb_indices], axis=0).astype(np.float32)

        # Percentile normalization (2-98%)
        p2, p98 = np.percentile(rgb, (2, 98))
        rgb_norm = np.clip((rgb - p2) / (p98 - p2 + 1e-8), 0, 1)
        rgb_norm = (rgb_norm * 255).astype(np.uint8)

        # Convert to PIL Image (H, W, C)
        return Image.fromarray(np.transpose(rgb_norm, (1, 2, 0)))


def get_season(date_str: str) -> str:
    """Return season name from YYYYMMDD date string."""
    month = int(date_str[4:6])
    if month in (12, 1, 2):
        return "winter"
    elif month in (3, 4, 5):
        return "spring"
    elif month in (6, 7, 8):
        return "summer"
    else:
        return "fall"


def export_sample(sample_dir: Path, output_dir: Path) -> list[Path]:
    """Export all timestamps for a sample as PNG files."""
    sample_id = sample_dir.name
    exported = []

    for ts_dir in sorted(sample_dir.iterdir()):
        if ts_dir.is_dir():
            tif_path = ts_dir / "all_bands.tif"
            if tif_path.exists():
                # Extract date and season from timestamp name
                ts_name = ts_dir.name
                date_str = ts_name[-8:] if len(ts_name) >= 8 else ts_name
                season = get_season(date_str) if date_str.isdigit() else "unknown"

                # Generate output filename
                output_name = f"{sample_id}_{season}_{date_str}.png"
                output_path = output_dir / output_name

                # Generate and save PNG
                img = generate_rgb_png(tif_path)
                img.save(output_path)
                exported.append(output_path)
                print(f"  Saved: {output_name}")

    return exported


def main():
    parser = argparse.ArgumentParser(
        description="Export SSL4EO-L samples as PNG images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export specific sample
  python scripts/export_samples.py --sample 0029460

  # Export 5 random samples
  python scripts/export_samples.py --random 5

  # Export to custom directory
  python scripts/export_samples.py --sample 0029460 --output ./previews

  # Export from different split
  python scripts/export_samples.py --sample 0029460 --split ssl4eo_l_etm_sr
        """
    )

    parser.add_argument(
        "--sample",
        type=str,
        help="Sample ID to export (e.g., 0029460)"
    )
    parser.add_argument(
        "--random",
        type=int,
        metavar="N",
        help="Export N random samples"
    )
    parser.add_argument(
        "--root",
        type=str,
        default="./data",
        help="Root directory containing the dataset (default: ./data)"
    )
    parser.add_argument(
        "--split",
        type=str,
        default="ssl4eo_l_oli_sr",
        help="Dataset split to use (default: ssl4eo_l_oli_sr)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./samples",
        help="Output directory for PNG files (default: ./samples)"
    )

    args = parser.parse_args()

    if not args.sample and not args.random:
        parser.error("Must specify either --sample or --random")

    # Check data directory exists
    data_dir = Path(args.root) / args.split
    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        print(f"Download the dataset first: python scripts/download.py --splits oli_sr")
        sys.exit(1)

    # Get sample directories
    all_samples = sorted([d for d in data_dir.iterdir() if d.is_dir()])
    if not all_samples:
        print(f"Error: No samples found in {data_dir}")
        sys.exit(1)

    # Select samples to export
    if args.sample:
        sample_dir = data_dir / args.sample
        if not sample_dir.exists():
            print(f"Error: Sample not found: {args.sample}")
            print(f"Available samples: {len(all_samples)} (e.g., {all_samples[0].name})")
            sys.exit(1)
        samples_to_export = [sample_dir]
    else:
        n = min(args.random, len(all_samples))
        samples_to_export = random.sample(all_samples, n)

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Export samples
    print(f"Exporting {len(samples_to_export)} sample(s) to {output_dir}/\n")
    total_exported = 0

    for sample_dir in samples_to_export:
        print(f"Sample {sample_dir.name}:")
        exported = export_sample(sample_dir, output_dir)
        total_exported += len(exported)
        print()

    print(f"Done! Exported {total_exported} images to {output_dir}/")


if __name__ == "__main__":
    main()
