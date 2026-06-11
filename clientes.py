import sqlite3
from datetime import datetime, date

import pandas as pd
import streamlit as st

from config import DATABASE_PATH


ORIGENS_CLIENTE = [
    "Loja Física",
    "Instagram",
    "WhatsApp",
    "Indicação",
    "Facebook",
    "TikTok",
    "Outro",
]


def conectar():
    conn = sqlite3.connect(DATABASE_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def dinheiro(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def executar_sql(sql, params=()):
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def carregar_clientes():
    conn = conectar()
    df = pd.read_sql_query(
        """
        SELECT
            c.id,
            c.nome,
            c.telefone,
            c.cidade,
            COALESCE(c.bairro_povoado, c.bairro) AS bairro_povoado,
            c.origem,
            c.data_nascimento,
            c.vip,
            c.observacoes,
            c.criado_em
        FROM clientes c
        ORDER BY c.id DESC
        """,
        conn,
    )
    conn.close()
    return df


def cadastrar_cliente(
    nome,
    telefone,
    cidade,
    bairro_povoado,
    origem,
    data_nascimento,
    vip,
    observacoes,
):
    executar_sql(
        """
        INSERT INTO clientes (
            nome,
            telefone,
            cidade,
            bairro,
            bairro_povoado,
            origem,
            data_nascimento,
            vip,
            observacoes,
            criado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            nome,
            telefone,
            cidade,
            bairro_povoado,
            bairro_povoado,
            origem,
            data_nascimento,
            vip,
            observacoes,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )


def atualizar_cliente(
    cliente_id,
    nome,
    telefone,
    cidade,
    bairro_povoado,
    origem,
    data_nascimento,
    vip,
    observacoes,
):
    executar_sql(
        """
        UPDATE clientes
        SET
            nome = ?,
            telefone = ?,
            cidade = ?,
            bairro = ?,
            bairro_povoado = ?,
            origem = ?,
            data_nascimento = ?,
            vip = ?,
            observacoes = ?
        WHERE id = ?
        """,
        (
            nome,
            telefone,
            cidade,
            bairro_povoado,
            bairro_povoado,
            origem,
            data_nascimento,
            vip,
            observacoes,
            cliente_id,
        ),
    )


def carregar_resumo_clientes():
    conn = conectar()

    compras = pd.read_sql_query(
        """
        SELECT
            cliente_id,
            COUNT(*) AS compras,
            SUM(total) AS total_gasto,
            AVG(total) AS ticket_medio,
            MIN(DATE(data_pedido)) AS primeira_compra,
            MAX(DATE(data_pedido)) AS ultima_compra
        FROM pedidos
        WHERE cliente_id IS NOT NULL
        AND status != 'Cancelado'
        GROUP BY cliente_id
        """,
        conn,
    )

    conn.close()
    return compras


def preparar_clientes_com_resumo():
    clientes_df = carregar_clientes()
    resumo_compras = carregar_resumo_clientes()

    if clientes_df.empty:
        return clientes_df

    if not resumo_compras.empty:
        clientes_df = clientes_df.merge(
            resumo_compras,
            how="left",
            left_on="id",
            right_on="cliente_id",
        )
    else:
        clientes_df["compras"] = 0
        clientes_df["total_gasto"] = 0
        clientes_df["ticket_medio"] = 0
        clientes_df["primeira_compra"] = None
        clientes_df["ultima_compra"] = None

    clientes_df["compras"] = clientes_df["compras"].fillna(0)
    clientes_df["total_gasto"] = clientes_df["total_gasto"].fillna(0)
    clientes_df["ticket_medio"] = clientes_df["ticket_medio"].fillna(0)

    return clientes_df


def card_resumo(titulo, valor, ajuda):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{titulo}</div>
            <div class="metric-value">{valor}</div>
            <div class="metric-help">{ajuda}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def formatar_data(data_texto):
    if not data_texto:
        return "-"
    try:
        return pd.to_datetime(data_texto).strftime("%d/%m/%Y")
    except Exception:
        return "-"


def card_cliente(cliente):
    vip = cliente["vip"] == "Sim"
    vip_texto = "⭐ CLIENTE VIP" if vip else "Cliente comum"

    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">👤 {cliente["nome"]}</div>
            <div class="op-msg">
                📱 <b>{cliente["telefone"] or "-"}</b><br>
                📍 {cliente["bairro_povoado"] or "-"} · {cliente["cidade"] or "-"}<br>
                🎯 Origem: <b>{cliente["origem"] or "-"}</b><br>
                {vip_texto}<br><br>

                🛒 Compras: <b>{int(cliente["compras"])}</b><br>
                💰 Total gasto: <b>{dinheiro(cliente["total_gasto"])}</b><br>
                🎟️ Ticket médio: <b>{dinheiro(cliente["ticket_medio"])}</b><br>
                📅 Última compra: <b>{formatar_data(cliente["ultima_compra"])}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def tela_clientes():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Relacionamento comercial</div>
            <div class="hero-title">Clientes</div>
            <div class="hero-subtitle">
                Cadastre clientes, acompanhe histórico de compras, regiões, origem e perfil VIP.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    clientes_df = preparar_clientes_com_resumo()

    total_clientes = len(clientes_df)
    clientes_vip = int((clientes_df["vip"] == "Sim").sum()) if not clientes_df.empty else 0
    regioes = clientes_df["bairro_povoado"].dropna().nunique() if not clientes_df.empty else 0
    com_compras = int((clientes_df["compras"].fillna(0) > 0).sum()) if not clientes_df.empty else 0
    ticket_medio_geral = clientes_df["ticket_medio"].mean() if not clientes_df.empty else 0

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        card_resumo("Clientes", total_clientes, "Base cadastrada")

    with c2:
        card_resumo("VIP", clientes_vip, "Clientes estratégicos")

    with c3:
        card_resumo("Regiões", regioes, "Áreas atendidas")

    with c4:
        card_resumo("Ticket", dinheiro(ticket_medio_geral), "Média por cliente")

    st.markdown('<div class="section-title">Cadastrar cliente</div>', unsafe_allow_html=True)

    with st.form("form_cadastrar_cliente", clear_on_submit=True):
        st.markdown('<div class="panel-title">📇 Dados básicos</div>', unsafe_allow_html=True)

        a1, a2 = st.columns([2, 1])

        with a1:
            nome = st.text_input("Nome do cliente *", placeholder="Ex: Ana Silva")

        with a2:
            telefone = st.text_input("Telefone/WhatsApp *", placeholder="Ex: 98999990000")

        b1, b2 = st.columns(2)

        with b1:
            cidade = st.text_input("Cidade *", placeholder="Ex: Itapecuru Mirim")

        with b2:
            bairro_povoado = st.text_input("Bairro/Região *", placeholder="Ex: Centro, Bairro Novo")

        st.markdown('<div class="panel-title">⭐ Perfil comercial</div>', unsafe_allow_html=True)

        c1b, c2b, c3b = st.columns(3)

        with c1b:
            origem = st.selectbox("Origem", ORIGENS_CLIENTE)

        with c2b:
            vip = st.selectbox("Cliente VIP?", ["Não", "Sim"])

        with c3b:
            data_nascimento = st.date_input(
                "Nascimento",
                value=None,
                min_value=date(1930, 1, 1),
                max_value=date.today(),
            )

        st.markdown('<div class="panel-title">📝 Observações</div>', unsafe_allow_html=True)

        observacoes = st.text_area(
            "Anotações importantes",
            placeholder="Ex: gosta de promoções, compra para presente, prefere WhatsApp...",
        )

        salvar = st.form_submit_button("Salvar cliente")

        if salvar:
            if not nome.strip():
                st.error("Informe o nome do cliente.")
            elif not telefone.strip():
                st.error("Informe o telefone do cliente.")
            elif not cidade.strip():
                st.error("Informe a cidade.")
            elif not bairro_povoado.strip():
                st.error("Informe o bairro ou região.")
            else:
                cadastrar_cliente(
                    nome.strip(),
                    telefone.strip(),
                    cidade.strip(),
                    bairro_povoado.strip(),
                    origem,
                    data_nascimento.strftime("%Y-%m-%d") if data_nascimento else None,
                    vip,
                    observacoes.strip(),
                )
                st.success("Cliente cadastrado com sucesso.")
                st.rerun()

    st.markdown('<div class="section-title">Consultar clientes</div>', unsafe_allow_html=True)

    clientes_df = preparar_clientes_com_resumo()

    if clientes_df.empty:
        st.markdown(
            """
            <div class="empty-state">
                Nenhum cliente cadastrado ainda. Cadastre o primeiro cliente acima.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    f1, f2 = st.columns([2, 1])

    with f1:
        busca = st.text_input("Buscar cliente", placeholder="Nome, telefone, bairro, cidade ou origem...")

    with f2:
        filtro_vip = st.selectbox("VIP", ["Todos", "Sim", "Não"])

    f3, f4 = st.columns(2)

    with f3:
        bairros_lista = ["Todos"] + sorted([x for x in clientes_df["bairro_povoado"].dropna().unique()])
        filtro_bairro = st.selectbox("Bairro/Região", bairros_lista)

    with f4:
        filtro_origem = st.selectbox("Origem", ["Todas"] + ORIGENS_CLIENTE)

    df = clientes_df.copy()

    if busca:
        b = busca.lower()
        df = df[
            df["nome"].fillna("").str.lower().str.contains(b)
            | df["telefone"].fillna("").str.lower().str.contains(b)
            | df["cidade"].fillna("").str.lower().str.contains(b)
            | df["bairro_povoado"].fillna("").str.lower().str.contains(b)
            | df["origem"].fillna("").str.lower().str.contains(b)
        ]

    if filtro_bairro != "Todos":
        df = df[df["bairro_povoado"] == filtro_bairro]

    if filtro_origem != "Todas":
        df = df[df["origem"] == filtro_origem]

    if filtro_vip != "Todos":
        df = df[df["vip"] == filtro_vip]

    if df.empty:
        st.markdown(
            '<div class="empty-state">Nenhum cliente encontrado com os filtros atuais.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="alert-good">
                {len(df)} cliente(s) encontrado(s).
            </div>
            """,
            unsafe_allow_html=True,
        )

        df_cards = df.sort_values(["vip", "total_gasto"], ascending=[False, False])

        for _, cliente in df_cards.head(12).iterrows():
            card_cliente(cliente)

        if len(df_cards) > 12:
            st.info("Mostrando os 12 primeiros clientes. Use a busca ou filtros para refinar.")

        with st.expander("Ver tabela completa"):
            tabela = df.copy()
            tabela["Total gasto"] = tabela["total_gasto"].fillna(0).apply(dinheiro)
            tabela["Ticket médio"] = tabela["ticket_medio"].fillna(0).apply(dinheiro)
            tabela["Compras"] = tabela["compras"].fillna(0).astype(int)
            tabela["Última compra"] = tabela["ultima_compra"].apply(formatar_data)

            tabela = tabela[
                [
                    "id",
                    "nome",
                    "telefone",
                    "cidade",
                    "bairro_povoado",
                    "origem",
                    "vip",
                    "Compras",
                    "Total gasto",
                    "Ticket médio",
                    "Última compra",
                ]
            ].rename(
                columns={
                    "id": "ID",
                    "nome": "Cliente",
                    "telefone": "Telefone",
                    "cidade": "Cidade",
                    "bairro_povoado": "Bairro/Região",
                    "origem": "Origem",
                    "vip": "VIP",
                }
            )

            st.dataframe(tabela, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Editar cliente</div>', unsafe_allow_html=True)

    opcoes_clientes = clientes_df["id"].astype(str) + " - " + clientes_df["nome"]
    selecionado = st.selectbox("Selecione um cliente", opcoes_clientes)

    cliente_id = int(selecionado.split(" - ")[0])
    cliente = clientes_df[clientes_df["id"] == cliente_id].iloc[0]

    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">Editando: {cliente["nome"]}</div>
            <div class="op-msg">
                Telefone: <b>{cliente["telefone"] or "-"}</b><br>
                Região: <b>{cliente["bairro_povoado"] or "-"}</b><br>
                Compras: <b>{int(cliente["compras"])}</b><br>
                Total gasto: <b>{dinheiro(cliente["total_gasto"])}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("form_editar_cliente"):
        st.markdown('<div class="panel-title">📇 Dados básicos</div>', unsafe_allow_html=True)

        e1, e2 = st.columns([2, 1])

        with e1:
            nome_edit = st.text_input("Nome", value=cliente["nome"])

        with e2:
            telefone_edit = st.text_input("Telefone", value=cliente["telefone"] or "")

        e3, e4 = st.columns(2)

        with e3:
            cidade_edit = st.text_input("Cidade", value=cliente["cidade"] or "")

        with e4:
            bairro_edit = st.text_input("Bairro/Região", value=cliente["bairro_povoado"] or "")

        st.markdown('<div class="panel-title">⭐ Perfil</div>', unsafe_allow_html=True)

        e5, e6, e7 = st.columns(3)

        with e5:
            origem_edit = st.selectbox(
                "Origem",
                ORIGENS_CLIENTE,
                index=ORIGENS_CLIENTE.index(cliente["origem"])
                if cliente["origem"] in ORIGENS_CLIENTE
                else 0,
            )

        with e6:
            vip_edit = st.selectbox(
                "VIP?",
                ["Não", "Sim"],
                index=1 if cliente["vip"] == "Sim" else 0,
            )

        with e7:
            data_padrao = None
            if cliente["data_nascimento"]:
                try:
                    data_padrao = datetime.strptime(cliente["data_nascimento"], "%Y-%m-%d").date()
                except Exception:
                    data_padrao = None

            data_nascimento_edit = st.date_input(
                "Nascimento",
                value=data_padrao,
                min_value=date(1930, 1, 1),
                max_value=date.today(),
            )

        observacoes_edit = st.text_area("Observações", value=cliente["observacoes"] or "")

        salvar_edicao = st.form_submit_button("Salvar alterações")

        if salvar_edicao:
            if not nome_edit.strip():
                st.error("Informe o nome do cliente.")
            elif not telefone_edit.strip():
                st.error("Informe o telefone.")
            elif not cidade_edit.strip():
                st.error("Informe a cidade.")
            elif not bairro_edit.strip():
                st.error("Informe o bairro/região.")
            else:
                atualizar_cliente(
                    cliente_id,
                    nome_edit.strip(),
                    telefone_edit.strip(),
                    cidade_edit.strip(),
                    bairro_edit.strip(),
                    origem_edit,
                    data_nascimento_edit.strftime("%Y-%m-%d") if data_nascimento_edit else None,
                    vip_edit,
                    observacoes_edit.strip(),
                )
                st.success("Cliente atualizado com sucesso.")
                st.rerun()