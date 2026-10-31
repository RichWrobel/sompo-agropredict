import os
import logging
from typing import Dict, List, Optional, Any
import oracledb
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agropredict")

class DatabaseError(Exception):
    pass

class OracleRepo:
    def __init__(self):
        self.user = os.getenv("ORACLE_USER", "system")
        self.password = os.getenv("ORACLE_PASSWORD", "admin")
        self.dsn = os.getenv("ORACLE_DSN", "localhost:1521/XE")
        self._conn = None

    def _get_connection(self):
        if self._conn is None:
            try:
                self._conn = oracledb.connect(user=self.user, password=self.password, dsn=self.dsn)
                logger.info("Conectado ao Oracle XE")
            except oracledb.DatabaseError as e:
                raise DatabaseError(f"Falha na conexão: {e}")
        return self._conn

    def health(self) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            cursor.fetchone()
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"Health check falhou: {e}")
            return False

    def inserir_predicao(self, dados: Dict[str, Any], resultado: Dict[str, Any]) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        id_out = cursor.var(oracledb.NUMBER)
        sql = """
            INSERT INTO predicoes (
                id_predicao, id_equipamento, id_operador,
                umidade_solo, declividade, chuva_24h, temperatura,
                velocidade, idade_maquina, horas_operacao, status_operacao,
                score_risco, classe_risco, recomendacao,
                prob_baixo, prob_medio, prob_alto, versao_modelo
            ) VALUES (
                seq_predicao.NEXTVAL, :equip, :oper,
                :umid, :decl, :chuva, :temp,
                :vel, :idade, :horas, :status,
                :score, :classe, :reco,
                :pb, :pm, :pa, :versao
            )
            RETURNING id_predicao INTO :id_out
        """
        id_equip = dados.get("id_equipamento", 1)
        id_oper = dados.get("id_operador", 1)
        cursor.execute(sql, {
            "equip": id_equip,
            "oper": id_oper,
            "umid": dados["umidade_solo"],
            "decl": dados["declividade"],
            "chuva": dados["chuva_24h"],
            "temp": dados["temperatura"],
            "vel": dados["velocidade"],
            "idade": dados["idade_maquina"],
            "horas": dados["horas_operacao"],
            "status": dados["status_operacao"],
            "score": resultado["score_risco"],
            "classe": resultado["classe_risco"],
            "reco": resultado["recomendacao"],
            "pb": resultado.get("probabilidades", {}).get("BAIXO", 0),
            "pm": resultado.get("probabilidades", {}).get("MEDIO", 0),
            "pa": resultado.get("probabilidades", {}).get("ALTO", 0),
            "versao": "v1.0",
            "id_out": id_out
        })
        conn.commit()
        cursor.close()
        return int(id_out.getvalue()[0])

    def inserir_alerta(self, id_predicao: int) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO alertas (id_alerta, id_predicao) VALUES (seq_alerta.NEXTVAL, :id_pred)", {"id_pred": id_predicao})
        conn.commit()
        cursor.close()

    def listar_predicoes(self, limite: int = 100, filtros: Optional[Dict] = None) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        params = {}
        sql = """
            SELECT 
                p.id_predicao, 
                TO_CHAR(p.data_hora, 'YYYY-MM-DD HH24:MI:SS') AS data_hora,
                p.id_equipamento,
                e.modelo AS equipamento,
                p.id_operador,
                o.nome AS operador,
                p.umidade_solo, p.declividade, p.chuva_24h, p.temperatura,
                p.velocidade, p.idade_maquina, p.horas_operacao, p.status_operacao,
                p.score_risco, p.classe_risco, p.recomendacao
            FROM predicoes p
            LEFT JOIN equipamentos e ON e.id_equipamento = p.id_equipamento
            LEFT JOIN operadores o ON o.id_operador = p.id_operador
            WHERE 1=1
        """
        if filtros:
            if "id_operador" in filtros and filtros["id_operador"] is not None:
                sql += " AND p.id_operador = :id_operador"
                params["id_operador"] = filtros["id_operador"]
            if "fazenda" in filtros and filtros["fazenda"]:
                sql += " AND e.fazenda = :fazenda"
                params["fazenda"] = filtros["fazenda"]
        sql += " ORDER BY p.data_hora DESC FETCH FIRST :limite ROWS ONLY"
        params["limite"] = limite
        cursor.execute(sql, params)
        colunas = [desc[0].lower() for desc in cursor.description]
        resultados = [dict(zip(colunas, row)) for row in cursor.fetchall()]
        cursor.close()
        return resultados

    def listar_alertas(self, limite: int = 50) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        sql = """
            SELECT 
                a.id_alerta,
                a.id_predicao,
                TO_CHAR(a.data_emissao, 'YYYY-MM-DD HH24:MI:SS') AS data_emissao,
                a.acao_tomada,
                TO_CHAR(a.data_acao, 'YYYY-MM-DD HH24:MI:SS') AS data_acao,
                a.observacao,
                p.classe_risco,
                p.recomendacao,
                e.modelo AS equipamento,
                o.nome AS operador
            FROM alertas a
            JOIN predicoes p ON p.id_predicao = a.id_predicao
            LEFT JOIN equipamentos e ON e.id_equipamento = p.id_equipamento
            LEFT JOIN operadores o ON o.id_operador = p.id_operador
            ORDER BY a.data_emissao DESC
            FETCH FIRST :limite ROWS ONLY
        """
        cursor.execute(sql, {"limite": limite})
        colunas = [desc[0].lower() for desc in cursor.description]
        resultados = [dict(zip(colunas, row)) for row in cursor.fetchall()]
        cursor.close()
        return resultados

    def atualizar_alerta(self, id_alerta: int, acao: str, observacao: Optional[str] = None) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE alertas 
            SET acao_tomada = :acao, 
                data_acao = SYSTIMESTAMP,
                observacao = :obs
            WHERE id_alerta = :id
        """, {"acao": acao, "obs": observacao, "id": id_alerta})
        conn.commit()
        rows = cursor.rowcount
        cursor.close()
        return rows > 0

    def metricas_diarias(self) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                TO_CHAR(dia, 'YYYY-MM-DD') AS dia,
                total_predicoes,
                qtd_baixo,
                qtd_medio,
                qtd_alto,
                score_medio,
                score_maximo
            FROM vw_metricas_diarias
            ORDER BY dia DESC
            FETCH FIRST 30 ROWS ONLY
        """)
        colunas = [desc[0].lower() for desc in cursor.description]
        resultados = [dict(zip(colunas, row)) for row in cursor.fetchall()]
        cursor.close()
        return resultados

_repo_instance = None
def obter_repositorio() -> OracleRepo:
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = OracleRepo()
    return _repo_instance