"""Configuração da aplicação, lida de variáveis de ambiente (prefixo MV_)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MV_", env_file=".env", extra="ignore")

    # Onde os processamentos (GeoTIFFs, metadados) ficam gravados.
    storage_dir: Path = Path("storage")

    # Catálogo STAC público (Microsoft Planetary Computer, acesso anônimo com URLs assinadas).
    stac_url: str = "https://planetarycomputer.microsoft.com/api/stac/v1"

    # SIRGAS 2000 / UTM 23S: mesmo CRS do projeto QGIS, pixels quadrados em metros.
    target_crs: str = "EPSG:31983"

    # Proteções contra pedidos que estourariam memória/tempo.
    max_aoi_km2: float = 2500.0
    max_scenes_per_job: int = 120
    max_concurrent_jobs: int = 1

    # Resolução usada para estimar nuvem/cobertura dentro da AOI (barata, só a banda de máscara).
    coverage_resolution_m: float = 100.0

    # Tamanho dos blocos (pixels) no processamento com dask.
    chunk_size: int = 1024

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
