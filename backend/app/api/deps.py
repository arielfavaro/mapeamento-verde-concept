"""Injeção de dependências: os serviços ficam em ``app.state`` e são trocáveis nos testes."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings
from app.services.catalog import SceneCatalog
from app.services.jobs import JobRunner, JobStore


@dataclass
class Services:
    settings: Settings
    catalog: SceneCatalog
    store: JobStore
    runner: JobRunner


def get_services(request: Request) -> Services:
    return request.app.state.services


ServicesDep = Annotated[Services, Depends(get_services)]
