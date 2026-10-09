"""Renderização de tiles XYZ (Web Mercator) a partir dos COGs gerados, para o Leaflet."""

from functools import lru_cache
from pathlib import Path

import numpy as np
from rio_tiler.colormap import cmap
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.io import Reader
from rio_tiler.models import ImageData

from app.domain.models import Layer, LayerKind

TILE_SIZE = 256


@lru_cache(maxsize=1)
def empty_tile() -> bytes:
    """Tile 100% transparente para áreas fora do raster."""
    data = np.ma.MaskedArray(np.zeros((1, TILE_SIZE, TILE_SIZE), dtype="uint8"), mask=True)
    return ImageData(data).render(img_format="PNG")


def colormap_stops(name: str, n: int = 11) -> list[str]:
    """Cores (hex) amostradas de uma paleta, para a legenda no frontend."""
    cm = cmap.get(name)
    keys = np.linspace(0, 255, n).round().astype(int)
    return ["#{:02x}{:02x}{:02x}".format(*cm[int(k)][:3]) for k in keys]


def render_tile(path: Path, layer: Layer, z: int, x: int, y: int) -> bytes:
    with Reader(str(path)) as src:
        try:
            if layer.kind is LayerKind.COMPOSITE and layer.bands:
                img = src.tile(x, y, z, tilesize=TILE_SIZE, indexes=tuple(layer.bands))
            else:
                img = src.tile(x, y, z, tilesize=TILE_SIZE, indexes=1)
        except TileOutsideBounds:
            return empty_tile()

    # O NoData dos GeoTIFFs é NaN e vira o fill_value do array mascarado; ao converter para uint8
    # no rescale, o numpy avisa "invalid value encountered in cast" a cada tile. A máscara já diz
    # quais pixels são vazios, então o fill_value pode ser qualquer número válido.
    img.array.fill_value = 0

    if layer.kind is LayerKind.COMPOSITE and layer.bands:
        img = img.rescale(in_range=((layer.vmin, layer.vmax),) * len(layer.bands))
        return img.render(img_format="PNG")
    if layer.kind is LayerKind.COUNT:
        # pixels com 0 observações ficam transparentes para destacar os buracos sobre o mapa base
        img.array.mask = np.ma.getmaskarray(img.array) | (img.array.data == 0)
    img = img.rescale(in_range=((layer.vmin, layer.vmax),))
    return img.render(img_format="PNG", colormap=cmap.get(layer.colormap) if layer.colormap else None)
