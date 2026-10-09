"""Fila de processamentos com estado persistido em disco.

Cada job vive em ``<storage>/jobs/<id>/`` com um ``job.json`` (gravado de forma atômica) e os
arquivos gerados. A execução usa um pool de threads do próprio processo: simples de operar em
um único container; para escalar horizontalmente, troque o ``JobRunner`` por Celery/RQ mantendo
a mesma interface.
"""

import logging
import shutil
import threading
import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from app.domain.errors import ProcessingError
from app.domain.models import Job, JobRequest, JobResult, JobState

log = logging.getLogger(__name__)

ProcessFn = Callable[[JobRequest, Path, Callable[[float, str], None]], JobResult]

MAX_LOG_LINES = 200


class JobNotFoundError(KeyError):
    pass


class JobStore:
    def __init__(self, root: Path) -> None:
        self.root = root / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def job_dir(self, job_id: str) -> Path:
        # ids são uuid4 hex: impede path traversal vindo da URL
        if not (len(job_id) == 32 and all(c in "0123456789abcdef" for c in job_id)):
            raise JobNotFoundError(job_id)
        return self.root / job_id

    def create(self, request: JobRequest) -> Job:
        now = datetime.now(UTC)
        job = Job(
            id=uuid.uuid4().hex,
            created_at=now,
            updated_at=now,
            state=JobState.QUEUED,
            message="Na fila",
            request=request,
        )
        self.job_dir(job.id).mkdir(parents=True)
        self._save(job)
        return job

    def get(self, job_id: str) -> Job:
        path = self.job_dir(job_id) / "job.json"
        if not path.exists():
            raise JobNotFoundError(job_id)
        return Job.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[Job]:
        jobs = []
        for path in self.root.glob("*/job.json"):
            try:
                jobs.append(Job.model_validate_json(path.read_text(encoding="utf-8")))
            except ValueError:
                log.warning("job.json inválido ignorado: %s", path)
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def update(self, job_id: str, *, log_line: str | None = None, **changes) -> Job:
        with self._lock:
            job = self.get(job_id).model_copy(update={**changes, "updated_at": datetime.now(UTC)})
            if log_line:
                stamp = datetime.now(UTC).strftime("%H:%M:%S")
                job.log = [*job.log, f"[{stamp}] {log_line}"][-MAX_LOG_LINES:]
            self._save(job)
            return job

    def delete(self, job_id: str) -> None:
        directory = self.job_dir(job_id)
        if not directory.exists():
            raise JobNotFoundError(job_id)
        shutil.rmtree(directory)

    def recover_interrupted(self) -> int:
        """Jobs que estavam rodando quando o servidor caiu não vão terminar: marca como falhos."""
        count = 0
        for job in self.list():
            if job.state in (JobState.QUEUED, JobState.RUNNING):
                self.update(
                    job.id,
                    state=JobState.FAILED,
                    error="Interrompido por reinício do servidor",
                    log_line="Interrompido por reinício do servidor",
                )
                count += 1
        return count

    def _save(self, job: Job) -> None:
        path = self.job_dir(job.id) / "job.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(job.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(path)


class JobRunner:
    def __init__(self, store: JobStore, process: ProcessFn, max_workers: int = 1) -> None:
        self._store = store
        self._process = process
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job")

    def submit(self, job_id: str):
        return self._pool.submit(self._run, job_id)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _run(self, job_id: str) -> None:
        store = self._store
        job = store.update(job_id, state=JobState.RUNNING, message="Iniciando", log_line="Iniciado")

        def report(progress: float, message: str) -> None:
            store.update(job_id, progress=round(min(max(progress, 0.0), 1.0), 3), message=message, log_line=message)

        try:
            result = self._process(job.request, store.job_dir(job_id), report)
        except Exception as exc:
            friendly = isinstance(exc, ProcessingError)
            message = str(exc) if friendly else f"Erro inesperado: {type(exc).__name__}: {exc}"
            if not friendly:
                log.error("Job %s falhou\n%s", job_id, traceback.format_exc())
            store.update(job_id, state=JobState.FAILED, error=message, message="Falhou", log_line=message)
            return
        store.update(
            job_id, state=JobState.SUCCEEDED, progress=1.0, message="Concluído", result=result, log_line="Concluído"
        )
