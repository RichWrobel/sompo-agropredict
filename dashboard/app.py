"""
app.py - Dashboard Sompo AgroPredict (Sprint 3 - integrado)
-------------------------------------------------------------
Dashboard Streamlit que agora faz parte do fluxo end-to-end:

    Sidebar (entrada) -> calculo local instantaneo (mesma logica do
    backend, via backend.model_service) -> botao "Registrar operacao"
    -> POST /api/v1/predicoes no backend -> persistencia + auditoria
    -> historico e metricas lidos de volta via GET no backend
    (controle de acesso por perfil: operador / gestor / analista).

Pre-requisito: o backend precisa estar rodando (ver README):
    uvicorn backend.main:app --reload --port 8000

Modo de execucao:
    streamlit run dashboard/app.py
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# Permite importar o pacote `backend` (raiz do repo) a partir de dashboard/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import ALERTA, MAXIMO, PERFIS, TOKENS  # noqa: E402
from backend.model_service import prever  # noqa: E402

# =====================================================================
# Configuracao geral
# =====================================================================
st.set_page_config(
    page_title="Sompo AgroPredict",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_BACKEND_URL = "http://localhost:8000"
CORES_RISCO = {"BAIXO": "#2C5F2D", "MEDIO": "#E8A33D", "ALTO": "#C8443D"}
EMOJI_RISCO = {"BAIXO": "🟢", "MEDIO": "🟡", "ALTO": "🔴"}


def label_alerta(valor, chave):
    if chave in MAXIMO and valor >= MAXIMO[chave]:
        return "🔴 MAX"
    if valor > ALERTA[chave]:
        return "⚠️ Alerta"
    return "✅ OK"


class _RespostaErro:
    """Objeto simples para representar falha de conexao sem quebrar o fluxo."""
    def __init__(self, detalhe):
        self.ok = False
        self.status_code = 0
        self.detalhe = detalhe

    def json(self):
        return {"detail": self.detalhe}


def chamar_backend(metodo: str, path: str, perfil_token: str, backend_url: str, **kwargs):
    """Wrapper fino sobre requests, com timeout curto e erros tratados."""
    url = f"{backend_url}{path}"
    headers = kwargs.pop("headers", {})
    headers["X-API-Key"] = perfil_token
    try:
        return requests.request(metodo, url, headers=headers, timeout=5, **kwargs)
    except requests.exceptions.RequestException as exc:
        return _RespostaErro(str(exc))


# =====================================================================
# Sidebar — Login (perfil) + Variaveis
# =====================================================================
st.sidebar.title("🌾 Sompo AgroPredict")
st.sidebar.markdown("**Calculadora de risco operacional**")
st.sidebar.markdown("---")

st.sidebar.markdown("### 🔐 Perfil de acesso")
perfil_selecionado = st.sidebar.selectbox(
    "Entrar como", PERFIS, format_func=lambda p: p.capitalize()
)
token_atual = TOKENS[perfil_selecionado]
st.sidebar.caption(
    "Perfis controlam o que cada usuario pode ver/fazer no backend "
    "(ex.: operador nao acessa histórico completo nem métricas)."
)

with st.sidebar.expander("⚙️ Conexão com o backend"):
    BACKEND_URL = st.text_input("URL do backend", value=DEFAULT_BACKEND_URL)

st.sidebar.markdown("---")
st.sidebar.markdown("### Variáveis ambientais")
umidade_solo = st.sidebar.slider("Umidade do solo (%)", 0, 100, 20)
declividade = st.sidebar.slider("Declividade (%)", 0, 25, 8)
chuva_24h = st.sidebar.slider("Chuva 24h (mm)", 0, 40, 4)
temperatura = st.sidebar.slider("Temperatura (°C)", 15, 45, 26)

st.sidebar.markdown("### Variáveis operacionais")
velocidade = st.sidebar.slider("Velocidade (km/h)", 0, 20, 7)
idade_maquina = st.sidebar.slider("Idade da máquina (anos)", 0, 20, 5)
horas_operacao = st.sidebar.slider("Horas de operação (acumuladas)", 0, 14, 5)
status_operacao = st.sidebar.selectbox("Tipo de operação", ["Colheita", "Deslocamento", "Manobra"])

# =====================================================================
# Predicao em tempo real (calculo local — mesma logica do backend,
# via backend.model_service.prever, sem duplicar regras de negocio)
# =====================================================================
entrada_dict = {
    "umidade_solo": umidade_solo, "declividade": declividade, "chuva_24h": chuva_24h,
    "temperatura": temperatura, "velocidade": velocidade, "idade_maquina": idade_maquina,
    "horas_operacao": horas_operacao, "status_operacao": status_operacao,
}

try:
    resultado = prever(entrada_dict)
except Exception as exc:
    st.error(f"❌ Não foi possível carregar o modelo: {exc}")
    st.stop()

classe_pred = resultado["classe_risco"]
score = resultado["score_risco"]
recomendacao = resultado["recomendacao"]

# =====================================================================
# Header
# =====================================================================
st.title("🌾 Sompo AgroPredict — Dashboard de Risco")
st.markdown(
    "**Em vez de pagar o sinistro depois, calculamos o risco antes.** "
    "Fluxo integrado: entrada → banco → modelo → score → interface."
)
st.caption(f"Conectado como **{perfil_selecionado}** · backend: `{BACKEND_URL}`")
st.markdown("---")

# =====================================================================
# Resultado em destaque + registro no backend
# =====================================================================
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.markdown(
        f"""
        <div style='background-color:{CORES_RISCO[classe_pred]};padding:30px;
                    border-radius:12px;color:white;text-align:center;'>
            <h1 style='margin:0;font-size:60px;'>{EMOJI_RISCO[classe_pred]} {classe_pred}</h1>
            <h2 style='margin:5px 0;'>Score: {score:.1f} / 100</h2>
            <p style='margin:10px 0 0 0;font-size:18px;'><strong>{recomendacao}</strong></p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if resultado["override_maximo"]:
        st.warning(f"⚡ **Override ativado:** variável(is) no limite máximo: {', '.join(resultado['variaveis_no_maximo'])}")
    elif resultado["variaveis_em_alerta"]:
        st.info(f"⚠️ {len(resultado['variaveis_em_alerta'])} variável(is) em alerta: {', '.join(resultado['variaveis_em_alerta'])}")

    if st.button("💾 Registrar operação no sistema (via backend)", type="primary"):
        resp = chamar_backend("POST", "/api/v1/predicoes", token_atual, BACKEND_URL, json=entrada_dict)
        if getattr(resp, "ok", False):
            corpo = resp.json()
            if corpo.get("persistido"):
                st.success(f"✅ Registrado no banco — id_predicao={corpo['id_predicao']}")
            else:
                st.warning("⚠️ Score calculado, mas o backend não conseguiu persistir (ver logs).")
        elif getattr(resp, "status_code", 0) == 401:
            st.error("🔒 Sessão inválida — token não reconhecido pelo backend.")
        else:
            detalhe = resp.json().get("detail") if resp is not None else "sem resposta"
            st.error(f"❌ Falha ao registrar no backend: {detalhe}")

with col2:
    st.markdown("### Probabilidades")
    for c, p in [("BAIXO", resultado["prob_baixo"]), ("MEDIO", resultado["prob_medio"]), ("ALTO", resultado["prob_alto"])]:
        st.markdown(f"**{EMOJI_RISCO[c]} {c}**")
        st.progress(float(p))
        st.caption(f"{p*100:.1f}%")

with col3:
    st.markdown("### Contexto")
    st.metric("Operação", status_operacao)
    st.metric("Velocidade", f"{velocidade} km/h")
    st.metric("Idade máquina", f"{idade_maquina} anos")

# =====================================================================
# Detalhes da entrada
# =====================================================================
st.markdown("---")
st.subheader("📊 Detalhes da operação avaliada")

col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Umidade do solo", f"{umidade_solo}%", label_alerta(umidade_solo, "umidade_solo"))
col_b.metric("Declividade", f"{declividade}%", label_alerta(declividade, "declividade"))
col_c.metric("Chuva 24h", f"{chuva_24h} mm", label_alerta(chuva_24h, "chuva_24h"))
col_d.metric("Temperatura", f"{temperatura}°C", label_alerta(temperatura, "temperatura"))

col_e, col_f, col_g, col_h = st.columns(4)
col_e.metric("Velocidade", f"{velocidade} km/h", label_alerta(velocidade, "velocidade"))
col_f.metric("Idade máquina", f"{idade_maquina} anos", label_alerta(idade_maquina, "idade_maquina"))
col_g.metric("Horas operação", f"{horas_operacao}h", label_alerta(horas_operacao, "horas_operacao"))
col_h.metric("Tipo", status_operacao)

# =====================================================================
# Área restrita — histórico, métricas e alertas (via backend)
# =====================================================================
st.markdown("---")
st.subheader("📅 Histórico, métricas e alertas")

permissoes_visao = {
    "operador": {"alertas"},
    "gestor": {"alertas", "historico", "metricas"},
    "analista": {"alertas", "historico", "metricas"},
}
pode_ver = permissoes_visao[perfil_selecionado]

if "historico" not in pode_ver and "metricas" not in pode_ver:
    st.info(
        "ℹ️ O perfil **operador** não tem acesso ao histórico completo nem às "
        "métricas agregadas — apenas aos alertas pendentes de confirmação abaixo. "
        "Troque para **gestor** ou **analista** na barra lateral para ver mais."
    )

tabs_labels = []
if "historico" in pode_ver:
    tabs_labels.append("Histórico de predições")
if "metricas" in pode_ver:
    tabs_labels.append("Métricas diárias")
if "alertas" in pode_ver:
    tabs_labels.append("Alertas")

if tabs_labels:
    tabs = st.tabs(tabs_labels)
    idx = 0

    if "historico" in pode_ver:
        with tabs[idx]:
            resp = chamar_backend("GET", "/api/v1/predicoes?limite=100", token_atual, BACKEND_URL)
            if getattr(resp, "ok", False):
                dados = resp.json()["predicoes"]
                if dados:
                    df_hist = pd.DataFrame(dados)
                    st.success(f"✅ {len(df_hist)} predições carregadas do backend.")
                    st.dataframe(df_hist, use_container_width=True)
                else:
                    st.info("Nenhuma predição registrada ainda. Use o botão de registro acima.")
            else:
                st.warning("⚠️ Não foi possível carregar o histórico. O backend está rodando?")
        idx += 1

    if "metricas" in pode_ver:
        with tabs[idx]:
            resp = chamar_backend("GET", "/api/v1/metricas", token_atual, BACKEND_URL)
            if getattr(resp, "ok", False):
                dados = resp.json()["metricas_diarias"]
                if dados:
                    st.dataframe(pd.DataFrame(dados), use_container_width=True)
                else:
                    st.info("Sem métricas ainda.")
            else:
                st.warning("⚠️ Não foi possível carregar as métricas.")
        idx += 1

    if "alertas" in pode_ver:
        with tabs[idx]:
            resp = chamar_backend("GET", "/api/v1/alertas?limite=50", token_atual, BACKEND_URL)
            if getattr(resp, "ok", False):
                alertas = resp.json()["alertas"]
                pendentes = [a for a in alertas if a["acao_tomada"] == "PENDENTE"]
                st.write(f"**{len(pendentes)}** alerta(s) pendente(s) de confirmação.")
                for a in pendentes[:10]:
                    with st.expander(f"Alerta #{a['id_alerta']} — {a['classe_risco']} — {a['recomendacao']}"):
                        c1, c2 = st.columns(2)
                        if c1.button("✅ Respeitei", key=f"resp_{a['id_alerta']}"):
                            r = chamar_backend(
                                "PATCH", f"/api/v1/alertas/{a['id_alerta']}", token_atual, BACKEND_URL,
                                json={"acao_tomada": "RESPEITOU"},
                            )
                            if getattr(r, "ok", False):
                                st.success("Registrado.")
                                st.rerun()
                        if c2.button("⚠️ Ignorei", key=f"ign_{a['id_alerta']}"):
                            r = chamar_backend(
                                "PATCH", f"/api/v1/alertas/{a['id_alerta']}", token_atual, BACKEND_URL,
                                json={"acao_tomada": "IGNOROU"},
                            )
                            if getattr(r, "ok", False):
                                st.warning("Registrado.")
                                st.rerun()
                if not pendentes:
                    st.success("Nenhum alerta pendente. 🎉")
            else:
                st.warning("⚠️ Não foi possível carregar os alertas.")

# =====================================================================
# Footer
# =====================================================================
st.markdown("---")
st.caption(
    f"Sompo AgroPredict · Sprint 3 (integração end-to-end) · Challenge Sompo × FIAP · "
    f"Modelo Random Forest · {datetime.now().year}"
)
