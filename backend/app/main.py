"""Ponto de entrada da API (FastAPI)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.deps import Services
from app.api.routes import jobs, meta, scenes
from app.config import Settings, get_settings
from app.domain.errors import ProcessingError
from app.logging_config import configure_logging
from app.services.catalog import PlanetaryComputerCatalog, SceneCatalog
from app.services.jobs import JobRunner, JobStore, ProcessFn
from app.services.processing import process_job

log = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    catalog: SceneCatalog | None = None,
    process: ProcessFn | None = None,
) -> FastAPI:
    """Monta a aplicação. Os parâmetros permitem injetar dublês nos testes."""
    settings = settings or get_settings()
    catalog = catalog or PlanetaryComputerCatalog(settings.stac_url)
    process = process or partial(_process_with, catalog=catalog, settings=settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store = JobStore(settings.storage_dir)
        recovered = store.recover_interrupted()
        if recovered:
            log.warning("%d processamento(s) interrompido(s) marcados como falhos", recovered)
        runner = JobRunner(store, process, settings.max_concurrent_jobs)
        app.state.services = Services(settings=settings, catalog=catalog, store=store, runner=runner)
        yield
        runner.shutdown()

    app = FastAPI(
        title="Mapeamento Verde API",
        version=__version__,
        description="Busca de cenas, composição sem nuvem e índices espectrais.",
        lifespan=lifespan,
        # sob /api para passar pelo mesmo proxy do nginx
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (meta.router, scenes.router, jobs.router):
        app.include_router(router, prefix="/api")

    @app.exception_handler(ProcessingError)
    async def _processing_error(_: Request, exc: ProcessingError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return app


def _process_with(request, out_dir, report, *, catalog: SceneCatalog, settings: Settings):
    return process_job(request, out_dir, catalog, settings, report)


configure_logging()
app = create_app()
