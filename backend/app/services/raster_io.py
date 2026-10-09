"""Gravação de GeoTIFFs otimizados para nuvem (COG), com overviews para o servidor de tiles."""

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import rasterio
from odc.geo.geobox import GeoBox


def write_cog(
    path: Path,
    bands: Sequence[np.ndarray],
    geobox: GeoBox,
    descriptions: Sequence[str],
    dtype: str = "float32",
    nodata: float | None = float("nan"),
    tags: dict[str, str] | None = None,
) -> Path:
    if len(bands) != len(descriptions):
        raise ValueError("cada banda precisa de uma descrição")
    height, width = geobox.shape
    profile = {
        "driver": "COG",
        "width": width,
        "height": height,
        "count": len(bands),
        "dtype": dtype,
        "crs": geobox.crs.to_wkt(),
        "transform": geobox.affine,
        "nodata": nodata,
        "compress": "DEFLATE",
        "predictor": 3 if np.dtype(dtype).kind == "f" else 2,
        "blocksize": 512,
        "overview_resampling": "average",
        "bigtiff": "IF_SAFER",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        for i, (band, desc) in enumerate(zip(bands, descriptions, strict=True), start=1):
            dst.write(band.astype(dtype, copy=False), i)
            dst.set_band_description(i, desc)
        if tags:
            dst.update_tags(**tags)
    return path
