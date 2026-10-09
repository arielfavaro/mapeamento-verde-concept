"""Área de interesse (AOI) como retângulo em WGS84."""

import math
import unicodedata
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class AoiPreset:
    id: str
    name: str
    bbox: tuple[float, float, float, float]  # oeste, sul, leste, norte
    description: str


PRESETS: tuple[AoiPreset, ...] = (
    AoiPreset(
        id="porto-ferreira",
        name="Porto Ferreira - SP",
        bbox=(-47.5546664, -21.935324, -47.3343908, -21.7547284),
        description="Retângulo envolvente do município (IBGE 3540705, 245 km²).",
    ),
)


def bbox_area_km2(west: float, south: float, east: float, north: float) -> float:
    """Área de um retângulo geográfico na esfera (exata para lat/lon constantes)."""
    lam = math.radians(east - west)
    return EARTH_RADIUS_KM**2 * lam * abs(math.sin(math.radians(north)) - math.sin(math.radians(south)))


def slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = "".join(c if c.isalnum() else "-" for c in norm.lower())
    return "-".join(filter(None, slug.split("-")))[:40] or "aoi"
