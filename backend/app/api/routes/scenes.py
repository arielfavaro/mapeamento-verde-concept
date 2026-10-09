from collections import defaultdict
from datetime import date

from fastapi import APIRouter, HTTPException

from app.api.deps import ServicesDep
from app.domain.aoi import bbox_area_km2
from app.domain.models import AcquisitionDate, SceneOut, SceneSearchRequest, SceneSearchResponse
from app.domain.sensors import get_sensor
from app.services.catalog import FoundItem
from app.services.loader import build_geobox, estimate_coverage

router = APIRouter(prefix="/scenes", tags=["cenas"])

# Estimar a nuvem dentro da AOI lê a banda de qualidade de cada cena; limita para manter a busca rápida.
MAX_SCENES_TO_ESTIMATE = 80


@router.post("/search", response_model=SceneSearchResponse)
def search_scenes(body: SceneSearchRequest, services: ServicesDep) -> SceneSearchResponse:
    settings = services.settings
    bbox = body.aoi.as_tuple()
    if bbox_area_km2(*bbox) > settings.max_aoi_km2:
        raise HTTPException(422, f"AOI maior que {settings.max_aoi_km2:.0f} km²")

    sensor = get_sensor(body.sensor)
    found = services.catalog.search(sensor, bbox, body.start, body.end, body.max_scene_cloud)

    per_date: dict[date, float] = {}
    if body.estimate_aoi_cloud and sensor.cloud_filterable and found:
        if len(found) > MAX_SCENES_TO_ESTIMATE:
            raise HTTPException(
                422, f"{len(found)} cenas: reduza o período para estimar a nuvem na AOI (máx. {MAX_SCENES_TO_ESTIMATE})"
            )
        geobox = build_geobox(bbox, settings.target_crs, settings.coverage_resolution_m)
        per_date = estimate_coverage(found, geobox, services.catalog.sign).per_date

    by_day: dict[date, list[FoundItem]] = defaultdict(list)
    for f in found:
        by_day[f.item.datetime.date()].append(f)

    dates = []
    for day in sorted(by_day):
        scenes = [_scene_out(f) for f in by_day[day]]
        clouds = [s.scene_cloud for s in scenes if s.scene_cloud is not None]
        dates.append(
            AcquisitionDate(
                date=day,
                scenes=scenes,
                scene_cloud_max=max(clouds) if clouds else None,
                aoi_valid_fraction=_nearest(per_date, day),
            )
        )
    return SceneSearchResponse(sensor=sensor.id, total_scenes=len(found), dates=dates)


def _scene_out(f: FoundItem) -> SceneOut:
    return SceneOut(
        id=f.item.id,
        collection=f.source.collection,
        datetime=f.item.datetime,
        platform=f.platform,
        tile=f.tile,
        scene_cloud=f.cloud,
        geometry=f.item.geometry,
        preview_url=f.preview_url,
    )


def _nearest(per_date: dict[date, float], day: date) -> float | None:
    """O dia solar usado na estimativa pode diferir em 1 dia da data UTC da cena."""
    candidates = [d for d in per_date if abs((d - day).days) <= 1]
    if not candidates:
        return None
    return round(per_date[min(candidates, key=lambda d: abs((d - day).days))], 4)
