"""Busca de cenas em catálogos STAC.

A interface ``SceneCatalog`` isola o resto do sistema do provedor concreto: hoje usamos o
Microsoft Planetary Computer (acesso anônimo), mas um catálogo do Earth Search ou do
Copernicus Data Space pode ser plugado implementando o mesmo método.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import planetary_computer
import pystac
import pystac_client

from app.domain.sensors import Sensor, Source

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FoundItem:
    source: Source
    item: pystac.Item

    @property
    def cloud(self) -> float | None:
        value = self.item.properties.get("eo:cloud_cover")
        return float(value) if value is not None else None

    @property
    def platform(self) -> str:
        return str(self.item.properties.get("platform", "")).lower()

    @property
    def tile(self) -> str:
        return self.source.tile_of(self.item.properties, self.item.id)

    @property
    def preview_url(self) -> str | None:
        asset = self.item.assets.get("rendered_preview")
        return asset.href if asset else None


class SceneCatalog(Protocol):
    def search(
        self,
        sensor: Sensor,
        bbox: tuple[float, float, float, float],
        start: date,
        end: date,
        max_scene_cloud: float | None,
    ) -> list[FoundItem]: ...

    def sign(self, href: str) -> str: ...


class PlanetaryComputerCatalog:
    """Catálogo STAC do Planetary Computer. As URLs são assinadas só na hora da leitura."""

    def __init__(self, url: str, max_items: int = 500) -> None:
        self._url = url
        self._max_items = max_items
        self._client: pystac_client.Client | None = None

    @property
    def client(self) -> pystac_client.Client:
        if self._client is None:
            self._client = pystac_client.Client.open(self._url)
        return self._client

    def search(
        self,
        sensor: Sensor,
        bbox: tuple[float, float, float, float],
        start: date,
        end: date,
        max_scene_cloud: float | None,
    ) -> list[FoundItem]:
        found: list[FoundItem] = []
        for source in sensor.sources:
            query = dict(source.query)
            if sensor.cloud_filterable and max_scene_cloud is not None and max_scene_cloud < 100:
                query["eo:cloud_cover"] = {"lt": max_scene_cloud}
            search = self.client.search(
                collections=[source.collection],
                bbox=bbox,
                datetime=f"{start.isoformat()}/{end.isoformat()}",
                query=query or None,
                max_items=self._max_items,
            )
            items = list(search.items())
            log.info("STAC %s %s..%s: %d itens", source.collection, start, end, len(items))
            found.extend(FoundItem(source, it) for it in items)
        found.sort(key=lambda f: f.item.datetime)
        return found

    def sign(self, href: str) -> str:
        return planetary_computer.sign(href)
