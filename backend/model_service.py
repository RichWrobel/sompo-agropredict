"""
model_service.py
-----------------
Carrega o modelo Random Forest (modelo.pkl) e expoe a funcao `prever`,
que e o unico ponto do sistema que fala com o modelo. Backend (API) e
o script de ingestao em lote reutilizam essa mesma funcao, garantindo
que a mesma logica de negocio (limiares de alerta/maximo, override,
recomendacao) seja usada em qualquer caminho de entrada de dados.

Os limiares ALERTA/MAXIMO e a logica de recomendacao replicam
fielmente o que ja existia em dashboard/app.py (Sprint 2), apenas
centralizados aqui para evitar divergencia entre modulos.
"""
import logging
from functools import lru_cache

import joblib
import pandas as pd

from backend.config import ALERTA, MAXIMO, MODELO_PATH, VERSAO_MODELO

logger = logging.getLogger("agropredict")

FEATURES = [
    "umidade_solo", "declividade", "chuva_24h", "temperatura",
    "velocidade", "idade_maquina", "horas_operacao", "status_operacao",
]


class ModeloIndisponivelError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def carregar_modelo():
    if not MODELO_PATH.exists():
        raise ModeloIndisponivelError(
            f"Modelo nao encontrado em {MODELO_PATH}. "
            "Execute modelo/random_forest.ipynb primeiro."
        )
    modelo = joblib.load(MODELO_PATH)
    logger.info("evento=modelo_carregado caminho=%s", MODELO_PATH)
    return modelo


def _verificar_maximo(dados: dict) -> list[str]:
    return [v for v, lim in MAXIMO.items() if dados.get(v, 0) >= lim]


def _contar_alertas(dados: dict) -> list[str]:
    return [v for v, lim in ALERTA.items() if dados.get(v, 0) > lim]


def _gerar_recomendacao(dados: dict, classe: str, vars_max: list[str]) -> str:
    if classe == "BAIXO":
        return "Seguir rota atual"
    if "umidade_solo" in vars_max or (dados["umidade_solo"] > 70 and dados["chuva_24h"] > 20):
        return "Risco de atolamento — evitar areas saturadas"
    if "declividade" in vars_max or (dados["velocidade"] > 15 and dados["declividade"] > 18):
        return "Atencao a inclinacao — reduzir velocidade imediatamente"
    if "chuva_24h" in vars_max:
        return "Chuva intensa — suspender operacao"
    if "temperatura" in vars_max or (dados["temperatura"] > 38 and dados["horas_operacao"] > 8):
        return "Pausa obrigatoria — risco de fadiga e superaquecimento"
    if "velocidade" in vars_max:
        return "Velocidade critica — reduzir imediatamente"
    if dados["idade_maquina"] > 10 and dados["horas_operacao"] > 8:
        return "Verificar equipamento — desgaste elevado"
    if classe == "ALTO":
        return "Interromper operacao"
    return "Reduzir velocidade e monitorar"


def prever(dados: dict) -> dict:
    """
    Executa uma predicao completa para um registro de telemetria.

    Retorna um dict pronto para persistencia/serializacao, contendo a
    classe de risco (com override de limiar maximo aplicado), score,
    probabilidades por classe, recomendacao e as variaveis que
    dispararam alerta/maximo (para explicabilidade e auditoria).
    """
    modelo = carregar_modelo()

    entrada = pd.DataFrame([{k: dados[k] for k in FEATURES}])
    classe_modelo = modelo.predict(entrada)[0]
    probas = modelo.predict_proba(entrada)[0]
    classes = list(modelo.classes_)
    probs = {c: float(p) for c, p in zip(classes, probas)}

    vars_max = _verificar_maximo(dados)
    vars_alerta = _contar_alertas(dados)
    em_max = len(vars_max) > 0

    classe_final = "ALTO" if em_max else classe_modelo
    score = 100.0 if em_max else float(max(probas) * 100)
    recomendacao = _gerar_recomendacao(dados, classe_final, vars_max)

    return {
        "classe_risco": classe_final,
        "score_risco": round(score, 2),
        "prob_baixo": round(probs.get("BAIXO", 0.0), 4),
        "prob_medio": round(probs.get("MEDIO", 0.0), 4),
        "prob_alto": round(probs.get("ALTO", 0.0), 4),
        "recomendacao": recomendacao,
        "override_maximo": em_max,
        "variaveis_no_maximo": vars_max,
        "variaveis_em_alerta": vars_alerta,
        "versao_modelo": VERSAO_MODELO,
    }
