#!/usr/bin/env python3
"""
Script to explore SSL4EO-L dataset metadata without downloading.
"""
import inspect
from torchgeo.datasets import SSL4EOL

print("=" * 70)
print("SSL4EO-L (SSL4EO Landsat) Dataset Metadata")
print("=" * 70)

# Dataset overview
print("\nDATASET OVERVIEW")
print("-" * 70)
print("Name: SSL4EO-L (Self-Supervised Learning for Earth Observation - Landsat)")
print("Purpose: Self-supervised pre-training on Landsat satellite imagery")
print("Paper: NeurIPS 2023 Datasets and Benchmarks Track")

# Patch properties
print("\nPATCH PROPERTIES")
print("-" * 70)
print("  Patch size:     264 x 264 pixels")
print("  Resolution:     30 m")
print("  Ground extent:  7920 x 7920 m per patch")
print("  Seasons:        4 timestamps per location")
print("  Format:         Single multispectral GeoTIFF per patch")

# Available splits
print("\nAVAILABLE SPLITS")
print("-" * 70)

split_info = {
    'tm_toa': {
        'satellites': 'Landsat 4-5',
        'sensor': 'TM (Thematic Mapper)',
        'level': 'TOA (Top of Atmosphere)',
        'size': '~300-400 GB'
    },
    'etm_toa': {
        'satellites': 'Landsat 7',
        'sensor': 'ETM+ (Enhanced Thematic Mapper Plus)',
        'level': 'TOA (Top of Atmosphere)',
        'size': '~300-400 GB'
    },
    'etm_sr': {
        'satellites': 'Landsat 7',
        'sensor': 'ETM+ (Enhanced Thematic Mapper Plus)',
        'level': 'SR (Surface Reflectance)',
        'size': '~300-400 GB'
    },
    'oli_tirs_toa': {
        'satellites': 'Landsat 8-9',
        'sensor': 'OLI+TIRS (Operational Land Imager + Thermal)',
        'level': 'TOA (Top of Atmosphere)',
        'size': '~300-400 GB'
    },
    'oli_sr': {
        'satellites': 'Landsat 8-9',
        'sensor': 'OLI (Operational Land Imager)',
        'level': 'SR (Surface Reflectance)',
        'size': '~300-400 GB'
    }
}

metadata = SSL4EOL.metadata
for split_name, bands_info in metadata.items():
    info = split_info[split_name]
    print(f"\n  [{split_name.upper()}]")
    print(f"    Satellites:  {info['satellites']}")
    print(f"    Sensor:      {info['sensor']}")
    print(f"    Level:       {info['level']}")
    print(f"    Bands:       {bands_info['all_bands']} ({len(bands_info['all_bands'])} total)")
    print(f"    RGB indices: {bands_info['rgb_bands']}")
    print(f"    Size:        {info['size']}")

# Band descriptions
print("\nBAND DESCRIPTIONS")
print("-" * 70)
print("\n  Landsat 8-9 OLI/OLI+TIRS bands:")
print("    B1:  Coastal Aerosol (0.43-0.45 um)")
print("    B2:  Blue (0.45-0.51 um)")
print("    B3:  Green (0.53-0.59 um)")
print("    B4:  Red (0.64-0.67 um)")
print("    B5:  NIR (0.85-0.88 um)")
print("    B6:  SWIR 1 (1.57-1.65 um)")
print("    B7:  SWIR 2 (2.11-2.29 um)")
print("    B8:  Panchromatic (0.50-0.68 um) [TOA only]")
print("    B9:  Cirrus (1.36-1.38 um) [TOA only]")
print("    B10: Thermal 1 (10.6-11.19 um) [TIRS TOA only]")
print("    B11: Thermal 2 (11.5-12.51 um) [TIRS TOA only]")

print("\n  Landsat 4-5 TM / Landsat 7 ETM+ bands:")
print("    B1:  Blue (0.45-0.52 um)")
print("    B2:  Green (0.52-0.60 um)")
print("    B3:  Red (0.63-0.69 um)")
print("    B4:  NIR (0.76-0.90 um)")
print("    B5:  SWIR 1 (1.55-1.75 um)")
print("    B6:  Thermal (10.4-12.5 um)")
print("    B7:  SWIR 2 (2.08-2.35 um)")
print("    B8:  Panchromatic (0.52-0.90 um) [ETM+ only]")

# Constructor parameters
print("\nCONSTRUCTOR PARAMETERS")
print("-" * 70)
sig = inspect.signature(SSL4EOL.__init__)
for param_name, param in sig.parameters.items():
    if param_name == 'self':
        continue
    default = param.default if param.default != inspect.Parameter.empty else "(required)"
    print(f"  {param_name}: {default}")

# Usage example
print("\nUSAGE EXAMPLE")
print("-" * 70)
print("""
  from torchgeo.datasets import SSL4EOL

  # Load OLI surface reflectance (Landsat 8-9)
  dataset = SSL4EOL(
      root="./data",
      split="oli_sr",      # or "tm_toa", "etm_toa", "etm_sr", "oli_tirs_toa"
      seasons=4,           # number of seasonal timestamps (1-4)
      download=True        # set True to download
  )

  # Access a sample
  sample = dataset[0]
  image = sample["image"]  # Shape: (seasons * bands, H, W)
""")

# Storage requirements
print("\nSTORAGE REQUIREMENTS")
print("-" * 70)
print("  Each split:       300-400 GB")
print("  Extraction space: 3x split size (for tar extraction)")
print("  Download time:    ~1.5 hours (with checksum)")
print("  Extraction time:  ~3 hours")
print("  Tip: Delete tarballs after extraction to save space")

print("\n" + "=" * 70)
