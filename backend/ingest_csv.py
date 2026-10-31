"""
ingest_csv.py
-------------
Ingestao em lote a partir de um arquivo CSV -- a segunda via de entrada
de dados prevista no requisito de integracao (a primeira e a API REST
em main.py). Reutiliza exatamente a mesma validacao (schemas.py) e o
mesmo model_service.prever() usados pela API, garantindo que o
resultado seja identico independente da origem dos dados.

Uso:
    python -m backend.ingest_csv --csv data/dataset_v2.csv --n 50
    python -m backend.ingest_csv --csv data/dataset_v2.csv --tudo

Cada linha do CSV e tratada como uma leitura de telemetria independente:
validada, persistida, avaliada pelo modelo e, se ALTO, gera um alerta.
Linhas invalidas (fora de faixa, status desconhecido etc.) sao
reportadas e puladas em vez de derrubar o processo inteiro.
"""
import argparse
import logging
import random

import pandas as pd
from pydantic import ValidationError

from backend.config import DATASET_PATH
from backend.database import DatabaseError, obter_repositorio
from backend.logging_config import log_auditoria
from backend.model_service import ModeloIndisponivelError, prever
from backend.schemas import TelemetriaInput

logger = logging.getLogger("agropredict")

IDS_EQUIPAMENTO_SEED = [1, 2, 3]
IDS_OPERADOR_SEED = [1, 2, 3]


def processar_arquivo(caminho_csv: str, n: int | None) -> dict:
    df = pd.read_csv(caminho_csv)
    if n is not None:
        df = df.sample(n=min(n, len(df)), random_state=42)

    repo = obter_repositorio()

    inseridas = 0
    rejeitadas = 0
    alertas_gerados = 0
    erros: list[str] = []

    for idx, row in df.iterrows():
        payload = {
            "umidade_solo": row["umidade_solo"],
            "declividade": row["declividade"],
            "chuva_24h": row["chuva_24h"],
            "temperatura": row["temperatura"],
            "velocidade": row["velocidade"],
            "idade_maquina": row["idade_maquina"],
            "horas_operacao": row["horas_operacao"],
            "status_operacao": row["status_operacao"],
            "id_equipamento": random.choice(IDS_EQUIPAMENTO_SEED),
            "id_operador": random.choice(IDS_OPERADOR_SEED),
        }

        try:
            # Mesma validacao usada pela API (faixas plausiveis, campos obrigatorios)
            dados = TelemetriaInput(**payload).model_dump()
        except ValidationError as exc:
            rejeitadas += 1
            erros.append(f"linha {idx}: {exc.errors()[0]['msg']}")
            continue

        try:
            resultado = prever(dados)
            id_predicao = repo.inserir_predicao(dados, resultado)
            if resultado["classe_risco"] == "ALTO":
                repo.inserir_alerta(id_predicao)
                alertas_gerados += 1
            inseridas += 1
        except (ModeloIndisponivelError, DatabaseError) as exc:
            rejeitadas += 1
            erros.append(f"linha {idx}: {exc}")

    log_auditoria(
        "ingestao_csv_concluida", perfil="analista(cli)", arquivo=caminho_csv,
        inseridas=inseridas, rejeitadas=rejeitadas, alertas=alertas_gerados,
    )

    return {
        "total_linhas": len(df),
        "inseridas": inseridas,
        "rejeitadas": rejeitadas,
        "alertas_gerados": alertas_gerados,
        "erros": erros[:20],  # limita output
    }


def main():
    parser = argparse.ArgumentParser(description="Ingestao em lote via CSV")
    parser.add_argument("--csv", default=str(DATASET_PATH), help="Caminho do CSV de entrada")
    parser.add_argument("--n", type=int, default=50, help="Numero de linhas a processar")
    parser.add_argument("--tudo", action="store_true", help="Processa o arquivo inteiro")
    args = parser.parse_args()

    print("=" * 60)
    print("Sompo AgroPredict - Ingestao em lote (CSV)")
    print("=" * 60)

    resumo = processar_arquivo(args.csv, None if args.tudo else args.n)

    print(f"Linhas no lote:      {resumo['total_linhas']}")
    print(f"Inseridas:           {resumo['inseridas']}")
    print(f"Rejeitadas:          {resumo['rejeitadas']}")
    print(f"Alertas gerados:     {resumo['alertas_gerados']}")
    if resumo["erros"]:
        print("\nPrimeiros erros:")
        for e in resumo["erros"]:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
