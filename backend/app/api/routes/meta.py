from fastapi import APIRouter, HTTPException
from rio_tiler.errors import InvalidColorMapName

from app import __version__
from app.api.deps import ServicesDep
from app.api.schemas import AoiPresetOut, ColormapOut, IndexOut, SensorOut
from app.domain.aoi import PRESETS
from app.domain.indices import INDICES
from app.domain.sensors import SENSORS
from app.services.tiles import colormap_stops

router = APIRouter(tags=["catálogo"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/config")
def get_config(services: ServicesDep) -> dict[str, str | float]:
    s = services.settings
    return {"version": __version__, "max_aoi_km2": s.max_aoi_km2, "target_crs": s.target_crs}


@router.get("/sensors", response_model=list[SensorOut])
def list_sensors() -> list[SensorOut]:
    return [SensorOut.from_domain(s) for s in SENSORS]


@router.get("/indices", response_model=list[IndexOut])
def list_indices() -> list[IndexOut]:
    return [IndexOut.from_domain(i) for i in INDICES]


@router.get("/aoi-presets", response_model=list[AoiPresetOut])
def list_presets() -> list[AoiPresetOut]:
    return [AoiPresetOut.from_domain(p) for p in PRESETS]


@router.get("/colormaps/{name}", response_model=ColormapOut)
def get_colormap(name: str) -> ColormapOut:
    try:
        return ColormapOut(name=name, colors=colormap_stops(name))
    except InvalidColorMapName as exc:
        raise HTTPException(404, f"Paleta desconhecida: {name}") from exc
