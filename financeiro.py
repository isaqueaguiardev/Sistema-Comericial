import sqlite3
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DATABASE_PATH


def conectar():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dinheiro(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def carregar_df(query, params=()):
    conn = conectar()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def executar_sql(sql, params=()):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    conn.close()


def soma_sql(query, params=()):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(query, params)
    valor = cursor.fetchone()[0]
    conn.close()
    return valor or 0


def cadastrar_despesa(data_despesa, descricao, categoria, valor, status, observacoes):
    executar_sql(
        """
        INSERT INTO despesas (
            data_despesa, descricao, categoria, valor, status, observacoes
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (data_despesa, descricao, categoria, valor, status, observacoes),
    )


def tela_financeiro():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Controle financeiro</div>
            <div class="hero-title">Financeiro</div>
            <div class="hero-subtitle">
                Analise faturamento, lucro, despesas e resultado da Airesbella por qualquer período.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-title">Período de análise</div>', unsafe_allow_html=True)

    hoje = date.today()
    inicio_mes = hoje.replace(day=1)

    f1, f2 = st.columns(2)

    with f1:
        data_inicial = st.date_input("Data inicial", value=inicio_mes)

    with f2:
        data_final = st.date_input("Data final", value=hoje)

    if data_inicial > data_final:
        st.error("A data inicial não pode ser maior que a data final.")
        return

    data_ini = data_inicial.strftime("%Y-%m-%d")
    data_fim = data_final.strftime("%Y-%m-%d")

    faturamento_periodo = soma_sql(
        """
        SELECT SUM(total) FROM pedidos
        WHERE DATE(data_pedido) BETWEEN ? AND ?
        AND status != 'Cancelado'
        """,
        (data_ini, data_fim),
    )

    lucro_bruto_periodo = soma_sql(
        """
        SELECT SUM(lucro_bruto) FROM pedidos
        WHERE DATE(data_pedido) BETWEEN ? AND ?
        AND status != 'Cancelado'
        """,
        (data_ini, data_fim),
    )

    despesas_pagas_periodo = soma_sql(
        """
        SELECT SUM(valor) FROM despesas
        WHERE DATE(data_despesa) BETWEEN ? AND ?
        AND status = 'Pago'
        """,
        (data_ini, data_fim),
    )

    despesas_pendentes_periodo = soma_sql(
        """
        SELECT SUM(valor) FROM despesas
        WHERE DATE(data_despesa) BETWEEN ? AND ?
        AND status = 'Pendente'
        """,
        (data_ini, data_fim),
    )

    total_pedidos = soma_sql(
        """
        SELECT COUNT(*) FROM pedidos
        WHERE DATE(data_pedido) BETWEEN ? AND ?
        AND status != 'Cancelado'
        """,
        (data_ini, data_fim),
    )

    ticket_medio = faturamento_periodo / total_pedidos if total_pedidos else 0
    resultado_periodo = lucro_bruto_periodo - despesas_pagas_periodo

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Faturamento</div>
            <div class="metric-value">{dinheiro(faturamento_periodo)}</div>
            <div class="metric-help">Total vendido no período</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Lucro bruto</div>
            <div class="metric-value">{dinheiro(lucro_bruto_periodo)}</div>
            <div class="metric-help">Venda menos custo dos produtos</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Despesas pagas</div>
            <div class="metric-value">{dinheiro(despesas_pagas_periodo)}</div>
            <div class="metric-help">Saídas pagas no período</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Resultado</div>
            <div class="metric-value">{dinheiro(resultado_periodo)}</div>
            <div class="metric-help">Lucro bruto - despesas pagas</div>
        </div>
        """, unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)

    with c5:
        st.metric("Pedidos", int(total_pedidos))

    with c6:
        st.metric("Ticket médio", dinheiro(ticket_medio))

    with c7:
        st.metric("Despesas pendentes", dinheiro(despesas_pendentes_periodo))

    with c8:
        margem_resultado = (resultado_periodo / faturamento_periodo * 100) if faturamento_periodo else 0
        st.metric("Margem resultado", f"{margem_resultado:.1f}%")

    st.markdown('<div class="section-title">Cadastrar despesa</div>', unsafe_allow_html=True)

    with st.form("form_cadastrar_despesa", clear_on_submit=True):
        d1, d2, d3 = st.columns([1, 2, 1])

        with d1:
            data_despesa = st.date_input("Data", value=date.today(), key="data_despesa_cadastro")

        with d2:
            descricao = st.text_input("Descrição *", placeholder="Ex: aluguel, energia, compra de sacolas...")

        with d3:
            categoria = st.selectbox(
                "Categoria",
                [
                    "Aluguel",
                    "Energia",
                    "Internet",
                    "Compra de estoque",
                    "Marketing",
                    "Transporte",
                    "Embalagens",
                    "Taxas",
                    "Outros",
                ],
            )

        d4, d5 = st.columns(2)

        with d4:
            valor = st.number_input("Valor", min_value=0.0, step=5.0, format="%.2f")

        with d5:
            status = st.selectbox("Status", ["Pago", "Pendente"])

        observacoes = st.text_area("Observações")

        salvar = st.form_submit_button("Salvar despesa")

        if salvar:
            if not descricao.strip():
                st.error("Informe a descrição da despesa.")
            elif valor <= 0:
                st.error("Informe um valor maior que zero.")
            else:
                cadastrar_despesa(
                    data_despesa.strftime("%Y-%m-%d"),
                    descricao.strip(),
                    categoria,
                    valor,
                    status,
                    observacoes.strip(),
                )
                st.success("Despesa cadastrada com sucesso.")
                st.rerun()

    st.markdown('<div class="section-title">Análises do período</div>', unsafe_allow_html=True)

    vendas_dia = carregar_df(
        """
        SELECT DATE(data_pedido) AS Data, SUM(total) AS Faturamento
        FROM pedidos
        WHERE DATE(data_pedido) BETWEEN ? AND ?
        AND status != 'Cancelado'
        GROUP BY DATE(data_pedido)
        ORDER BY Data
        """,
        (data_ini, data_fim),
    )

    despesas_categoria = carregar_df(
        """
        SELECT categoria AS Categoria, SUM(valor) AS Total
        FROM despesas
        WHERE DATE(data_despesa) BETWEEN ? AND ?
        AND status = 'Pago'
        GROUP BY categoria
        ORDER BY Total DESC
        """,
        (data_ini, data_fim),
    )

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown('<div class="panel-title">Faturamento por dia</div>', unsafe_allow_html=True)
        if vendas_dia.empty:
            st.markdown('<div class="empty-state">Sem vendas no período selecionado.</div>', unsafe_allow_html=True)
        else:
            fig = px.line(vendas_dia, x="Data", y="Faturamento", markers=True)
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#3A2A2A"),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_g2:
        st.markdown('<div class="panel-title">Despesas pagas por categoria</div>', unsafe_allow_html=True)
        if despesas_categoria.empty:
            st.markdown('<div class="empty-state">Nenhuma despesa paga no período.</div>', unsafe_allow_html=True)
        else:
            fig = px.pie(despesas_categoria, names="Categoria", values="Total", hole=0.45)
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#3A2A2A"),
            )
            st.plotly_chart(fig, use_container_width=True)

    col_t1, col_t2 = st.columns(2)

    with col_t1:
        st.markdown('<div class="panel-title">Vendas por forma de pagamento</div>', unsafe_allow_html=True)

        formas = carregar_df(
            """
            SELECT forma_pagamento AS Forma, SUM(total) AS Total
            FROM pedidos
            WHERE DATE(data_pedido) BETWEEN ? AND ?
            AND status != 'Cancelado'
            GROUP BY forma_pagamento
            ORDER BY Total DESC
            """,
            (data_ini, data_fim),
        )

        if formas.empty:
            st.markdown('<div class="empty-state">Sem dados de pagamento no período.</div>', unsafe_allow_html=True)
        else:
            formas["Total"] = formas["Total"].apply(dinheiro)
            st.dataframe(formas, use_container_width=True, hide_index=True)

    with col_t2:
        st.markdown('<div class="panel-title">Vendas por tipo</div>', unsafe_allow_html=True)

        tipos = carregar_df(
            """
            SELECT tipo_venda AS Tipo, SUM(total) AS Total
            FROM pedidos
            WHERE DATE(data_pedido) BETWEEN ? AND ?
            AND status != 'Cancelado'
            GROUP BY tipo_venda
            ORDER BY Total DESC
            """,
            (data_ini, data_fim),
        )

        if tipos.empty:
            st.markdown('<div class="empty-state">Sem vendas por tipo no período.</div>', unsafe_allow_html=True)
        else:
            tipos["Total"] = tipos["Total"].apply(dinheiro)
            st.dataframe(tipos, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Despesas do período</div>', unsafe_allow_html=True)

    despesas = carregar_df(
        """
        SELECT
            id AS ID,
            data_despesa AS Data,
            descricao AS Descrição,
            categoria AS Categoria,
            valor AS Valor,
            status AS Status,
            observacoes AS Observações
        FROM despesas
        WHERE DATE(data_despesa) BETWEEN ? AND ?
        ORDER BY id DESC
        """,
        (data_ini, data_fim),
    )

    if despesas.empty:
        st.markdown('<div class="empty-state">Nenhuma despesa cadastrada no período selecionado.</div>', unsafe_allow_html=True)
    else:
        despesas["Valor"] = despesas["Valor"].apply(dinheiro)
        st.dataframe(despesas, use_container_width=True, hide_index=True)