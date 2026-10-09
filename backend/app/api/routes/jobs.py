import os
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api.deps import ServicesDep
from app.domain.aoi import bbox_area_km2
from app.domain.models import Job, JobRequest, JobState, JobSummary
from app.services.jobs import JobNotFoundError
from app.services.tiles import render_tile

router = APIRouter(prefix="/jobs", tags=["processamentos"])


def _get_job(services: ServicesDep, job_id: str) -> Job:
    try:
        return services.store.get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(404, "Processamento não encontrado") from exc


def _output_path(services: ServicesDep, job: Job, name: str) -> Path:
    if job.result is None or name not in {f.name for f in job.result.files}:
        raise HTTPException(404, "Arquivo não encontrado")
    return services.store.job_dir(job.id) / name


@router.post("", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
def create_job(body: JobRequest, services: ServicesDep) -> Job:
    limit = services.settings.max_aoi_km2
    if bbox_area_km2(*body.aoi.as_tuple()) > limit:
        raise HTTPException(422, f"AOI maior que {limit:.0f} km²")
    job = services.store.create(body)
    services.runner.submit(job.id)
    return job


@router.get("", response_model=list[JobSummary])
def list_jobs(services: ServicesDep) -> list[JobSummary]:
    return [job.summary() for job in services.store.list()]


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: str, services: ServicesDep) -> Job:
    return _get_job(services, job_id)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str, services: ServicesDep) -> Response:
    job = _get_job(services, job_id)
    if job.state in (JobState.QUEUED, JobState.RUNNING):
        raise HTTPException(409, "Aguarde o processamento terminar para excluir")
    services.store.delete(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{job_id}/files/{name}")
def download_file(job_id: str, name: str, services: ServicesDep) -> FileResponse:
    job = _get_job(services, job_id)
    return FileResponse(_output_path(services, job, name), filename=name)


@router.get("/{job_id}/archive.zip")
def download_archive(job_id: str, services: ServicesDep) -> FileResponse:
    job = _get_job(services, job_id)
    if job.result is None or not job.result.files:
        raise HTTPException(404, "Processamento sem resultado")
    # Monta o ZIP em arquivo temporário (pode ter centenas de MB) e apaga depois do envio.
    # GeoTIFFs já são comprimidos (DEFLATE): ZIP_STORED evita gastar CPU à toa.
    with (
        tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp,
        zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED) as zf,
    ):
        for f in job.result.files:
            zf.write(services.store.job_dir(job.id) / f.name, arcname=f.name)
    stem = job.result.files[0].name.rsplit("_", 1)[0]
    return FileResponse(
        tmp.name,
        media_type="application/zip",
        filename=f"{stem}.zip",
        background=BackgroundTask(os.unlink, tmp.name),
    )


@router.get("/{job_id}/tiles/{layer_id}/{z}/{x}/{y}.png")
def get_tile(job_id: str, layer_id: str, z: int, x: int, y: int, services: ServicesDep) -> Response:
    job = _get_job(services, job_id)
    if job.result is None:
        raise HTTPException(404, "Processamento sem resultado")
    layer = next((lyr for lyr in job.result.layers if lyr.id == layer_id), None)
    if layer is None:
        raise HTTPException(404, "Camada não encontrada")
    content = render_tile(_output_path(services, job, layer.file), layer, z, x, y)
    # resultados são imutáveis depois de prontos
    return Response(content, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
