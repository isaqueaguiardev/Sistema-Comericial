import sqlite3
from backup import criar_backup_automatico_diario
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from calendario import tela_calendario
from clientes import tela_clientes
from config import APP_NAME, APP_VERSION, DATABASE_PATH
from database import inicializar_banco, autenticar_usuario, registrar_log
from estoque import tela_estoque
from financeiro import tela_financeiro
from pdv import tela_pdv
from pedidos import tela_pedidos
from produtos import tela_produtos
from relatorios import tela_relatorios
from tela_configuracoes import tela_configuracoes, carregar_configuracoes_empresa

from dashboard_utils import (
    obter_indicadores_periodo,
    obter_top_produtos,
    obter_ultimas_atividades,
    obter_radar_oportunidades,
    obter_clima_empresa,
    calcular_meta_inteligente,
)


st.set_page_config(
    page_title=APP_NAME,
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="collapsed",
)


inicializar_banco()
criar_backup_automatico_diario()
EMPRESA_ATUAL = carregar_configuracoes_empresa()


def conectar():
    conn = sqlite3.connect(DATABASE_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def carregar_df(query, params=()):
    conn = conectar()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def dinheiro(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def ir_para(pagina):
    st.session_state["menu_atual"] = pagina
    st.rerun()


def card_indicador(icone, label, valor, ajuda):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-icon">{icone}</div>
            <div class="metric-label">{label}</div>
            <div class="metric-value">{valor}</div>
            <div class="metric-help">{ajuda}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def aplicar_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        #MainMenu {
            visibility: hidden;
        }

        footer {
            visibility: hidden;
        }

        [data-testid="stDecoration"] {
            visibility: hidden;
            height: 0%;
        }

        [data-testid="stStatusWidget"] {
            visibility: hidden;
            height: 0%;
        }

        .stApp {
            background:
                radial-gradient(circle at 15% 10%, rgba(255, 190, 218, 0.95), transparent 28%),
                radial-gradient(circle at 85% 18%, rgba(255, 225, 235, 0.95), transparent 30%),
                radial-gradient(circle at 50% 100%, rgba(217, 165, 165, 0.45), transparent 35%),
                linear-gradient(135deg, #FFF0F6 0%, #F8D7E8 38%, #F6C9DA 68%, #FFF7FA 100%);
            color: #2B1B1B;
        }

        header[data-testid="stHeader"] {
            background: rgba(255, 240, 246, 0.85);
            backdrop-filter: blur(18px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.35);
        }

        section[data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(255, 244, 248, 0.96), rgba(248, 199, 221, 0.90)),
                linear-gradient(135deg, #F8D7E8, #D9A5A5);
            border-right: 1px solid rgba(217, 165, 165, 0.35);
            box-shadow: 10px 0 35px rgba(120, 60, 85, 0.10);
        }

        section[data-testid="stSidebar"] * {
            color: #2B1B1B !important;
            font-weight: 750;
        }

        div[role="radiogroup"] label {
            padding: 11px 15px !important;
            border-radius: 16px !important;
            margin-bottom: 7px !important;
            transition: all 0.2s ease;
            font-size: 15px !important;
        }

        div[role="radiogroup"] label:hover {
            background: rgba(255,255,255,0.60) !important;
            transform: translateX(3px);
        }

        .login-wrapper {
            max-width: 460px;
            margin: 8vh auto 0 auto;
            background: rgba(255,255,255,0.84);
            border: 1px solid rgba(255,255,255,0.75);
            border-radius: 32px;
            padding: 34px;
            box-shadow: 0 22px 65px rgba(160, 80, 115, 0.20);
            backdrop-filter: blur(18px);
            text-align: center;
        }

        .login-title {
            font-size: 34px;
            font-weight: 950;
            color: #2B1B1B;
            margin-bottom: 8px;
        }

        .login-subtitle {
            font-size: 15px;
            font-weight: 700;
            color: #6B4650;
            margin-bottom: 22px;
        }

        .hero {
            padding: 36px 40px;
            border-radius: 34px;
            background:
                linear-gradient(135deg, rgba(255,255,255,0.84), rgba(255,230,240,0.76)),
                radial-gradient(circle at top right, rgba(255, 182, 214, 0.75), transparent 32%),
                linear-gradient(135deg, #FFF7FA, #F8D7E8);
            border: 1px solid rgba(255, 255, 255, 0.72);
            box-shadow: 0 22px 65px rgba(160, 80, 115, 0.18);
            margin-bottom: 28px;
        }

        .hero-small {
            color: #A84E73;
            font-size: 12px;
            font-weight: 950;
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-bottom: 10px;
        }

        .hero-title {
            font-size: 48px;
            line-height: 1.05;
            font-weight: 950;
            color: #2B1B1B;
            margin-bottom: 12px;
        }

        .hero-subtitle {
            font-size: 18px;
            color: #5F3B45;
            max-width: 900px;
            line-height: 1.65;
            font-weight: 650;
        }

        .metric-card {
            background: rgba(255,255,255,0.82);
            backdrop-filter: blur(18px);
            border-radius: 28px;
            padding: 26px;
            border: 1px solid rgba(255,255,255,0.78);
            box-shadow: 0 18px 48px rgba(160, 80, 115, 0.16);
            min-height: 158px;
            position: relative;
            overflow: hidden;
        }

        .metric-card::before {
            content: "";
            position: absolute;
            right: -32px;
            top: -32px;
            width: 120px;
            height: 120px;
            border-radius: 999px;
            background: linear-gradient(135deg, rgba(248, 120, 170, 0.25), rgba(201,168,106,0.20));
        }

        .metric-card::after {
            content: "";
            position: absolute;
            left: 0;
            bottom: 0;
            width: 100%;
            height: 5px;
            background: linear-gradient(90deg, #F37BAA, #D9A5A5, #C9A86A);
        }

        .metric-icon {
            font-size: 28px;
            margin-bottom: 10px;
        }

        .metric-label {
            font-size: 13px;
            font-weight: 950;
            color: #7B3E58;
            letter-spacing: .4px;
            margin-bottom: 10px;
            text-transform: uppercase;
        }

        .metric-value {
            font-size: 35px;
            font-weight: 950;
            color: #2B1B1B;
            margin-bottom: 8px;
        }

        .metric-help {
            font-size: 14px;
            color: #7A4F5D;
            font-weight: 750;
        }

        .section-title {
            font-size: 31px;
            font-weight: 950;
            color: #2B1B1B;
            margin-top: 30px;
            margin-bottom: 18px;
        }

        .panel {
            background: rgba(255,255,255,0.78);
            border: 1px solid rgba(255,255,255,0.72);
            border-radius: 28px;
            padding: 24px;
            box-shadow: 0 18px 45px rgba(160, 80, 115, 0.14);
            margin-bottom: 18px;
        }

        .panel-title {
            font-size: 23px;
            font-weight: 950;
            color: #2B1B1B;
            margin-bottom: 16px;
        }

        .alert-good, .op-card, .empty-state {
            background: rgba(255,255,255,0.82);
            border: 1px solid rgba(255,255,255,0.70);
            border-radius: 20px;
            padding: 18px 20px;
            color: #2B1B1B;
            font-weight: 850;
            margin-bottom: 14px;
            box-shadow: 0 12px 30px rgba(160, 80, 115, 0.10);
        }

        .alert-good {
            border-left: 7px solid #F37BAA;
        }

        .op-card {
            border-left: 7px solid #C9A86A;
        }

        .empty-state {
            border: 1px dashed rgba(183, 110, 138, 0.55);
            color: #6A3F4D;
        }

        .op-title {
            font-size: 17px;
            font-weight: 950;
            color: #2B1B1B;
            margin-bottom: 6px;
        }

        .op-msg {
            font-size: 14px;
            font-weight: 700;
            color: #6B4650;
            line-height: 1.5;
        }

        .footer-note {
            margin-top: 30px;
            color: #8B5B68;
            font-size: 12px;
            text-align: center;
            font-weight: 750;
        }

        h1, h2, h3, p {
            color: #2B1B1B;
        }

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"],
        div[data-baseweb="textarea"] textarea,
        input,
        textarea {
            background-color: #FFFFFF !important;
            color: #2B1B1B !important;
            border: 1px solid rgba(183, 110, 138, 0.35) !important;
            border-radius: 14px !important;
        }

        div[data-baseweb="select"] span,
        div[data-baseweb="input"] input,
        div[data-baseweb="textarea"] textarea {
            color: #2B1B1B !important;
            font-weight: 700 !important;
        }

        div[data-testid="stButton"] > button,
        div.stButton > button,
        .stButton > button,
        button[data-testid="baseButton-secondary"],
        button[data-testid="baseButton-primary"],
        button[data-testid="baseButton-minimal"] {
            background: linear-gradient(135deg, #F37BAA 0%, #D9A5A5 55%, #C9A86A 100%) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 18px !important;
            min-height: 55px !important;
            font-size: 15px !important;
            font-weight: 900 !important;
            box-shadow: 0 8px 22px rgba(180,90,120,.25) !important;
            transition: all .2s ease !important;
        }

        div[data-testid="stButton"] > button *,
        div.stButton > button *,
        .stButton > button *,
        button[data-testid="baseButton-secondary"] *,
        button[data-testid="baseButton-primary"] *,
        button[data-testid="baseButton-minimal"] * {
            color: #FFFFFF !important;
            font-weight: 900 !important;
        }

        div[data-testid="stButton"] > button:hover,
        div.stButton > button:hover,
        .stButton > button:hover,
        button[data-testid="baseButton-secondary"]:hover,
        button[data-testid="baseButton-primary"]:hover,
        button[data-testid="baseButton-minimal"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 28px rgba(180,90,120,.35) !important;
        }

        button:disabled,
        button[disabled],
        div[data-testid="stButton"] > button:disabled,
        div.stButton > button:disabled,
        .stButton > button:disabled {
            background: linear-gradient(135deg, #F7B5CD 0%, #D9A5A5 55%, #C9A86A 100%) !important;
            color: #FFFFFF !important;
            opacity: 0.55 !important;
            border: none !important;
            box-shadow: none !important;
        }

        button:disabled *,
        button[disabled] * {
            color: #FFFFFF !important;
            font-weight: 900 !important;
        }

        button[data-testid="stNumberInputStepUp"],
        button[data-testid="stNumberInputStepDown"] {
            background: #FFFFFF !important;
            color: #2B1B1B !important;
            border: 1px solid rgba(183, 110, 138, 0.35) !important;
        }

        div[data-testid="stAlert"] {
            background-color: rgba(255,255,255,0.80) !important;
            color: #2B1B1B !important;
            border-radius: 16px !important;
            border: 1px solid rgba(183, 110, 138, 0.25) !important;
        }

        div[data-testid="stAlert"] * {
            color: #2B1B1B !important;
        }

        div[data-testid="stDataFrame"] {
            background: rgba(255,255,255,0.86);
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.75);
        }

        @media (max-width: 768px) {
            .login-wrapper {
                margin: 4vh auto 0 auto;
                padding: 24px 20px;
                border-radius: 24px;
            }

            .login-title {
                font-size: 28px;
            }

            .hero {
                padding: 18px 18px;
                border-radius: 22px;
                margin-bottom: 18px;
            }

            .hero-title {
                font-size: 25px;
                line-height: 1.12;
                margin-bottom: 8px;
            }

            .hero-subtitle {
                font-size: 14px;
                line-height: 1.35;
            }

            .section-title {
                font-size: 24px;
                margin-top: 22px;
                margin-bottom: 14px;
            }

            .metric-card {
                padding: 20px;
                border-radius: 22px;
                min-height: auto;
                margin-bottom: 14px;
            }

            .metric-value {
                font-size: 28px;
            }

            .panel {
                padding: 18px;
                border-radius: 22px;
            }

            .panel-title {
                font-size: 20px;
            }

            div[data-testid="stDataFrame"] {
                overflow-x: auto;
            }

            div[data-testid="stButton"] > button {
                width: 100%;
                min-height: 52px !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def tela_login():
    st.markdown(
        f"""
        <div class="login-wrapper">
            <div class="login-title">{EMPRESA_ATUAL.get("icone", "🏪")} {EMPRESA_ATUAL.get("nome", "Sistema Comercial")}</div>
            <div class="login-subtitle">Acesse sua área de gestão comercial.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("form_login"):
        usuario = st.text_input("Usuário", placeholder="Digite seu usuário")
        senha = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        entrar = st.form_submit_button("Entrar")

        if entrar:
            if not usuario.strip() or not senha.strip():
                st.error("Informe usuário e senha.")
                return

            dados_usuario = autenticar_usuario(usuario.strip(), senha.strip())

            if dados_usuario is None:
                st.error("Usuário ou senha inválidos.")
                return

            st.session_state["autenticado"] = True
            st.session_state["usuario_logado"] = dados_usuario
            st.session_state["menu_atual"] = "Dashboard"

            try:
                registrar_log(
                    dados_usuario["usuario"],
                    "Login realizado",
                    f"Usuário {dados_usuario['nome']} acessou o sistema."
                )
            except Exception:
                pass

            st.success("Login realizado com sucesso.")
            st.rerun()

    st.markdown(
        """
        <div class="footer-note">
            Acesso restrito · Sistema Comercial
        </div>
        """,
        unsafe_allow_html=True,
    )


def fazer_logout():
    usuario = st.session_state.get("usuario_logado", {}).get("usuario", "")
    try:
        if usuario:
            registrar_log(usuario, "Logout realizado", "Usuário saiu do sistema.")
    except Exception:
        pass

    for chave in ["autenticado", "usuario_logado", "menu_atual"]:
        if chave in st.session_state:
            del st.session_state[chave]

    st.rerun()


def dashboard():
    hoje = date.today()
    inicio_mes = hoje.replace(day=1)

    saudacao_dashboard = EMPRESA_ATUAL.get(
        "saudacao_dashboard",
        f"Olá, {EMPRESA_ATUAL.get('nome', 'Sistema Comercial')} 👋"
    )

    mensagem_dashboard = EMPRESA_ATUAL.get(
        "mensagem_dashboard",
        "Resumo atualizado do seu negócio."
    )

    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-title">
                {saudacao_dashboard}
            </div>
            <div class="hero-subtitle">
                {mensagem_dashboard}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-title">Período de análise</div>', unsafe_allow_html=True)

    p1, p2 = st.columns(2)

    with p1:
        data_inicial = st.date_input("Data inicial", value=inicio_mes, key="dash_data_ini")

    with p2:
        data_final = st.date_input("Data final", value=hoje, key="dash_data_fim")

    if data_inicial > data_final:
        st.error("A data inicial não pode ser maior que a data final.")
        st.stop()

    data_ini = data_inicial.strftime("%Y-%m-%d")
    data_fim = data_final.strftime("%Y-%m-%d")

    meta = calcular_meta_inteligente(data_ini, data_fim)
    indicadores = obter_indicadores_periodo(data_ini, data_fim)

    st.markdown(f"""
    <div style="background: rgba(255,255,255,0.75); padding: 25px; border-radius: 24px; margin-bottom: 25px; box-shadow: 0 8px 25px rgba(0,0,0,0.08);">
        <div style="font-size:14px; font-weight:700; letter-spacing:2px; color:#B45F8C; margin-bottom:10px;">🎯 META</div>
        <div style="font-size:42px; font-weight:800; color:#2D1B1B;">R$ {meta['meta']:.2f}</div>
        <div style="font-size:14px; color:#666; margin-bottom:20px;">Meta calculada automaticamente pelo sistema</div>
        <progress value="{meta['progresso']}" max="100" style="width:100%; height:20px;"></progress>
        <div style="margin-top:20px; display:flex; justify-content:space-between; flex-wrap:wrap; gap:20px;">
            <div><b>Vendido</b><br>R$ {meta['vendido']:.2f}</div>
            <div><b>Faltante</b><br>R$ {meta['faltante']:.2f}</div>
            <div><b>Meta diária</b><br>R$ {meta['media_diaria']:.2f}</div>
            <div><b>Dias restantes</b><br>{meta['dias_meta_restantes']}</div>
            <div><b>Confiança</b><br>{meta['confianca']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        card_indicador("💰", "Faturamento", dinheiro(indicadores["faturamento"]), "Total vendido no período")

    with col2:
        card_indicador("📈", "Lucro bruto", dinheiro(indicadores["lucro"]), "Venda menos custo dos produtos")

    with col3:
        card_indicador("🛒", "Pedidos", indicadores["pedidos"], "Pedidos válidos no período")

    with col4:
        card_indicador("🎟️", "Ticket médio", dinheiro(indicadores["ticket_medio"]), "Média por pedido")

    st.markdown('<div class="section-title">Visão rápida</div>', unsafe_allow_html=True)

    left, right = st.columns([1.2, 1])

    with left:
        st.markdown('<div class="panel"><div class="panel-title">📝 Últimas atividades</div>', unsafe_allow_html=True)

        atividades = obter_ultimas_atividades(8)

        if atividades.empty:
            st.markdown('<div class="empty-state">Nenhuma atividade registrada ainda.</div>', unsafe_allow_html=True)
        else:
            atividades_view = atividades[["data", "tipo", "descricao"]].rename(
                columns={"data": "Data", "tipo": "Tipo", "descricao": "Descrição"}
            )
            st.dataframe(atividades_view, use_container_width=True, hide_index=True)

        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        clima = obter_clima_empresa(data_ini, data_fim)
        motivos_html = "".join([f"<li>{m}</li>" for m in clima["motivos"]])

        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">{clima["cor"]} Clima da empresa</div>
                <div class="metric-value">{clima["status"]}</div>
                <div class="metric-help">Pontuação operacional: {clima["pontos"]}/100</div>
                <br>
                <div class="op-msg">{clima["mensagem"]}</div>
                <ul class="op-msg">
                    {motivos_html}
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Top produtos</div>', unsafe_allow_html=True)

    top_produtos = obter_top_produtos(data_ini, data_fim, 8)

    if top_produtos.empty:
        st.markdown(
            '<div class="empty-state">Ainda não há vendas suficientes para listar produtos no período.</div>',
            unsafe_allow_html=True,
        )
    else:
        g1, g2 = st.columns([1.2, 1])

        with g1:
            fig = px.bar(top_produtos, x="Produto", y="Quantidade", text="Quantidade")
            fig.update_traces(textposition="outside")
            fig.update_layout(
                height=420,
                plot_bgcolor="rgba(255,255,255,0)",
                paper_bgcolor="rgba(255,255,255,0)",
                font=dict(color="#2B1B1B", size=14),
                xaxis=dict(title="Produto", tickfont=dict(color="#2B1B1B", size=13)),
                yaxis=dict(title="Quantidade vendida", tickfont=dict(color="#2B1B1B", size=13)),
                margin=dict(l=20, r=20, t=20, b=80),
            )
            st.plotly_chart(fig, use_container_width=True)

        with g2:
            tabela_top = top_produtos.copy()
            tabela_top["Faturamento"] = tabela_top["Faturamento"].apply(dinheiro)
            tabela_top["Lucro"] = tabela_top["Lucro"].apply(dinheiro)
            st.dataframe(tabela_top, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Radar de oportunidades</div>', unsafe_allow_html=True)

    oportunidades = obter_radar_oportunidades(data_ini, data_fim)

    for op in oportunidades:
        st.markdown(
            f"""
            <div class="op-card">
                <div class="op-title">{op["icone"]} {op["titulo"]}</div>
                <div class="op-msg">{op["mensagem"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="footer-note">Sistema Comercial · Gestão integrada de vendas, estoque e financeiro</div>',
        unsafe_allow_html=True,
    )


def app_principal():
    paginas = [
        "Dashboard",
        "Produtos",
        "Clientes",
        "PDV",
        "Pedidos",
        "Estoque",
        "Financeiro",
        "Relatórios",
        "Calendário",
        "Configurações",
    ]

    if "menu_atual" not in st.session_state:
        st.session_state["menu_atual"] = "Dashboard"

    if st.session_state["menu_atual"] not in paginas:
        st.session_state["menu_atual"] = "Dashboard"

    if EMPRESA_ATUAL.get("logo"):
        st.sidebar.image(EMPRESA_ATUAL["logo"], use_container_width=True)
    else:
        st.sidebar.markdown(
            f"## {EMPRESA_ATUAL.get('icone', '🏪')} {EMPRESA_ATUAL.get('nome', 'Sistema Comercial')}"
        )

    st.sidebar.caption(EMPRESA_ATUAL.get("slogan", "Sistema de gestão"))
    st.sidebar.markdown("---")

    usuario_logado = st.session_state.get("usuario_logado", {})
    st.sidebar.markdown(f"**Usuário:** {usuario_logado.get('nome', 'Usuário')}")
    st.sidebar.markdown(f"**Perfil:** {usuario_logado.get('perfil', '-')}")
    st.sidebar.markdown("---")

    menu = st.sidebar.radio(
        "Menu principal",
        paginas,
        index=paginas.index(st.session_state["menu_atual"]),
        key="menu_radio",
    )

    st.session_state["menu_atual"] = menu

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Versão:** {APP_VERSION}")
    st.sidebar.markdown(
        f"**Cidade:** {EMPRESA_ATUAL.get('cidade', '')} - {EMPRESA_ATUAL.get('estado', '')}"
    )

    if st.sidebar.button("Sair"):
        fazer_logout()

    if menu == "Dashboard":
        dashboard()
    elif menu == "Produtos":
        tela_produtos()
    elif menu == "Clientes":
        tela_clientes()
    elif menu == "PDV":
        tela_pdv()
    elif menu == "Pedidos":
        tela_pedidos()
    elif menu == "Estoque":
        tela_estoque()
    elif menu == "Financeiro":
        tela_financeiro()
    elif menu == "Relatórios":
        tela_relatorios()
    elif menu == "Calendário":
        tela_calendario()
    elif menu == "Configurações":
        tela_configuracoes()


aplicar_css()

if not st.session_state.get("autenticado", False):
    tela_login()
else:
    app_principal()