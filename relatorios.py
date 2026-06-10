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


def tela_relatorios():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Centro de inteligência comercial</div>
            <div class="hero-title">Relatórios Inteligentes</div>
            <div class="hero-subtitle">
                Analise vendas, lucro, clientes, regiões, produtos, estoque,
                entregas e oportunidades de crescimento em um único painel.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    hoje = date.today()
    inicio_mes = hoje.replace(day=1)

    st.markdown('<div class="section-title">Período de análise</div>', unsafe_allow_html=True)

    p1, p2 = st.columns(2)

    with p1:
        data_inicial = st.date_input("Data inicial", value=inicio_mes, key="rel_data_ini")

    with p2:
        data_final = st.date_input("Data final", value=hoje, key="rel_data_fim")

    if data_inicial > data_final:
        st.error("A data inicial não pode ser maior que a data final.")
        return

    data_ini = data_inicial.strftime("%Y-%m-%d")
    data_fim = data_final.strftime("%Y-%m-%d")

    pedidos = carregar_df(
        """
        SELECT
            p.id,
            DATE(p.data_pedido) AS data,
            p.tipo_venda,
            p.forma_pagamento,
            p.status,
            p.total,
            p.custo_total,
            p.lucro_bruto,
            p.tipo_entrega,
            p.bairro_entrega,
            p.taxa_entrega,
            c.id AS cliente_id,
            c.nome AS cliente,
            c.cidade AS cidade_cliente,
            COALESCE(c.bairro_povoado, c.bairro) AS bairro_cliente,
            c.origem,
            c.vip
        FROM pedidos p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        WHERE DATE(p.data_pedido) BETWEEN ? AND ?
        AND p.status != 'Cancelado'
        """,
        (data_ini, data_fim),
    )

    itens = carregar_df(
        """
        SELECT
            pi.pedido_id,
            pr.id AS produto_id,
            pr.nome AS produto,
            pr.categoria,
            pr.marca,
            pr.codigo_sku,
            pi.quantidade,
            pi.total_item,
            pi.custo_total_item,
            pi.lucro_item
        FROM pedido_itens pi
        JOIN produtos pr ON pr.id = pi.produto_id
        JOIN pedidos p ON p.id = pi.pedido_id
        WHERE DATE(p.data_pedido) BETWEEN ? AND ?
        AND p.status != 'Cancelado'
        """,
        (data_ini, data_fim),
    )

    clientes = carregar_df(
        """
        SELECT
            c.id,
            c.nome,
            c.telefone,
            c.cidade,
            COALESCE(c.bairro_povoado, c.bairro) AS bairro_povoado,
            c.origem,
            c.vip,
            c.criado_em
        FROM clientes c
        """,
    )

    produtos = carregar_df(
        """
        SELECT
            id,
            nome,
            categoria,
            marca,
            codigo_sku,
            estoque_atual,
            estoque_minimo,
            custo,
            preco_venda,
            preco_atacado,
            ativo
        FROM produtos
        WHERE ativo = 1
        """,
    )

    faturamento = pedidos["total"].sum() if not pedidos.empty else 0
    lucro = pedidos["lucro_bruto"].sum() if not pedidos.empty else 0
    qtd_pedidos = len(pedidos)
    ticket_medio = faturamento / qtd_pedidos if qtd_pedidos else 0

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Faturamento</div>
            <div class="metric-value">{dinheiro(faturamento)}</div>
            <div class="metric-help">Total vendido no período</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Lucro bruto</div>
            <div class="metric-value">{dinheiro(lucro)}</div>
            <div class="metric-help">Venda menos custo</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Pedidos</div>
            <div class="metric-value">{qtd_pedidos}</div>
            <div class="metric-help">Pedidos no período</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Ticket médio</div>
            <div class="metric-value">{dinheiro(ticket_medio)}</div>
            <div class="metric-help">Média por pedido</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">Radar de oportunidades</div>', unsafe_allow_html=True)

    oportunidades = []

    if not produtos.empty:
        baixos = produtos[produtos["estoque_atual"] <= produtos["estoque_minimo"]]
        zerados = produtos[produtos["estoque_atual"] <= 0]

        if len(baixos) > 0:
            oportunidades.append(f"⚠️ {len(baixos)} produto(s) com estoque baixo.")

        if len(zerados) > 0:
            oportunidades.append(f"🚨 {len(zerados)} produto(s) sem estoque.")

    if not clientes.empty:
        bairros_clientes = clientes.groupby("bairro_povoado").size().reset_index(name="Clientes")
        bairros_clientes = bairros_clientes.dropna()

        if not bairros_clientes.empty:
            top_bairro = bairros_clientes.sort_values("Clientes", ascending=False).iloc[0]
            oportunidades.append(
                f"📍 Região com mais clientes: {top_bairro['bairro_povoado']} "
                f"({top_bairro['Clientes']} clientes)."
            )

    if not pedidos.empty:
        entregas_pendentes = carregar_df(
            """
            SELECT COUNT(*) AS total
            FROM pedidos
            WHERE tipo_entrega = 'Entrega'
            AND status NOT IN ('Entregue', 'Cancelado')
            """
        )
        pend = int(entregas_pendentes.iloc[0]["total"]) if not entregas_pendentes.empty else 0

        if pend > 0:
            oportunidades.append(f"🚚 {pend} entrega(s) pendente(s).")

    if not itens.empty:
        lucro_produto = itens.groupby("produto")["lucro_item"].sum().reset_index()

        if not lucro_produto.empty:
            melhor_lucro = lucro_produto.sort_values("lucro_item", ascending=False).iloc[0]
            oportunidades.append(
                f"⭐ Produto com maior lucro no período: "
                f"{melhor_lucro['produto']} ({dinheiro(melhor_lucro['lucro_item'])})."
            )

    if oportunidades:
        for op in oportunidades:
            st.markdown(f'<div class="alert-good">{op}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="empty-state">Ainda não há dados suficientes para gerar oportunidades.</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Relatórios comerciais</div>', unsafe_allow_html=True)

    r1, r2 = st.columns(2)

    with r1:
        st.markdown('<div class="panel-title">Produtos mais vendidos</div>', unsafe_allow_html=True)

        if itens.empty:
            st.markdown('<div class="empty-state">Sem vendas no período.</div>', unsafe_allow_html=True)
        else:
            mais_vendidos = itens.groupby("produto").agg(
                Quantidade=("quantidade", "sum"),
                Faturamento=("total_item", "sum"),
                Lucro=("lucro_item", "sum"),
            ).reset_index().sort_values("Quantidade", ascending=False).head(10)

            fig = px.bar(mais_vendidos, x="produto", y="Quantidade")
            fig.update_layout(
                xaxis_title="Produto",
                yaxis_title="Quantidade",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#3A2A2A"),
            )
            st.plotly_chart(fig, use_container_width=True)

    with r2:
        st.markdown('<div class="panel-title">Ranking de lucro por produto</div>', unsafe_allow_html=True)

        if itens.empty:
            st.markdown('<div class="empty-state">Sem dados de lucro no período.</div>', unsafe_allow_html=True)
        else:
            lucro_produtos = itens.groupby("produto").agg(
                Quantidade=("quantidade", "sum"),
                Faturamento=("total_item", "sum"),
                Lucro=("lucro_item", "sum"),
            ).reset_index().sort_values("Lucro", ascending=False).head(10)

            tabela_lucro = lucro_produtos.copy()
            tabela_lucro["Faturamento"] = tabela_lucro["Faturamento"].apply(dinheiro)
            tabela_lucro["Lucro"] = tabela_lucro["Lucro"].apply(dinheiro)
            tabela_lucro = tabela_lucro.rename(columns={"produto": "Produto"})

            st.dataframe(tabela_lucro, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Relatórios de clientes e regiões</div>', unsafe_allow_html=True)

    g1, g2 = st.columns(2)

    with g1:
        st.markdown('<div class="panel-title">Clientes por região</div>', unsafe_allow_html=True)

        if clientes.empty:
            st.markdown('<div class="empty-state">Nenhum cliente cadastrado.</div>', unsafe_allow_html=True)
        else:
            clientes_bairro = clientes.groupby("bairro_povoado").size().reset_index(name="Clientes")
            clientes_bairro = clientes_bairro.dropna().sort_values("Clientes", ascending=False)

            if clientes_bairro.empty:
                st.markdown('<div class="empty-state">Sem região cadastrada.</div>', unsafe_allow_html=True)
            else:
                fig = px.bar(clientes_bairro.head(15), x="bairro_povoado", y="Clientes")
                fig.update_layout(
                    xaxis_title="Região",
                    yaxis_title="Clientes",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#3A2A2A"),
                )
                st.plotly_chart(fig, use_container_width=True)

    with g2:
        st.markdown('<div class="panel-title">Clientes por origem</div>', unsafe_allow_html=True)

        if clientes.empty:
            st.markdown('<div class="empty-state">Nenhum cliente cadastrado.</div>', unsafe_allow_html=True)
        else:
            origem = clientes.groupby("origem").size().reset_index(name="Clientes")
            origem = origem.dropna().sort_values("Clientes", ascending=False)

            if origem.empty:
                st.markdown('<div class="empty-state">Sem origem cadastrada.</div>', unsafe_allow_html=True)
            else:
                fig = px.pie(origem, names="origem", values="Clientes", hole=0.45)
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#3A2A2A"),
                )
                st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-title">Mapa de expansão</div>', unsafe_allow_html=True)

    if clientes.empty:
        st.markdown(
            '<div class="empty-state">Cadastre clientes para gerar o mapa de expansão.</div>',
            unsafe_allow_html=True,
        )
    else:
        clientes_regiao = clientes.groupby("bairro_povoado").size().reset_index(name="Clientes")
        clientes_regiao = clientes_regiao.dropna()

        if clientes_regiao.empty:
            st.markdown(
                '<div class="empty-state">Sem regiões suficientes para análise.</div>',
                unsafe_allow_html=True,
            )
        else:
            def potencial(row):
                if row["Clientes"] >= 20:
                    return "ALTO - fortalecer presença na região"
                if row["Clientes"] >= 10:
                    return "MÉDIO - observar região"
                return "BAIXO"

            mapa = clientes_regiao.copy()
            mapa["Potencial"] = mapa.apply(potencial, axis=1)
            mapa = mapa.sort_values("Clientes", ascending=False)
            mapa = mapa.rename(columns={"bairro_povoado": "Região"})

            st.dataframe(mapa, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Estoque e produtos parados</div>', unsafe_allow_html=True)

    e1, e2 = st.columns(2)

    with e1:
        st.markdown('<div class="panel-title">Estoque baixo</div>', unsafe_allow_html=True)

        if produtos.empty:
            st.markdown('<div class="empty-state">Nenhum produto cadastrado.</div>', unsafe_allow_html=True)
        else:
            baixo = produtos[produtos["estoque_atual"] <= produtos["estoque_minimo"]].copy()

            if baixo.empty:
                st.markdown('<div class="alert-good">✅ Nenhum produto com estoque baixo.</div>', unsafe_allow_html=True)
            else:
                baixo = baixo[["codigo_sku", "nome", "categoria", "estoque_atual", "estoque_minimo"]]
                baixo = baixo.rename(
                    columns={
                        "codigo_sku": "SKU",
                        "nome": "Produto",
                        "categoria": "Categoria",
                        "estoque_atual": "Estoque",
                        "estoque_minimo": "Mínimo",
                    }
                )
                st.dataframe(baixo, use_container_width=True, hide_index=True)

    with e2:
        st.markdown('<div class="panel-title">Produtos sem venda no período</div>', unsafe_allow_html=True)

        if produtos.empty:
            st.markdown('<div class="empty-state">Nenhum produto cadastrado.</div>', unsafe_allow_html=True)
        else:
            vendidos_ids = itens["produto_id"].unique() if not itens.empty else []
            parados = produtos[~produtos["id"].isin(vendidos_ids)].copy()

            if parados.empty:
                st.markdown(
                    '<div class="alert-good">✅ Todos os produtos tiveram venda no período.</div>',
                    unsafe_allow_html=True,
                )
            else:
                parados = parados[["codigo_sku", "nome", "categoria", "estoque_atual"]]
                parados = parados.rename(
                    columns={
                        "codigo_sku": "SKU",
                        "nome": "Produto",
                        "categoria": "Categoria",
                        "estoque_atual": "Estoque",
                    }
                )
                st.dataframe(parados, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Vendas e entregas</div>', unsafe_allow_html=True)

    v1, v2 = st.columns(2)

    with v1:
        st.markdown('<div class="panel-title">Vendas por forma de pagamento</div>', unsafe_allow_html=True)

        if pedidos.empty:
            st.markdown('<div class="empty-state">Sem pedidos no período.</div>', unsafe_allow_html=True)
        else:
            pagamento = pedidos.groupby("forma_pagamento")["total"].sum().reset_index()
            pagamento = pagamento.sort_values("total", ascending=False)
            pagamento["Total"] = pagamento["total"].apply(dinheiro)
            pagamento = pagamento.rename(columns={"forma_pagamento": "Forma"})

            st.dataframe(pagamento[["Forma", "Total"]], use_container_width=True, hide_index=True)

    with v2:
        st.markdown('<div class="panel-title">Entregas por região</div>', unsafe_allow_html=True)

        if pedidos.empty:
            st.markdown('<div class="empty-state">Sem entregas no período.</div>', unsafe_allow_html=True)
        else:
            entregas = pedidos[pedidos["tipo_entrega"] == "Entrega"].copy()

            if entregas.empty:
                st.markdown('<div class="empty-state">Nenhuma entrega no período.</div>', unsafe_allow_html=True)
            else:
                entregas_bairro = entregas.groupby("bairro_entrega").agg(
                    Entregas=("id", "count"),
                    Faturamento=("total", "sum"),
                ).reset_index().sort_values("Entregas", ascending=False)

                entregas_bairro["Faturamento"] = entregas_bairro["Faturamento"].apply(dinheiro)
                entregas_bairro = entregas_bairro.rename(columns={"bairro_entrega": "Região"})

                st.dataframe(entregas_bairro, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Crescimento</div>', unsafe_allow_html=True)

    crescimento_clientes = clientes.copy()

    if not crescimento_clientes.empty:
        crescimento_clientes["Mes"] = pd.to_datetime(
            crescimento_clientes["criado_em"]
        ).dt.to_period("M").astype(str)

        clientes_mes = crescimento_clientes.groupby("Mes").size().reset_index(
            name="Clientes novos"
        )
    else:
        clientes_mes = pd.DataFrame()

    if clientes_mes.empty:
        st.markdown(
            '<div class="empty-state">Sem dados suficientes para crescimento de clientes.</div>',
            unsafe_allow_html=True,
        )
    else:
        fig = px.line(clientes_mes, x="Mes", y="Clientes novos", markers=True)
        fig.update_layout(
            xaxis_title="Mês",
            yaxis_title="Clientes novos",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#3A2A2A"),
        )
        st.plotly_chart(fig, use_container_width=True)