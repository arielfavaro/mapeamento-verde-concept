"""Catálogo de satélites suportados: como acessar no STAC e como explicar para o usuário.

Cada satélite (``Sensor``) tem uma ou mais fontes (``Source``, uma coleção STAC). O HLS, por
exemplo, combina duas coleções (S30 e L30) já harmonizadas pela NASA.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.domain.masks import MaskKind


class SensorKind(StrEnum):
    OPTICAL = "optical"
    RADAR = "radar"


@dataclass(frozen=True)
class BandInfo:
    common: str
    label: str
    wavelength: str
    resolution_m: int


@dataclass(frozen=True)
class Source:
    collection: str
    # nome comum -> nome do asset STAC
    bands: dict[str, str]
    scale: float = 1.0
    offset: float = 0.0
    nodata: float | None = None
    dtype: str = "float32"
    mask_asset: str | None = None
    mask_kind: MaskKind | None = None
    query: dict[str, Any] = field(default_factory=dict)
    # Sentinel-2 com baseline >= 04.00 grava DN com +1000; precisa subtrair para harmonizar.
    harmonize_s2_offset: bool = False
    tile_of: Callable[[dict[str, Any], str], str] = field(default=lambda props, item_id: "", repr=False)


@dataclass(frozen=True)
class SensorInfo:
    summary: str
    how_it_works: str
    processing: str
    strengths: tuple[str, ...]
    limitations: tuple[str, ...]
    best_for: tuple[str, ...]
    mission: str


@dataclass(frozen=True)
class Sensor:
    id: str
    name: str
    kind: SensorKind
    resolution_m: int
    revisit: str
    since: str
    sources: tuple[Source, ...]
    bands: tuple[BandInfo, ...]
    info: SensorInfo
    # Bandas usadas para a composição RGB de visualização.
    rgb: tuple[str, str, str] | None = ("red", "green", "blue")
    false_color: tuple[str, str, str] | None = ("nir", "red", "green")

    @property
    def band_names(self) -> frozenset[str]:
        return frozenset(b.common for b in self.bands)

    @property
    def cloud_filterable(self) -> bool:
        return self.kind is SensorKind.OPTICAL


def _s2_tile(props: dict[str, Any], _id: str) -> str:
    return props.get("s2:mgrs_tile", "")


def _landsat_tile(props: dict[str, Any], _id: str) -> str:
    return f"{props.get('landsat:wrs_path', '')}/{props.get('landsat:wrs_row', '')}"


def _hls_tile(_props: dict[str, Any], item_id: str) -> str:
    # ex.: HLS.S30.T23KKS.2025208T132239.v2.0
    parts = item_id.split(".")
    return parts[2].lstrip("T") if len(parts) > 2 else ""


def _s1_tile(props: dict[str, Any], _id: str) -> str:
    orbit = props.get("sat:orbit_state", "")
    return f"órbita {props.get('sat:relative_orbit', '?')} ({orbit})"


SENTINEL_2 = Sensor(
    id="sentinel-2",
    name="Sentinel-2 MSI (L2A)",
    kind=SensorKind.OPTICAL,
    resolution_m=10,
    revisit="5 dias por ponto (2 satélites); 6–8 passagens/mês sobre Porto Ferreira por sobreposição de órbitas",
    since="2015 (2A), 2017 (2B), 2024 (2C)",
    sources=(
        Source(
            collection="sentinel-2-l2a",
            bands={
                "blue": "B02",
                "green": "B03",
                "red": "B04",
                "rededge": "B05",
                "nir": "B08",
                "swir1": "B11",
                "swir2": "B12",
            },
            scale=1e-4,
            nodata=0,
            dtype="uint16",
            mask_asset="SCL",
            mask_kind=MaskKind.SCL,
            harmonize_s2_offset=True,
            tile_of=_s2_tile,
        ),
    ),
    bands=(
        BandInfo("blue", "B2 · Azul", "490 nm", 10),
        BandInfo("green", "B3 · Verde", "560 nm", 10),
        BandInfo("red", "B4 · Vermelho", "665 nm", 10),
        BandInfo("rededge", "B5 · Red Edge", "705 nm", 20),
        BandInfo("nir", "B8 · NIR", "842 nm", 10),
        BandInfo("swir1", "B11 · SWIR 1", "1610 nm", 20),
        BandInfo("swir2", "B12 · SWIR 2", "2190 nm", 20),
    ),
    info=SensorInfo(
        mission="Copernicus (ESA / União Europeia)",
        summary="Câmera multiespectral de 13 bandas com a melhor resolução gratuita (10 m) e bandas "
        "Red Edge. É a opção padrão para mapear talhões, mata ciliar e corpos d'água.",
        how_it_works="Sensor óptico passivo: mede a luz do sol refletida pela superfície. O satélite cruza o "
        "equador às ~10h30 (hora local) e varre uma faixa de 290 km. A cena é entregue em tiles "
        "MGRS de 110×110 km; Porto Ferreira cai na divisa de 4 tiles (22KHA, 22KHB, 23KKR, 23KKS).",
        processing="Nível 2A (reflectância de superfície, corrigida pelo Sen2Cor). A nuvem é mascarada "
        "pixel a pixel pela banda SCL (sombra, nuvem média/alta e cirrus), com margem de segurança. "
        "Desde a baseline 04.00 (jan/2022) os números digitais têm +1000; o offset é removido para que "
        "a série antiga e a nova fiquem comparáveis (equivale ao S2_SR_HARMONIZED do Earth Engine).",
        strengths=(
            "10 m nas bandas visíveis e NIR",
            "Red Edge (B5) permite NDRE: estresse antes de aparecer no NDVI",
            "Revisita frequente: de 6 a 8 passagens por mês na região",
        ),
        limitations=(
            "Óptico: não enxerga através de nuvens. De dezembro a fevereiro pode não haver nenhum dia limpo no mês",
            "Bandas Red Edge e SWIR têm 20 m (são reamostradas para 10 m)",
        ),
        best_for=("Vigor vegetal e cana-de-açúcar", "APP e mata ciliar", "Corpos d'água", "Cicatrizes de queimada"),
    ),
)

LANDSAT = Sensor(
    id="landsat",
    name="Landsat 8/9 OLI (Coleção 2, Nível 2)",
    kind=SensorKind.OPTICAL,
    resolution_m=30,
    revisit="16 dias por satélite; 8 dias combinando Landsat 8 e 9",
    since="2013 (Landsat 8), 2021 (Landsat 9)",
    sources=(
        Source(
            collection="landsat-c2-l2",
            bands={
                "blue": "blue",
                "green": "green",
                "red": "red",
                "nir": "nir08",
                "swir1": "swir16",
                "swir2": "swir22",
            },
            scale=2.75e-5,
            offset=-0.2,
            nodata=0,
            dtype="uint16",
            mask_asset="qa_pixel",
            mask_kind=MaskKind.QA_PIXEL,
            query={"platform": {"in": ["landsat-8", "landsat-9"]}},
            tile_of=_landsat_tile,
        ),
    ),
    bands=(
        BandInfo("blue", "B2 · Azul", "482 nm", 30),
        BandInfo("green", "B3 · Verde", "561 nm", 30),
        BandInfo("red", "B4 · Vermelho", "655 nm", 30),
        BandInfo("nir", "B5 · NIR", "865 nm", 30),
        BandInfo("swir1", "B6 · SWIR 1", "1609 nm", 30),
        BandInfo("swir2", "B7 · SWIR 2", "2201 nm", 30),
    ),
    info=SensorInfo(
        mission="NASA / USGS",
        summary="Programa de observação mais longo da Terra (desde 1972), com radiometria muito estável. "
        "Ideal para comparações de vários anos.",
        how_it_works="Sensor óptico passivo (OLI/OLI-2) com faixa de 185 km, organizado em órbitas WRS-2 "
        "(path/row). Cada satélite repete a mesma cena a cada 16 dias; os dois juntos, a cada 8.",
        processing="Coleção 2 Nível 2: reflectância de superfície calculada pelo USGS (LaSRC), convertida com "
        "fator 0,0000275 e offset −0,2. Nuvem, sombra, cirrus e neve são mascaradas pela banda QA_PIXEL. "
        "Landsat 7 fica de fora (falha do SLC desde 2003 gera listras sem dado).",
        strengths=(
            "Série histórica longa e consistente para tendências de vários anos",
            "Calibração de referência mundial",
            "Banda térmica disponível no produto (não usada aqui)",
        ),
        limitations=(
            "30 m: talhões pequenos e faixas de APP estreitas ficam misturados",
            "Sem Red Edge: o NDRE não é calculado",
            "Menos passagens que o Sentinel-2: períodos chuvosos ficam com pouca imagem",
        ),
        best_for=("Comparações de longo prazo", "Mudança de uso do solo", "Validação cruzada com o Sentinel-2"),
    ),
)

HLS = Sensor(
    id="hls",
    name="HLS v2 (Landsat + Sentinel-2 harmonizados)",
    kind=SensorKind.OPTICAL,
    resolution_m=30,
    revisit="2–3 dias combinando Sentinel-2 e Landsat 8/9",
    since="2013 (L30), 2015 (S30)",
    sources=(
        Source(
            collection="hls2-s30",
            bands={"blue": "B02", "green": "B03", "red": "B04", "nir": "B8A", "swir1": "B11", "swir2": "B12"},
            scale=1e-4,
            nodata=-9999,
            dtype="int16",
            mask_asset="Fmask",
            mask_kind=MaskKind.FMASK,
            tile_of=_hls_tile,
        ),
        Source(
            collection="hls2-l30",
            bands={"blue": "B02", "green": "B03", "red": "B04", "nir": "B05", "swir1": "B06", "swir2": "B07"},
            scale=1e-4,
            nodata=-9999,
            dtype="int16",
            mask_asset="Fmask",
            mask_kind=MaskKind.FMASK,
            tile_of=_hls_tile,
        ),
    ),
    bands=(
        BandInfo("blue", "Azul", "~490 nm", 30),
        BandInfo("green", "Verde", "~560 nm", 30),
        BandInfo("red", "Vermelho", "~660 nm", 30),
        BandInfo("nir", "NIR estreito (S2 B8A / L B5)", "~865 nm", 30),
        BandInfo("swir1", "SWIR 1", "~1610 nm", 30),
        BandInfo("swir2", "SWIR 2", "~2200 nm", 30),
    ),
    info=SensorInfo(
        mission="NASA (Harmonized Landsat Sentinel-2)",
        summary="Junta Sentinel-2 e Landsat 8/9 em uma única série de 30 m, como se fosse um só satélite: "
        "é a forma mais eficaz de conseguir dias sem nuvem na estação chuvosa.",
        how_it_works="A NASA reprocessa as duas missões com a mesma correção atmosférica, reamostra tudo para a "
        "grade MGRS de 30 m, ajusta as diferenças de banda espectral e normaliza o ângulo de visada (BRDF). "
        "Com isso, uma cena Landsat e uma Sentinel-2 podem ser misturadas na mesma mediana.",
        processing="Produtos S30 (Sentinel-2) e L30 (Landsat) pesquisados juntos; nuvem, sombra e "
        "adjacência são mascaradas pela banda Fmask. Usa o NIR estreito (B8A) do Sentinel-2 por ser o "
        "equivalente espectral do NIR do Landsat.",
        strengths=(
            "Maior frequência de observação gratuita: uma imagem a cada 2–3 dias",
            "Série consistente entre sensores",
            "Melhor chance de uma composição sem buracos na estação chuvosa",
        ),
        limitations=(
            "30 m, mesmo nos dados vindos do Sentinel-2",
            "Sem Red Edge (o Landsat não tem), então nada de NDRE",
            "Os produtos saem com alguns dias de atraso em relação aos originais",
        ),
        best_for=("Séries temporais densas", "Meses chuvosos", "Fenologia (ciclo da cana)"),
    ),
)

SENTINEL_1 = Sensor(
    id="sentinel-1",
    name="Sentinel-1 SAR (RTC, banda C)",
    kind=SensorKind.RADAR,
    resolution_m=10,
    revisit="12 dias por satélite; ~6 dias com Sentinel-1A + 1C (desde 2025)",
    since="2014 (1A), 2024 (1C)",
    sources=(
        Source(
            collection="sentinel-1-rtc",
            bands={"vv": "vv", "vh": "vh"},
            nodata=-32768,
            dtype="float32",
            tile_of=_s1_tile,
        ),
    ),
    bands=(
        BandInfo("vv", "VV (co-polarizada)", "5,6 cm (banda C)", 10),
        BandInfo("vh", "VH (polarização cruzada)", "5,6 cm (banda C)", 10),
    ),
    info=SensorInfo(
        mission="Copernicus (ESA / União Europeia)",
        summary="Radar de abertura sintética: emite micro-ondas e mede o eco. Enxerga através de nuvens "
        "e à noite, por isso é o complemento natural dos ópticos na estação chuvosa.",
        how_it_works="O sinal (5,6 cm) interage com a geometria e a umidade da superfície, não com a cor: água "
        "calma reflete para longe e aparece escura, vegetação gera espalhamento volumétrico (VH alto) e "
        "construções geram reflexão dupla (muito brilhantes).",
        processing="Produto RTC do Planetary Computer: retroespalhamento gamma0 com correção radiométrica do "
        "relevo, em escala linear. A mediana temporal reduz o speckle (ruído granular típico do radar). "
        "Não há máscara de nuvem porque o radar não é afetado por elas.",
        strengths=(
            "Independente de nuvem e de iluminação solar",
            "Excelente para delimitar água e áreas alagadas",
            "Sensível à estrutura e à umidade da vegetação",
        ),
        limitations=(
            "Não calcula índices ópticos (NDVI e afins); usa RVI e as razões de polarização",
            "Speckle: pixels individuais são ruidosos",
            "Arquivos grandes: o download é mais lento que o dos ópticos",
        ),
        best_for=("Água e cheias na estação chuvosa", "Acompanhar a cana quando há nuvem", "Complemento aos ópticos"),
    ),
    rgb=None,
    false_color=None,
)

SENSORS: tuple[Sensor, ...] = (SENTINEL_2, HLS, LANDSAT, SENTINEL_1)
SENSOR_BY_ID: dict[str, Sensor] = {s.id: s for s in SENSORS}


def get_sensor(sensor_id: str) -> Sensor:
    try:
        return SENSOR_BY_ID[sensor_id]
    except KeyError as exc:
        raise ValueError(f"Satélite desconhecido: {sensor_id}") from exc
