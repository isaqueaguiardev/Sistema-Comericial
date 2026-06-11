import sqlite3
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DATABASE_PATH


CATEGORIAS_DESPESA = [
    "Aluguel",
    "Energia",
    "Internet",
    "Compra de estoque",
    "Marketing",
    "Transporte",
    "Embalagens",
    "Taxas",
    "Outros",
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


def carregar_df(query, params=()):
    conn = conectar()
    try:
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()


def executar_sql(sql, params=()):
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def soma_sql(query, params=()):
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        valor = cursor.fetchone()[0]
        return valor or 0
    finally:
        conn.close()


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
        return str(data_texto)


def gerar_diagnostico(
    faturamento,
    lucro_bruto,
    despesas_pagas,
    resultado,
    margem_resultado,
    despesas_pendentes,
    total_pedidos,
):
    if faturamento <= 0 and despesas_pagas <= 0:
        return {
            "icone": "⚪",
            "titulo": "Sem dados suficientes",
            "mensagem": "Ainda não há vendas ou despesas no período para gerar uma leitura financeira.",
        }

    if resultado > 0 and margem_resultado >= 25 and despesas_pagas <= lucro_bruto:
        return {
            "icone": "🟢",
            "titulo": "Negócio saudável",
            "mensagem": (
                f"O resultado do período está positivo em {dinheiro(resultado)}. "
                f"A margem líquida aproximada é de {margem_resultado:.1f}% e as despesas estão sob controle."
            ),
        }

    if resultado > 0 and margem_resultado < 25:
        return {
            "icone": "🟡",
            "titulo": "Resultado positivo, mas apertado",
            "mensagem": (
                f"O negócio teve resultado positivo de {dinheiro(resultado)}, "
                f"mas a margem líquida está em {margem_resultado:.1f}%. "
                "Vale revisar despesas e preços para aumentar a folga financeira."
            ),
        }

    if resultado <= 0 and faturamento > 0:
        return {
            "icone": "🔴",
            "titulo": "Atenção ao caixa",
            "mensagem": (
                f"O resultado do período ficou em {dinheiro(resultado)}. "
                "As despesas pagas consumiram o lucro bruto. Revise custos, despesas e margem dos produtos."
            ),
        }

    if total_pedidos == 0 and despesas_pagas > 0:
        return {
            "icone": "🟡",
            "titulo": "Despesas sem vendas no período",
            "mensagem": (
                f"Foram registradas despesas de {dinheiro(despesas_pagas)}, "
                "mas não houve vendas no período filtrado."
            ),
        }

    return {
        "icone": "🟡",
        "titulo": "Acompanhe de perto",
        "mensagem": (
            "Existem movimentações financeiras no período. Continue acompanhando vendas, despesas e resultado."
        ),
    }


def renderizar_despesa_card(despesa):
    status = despesa["Status"]
    status_txt = "✅ Pago" if status == "Pago" else "🟡 Pendente"

    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">💸 {despesa["Descrição"]}</div>
            <div class="op-msg">
                Data: <b>{formatar_data(despesa["Data"])}</b><br>
                Categoria: <b>{despesa["Categoria"] or "-"}</b><br>
                Valor: <b>{dinheiro(despesa["Valor"])}</b><br>
                Status: <b>{status_txt}</b><br>
                Observações: <b>{despesa["Observações"] or "-"}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def tela_financeiro():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Controle financeiro</div>
            <div class="hero-title">Financeiro</div>
            <div class="hero-subtitle">
                Veja se a empresa está realmente dando resultado: vendas, lucro, despesas, margem e saúde financeira.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    hoje = date.today()
    inicio_mes = hoje.replace(day=1)

    st.markdown('<div class="section-title">Período de análise</div>', unsafe_allow_html=True)

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
    dias_periodo = max((data_final - data_inicial).days + 1, 1)

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
    margem_resultado = (resultado_periodo / faturamento_periodo * 100) if faturamento_periodo else 0
    margem_bruta = (lucro_bruto_periodo / faturamento_periodo * 100) if faturamento_periodo else 0
    media_diaria = faturamento_periodo / dias_periodo if dias_periodo else 0

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

    melhor_dia = "-"
    melhor_dia_valor = 0

    if not vendas_dia.empty:
        melhor_linha = vendas_dia.sort_values("Faturamento", ascending=False).iloc[0]
        melhor_dia = formatar_data(melhor_linha["Data"])
        melhor_dia_valor = melhor_linha["Faturamento"]

    dias_com_venda = vendas_dia["Data"].nunique() if not vendas_dia.empty else 0
    dias_sem_venda = max(dias_periodo - dias_com_venda, 0)

    st.markdown('<div class="section-title">Painel executivo</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        card_resumo("Faturamento", dinheiro(faturamento_periodo), "Total vendido")

    with c2:
        card_resumo("Lucro bruto", dinheiro(lucro_bruto_periodo), f"Margem bruta {margem_bruta:.1f}%")

    with c3:
        card_resumo("Despesas pagas", dinheiro(despesas_pagas_periodo), "Saídas realizadas")

    with c4:
        card_resumo("Resultado", dinheiro(resultado_periodo), f"Margem líquida {margem_resultado:.1f}%")

    c5, c6, c7, c8 = st.columns(4)

    with c5:
        card_resumo("Pedidos", int(total_pedidos), "Vendas no período")

    with c6:
        card_resumo("Ticket médio", dinheiro(ticket_medio), "Média por pedido")

    with c7:
        card_resumo("Média diária", dinheiro(media_diaria), "Faturamento por dia")

    with c8:
        card_resumo("Pendentes", dinheiro(despesas_pendentes_periodo), "Despesas em aberto")

    d1, d2 = st.columns(2)

    with d1:
        card_resumo("Melhor dia", melhor_dia, dinheiro(melhor_dia_valor))

    with d2:
        card_resumo("Dias sem venda", dias_sem_venda, "Dentro do período")

    diagnostico = gerar_diagnostico(
        faturamento_periodo,
        lucro_bruto_periodo,
        despesas_pagas_periodo,
        resultado_periodo,
        margem_resultado,
        despesas_pendentes_periodo,
        total_pedidos,
    )

    st.markdown('<div class="section-title">Diagnóstico financeiro</div>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">{diagnostico["icone"]} {diagnostico["titulo"]}</div>
            <div class="op-msg">{diagnostico["mensagem"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if despesas_pendentes_periodo > 0:
        st.markdown(
            f"""
            <div class="op-card">
                <div class="op-title">🟡 Despesas pendentes</div>
                <div class="op-msg">
                    Existem {dinheiro(despesas_pendentes_periodo)} em despesas pendentes no período.
                    Esse valor ainda pode impactar o resultado real do caixa.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Cadastrar despesa</div>', unsafe_allow_html=True)

    with st.form("form_cadastrar_despesa", clear_on_submit=True):
        st.markdown('<div class="panel-title">💸 Dados da despesa</div>', unsafe_allow_html=True)

        d1, d2 = st.columns([1, 2])

        with d1:
            data_despesa = st.date_input("Data", value=date.today(), key="data_despesa_cadastro")

        with d2:
            descricao = st.text_input("Descrição *", placeholder="Ex: aluguel, energia, compra de sacolas...")

        d3, d4 = st.columns(2)

        with d3:
            categoria = st.selectbox("Categoria", CATEGORIAS_DESPESA)

        with d4:
            valor = st.number_input("Valor", min_value=0.0, step=5.0, format="%.2f")

        d5, d6 = st.columns(2)

        with d5:
            status = st.selectbox("Status", ["Pago", "Pendente"])

        with d6:
            st.markdown(
                f"""
                <div class="alert-good">
                    Valor informado:<br><b>{dinheiro(valor)}</b>
                </div>
                """,
                unsafe_allow_html=True,
            )

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
                height=360,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#3A2A2A"),
                margin=dict(l=10, r=10, t=20, b=30),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_g2:
        st.markdown('<div class="panel-title">Despesas pagas por categoria</div>', unsafe_allow_html=True)

        if despesas_categoria.empty:
            st.markdown('<div class="empty-state">Nenhuma despesa paga no período.</div>', unsafe_allow_html=True)
        else:
            fig = px.pie(despesas_categoria, names="Categoria", values="Total", hole=0.45)
            fig.update_layout(
                height=360,
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#3A2A2A"),
                margin=dict(l=10, r=10, t=20, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-title">Resumo por categoria</div>', unsafe_allow_html=True)

    if despesas_categoria.empty:
        st.markdown('<div class="empty-state">Nenhuma despesa paga no período.</div>', unsafe_allow_html=True)
    else:
        for _, linha in despesas_categoria.head(8).iterrows():
            st.markdown(
                f"""
                <div class="panel">
                    <div class="panel-title">💸 {linha["Categoria"]}</div>
                    <div class="op-msg">
                        Total pago: <b>{dinheiro(linha["Total"])}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

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
            formas_view = formas.copy()
            formas_view["Total"] = formas_view["Total"].apply(dinheiro)

            for _, linha in formas_view.iterrows():
                st.markdown(
                    f"""
                    <div class="panel">
                        <div class="panel-title">💳 {linha["Forma"] or "Não informado"}</div>
                        <div class="op-msg">Total: <b>{linha["Total"]}</b></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with st.expander("Ver tabela de pagamentos"):
                st.dataframe(formas_view, use_container_width=True, hide_index=True)

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
            tipos_view = tipos.copy()
            tipos_view["Total"] = tipos_view["Total"].apply(dinheiro)

            for _, linha in tipos_view.iterrows():
                st.markdown(
                    f"""
                    <div class="panel">
                        <div class="panel-title">🏷️ {linha["Tipo"] or "Não informado"}</div>
                        <div class="op-msg">Total: <b>{linha["Total"]}</b></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with st.expander("Ver tabela de tipos"):
                st.dataframe(tipos_view, use_container_width=True, hide_index=True)

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
        for _, despesa in despesas.head(12).iterrows():
            renderizar_despesa_card(despesa)

        if len(despesas) > 12:
            st.info("Mostrando as 12 despesas mais recentes do período.")

        with st.expander("Ver tabela completa de despesas"):
            despesas_view = despesas.copy()
            despesas_view["Valor"] = despesas_view["Valor"].apply(dinheiro)
            despesas_view["Data"] = despesas_view["Data"].apply(formatar_data)
            st.dataframe(despesas_view, use_container_width=True, hide_index=True)