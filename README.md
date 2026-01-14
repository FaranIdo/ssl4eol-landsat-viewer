# SSL4EO-L Landsat Viewer

An interactive web-based viewer for exploring the [SSL4EO-L](https://github.com/zhu-xlab/SSL4EO-S12) Landsat satellite imagery dataset. Browse 250,000 locations worldwide with multi-temporal Landsat imagery directly in your browser.

## Features

- **Interactive Map Interface** - Leaflet.js-powered map with satellite and OpenStreetMap basemaps
- **RGB Visualization** - Automatic RGB composite generation with percentile normalization
- **Multi-temporal Layers** - View 4 seasonal timestamps per location with easy layer switching
- **Opacity Control** - Adjustable overlay opacity for comparison with basemaps
- **Click-to-Find** - Click anywhere on the map to find and load the nearest sample
- **Searchable Samples** - Dropdown with search functionality for 250,000 sample IDs
- **Fast Performance** - LRU caching for efficient tile delivery

## Quick Start

```bash
# Clone the repository
git clone https://github.com/FaranIdo/ssl4eol-landsat-viewer
cd ssl4eol-landsat-viewer

# Install dependencies
pip install -r requirements.txt

# Download the dataset (~274 GB for oli_sr split)
python scripts/download.py --splits oli_sr --root ./data

# Optional: Build location index (enables click-to-find feature)
python scripts/build_index.py --root ./data

# Start the viewer
python viewer.py --root ./data

# Open http://127.0.0.1:8080 in your browser
```

## Installation

### Prerequisites

- Python 3.8+
- ~300 GB free disk space (minimum, for one split)
- ~800 GB free disk space (recommended, for extraction)

### Install Dependencies

```bash
pip install -r requirements.txt
```

Or install individually:

```bash
pip install flask rasterio numpy pillow torchgeo
```

## Data Download

The SSL4EO-L dataset is large. Each split is 300-400 GB. Choose the split that best fits your needs:

| Split | Satellite | Processing Level | Bands | Years | Size |
|-------|-----------|------------------|-------|-------|------|
| `oli_sr` | Landsat 8-9 | Surface Reflectance | 7 | 2021-2022 | ~274 GB |
| `oli_tirs_toa` | Landsat 8-9 | Top of Atmosphere | 11 | 2021-2022 | ~385 GB |
| `etm_sr` | Landsat 7 | Surface Reflectance | 6 | 2001-2002 | ~274 GB |
| `etm_toa` | Landsat 7 | Top of Atmosphere | 9 | 2001-2002 | ~385 GB |
| `tm_toa` | Landsat 4-5 | Top of Atmosphere | 7 | 2009-2010 | ~350 GB |

**Recommended**: Start with `oli_sr` (Landsat 8-9 Surface Reflectance) for best image quality.

### Download Commands

```bash
# Download recommended split (oli_sr)
python scripts/download.py --splits oli_sr --root ./data

# Dry run to see download details without downloading
python scripts/download.py --splits oli_sr --dry-run

# Download with checksum verification (slower but safer)
python scripts/download.py --splits oli_sr --checksum

# Download multiple splits
python scripts/download.py --splits oli_sr etm_sr --root ./data

# List all available splits
python scripts/download.py --list
```

### Generate Location Index

After downloading, optionally build the location index to enable the click-to-find feature:

```bash
python scripts/build_index.py --root ./data
```

This creates a `locations.json` file mapping each sample to its geographic coordinates. **This step is optional** - the viewer works without it, but clicking on the map to find the nearest sample will be disabled.

## Usage

### Start the Viewer

```bash
# Basic usage (uses ./data directory)
python viewer.py

# Specify custom data directory
python viewer.py --root /path/to/data

# Use a different split
python viewer.py --root ./data --split ssl4eo_l_etm_sr

# Run on different port/host
python viewer.py --port 8000 --host 0.0.0.0
```

### Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--root` | `./data` | Root directory containing the dataset |
| `--split` | `ssl4eo_l_oli_sr` | Dataset split to use |
| `--port` | `8080` | Port to run the server on |
| `--host` | `127.0.0.1` | Host to bind to |

### Dataset Info

View dataset metadata and available splits without downloading:

```bash
python scripts/info.py
```

### View Samples

Generate PNG files from samples for local viewing (no web server needed):

```bash
# View a specific sample (generates 4 PNGs, one per season)
python scripts/view_samples.py --sample 0029460

# View 5 random samples
python scripts/view_samples.py --random 5

# Save to custom directory
python scripts/view_samples.py --sample 0029460 --output ./previews
```

Output files are named `{sample_id}_{season}_{date}.png` (e.g., `0029460_summer_20210622.png`).

## Dataset Information

SSL4EO-L (Self-Supervised Learning for Earth Observation - Landsat) contains:

- **250,000 unique locations** worldwide
- **5 million patches** total (250k locations x 4 seasons x 5 splits)
- **264 x 264 pixels** per patch at 30m resolution
- **~8 km x 8 km** ground coverage per patch
- **4 seasonal timestamps** per location

Locations are sampled from 10,000 cities worldwide using a Gaussian distribution.

## Credits

- **SSL4EO-L Dataset**: [zhu-xlab/SSL4EO-S12](https://github.com/zhu-xlab/SSL4EO-S12)
- **Paper**: [SSL4EO-L: Datasets and Foundation Models for Landsat Imagery](https://arxiv.org/abs/2306.09424) (NeurIPS 2023)
- **TorchGeo**: Dataset loading via [TorchGeo](https://github.com/microsoft/torchgeo)

## Citation

If you use this viewer or the SSL4EO-L dataset, please cite:

```bibtex
@inproceedings{stewart2023ssl4eol,
  title={SSL4EO-L: Datasets and Foundation Models for Landsat Imagery},
  author={Stewart, Adam and Lehmann, Nils and Corley, Isaac and Wang, Yi and Chang, Yi-Chia and Ait Ali Braham, Nassim and Seehra, Shradha and Robinson, Caleb and Bansal, Arindam},
  booktitle={Advances in Neural Information Processing Systems},
  year={2023}
}
```
