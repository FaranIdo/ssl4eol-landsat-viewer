#!/usr/bin/env python3
"""
SSL4EO-L Dataset Download Script

Downloads specified subsets of the SSL4EO-L dataset using TorchGeo.
Each split is 300-400 GB, so ensure you have sufficient disk space.

Usage:
    python scripts/download.py --splits oli_sr
    python scripts/download.py --splits oli_sr etm_sr
    python scripts/download.py --splits all
    python scripts/download.py --splits oli_sr --seasons 4 --checksum
"""

import argparse
import sys
import time
import shutil
from pathlib import Path
from datetime import datetime, timedelta


AVAILABLE_SPLITS = ["tm_toa", "etm_toa", "etm_sr", "oli_tirs_toa", "oli_sr"]

SPLIT_INFO = {
    "tm_toa": {
        "satellite": "Landsat 4-5",
        "sensor": "TM (Thematic Mapper)",
        "level": "TOA (Top of Atmosphere)",
        "bands": 7,
        "years": "2009-2010",
        "size": "~300-400 GB",
        "size_gb": 350,  # Estimate for progress calculation
    },
    "etm_toa": {
        "satellite": "Landsat 7",
        "sensor": "ETM+ (Enhanced Thematic Mapper Plus)",
        "level": "TOA (Top of Atmosphere)",
        "bands": 9,
        "years": "2001-2002",
        "size": "~300-400 GB",
        "size_gb": 385,
    },
    "etm_sr": {
        "satellite": "Landsat 7",
        "sensor": "ETM+ (Enhanced Thematic Mapper Plus)",
        "level": "SR (Surface Reflectance)",
        "bands": 6,
        "years": "2001-2002",
        "size": "~300-400 GB",
        "size_gb": 274,
    },
    "oli_tirs_toa": {
        "satellite": "Landsat 8-9",
        "sensor": "OLI+TIRS (Operational Land Imager + Thermal)",
        "level": "TOA (Top of Atmosphere)",
        "bands": 11,
        "years": "2021-2022",
        "size": "~300-400 GB",
        "size_gb": 385,
    },
    "oli_sr": {
        "satellite": "Landsat 8-9",
        "sensor": "OLI (Operational Land Imager)",
        "level": "SR (Surface Reflectance)",
        "bands": 7,
        "years": "2021-2022",
        "size": "~300-400 GB",
        "size_gb": 274,
    },
}


def format_size(bytes_size: float) -> str:
    """Format bytes to human readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.2f} PB"


def format_time(seconds: float) -> str:
    """Format seconds to human readable time."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_eta(seconds: float) -> str:
    """Format ETA to human readable string."""
    if seconds <= 0:
        return "calculating..."

    td = timedelta(seconds=int(seconds))
    hours, remainder = divmod(td.seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if td.days > 0:
        return f"{td.days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def get_directory_size(path: Path) -> int:
    """Get total size of a directory in bytes."""
    total = 0
    if path.exists():
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    return total


def check_disk_space(path: Path, required_gb: float) -> tuple[bool, float]:
    """Check if enough disk space is available."""
    try:
        total, used, free = shutil.disk_usage(path)
        free_gb = free / (1024**3)
        return free_gb >= required_gb, free_gb
    except Exception:
        return True, -1  # Assume OK if we can't check


class DownloadProgressMonitor:
    """Monitor download progress by watching directory size."""

    def __init__(self, root: Path, split: str, expected_size_gb: float):
        self.root = root
        self.split = split
        self.expected_size_bytes = expected_size_gb * (1024**3)
        self.start_time = None
        self.start_size = 0

    def start(self):
        """Start monitoring."""
        self.start_time = time.time()
        self.start_size = get_directory_size(self.root)

    def get_progress(self) -> dict:
        """Get current progress stats."""
        if self.start_time is None:
            return {"progress": 0, "speed": 0, "eta": -1, "downloaded": 0}

        current_size = get_directory_size(self.root)
        downloaded = current_size - self.start_size
        elapsed = time.time() - self.start_time

        # Calculate speed (bytes per second)
        speed = downloaded / elapsed if elapsed > 0 else 0

        # Calculate progress
        progress = (downloaded / self.expected_size_bytes * 100) if self.expected_size_bytes > 0 else 0
        progress = min(progress, 100)  # Cap at 100%

        # Calculate ETA
        remaining_bytes = self.expected_size_bytes - downloaded
        eta = remaining_bytes / speed if speed > 0 else -1

        return {
            "progress": progress,
            "speed": speed,
            "eta": eta,
            "downloaded": downloaded,
            "elapsed": elapsed,
        }

    def print_status(self):
        """Print current status."""
        stats = self.get_progress()

        progress_bar_width = 30
        filled = int(progress_bar_width * stats["progress"] / 100)
        bar = "=" * filled + ">" + " " * (progress_bar_width - filled - 1)

        status = (
            f"\r[{bar}] {stats['progress']:.1f}% | "
            f"{format_size(stats['downloaded'])} | "
            f"{format_size(stats['speed'])}/s | "
            f"ETA: {format_eta(stats['eta'])}"
        )
        print(status, end="", flush=True)


def print_split_info(splits: list[str], root: str) -> None:
    """Print information about selected splits."""
    print("\n" + "=" * 70)
    print("SELECTED SPLITS FOR DOWNLOAD")
    print("=" * 70)

    total_size_gb = 0
    for split in splits:
        info = SPLIT_INFO[split]
        print(f"\n  [{split.upper()}]")
        print(f"    Satellite: {info['satellite']}")
        print(f"    Sensor:    {info['sensor']}")
        print(f"    Level:     {info['level']}")
        print(f"    Bands:     {info['bands']}")
        print(f"    Years:     {info['years']}")
        print(f"    Size:      {info['size']}")
        total_size_gb += info['size_gb']

    # Check disk space
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    has_space, free_gb = check_disk_space(root_path, total_size_gb * 3)

    print("\n" + "-" * 70)
    print(f"  Total estimated download size: ~{total_size_gb} GB")
    print(f"  Extraction space needed:       ~{total_size_gb * 3} GB")
    if free_gb > 0:
        print(f"  Available disk space:          {free_gb:.1f} GB")
        if not has_space:
            print(f"  WARNING: Insufficient disk space!")

    # Estimate download time (assuming ~50 MB/s average)
    estimated_time_hours = total_size_gb / (50 * 3.6)  # 50 MB/s = 180 GB/h
    print(f"  Estimated download time:       ~{estimated_time_hours:.1f} hours (at 50 MB/s)")
    print("=" * 70 + "\n")


def download_split(
    split: str,
    root: str,
    seasons: int,
    checksum: bool,
    dry_run: bool
) -> bool:
    """Download a single split."""
    import threading

    if dry_run:
        print(f"[DRY RUN] Would download: {split}")
        print(f"          Root: {root}")
        print(f"          Seasons: {seasons}")
        print(f"          Checksum: {checksum}")
        return True

    # Check disk space first
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)

    expected_size_gb = SPLIT_INFO[split]["size_gb"]
    required_space = expected_size_gb * 3  # Need 3x for extraction

    has_space, free_gb = check_disk_space(root_path, required_space)
    if not has_space:
        print(f"\nError: Insufficient disk space!")
        print(f"  Required: ~{required_space:.0f} GB")
        print(f"  Available: {free_gb:.1f} GB")
        return False

    try:
        from torchgeo.datasets import SSL4EOL

        print(f"\n{'='*70}")
        print(f"DOWNLOADING: {split.upper()}")
        print(f"{'='*70}")
        print(f"  Satellite:    {SPLIT_INFO[split]['satellite']}")
        print(f"  Sensor:       {SPLIT_INFO[split]['sensor']}")
        print(f"  Level:        {SPLIT_INFO[split]['level']}")
        print(f"  Expected size: ~{expected_size_gb} GB")
        print(f"  Free space:   {free_gb:.1f} GB")
        print(f"  Root:         {root}")
        print(f"  Seasons:      {seasons}")
        print(f"  Checksum:     {checksum}")
        print(f"  Started at:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 70)

        # Set up progress monitor
        monitor = DownloadProgressMonitor(root_path, split, expected_size_gb)
        stop_monitoring = threading.Event()

        def monitor_progress():
            """Background thread to print progress."""
            monitor.start()
            while not stop_monitoring.is_set():
                monitor.print_status()
                time.sleep(2)  # Update every 2 seconds
            # Final status
            monitor.print_status()
            print()  # New line after progress bar

        # Start monitoring in background thread
        monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
        monitor_thread.start()

        # Actually download
        download_start = time.time()
        dataset = SSL4EOL(
            root=root,
            split=split,
            seasons=seasons,
            download=True,
            checksum=checksum,
        )
        download_time = time.time() - download_start

        # Stop monitoring
        stop_monitoring.set()
        monitor_thread.join(timeout=5)

        # Final stats
        final_size = get_directory_size(root_path)
        print(f"\n{'='*70}")
        print(f"COMPLETED: {split.upper()}")
        print(f"{'='*70}")
        print(f"  Dataset length:   {len(dataset):,} samples")
        print(f"  Download time:    {format_eta(download_time)}")
        print(f"  Total size:       {format_size(final_size)}")
        print(f"  Finished at:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Print sample info
        try:
            sample = dataset[0]
            print(f"  Sample shape:     {sample['image'].shape}")
        except Exception:
            pass

        print(f"{'='*70}\n")
        return True

    except KeyboardInterrupt:
        print(f"\n\nDownload interrupted by user!")
        stop_monitoring.set()
        return False

    except Exception as e:
        print(f"\n\nError downloading {split}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download SSL4EO-L dataset subsets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download OLI surface reflectance only (recommended for most use cases)
  python scripts/download.py --splits oli_sr

  # Download multiple splits
  python scripts/download.py --splits oli_sr etm_sr

  # Download all splits (WARNING: ~1.5-2 TB total)
  python scripts/download.py --splits all

  # Dry run to see what would be downloaded
  python scripts/download.py --splits oli_sr --dry-run

  # Download with checksum verification (slower but safer)
  python scripts/download.py --splits oli_sr --checksum

Available splits:
  tm_toa       - Landsat 4-5 TM, TOA, 7 bands, 2009-2010
  etm_toa      - Landsat 7 ETM+, TOA, 9 bands, 2001-2002
  etm_sr       - Landsat 7 ETM+, SR, 6 bands, 2001-2002
  oli_tirs_toa - Landsat 8-9 OLI+TIRS, TOA, 11 bands, 2021-2022
  oli_sr       - Landsat 8-9 OLI, SR, 7 bands, 2021-2022
        """
    )

    parser.add_argument(
        "--splits",
        nargs="+",
        required=True,
        help="Splits to download. Use 'all' for all splits, or specify: "
             + ", ".join(AVAILABLE_SPLITS)
    )

    parser.add_argument(
        "--root",
        type=str,
        default="./data",
        help="Root directory for dataset storage (default: ./data)"
    )

    parser.add_argument(
        "--seasons",
        type=int,
        default=4,
        choices=[1, 2, 3, 4],
        help="Number of seasonal timestamps to load (default: 4)"
    )

    parser.add_argument(
        "--checksum",
        action="store_true",
        help="Verify checksums after download (slower but safer)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without actually downloading"
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List available splits and exit"
    )

    args = parser.parse_args()

    # List mode
    if args.list:
        print("\nAvailable SSL4EO-L splits:\n")
        for split in AVAILABLE_SPLITS:
            info = SPLIT_INFO[split]
            print(f"  {split:15} - {info['satellite']:12} | {info['level']:25} | {info['bands']:2} bands | {info['years']}")
        print()
        sys.exit(0)

    # Parse splits
    if "all" in args.splits:
        splits = AVAILABLE_SPLITS
    else:
        splits = []
        for s in args.splits:
            if s not in AVAILABLE_SPLITS:
                print(f"Error: Unknown split '{s}'")
                print(f"Available splits: {', '.join(AVAILABLE_SPLITS)}")
                sys.exit(1)
            splits.append(s)

    # Remove duplicates while preserving order
    splits = list(dict.fromkeys(splits))

    # Print info
    print_split_info(splits, args.root)

    # Confirm download
    if not args.dry_run:
        response = input("Proceed with download? [y/N]: ").strip().lower()
        if response != "y":
            print("Download cancelled.")
            sys.exit(0)

    # Create root directory
    root_path = Path(args.root)
    root_path.mkdir(parents=True, exist_ok=True)

    # Download each split
    success_count = 0
    failed_splits = []

    for split in splits:
        success = download_split(
            split=split,
            root=args.root,
            seasons=args.seasons,
            checksum=args.checksum,
            dry_run=args.dry_run,
        )
        if success:
            success_count += 1
        else:
            failed_splits.append(split)

    # Summary
    print("\n" + "=" * 70)
    print("DOWNLOAD SUMMARY")
    print("=" * 70)
    print(f"  Successful: {success_count}/{len(splits)}")
    if failed_splits:
        print(f"  Failed: {', '.join(failed_splits)}")
    print("=" * 70 + "\n")

    sys.exit(0 if not failed_splits else 1)


if __name__ == "__main__":
    main()
