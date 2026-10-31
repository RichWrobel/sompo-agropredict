"""
logging_config.py
------------------
Logging estruturado para auditoria do backend.

Cada requisicao relevante (entrada de dados, decisao do modelo, acao de
alerta) gera uma linha de log com: quem (perfil), o que (endpoint/acao),
quando (timestamp) e o resultado (classe de risco, status HTTP etc.).
Isso atende ao requisito de "manter registros basicos de uso que
permitam rastrear entradas, saidas e decisoes do sistema".
"""
import logging
import sys
from logging.handlers import RotatingFileHandler

from backend.config import LOG_DIR, LOG_FILE

LOG_DIR.mkdir(parents=True, exist_ok=True)

_FORMATO = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)


def configurar_logging() -> logging.Logger:
    logger = logging.getLogger("agropredict")
    if logger.handlers:
        # Evita handlers duplicados se chamado mais de uma vez (ex.: reload)
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(_FORMATO)

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


logger = configurar_logging()


def log_auditoria(evento: str, perfil: str = "-", **detalhes):
    """
    Registra uma linha de auditoria padronizada.

    Exemplo:
        log_auditoria("predicao_registrada", perfil="operador",
                       id_predicao=42, classe_risco="ALTO", origem="api")
    """
    partes = " ".join(f"{k}={v}" for k, v in detalhes.items())
    logger.info("evento=%s perfil=%s %s", evento, perfil, partes)
