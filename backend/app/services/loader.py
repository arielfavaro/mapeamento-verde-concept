"""Leitura dos dados remotos (COGs) recortados na AOI e reprojetados para a grade de saída.

Só os blocos que cruzam a AOI são baixados (requisições HTTP por faixa de bytes). Cenas do mesmo
dia em tiles diferentes são fundidas em um único plano (``groupby="solar_day"``), o que evita
contar duas vezes a mesma aquisição nas áreas de sobreposição dos tiles.
"""

import logging
import warnings
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date

import numpy as np
import odc.stac
import pandas as pd
import xarray as xr
from odc.geo.geobox import GeoBox
from odc.geo.geom import BoundingBox, Geometry, box
from rasterio.errors import NotGeoreferencedWarning

from app.domain.masks import valid_mask
from app.domain.sensors import Source
from app.services.catalog import FoundItem

log = logging.getLogger(__name__)

odc.stac.configure_rio(cloud_defaults=True)

S2_HARMONIZATION_BASELINE = "04.00"
S2_BOA_OFFSET_DN = -1000


# Com fail_on_error=False, o odc-stac não interrompe o job quando um COG remoto falha de vez
# (depois das novas tentativas do GDAL): ele registra este aviso e deixa o bloco sem dado.
_ODC_READER_LOGGER = "odc.loader._rio"
_ODC_READ_FAILURE = "Ignoring read failure"


class ReadFailureMonitor(logging.Handler):
    """Registra as leituras remotas abandonadas que pertencem às cenas de um processamento.

    Filtra pelas URLs das cenas do job, de modo que falhas de outro job rodando em paralelo
    não sejam atribuídas a este.
    """

    def __init__(self, hrefs: set[str]) -> None:
        super().__init__(logging.WARNING)
        self._hrefs = hrefs
        self.failures: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if not str(record.msg).startswith(_ODC_READ_FAILURE) or not record.args:
            return
        args = record.args if isinstance(record.args, tuple) else (record.args,)
        href = _strip_query(str(args[0]))
        if href in self._hrefs:
            self.failures.append(href)


def _strip_query(url: str) -> str:
    # remove a assinatura (SAS token) para comparar com o href original do STAC
    return url.split("?", 1)[0]


@contextmanager
def monitor_read_failures(items: Iterable[FoundItem]) -> Iterator[ReadFailureMonitor]:
    hrefs = {_strip_query(asset.href) for it in items for asset in it.item.assets.values()}
    handler = ReadFailureMonitor(hrefs)
    logger = logging.getLogger(_ODC_READER_LOGGER)
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


def build_geobox(bbox: tuple[float, float, float, float], crs: str, resolution_m: float) -> GeoBox:
    bb = BoundingBox(*bbox, crs="EPSG:4326").to_crs(crs)
    return GeoBox.from_bbox(bb, resolution=resolution_m, tight=False)


def footprint_coverage(items: Sequence[FoundItem], bbox: tuple[float, float, float, float]) -> float:
    """Fração da AOI coberta pela união das pegadas das cenas (sem considerar nuvem)."""
    aoi = box(*bbox, crs="EPSG:4326")
    if not items:
        return 0.0
    union: Geometry | None = None
    for it in items:
        geom = Geometry(it.item.geometry, crs="EPSG:4326")
        union = geom if union is None else union.union(geom)
    assert union is not None
    return float(min(1.0, union.intersection(aoi).area / aoi.area))


@dataclass
class SourceStack:
    """Pilha temporal de uma fonte: um plano por dia de aquisição, já com a máscara calculada."""

    source: Source
    items: list[FoundItem]
    times: list[pd.Timestamp]
    groups: list[list[FoundItem]]
    valid: np.ndarray | None  # (tempo, y, x) True = pixel utilizável; None = sem banda de qualidade
    valid_fraction: list[float]  # fração da AOI utilizável em cada data


def _stac_cfg(source: Source) -> dict:
    assets = {asset: {"data_type": source.dtype, "nodata": source.nodata} for asset in source.bands.values()}
    if source.mask_asset:
        mask_nodata = {"SCL": 0, "qa_pixel": 1, "Fmask": 255}.get(source.mask_asset)
        mask_dtype = "uint16" if source.mask_asset == "qa_pixel" else "uint8"
        assets[source.mask_asset] = {"data_type": mask_dtype, "nodata": mask_nodata}
    return {source.collection: {"assets": assets}}


def _group_items(times: Sequence[pd.Timestamp], items: Sequence[FoundItem]) -> list[list[FoundItem]]:
    """Associa cada plano temporal às cenas daquele dia (o odc-stac usa o horário da 1ª cena do grupo)."""
    by_day: dict[date, list[FoundItem]] = defaultdict(list)
    for it in items:
        by_day[_solar_day(it)].append(it)
    groups = []
    for t in times:
        nearest = min(by_day, key=lambda d: abs((pd.Timestamp(d) - t.tz_localize(None).normalize()).days))
        groups.append(by_day[nearest])
    return groups


def _solar_day(it: FoundItem) -> date:
    dt = pd.Timestamp(it.item.datetime).tz_convert(None) if it.item.datetime.tzinfo else pd.Timestamp(it.item.datetime)
    lon = (it.item.bbox[0] + it.item.bbox[2]) / 2 if it.item.bbox else 0.0
    return (dt + pd.Timedelta(hours=lon / 15)).date()


def _load(
    items: Sequence[FoundItem],
    assets: list[str],
    geobox: GeoBox,
    sign: Callable[[str], str],
    *,
    resampling: str,
    chunks: dict[str, int] | None,
) -> xr.Dataset:
    source = items[0].source
    with warnings.catch_warnings():
        # assets auxiliares sem georreferência; os demais avisos continuam visíveis
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        return odc.stac.load(
            [it.item for it in items],
            bands=assets,
            geobox=geobox,
            groupby="solar_day",
            resampling=resampling,
            chunks=chunks,
            stac_cfg=_stac_cfg(source),
            patch_url=sign,
            fail_on_error=False,
        )


def load_stack(
    items: Sequence[FoundItem],
    geobox: GeoBox,
    sign: Callable[[str], str],
    cloud_buffer_px: int = 0,
) -> SourceStack:
    """Monta a pilha temporal e a máscara de validade a partir da banda de qualidade.

    Fontes sem banda de qualidade (radar) não baixam nada aqui: a validade vem dos próprios
    dados durante a composição, e a fração por data é estimada pela pegada das cenas.
    """
    source = items[0].source
    aoi_bbox = tuple(geobox.extent.to_crs("EPSG:4326").boundingbox)
    if source.mask_asset and source.mask_kind:
        ds = _load(items, [source.mask_asset], geobox, sign, resampling="nearest", chunks=None)
        qa = ds[source.mask_asset].values
        valid: np.ndarray | None = np.stack([valid_mask(source.mask_kind, q, cloud_buffer_px) for q in qa])
    else:
        first_band = next(iter(source.bands.values()))
        ds = _load(items, [first_band], geobox, sign, resampling="nearest", chunks={})
        valid = None
    times = [pd.Timestamp(t) for t in ds.time.values]
    groups = _group_items(times, items)
    if valid is not None:
        fractions = [float(v.mean()) for v in valid]
    else:
        fractions = [footprint_coverage(g, aoi_bbox) for g in groups]
    return SourceStack(source, list(items), times, groups, valid, fractions)


def load_band(
    stack: SourceStack,
    band: str,
    geobox: GeoBox,
    sign: Callable[[str], str],
    chunk_size: int,
) -> xr.DataArray:
    """Banda em reflectância (ou gamma0) como float32 lazy (dask), com nuvem e sem dado = NaN."""
    source = stack.source
    asset = source.bands[band]
    ds = _load(
        stack.items,
        [asset],
        geobox,
        sign,
        resampling="bilinear",
        chunks={"x": chunk_size, "y": chunk_size},
    )
    raw = ds[asset]
    if len(raw.time) != len(stack.times):
        raise RuntimeError(f"{asset}: número de datas diverge da máscara ({len(raw.time)} ≠ {len(stack.times)})")

    offset = np.full(len(stack.times), source.offset, dtype=np.float32)
    if source.harmonize_s2_offset:
        for i, group in enumerate(stack.groups):
            baseline = str(group[0].item.properties.get("s2:processing_baseline", "00.00"))
            if baseline >= S2_HARMONIZATION_BASELINE:
                offset[i] += S2_BOA_OFFSET_DN * source.scale
    offset_da = xr.DataArray(offset, dims="time", coords={"time": raw.time})

    data = raw.astype(np.float32) * np.float32(source.scale) + offset_da
    if source.nodata is not None:
        data = data.where(raw != source.nodata)
    if stack.valid is not None:
        data = data.where(xr.DataArray(stack.valid, dims=raw.dims, coords=raw.coords))
    return data.chunk({"time": -1})


@dataclass(frozen=True)
class CoverageEstimate:
    coverage: float  # fração da AOI com ao menos uma observação válida
    per_date: dict[date, float]  # fração válida da AOI em cada data


def by_source(items: Sequence[FoundItem]) -> list[list[FoundItem]]:
    groups: dict[str, list[FoundItem]] = defaultdict(list)
    for it in items:
        groups[it.source.collection].append(it)
    return list(groups.values())


def estimate_coverage(
    items: Sequence[FoundItem],
    geobox: GeoBox,
    sign: Callable[[str], str],
) -> CoverageEstimate:
    """Estimativa barata (grade grosseira, só a banda de qualidade) da cobertura sem nuvem."""
    if not items:
        return CoverageEstimate(0.0, {})
    per_date: dict[date, float] = {}
    any_valid = np.zeros(geobox.shape, dtype=bool)
    footprint_only: list[FoundItem] = []
    for group in by_source(items):
        stack = load_stack(group, geobox, sign)
        if stack.valid is None:
            footprint_only.extend(group)
        else:
            any_valid |= stack.valid.any(axis=0)
        for t, frac in zip(stack.times, stack.valid_fraction, strict=True):
            day = t.date()
            per_date[day] = max(per_date.get(day, 0.0), frac)
    coverage = float(any_valid.mean())
    if footprint_only:
        aoi_bbox = tuple(geobox.extent.to_crs("EPSG:4326").boundingbox)
        coverage = max(coverage, footprint_coverage(footprint_only, aoi_bbox))
    return CoverageEstimate(coverage, per_date)
