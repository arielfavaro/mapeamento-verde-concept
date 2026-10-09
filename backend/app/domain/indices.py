"""Índices espectrais: definição (metadados para a interface) e cálculo (numpy puro).

As bandas são referenciadas por nome comum (``red``, ``nir``, ``swir1``...), de modo que o
mesmo índice funciona para qualquer satélite que tenha as bandas necessárias.
Reflectâncias ópticas chegam em escala 0–1; radar chega em gamma0 linear.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import numpy as np

Bands = Mapping[str, np.ndarray]


@dataclass(frozen=True)
class IndexClass:
    """Faixa de valores com interpretação (usada na legenda e nas estatísticas de área)."""

    min: float
    max: float
    label: str


@dataclass(frozen=True)
class SpectralIndex:
    id: str
    name: str
    category: str
    formula: str
    bands: tuple[str, ...]
    description: str
    reference: str
    colormap: str
    vmin: float
    vmax: float
    compute: Callable[[Bands], np.ndarray] = field(repr=False)
    classes: tuple[IndexClass, ...] = ()
    unit: str = ""


def normalized_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """(a - b) / (a + b), com NaN onde o denominador é zero ou algum dado falta."""
    a = a.astype(np.float32, copy=False)
    b = b.astype(np.float32, copy=False)
    den = a + b
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (a - b) / den
    out[den == 0] = np.nan
    return out


def _nd(a: str, b: str) -> Callable[[Bands], np.ndarray]:
    return lambda bands: normalized_difference(bands[a], bands[b])


def _evi(b: Bands) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 2.5 * (b["nir"] - b["red"]) / (b["nir"] + 6 * b["red"] - 7.5 * b["blue"] + 1)
    return out.astype(np.float32)


def _savi(b: Bands, soil: float = 0.5) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (1 + soil) * (b["nir"] - b["red"]) / (b["nir"] + b["red"] + soil)
    return out.astype(np.float32)


def _db(x: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 10 * np.log10(np.where(x > 0, x, np.nan))
    return out.astype(np.float32)


def _rvi(b: Bands) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 4 * b["vh"] / (b["vv"] + b["vh"])
    return out.astype(np.float32)


def _cross_ratio(b: Bands) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return _db(b["vh"] / b["vv"])


VEG = "Vegetação"
AGUA = "Água e umidade"
FOGO = "Fogo e queimadas"
RADAR = "Radar (SAR)"

INDICES: tuple[SpectralIndex, ...] = (
    SpectralIndex(
        id="NDVI",
        name="NDVI",
        category=VEG,
        formula="(NIR − RED) / (NIR + RED)",
        bands=("nir", "red"),
        compute=_nd("nir", "red"),
        description="Densidade de biomassa verde e atividade fotossintética. Satura em dossel muito denso.",
        reference="Rouse et al. (1974)",
        colormap="rdylgn",
        vmin=-0.1,
        vmax=0.85,
        classes=(
            IndexClass(-1.0, 0.0, "Água, nuvem residual, asfalto"),
            IndexClass(0.0, 0.2, "Solo exposto, área urbana, palhada"),
            IndexClass(0.2, 0.5, "Vegetação esparsa, pastagem, cultura inicial"),
            IndexClass(0.5, 0.7, "Vegetação moderada a densa"),
            IndexClass(0.7, 1.0, "Floresta densa, cana no ápice, pivô irrigado"),
        ),
    ),
    SpectralIndex(
        id="NDRE",
        name="NDRE",
        category=VEG,
        formula="(NIR − RedEdge) / (NIR + RedEdge)",
        bands=("nir", "rededge"),
        compute=_nd("nir", "rededge"),
        description="Sensível ao teor de clorofila; detecta estresse nutricional/hídrico antes do NDVI. "
        "Exige banda Red Edge (só Sentinel-2).",
        reference="Gitelson & Merzlyak (1994)",
        colormap="rdylgn",
        vmin=-0.1,
        vmax=0.75,
        classes=(
            IndexClass(-1.0, 0.0, "Água, superfícies sem vegetação"),
            IndexClass(0.0, 0.2, "Solo exposto ou vegetação muito estressada"),
            IndexClass(0.2, 0.4, "Clorofila moderada / possível estresse"),
            IndexClass(0.4, 1.0, "Clorofila alta, vegetação sadia"),
        ),
    ),
    SpectralIndex(
        id="EVI",
        name="EVI",
        category=VEG,
        formula="2,5 · (NIR − RED) / (NIR + 6·RED − 7,5·BLUE + 1)",
        bands=("nir", "red", "blue"),
        compute=_evi,
        description="Variante do NDVI com correção atmosférica (azul) e de solo; satura menos em "
        "florestas e canaviais densos.",
        reference="Huete et al. (2002)",
        colormap="rdylgn",
        vmin=-0.1,
        vmax=0.8,
        classes=(
            IndexClass(-1.0, 0.1, "Sem vegetação"),
            IndexClass(0.1, 0.3, "Vegetação esparsa"),
            IndexClass(0.3, 0.5, "Vegetação moderada"),
            IndexClass(0.5, 1.5, "Vegetação densa e vigorosa"),
        ),
    ),
    SpectralIndex(
        id="SAVI",
        name="SAVI",
        category=VEG,
        formula="1,5 · (NIR − RED) / (NIR + RED + 0,5)",
        bands=("nir", "red"),
        compute=_savi,
        description="NDVI ajustado ao brilho do solo (L = 0,5); melhor em pastagens e culturas no início do ciclo.",
        reference="Huete (1988)",
        colormap="rdylgn",
        vmin=-0.1,
        vmax=0.8,
        classes=(
            IndexClass(-1.5, 0.1, "Sem vegetação"),
            IndexClass(0.1, 0.3, "Vegetação esparsa / solo dominante"),
            IndexClass(0.3, 0.5, "Vegetação moderada"),
            IndexClass(0.5, 1.5, "Vegetação densa"),
        ),
    ),
    SpectralIndex(
        id="NDWI",
        name="NDWI",
        category=AGUA,
        formula="(GREEN − NIR) / (GREEN + NIR)",
        bands=("green", "nir"),
        compute=_nd("green", "nir"),
        description="Realça água livre (rios, represas, lagoas). Valores positivos indicam água.",
        reference="McFeeters (1996)",
        colormap="blues",
        vmin=-0.5,
        vmax=0.5,
        classes=(
            IndexClass(-1.0, -0.3, "Vegetação densa / solo seco"),
            IndexClass(-0.3, 0.0, "Transição, superfícies úmidas"),
            IndexClass(0.0, 1.0, "Água superficial"),
        ),
    ),
    SpectralIndex(
        id="MNDWI",
        name="MNDWI",
        category=AGUA,
        formula="(GREEN − SWIR1) / (GREEN + SWIR1)",
        bands=("green", "swir1"),
        compute=_nd("green", "swir1"),
        description="Versão do NDWI com SWIR, que suprime falsos positivos de área construída e solo exposto.",
        reference="Xu (2006)",
        colormap="coolwarm",
        vmin=-0.5,
        vmax=0.5,
        classes=(
            IndexClass(-1.0, -0.2, "Solo seco, área construída, vegetação"),
            IndexClass(-0.2, 0.0, "Umidade superficial"),
            IndexClass(0.0, 1.0, "Água"),
        ),
    ),
    SpectralIndex(
        id="NDMI",
        name="NDMI",
        category=AGUA,
        formula="(NIR − SWIR1) / (NIR + SWIR1)",
        bands=("nir", "swir1"),
        compute=_nd("nir", "swir1"),
        description="Teor de água no dossel. Queda indica estresse hídrico.",
        reference="Gao (1996)",
        colormap="ylgnbu",
        vmin=-0.3,
        vmax=0.6,
        classes=(
            IndexClass(-1.0, 0.0, "Solo seco, estresse hídrico severo, área urbana"),
            IndexClass(0.0, 0.2, "Vegetação seca / palhada"),
            IndexClass(0.2, 0.4, "Umidade moderada"),
            IndexClass(0.4, 1.0, "Dossel túrgido e hidratado"),
        ),
    ),
    SpectralIndex(
        id="NBR",
        name="NBR",
        category=FOGO,
        formula="(NIR − SWIR2) / (NIR + SWIR2)",
        bands=("nir", "swir2"),
        compute=_nd("nir", "swir2"),
        description="Cicatrizes de fogo: queimadas derrubam o NIR e elevam o SWIR2. Para severidade, "
        "compare datas únicas antes/depois (ΔNBR) em vez de medianas longas.",
        reference="Key & Benson (2006)",
        colormap="ylorrd_r",
        vmin=-0.3,
        vmax=0.8,
        classes=(
            IndexClass(-1.0, -0.1, "Queimada recente / cinzas"),
            IndexClass(-0.1, 0.1, "Solo exposto"),
            IndexClass(0.1, 0.5, "Vegetação moderada não queimada"),
            IndexClass(0.5, 1.0, "Vegetação vigorosa não queimada"),
        ),
    ),
    SpectralIndex(
        id="RVI",
        name="RVI (radar)",
        category=RADAR,
        formula="4 · VH / (VV + VH)",
        bands=("vv", "vh"),
        compute=_rvi,
        description="Índice de vegetação por radar (dupla polarização): cresce com a biomassa e a "
        "estrutura do dossel. Funciona com nuvens.",
        reference="Nasirzadehdizaji et al. (2019)",
        colormap="rdylgn",
        vmin=0.0,
        vmax=1.0,
        classes=(
            IndexClass(0.0, 0.3, "Água, solo exposto, área urbana"),
            IndexClass(0.3, 0.6, "Vegetação baixa / pastagem"),
            IndexClass(0.6, 2.0, "Vegetação alta / densa"),
        ),
    ),
    SpectralIndex(
        id="VV_DB",
        name="VV (dB)",
        category=RADAR,
        formula="10 · log10(VV)",
        bands=("vv",),
        compute=lambda b: _db(b["vv"]),
        unit="dB",
        description="Retroespalhamento co-polarizado. Água calma reflete como espelho e fica muito escura.",
        reference="ESA Sentinel-1 User Guide",
        colormap="greys_r",
        vmin=-25.0,
        vmax=0.0,
        classes=(
            IndexClass(-50.0, -18.0, "Água calma / sombra de radar"),
            IndexClass(-18.0, -10.0, "Solo, pastagem, vegetação"),
            IndexClass(-10.0, 20.0, "Área urbana, superfícies rugosas"),
        ),
    ),
    SpectralIndex(
        id="CR",
        name="VH/VV (dB)",
        category=RADAR,
        formula="10 · log10(VH / VV)",
        bands=("vv", "vh"),
        compute=_cross_ratio,
        unit="dB",
        description="Razão de polarização cruzada: aumenta com espalhamento volumétrico (dossel vegetal).",
        reference="Vreugdenhil et al. (2018)",
        colormap="ylgn",
        vmin=-15.0,
        vmax=-3.0,
        classes=(
            IndexClass(-50.0, -12.0, "Superfície lisa ou sem vegetação"),
            IndexClass(-12.0, -7.0, "Vegetação intermediária"),
            IndexClass(-7.0, 10.0, "Dossel denso"),
        ),
    ),
)

INDEX_BY_ID: dict[str, SpectralIndex] = {i.id: i for i in INDICES}


def available_indices(band_names: set[str] | frozenset[str]) -> list[SpectralIndex]:
    """Índices calculáveis com as bandas oferecidas por um satélite."""
    return [i for i in INDICES if set(i.bands) <= band_names]


def compute_index(index: SpectralIndex, bands: Bands) -> np.ndarray:
    missing = set(index.bands) - set(bands)
    if missing:
        raise ValueError(f"{index.id} precisa das bandas {sorted(missing)}")
    return index.compute(bands).astype(np.float32, copy=False)
