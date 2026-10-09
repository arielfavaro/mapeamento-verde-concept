"""Schemas (pydantic) de entrada e saída da API."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.indices import INDEX_BY_ID, available_indices
from app.domain.sensors import SENSOR_BY_ID


class BBox(BaseModel):
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.west >= self.east or self.south >= self.north:
            raise ValueError("bbox inválido: oeste < leste e sul < norte")
        return self

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.west, self.south, self.east, self.north)


class _PeriodRequest(BaseModel):
    sensor: str
    aoi: BBox
    start: date
    end: date

    @field_validator("sensor")
    @classmethod
    def _known_sensor(cls, v: str) -> str:
        if v not in SENSOR_BY_ID:
            raise ValueError(f"satélite desconhecido: {v}")
        return v

    @model_validator(mode="after")
    def _period(self) -> Self:
        if self.end < self.start:
            raise ValueError("a data final deve ser igual ou posterior à inicial")
        return self


class SceneSearchRequest(_PeriodRequest):
    max_scene_cloud: float = Field(80, ge=0, le=100)
    estimate_aoi_cloud: bool = False


class SceneOut(BaseModel):
    id: str
    collection: str
    datetime: datetime
    platform: str
    tile: str
    scene_cloud: float | None
    geometry: dict[str, Any]
    preview_url: str | None = None


class AcquisitionDate(BaseModel):
    """Cenas agrupadas por dia de aquisição (vários tiles do mesmo dia cobrem a AOI juntos)."""

    date: date
    scenes: list[SceneOut]
    scene_cloud_max: float | None
    aoi_valid_fraction: float | None = None


class SceneSearchResponse(BaseModel):
    sensor: str
    total_scenes: int
    dates: list[AcquisitionDate]


class CompositeMethod(StrEnum):
    MEDIAN = "median"
    BEST_DATE = "best_date"


class JobRequest(_PeriodRequest):
    aoi_name: str = Field("AOI", max_length=60)
    method: CompositeMethod = CompositeMethod.MEDIAN
    max_scene_cloud: float = Field(80, ge=0, le=100)
    cloud_buffer_px: int = Field(2, ge=0, le=10)
    adaptive_window: bool = True
    target_coverage: float = Field(0.98, ge=0.5, le=1.0)
    max_window_days: int = Field(120, ge=1, le=366)
    scene_ids: list[str] | None = Field(None, description="Seleção manual; desativa a janela adaptativa")
    indices: list[str] | None = Field(None, description="Padrão: todos os disponíveis para o satélite")
    resolution_m: float | None = Field(None, ge=10, le=1000)

    @model_validator(mode="after")
    def _indices_supported(self) -> Self:
        if self.indices is None:
            return self
        sensor = SENSOR_BY_ID[self.sensor]
        allowed = {i.id for i in available_indices(sensor.band_names)}
        unknown = [i for i in self.indices if i not in INDEX_BY_ID]
        unsupported = [i for i in self.indices if i in INDEX_BY_ID and i not in allowed]
        if unknown:
            raise ValueError(f"índices desconhecidos: {unknown}")
        if unsupported:
            raise ValueError(f"{sensor.name} não tem as bandas para: {unsupported}")
        return self


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class LayerKind(StrEnum):
    COMPOSITE = "composite"
    INDEX = "index"
    COUNT = "count"


class Layer(BaseModel):
    id: str
    name: str
    kind: LayerKind
    file: str
    colormap: str | None = None
    vmin: float
    vmax: float
    unit: str = ""
    bands: list[int] | None = None  # índices (1-based) no arquivo, para composições RGB


class OutputFile(BaseModel):
    name: str
    description: str
    size_bytes: int


class IndexClassArea(BaseModel):
    label: str
    min: float
    max: float
    area_km2: float
    fraction: float


class IndexStats(BaseModel):
    valid_pixels: int
    mean: float | None
    std: float | None
    percentiles: dict[str, float]
    histogram: list[int]
    histogram_edges: list[float]
    classes: list[IndexClassArea]


class WindowAttemptOut(BaseModel):
    start: date
    end: date
    coverage: float
    scenes: int


class AcquisitionUsed(BaseModel):
    date: date
    scene_ids: list[str]
    platforms: list[str]
    valid_fraction: float


class JobResult(BaseModel):
    window_start: date
    window_end: date
    window_attempts: list[WindowAttemptOut]
    acquisitions: list[AcquisitionUsed]
    coverage: float
    crs: str
    resolution_m: float
    width: int
    height: int
    bounds_wgs84: tuple[float, float, float, float]
    files: list[OutputFile]
    layers: list[Layer]
    stats: dict[str, IndexStats]
    warnings: list[str] = []


class JobSummary(BaseModel):
    """Visão resumida para listagens (sem resultado nem log, que podem ser grandes)."""

    id: str
    created_at: datetime
    updated_at: datetime
    state: JobState
    progress: float = 0.0
    message: str = ""
    request: JobRequest
    error: str | None = None


class Job(JobSummary):
    result: JobResult | None = None
    log: list[str] = []

    def summary(self) -> JobSummary:
        return JobSummary.model_validate(self.model_dump(exclude={"result", "log"}))
