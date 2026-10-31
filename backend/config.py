"""
config.py
---------
Configuracao central do backend Sompo AgroPredict (Sprint 3).

Todas as configuracoes sensiveis (credenciais, tokens) sao lidas de
variaveis de ambiente. Nunca commitar valores reais de producao --
os defaults abaixo servem apenas para desenvolvimento/demo local.
"""
import os
from pathlib import Path

# =====================================================================
# Caminhos
# =====================================================================
BASE_DIR = Path(__file__).resolve().parent.parent          # raiz do repo
MODELO_PATH = BASE_DIR / "modelo" / "modelo.pkl"
DATASET_PATH = BASE_DIR / "data" / "dataset_v2.csv"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "agropredict.log"
SQLITE_PATH = BASE_DIR / "data" / "agropredict_local.db"

# =====================================================================
# Banco de dados
# =====================================================================
# "oracle" (producao / Sprint 2) ou "sqlite" (fallback local, usado quando
# o Oracle XE nao esta disponivel -- ex.: ambiente de desenvolvimento,
# testes automatizados, demonstracao sem infraestrutura).
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").lower()

ORACLE_CONFIG = {
    "user":     os.getenv("ORACLE_USER", "system"),
    "password": os.getenv("ORACLE_PASSWORD", "admin"),
    "dsn":      os.getenv("ORACLE_DSN", "localhost:1521/XE"),
}

# =====================================================================
# Seguranca — controle de acesso por perfil
# =====================================================================
# Cada perfil tem um token (API key) proprio. Em producao, substituir por
# um mecanismo real (OAuth2/JWT + tabela de usuarios); aqui usamos tokens
# estaticos via variavel de ambiente para manter o escopo do MVP simples,
# porem funcional e auditavel.
PERFIS = ("operador", "gestor", "analista")

TOKENS = {
    "operador": os.getenv("TOKEN_OPERADOR", "op-token-dev-0001"),
    "gestor":   os.getenv("TOKEN_GESTOR",   "ge-token-dev-0002"),
    "analista": os.getenv("TOKEN_ANALISTA", "an-token-dev-0003"),
}

# Permissoes por endpoint/acao. Mantido explicito (allow-list) em vez de
# checagem implicita, para deixar claro no codigo quem pode fazer o que.
PERMISSOES = {
    "registrar_predicao":   {"operador", "gestor", "analista"},
    "ingestao_lote":        {"gestor", "analista"},
    "listar_predicoes":     {"gestor", "analista"},
    "listar_alertas":       {"operador", "gestor", "analista"},
    "atualizar_alerta":     {"operador", "gestor", "analista"},
    "metricas":             {"gestor", "analista"},
}

# =====================================================================
# Regras de negocio (mesmos limiares usados no dashboard/app.py e em
# data/gerar_dataset_v2.py -- mantidos em um unico lugar para evitar
# divergencia entre os modulos)
# =====================================================================
ALERTA = {
    "umidade_solo":   30,
    "declividade":    18,
    "chuva_24h":      10,
    "temperatura":    38,
    "velocidade":     10,
    "idade_maquina":  10,
    "horas_operacao":  8,
}
MAXIMO = {
    "umidade_solo":  45,
    "declividade":   25,
    "chuva_24h":     40,
    "temperatura":   45,
    "velocidade":    20,
}

# Faixas plausiveis para validacao de entrada (rejeita outliers/erros de
# sensor antes de persistir ou alimentar o modelo).
FAIXAS_PLAUSIVEIS = {
    "umidade_solo":   (0, 100),
    "declividade":    (0, 45),
    "chuva_24h":      (0, 300),
    "temperatura":    (-10, 55),
    "velocidade":     (0, 40),
    "idade_maquina":  (0, 40),
    "horas_operacao": (0, 24),
}

STATUS_OPERACAO_VALIDOS = ("Colheita", "Deslocamento", "Manobra")

VERSAO_MODELO = "v1.0"
