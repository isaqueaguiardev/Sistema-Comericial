import sqlite3
from datetime import datetime

import streamlit as st

from config import DATABASE_PATH, EMPRESA


def conectar():
    conn = sqlite3.connect(DATABASE_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def executar_sql(sql, params=()):
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def consultar_sql(sql, params=()):
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        conn.close()


def criar_tabela_configuracoes():
    executar_sql(
        """
        CREATE TABLE IF NOT EXISTS configuracoes_empresa (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nome TEXT,
            slogan TEXT,
            cidade TEXT,
            estado TEXT,
            segmento TEXT,
            icone TEXT,
            saudacao_dashboard TEXT,
            mensagem_dashboard TEXT,
            atualizado_em TEXT
        )
        """
    )


def carregar_configuracoes_empresa():
    criar_tabela_configuracoes()

    dados = consultar_sql(
        """
        SELECT *
        FROM configuracoes_empresa
        WHERE id = 1
        """
    )

    if not dados:
        executar_sql(
            """
            INSERT INTO configuracoes_empresa (
                id,
                nome,
                slogan,
                cidade,
                estado,
                segmento,
                icone,
                saudacao_dashboard,
                mensagem_dashboard,
                atualizado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                EMPRESA.get("nome", "Sistema Comercial"),
                EMPRESA.get("slogan", "Seu slogan aqui"),
                EMPRESA.get("cidade", "Sua cidade aqui"),
                EMPRESA.get("estado", ""),
                EMPRESA.get("segmento", "Loja/Comércio"),
                EMPRESA.get("icone", "🏪"),
                EMPRESA.get("saudacao_dashboard", "Olá 👋"),
                EMPRESA.get("mensagem_dashboard", "Bem-vindo de volta."),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        dados = consultar_sql(
            """
            SELECT *
            FROM configuracoes_empresa
            WHERE id = 1
            """
        )

    return dict(dados[0])


def salvar_configuracoes_empresa(
    nome,
    slogan,
    cidade,
    estado,
    segmento,
    icone,
    saudacao_dashboard,
    mensagem_dashboard,
):
    criar_tabela_configuracoes()

    executar_sql(
        """
        INSERT INTO configuracoes_empresa (
            id,
            nome,
            slogan,
            cidade,
            estado,
            segmento,
            icone,
            saudacao_dashboard,
            mensagem_dashboard,
            atualizado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            nome = excluded.nome,
            slogan = excluded.slogan,
            cidade = excluded.cidade,
            estado = excluded.estado,
            segmento = excluded.segmento,
            icone = excluded.icone,
            saudacao_dashboard = excluded.saudacao_dashboard,
            mensagem_dashboard = excluded.mensagem_dashboard,
            atualizado_em = excluded.atualizado_em
        """,
        (
            1,
            nome,
            slogan,
            cidade,
            estado,
            segmento,
            icone,
            saudacao_dashboard,
            mensagem_dashboard,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )


def tela_configuracoes():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Personalização</div>
            <div class="hero-title">Configurações</div>
            <div class="hero-subtitle">
                Personalize os dados básicos da empresa exibidos no sistema.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    config = carregar_configuracoes_empresa()

    st.markdown('<div class="section-title">Dados da empresa</div>', unsafe_allow_html=True)

    with st.form("form_configuracoes_empresa"):
        c1, c2 = st.columns([2, 1])

        with c1:
            nome = st.text_input("Nome da empresa", value=config.get("nome") or "")

        with c2:
            icone = st.text_input("Ícone", value=config.get("icone") or "🏪")

        slogan = st.text_input("Slogan", value=config.get("slogan") or "")

        c3, c4 = st.columns(2)

        with c3:
            cidade = st.text_input("Cidade", value=config.get("cidade") or "")

        with c4:
            estado = st.text_input("Estado", value=config.get("estado") or "")

        segmento = st.text_input("Segmento", value=config.get("segmento") or "")

        st.markdown('<div class="section-title">Dashboard</div>', unsafe_allow_html=True)

        saudacao_dashboard = st.text_input(
            "Saudação do Dashboard",
            value=config.get("saudacao_dashboard") or "Olá 👋",
        )

        mensagem_dashboard = st.text_area(
            "Mensagem do Dashboard",
            value=config.get("mensagem_dashboard") or "Bem-vindo de volta.",
        )

        salvar = st.form_submit_button("Salvar configurações")

        if salvar:
            if not nome.strip():
                st.error("Informe o nome da empresa.")
            else:
                salvar_configuracoes_empresa(
                    nome.strip(),
                    slogan.strip(),
                    cidade.strip(),
                    estado.strip(),
                    segmento.strip(),
                    icone.strip(),
                    saudacao_dashboard.strip(),
                    mensagem_dashboard.strip(),
                )
                st.success("Configurações salvas com sucesso.")
                st.rerun()

    config = carregar_configuracoes_empresa()

    st.markdown('<div class="section-title">Prévia</div>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">{config.get("icone", "🏪")} {config.get("nome", "Sistema Comercial")}</div>
            <div class="op-msg">
                {config.get("slogan", "")}<br>
                {config.get("cidade", "")} - {config.get("estado", "")}<br>
                Segmento: <b>{config.get("segmento", "")}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )