"""Configuração de logs da aplicação."""

import logging
import time

HEALTH_PATH = "/api/health"


class _UTCFormatter(logging.Formatter):
    """Horário em UTC com sufixo Z: sem ambiguidade frente ao horário local do Docker."""

    converter = time.gmtime


class HealthCheckFilter(logging.Filter):
    """Descarta do access log as chamadas do healthcheck (uma a cada 15 s)."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args if isinstance(record.args, tuple) else ()
        # uvicorn.access: (cliente, método, caminho, versão HTTP, status)
        return not (len(args) >= 3 and str(args[2]) == HEALTH_PATH)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        _UTCFormatter("%(asctime)s.%(msecs)03dZ %(levelname)s %(name)s: %(message)s", "%Y-%m-%dT%H:%M:%S")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())
