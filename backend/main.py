"""
main.py
-------
Backend Sompo AgroPredict (Sprint 3) — orquestracao ponta a ponta.

Fluxo implementado:
    Entrada (API REST ou CSV) -> validacao -> persistencia (Oracle/SQLite)
    -> modelo (Random Forest) -> score de risco + alerta -> resposta/dashboard

Rodar localmente:
    uvicorn backend.main:app --reload --port 8000

Documentacao interativa (Swagger): http://localhost:8000/docs
"""
import logging
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

# ========== IMPORTS CORRIGIDOS (RELATIVOS) ==========
from .database import DatabaseError, obter_repositorio
from .logging_config import log_auditoria
from .model_service import ModeloIndisponivelError, carregar_modelo, prever
from .schemas import (
    AcaoAlertaInput,
    PredicaoOutput,
    TelemetriaInput,
)
from .security import exigir_permissao, sanitizar_texto

logger = logging.getLogger("agropredict")

app = FastAPI(
    title="Sompo AgroPredict API",
    description="Orquestracao end-to-end: telemetria -> banco -> modelo -> score de risco.",
    version="3.0.0",
)

# CORS liberado para localhost (dashboard Streamlit roda em outra porta)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    try:
        carregar_modelo()
        obter_repositorio()
        log_auditoria("startup_ok")
    except (ModeloIndisponivelError, DatabaseError) as exc:
        logger.error("evento=startup_falhou detalhe=%s", exc)


# =====================================================================
# Health check (sem autenticacao)
# =====================================================================
@app.get("/health")
def health():
    try:
        repo = obter_repositorio()
        bd_ok = repo.health()
    except Exception:
        bd_ok = False
    try:
        carregar_modelo()
        modelo_ok = True
    except Exception:
        modelo_ok = False
    status_geral = "ok" if (bd_ok and modelo_ok) else "degradado"
    return {"status": status_geral, "banco": bd_ok, "modelo": modelo_ok}


# =====================================================================
# Predicao individual (entrada em tempo real: sensor, app do operador, etc.)
# =====================================================================
@app.post(
    "/api/v1/predicoes",
    response_model=PredicaoOutput,
    dependencies=[Depends(exigir_permissao("registrar_predicao"))],
)
def registrar_predicao(
    dados: TelemetriaInput,
    perfil: str = Depends(exigir_permissao("registrar_predicao")),
):
    """
    Recebe uma leitura de telemetria/ambiente/operacao, persiste no
    banco, aciona o modelo e retorna o score de risco + recomendacao.
    Gera um alerta automaticamente quando a classe resultante e ALTO.
    """
    try:
        repo = obter_repositorio()
        dados_dict = dados.model_dump()
        resultado = prever(dados_dict)

        id_predicao = repo.inserir_predicao(dados_dict, resultado)
        if resultado["classe_risco"] == "ALTO":
            repo.inserir_alerta(id_predicao)

        log_auditoria(
            "predicao_registrada", perfil=perfil, id_predicao=id_predicao,
            classe_risco=resultado["classe_risco"], score=resultado["score_risco"],
            origem="api",
        )

        return PredicaoOutput(
            id_predicao=id_predicao,
            persistido=True,
            **resultado,
        )
    except ModeloIndisponivelError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DatabaseError as exc:
        log_auditoria("persistencia_falhou", perfil=perfil, detalhe=str(exc))
        resultado = prever(dados.model_dump())
        return PredicaoOutput(id_predicao=None, persistido=False, **resultado)
    except Exception as exc:
        logger.exception("evento=erro_inesperado_predicao")
        raise HTTPException(status_code=500, detail="Erro interno ao processar predicao.") from exc


# =====================================================================
# Listagem / consultas (gestor, analista)
# =====================================================================
@app.get(
    "/api/v1/predicoes",
    dependencies=[Depends(exigir_permissao("listar_predicoes"))],
)
def listar_predicoes(
    limite: int = Query(default=50, ge=1, le=500),
    perfil: str = Depends(exigir_permissao("listar_predicoes")),
):
    repo = obter_repositorio()
    dados = repo.listar_predicoes(limite=limite)
    log_auditoria("listagem_predicoes", perfil=perfil, quantidade=len(dados))
    return {"total": len(dados), "predicoes": dados}


@app.get(
    "/api/v1/alertas",
    dependencies=[Depends(exigir_permissao("listar_alertas"))],
)
def listar_alertas(
    limite: int = Query(default=50, ge=1, le=500),
    perfil: str = Depends(exigir_permissao("listar_alertas")),
):
    repo = obter_repositorio()
    dados = repo.listar_alertas(limite=limite)
    log_auditoria("listagem_alertas", perfil=perfil, quantidade=len(dados))
    return {"total": len(dados), "alertas": dados}


@app.patch(
    "/api/v1/alertas/{id_alerta}",
    dependencies=[Depends(exigir_permissao("atualizar_alerta"))],
)
def atualizar_alerta(
    id_alerta: int,
    acao: AcaoAlertaInput,
    perfil: str = Depends(exigir_permissao("atualizar_alerta")),
):
    """Operador confirma se respeitou ou ignorou um alerta emitido."""
    repo = obter_repositorio()
    observacao = sanitizar_texto(acao.observacao, "observacao") if acao.observacao else None
    ok = repo.atualizar_alerta(id_alerta, acao.acao_tomada, observacao)
    if not ok:
        raise HTTPException(status_code=404, detail="Alerta nao encontrado.")
    log_auditoria(
        "alerta_atualizado", perfil=perfil, id_alerta=id_alerta, acao=acao.acao_tomada
    )
    return {"id_alerta": id_alerta, "acao_tomada": acao.acao_tomada, "atualizado": True}


@app.get(
    "/api/v1/metricas",
    dependencies=[Depends(exigir_permissao("metricas"))],
)
def metricas(perfil: str = Depends(exigir_permissao("metricas"))):
    repo = obter_repositorio()
    dados = repo.metricas_diarias()
    log_auditoria("consulta_metricas", perfil=perfil)
    return {"metricas_diarias": dados}