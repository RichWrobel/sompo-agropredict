"""
security.py
------------
Controle de acesso e sanitizacao de entradas para o backend.

Modelo de seguranca (adequado ao escopo de MVP da Sprint 3):
- Autenticacao via API key estatica (header `X-API-Key`), uma por perfil.
- Autorizacao por perfil (operador / gestor / analista), checada por
  endpoint atraves da allow-list em `config.PERMISSOES`.
- Sanitizacao basica de strings de entrada (tamanho, whitelist de
  caracteres) para reduzir superficie de injecao antes de qualquer
  dado tocar o banco ou o modelo.

Producao real deveria evoluir para OAuth2/JWT com usuarios em base
propria, expiracao de token e rotacao de chaves -- fora do escopo do
MVP, mencionado no README como proximo passo.
"""
import re

from fastapi import Header, HTTPException, status

from backend.config import PERFIS, PERMISSOES, TOKENS
from backend.logging_config import log_auditoria

# Mapa reverso token -> perfil (montado uma vez)
_TOKEN_PARA_PERFIL = {token: perfil for perfil, token in TOKENS.items()}

_REGEX_TEXTO_SEGURO = re.compile(r"^[\w \-.,/áéíóúãõâêîôûàçÁÉÍÓÚÃÕÂÊÎÔÛÀÇ]{0,200}$")


def obter_perfil(x_api_key: str = Header(default=None, alias="X-API-Key")) -> str:
    """
    Dependency do FastAPI: valida a API key recebida no header e retorna
    o perfil associado. Lanca 401 se ausente/invalida.
    """
    if not x_api_key or x_api_key not in _TOKEN_PARA_PERFIL:
        log_auditoria("auth_falhou", perfil="desconhecido")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key ausente ou invalida. Envie o header 'X-API-Key'.",
        )
    return _TOKEN_PARA_PERFIL[x_api_key]


def exigir_permissao(acao: str):
    """
    Factory de dependency do FastAPI para checagem de RBAC.

    Uso:
        @app.post(..., dependencies=[Depends(exigir_permissao("registrar_predicao"))])
    """
    perfis_permitidos = PERMISSOES.get(acao, set())

    def _checar(perfil: str = Header(default=None, alias="X-API-Key")) -> str:
        # Reaproveita obter_perfil para validar o token primeiro
        perfil_resolvido = obter_perfil(perfil)
        if perfil_resolvido not in perfis_permitidos:
            log_auditoria("acesso_negado", perfil=perfil_resolvido, acao=acao)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Perfil '{perfil_resolvido}' nao tem permissao para "
                    f"'{acao}'. Perfis permitidos: {sorted(perfis_permitidos)}."
                ),
            )
        return perfil_resolvido

    return _checar


def sanitizar_texto(valor: str, campo: str, max_len: int = 200) -> str:
    """
    Sanitiza uma string de entrada: remove espacos nas bordas, limita o
    tamanho e rejeita caracteres fora de uma whitelist segura (letras,
    numeros, acentos, espaco e pontuacao basica). Usado em qualquer
    campo textual livre (ex.: observacao de alerta) antes de persistir.
    """
    if valor is None:
        return valor
    valor = valor.strip()[:max_len]
    if not _REGEX_TEXTO_SEGURO.match(valor):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campo '{campo}' contem caracteres nao permitidos.",
        )
    return valor
