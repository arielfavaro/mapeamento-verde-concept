"""Schemas de leitura do catálogo de satélites e índices (apresentação)."""

from pydantic import BaseModel

from app.domain.aoi import AoiPreset, bbox_area_km2
from app.domain.indices import SpectralIndex, available_indices
from app.domain.sensors import Sensor
from app.services.tiles import colormap_stops


class BandOut(BaseModel):
    common: str
    label: str
    wavelength: str
    resolution_m: int


class SensorInfoOut(BaseModel):
    mission: str
    summary: str
    how_it_works: str
    processing: str
    strengths: list[str]
    limitations: list[str]
    best_for: list[str]


class SensorOut(BaseModel):
    id: str
    name: str
    kind: str
    resolution_m: int
    revisit: str
    since: str
    collections: list[str]
    cloud_filterable: bool
    bands: list[BandOut]
    indices: list[str]
    info: SensorInfoOut

    @classmethod
    def from_domain(cls, s: Sensor) -> "SensorOut":
        return cls(
            id=s.id,
            name=s.name,
            kind=s.kind.value,
            resolution_m=s.resolution_m,
            revisit=s.revisit,
            since=s.since,
            collections=[src.collection for src in s.sources],
            cloud_filterable=s.cloud_filterable,
            bands=[BandOut(**b.__dict__) for b in s.bands],
            indices=[i.id for i in available_indices(s.band_names)],
            info=SensorInfoOut(
                mission=s.info.mission,
                summary=s.info.summary,
                how_it_works=s.info.how_it_works,
                processing=s.info.processing,
                strengths=list(s.info.strengths),
                limitations=list(s.info.limitations),
                best_for=list(s.info.best_for),
            ),
        )


class IndexClassOut(BaseModel):
    min: float
    max: float
    label: str


class IndexOut(BaseModel):
    id: str
    name: str
    category: str
    formula: str
    bands: list[str]
    description: str
    reference: str
    colormap: str
    colors: list[str]
    vmin: float
    vmax: float
    unit: str
    classes: list[IndexClassOut]

    @classmethod
    def from_domain(cls, i: SpectralIndex) -> "IndexOut":
        return cls(
            id=i.id,
            name=i.name,
            category=i.category,
            formula=i.formula,
            bands=list(i.bands),
            description=i.description,
            reference=i.reference,
            colormap=i.colormap,
            colors=colormap_stops(i.colormap),
            vmin=i.vmin,
            vmax=i.vmax,
            unit=i.unit,
            classes=[IndexClassOut(min=c.min, max=c.max, label=c.label) for c in i.classes],
        )


class AoiPresetOut(BaseModel):
    id: str
    name: str
    bbox: tuple[float, float, float, float]
    description: str
    area_km2: float

    @classmethod
    def from_domain(cls, p: AoiPreset) -> "AoiPresetOut":
        return cls(
            id=p.id, name=p.name, bbox=p.bbox, description=p.description, area_km2=round(bbox_area_km2(*p.bbox), 1)
        )


class ColormapOut(BaseModel):
    name: str
    colors: list[str]
