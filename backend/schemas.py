"""
schemas.py
----------
Contratos de entrada/saida da API (Pydantic v2).

A validacao de faixas plausiveis acontece aqui, na borda do sistema --
nenhum dado fora dos limites definidos em config.FAIXAS_PLAUSIVEIS chega
a ser persistido ou enviado ao modelo. Isso implementa o requisito de
"validar a consistencia das entradas (faixas plausiveis, campos
obrigatorios)".
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from backend.config import FAIXAS_PLAUSIVEIS, STATUS_OPERACAO_VALIDOS

StatusOperacao = Literal["Colheita", "Deslocamento", "Manobra"]


class TelemetriaInput(BaseModel):
    """Payload recebido de telemetria/ambiente/operacao (uma leitura)."""

    umidade_solo: float = Field(..., description="Umidade do solo (%)")
    declividade: float = Field(..., description="Declividade do terreno (%)")
    chuva_24h: float = Field(..., description="Chuva acumulada em 24h (mm)")
    temperatura: float = Field(..., description="Temperatura ambiente (C)")
    velocidade: float = Field(..., description="Velocidade do equipamento (km/h)")
    idade_maquina: float = Field(..., description="Idade da maquina (anos)")
    horas_operacao: float = Field(..., description="Horas de operacao acumuladas no dia")
    status_operacao: StatusOperacao

    id_equipamento: Optional[int] = Field(default=None, ge=1)
    id_operador: Optional[int] = Field(default=None, ge=1)

    @field_validator(
        "umidade_solo", "declividade", "chuva_24h", "temperatura",
        "velocidade", "idade_maquina", "horas_operacao",
    )
    @classmethod
    def _validar_faixa_plausivel(cls, valor: float, info):
        minimo, maximo = FAIXAS_PLAUSIVEIS[info.field_name]
        if not (minimo <= valor <= maximo):
            raise ValueError(
                f"{info.field_name}={valor} fora da faixa plausivel "
                f"[{minimo}, {maximo}]"
            )
        return valor

    @field_validator("status_operacao")
    @classmethod
    def _validar_status(cls, valor: str):
        if valor not in STATUS_OPERACAO_VALIDOS:
            raise ValueError(f"status_operacao invalido: {valor}")
        return valor


class PredicaoOutput(BaseModel):
    id_predicao: Optional[int] = None
    classe_risco: str
    score_risco: float
    prob_baixo: float
    prob_medio: float
    prob_alto: float
    recomendacao: str
    override_maximo: bool
    variaveis_no_maximo: list[str] = []
    variaveis_em_alerta: list[str] = []
    persistido: bool
    versao_modelo: str


class AcaoAlertaInput(BaseModel):
    acao_tomada: Literal["RESPEITOU", "IGNOROU"]
    observacao: Optional[str] = Field(default=None, max_length=500)


class IngestaoLoteResumo(BaseModel):
    total_linhas: int
    inseridas: int
    rejeitadas: int
    alertas_gerados: int
    erros: list[str] = []
