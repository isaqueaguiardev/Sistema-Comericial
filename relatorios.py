import sqlite3
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DATABASE_PATH


def conectar():
    conn = sqlite3.connect(DATABASE_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def dinheiro(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def formatar_data(data_texto):
    if not data_texto:
        return "-"
    try:
        return pd.to_datetime(data_texto).strftime("%d/%m/%Y")
    except Exception:
        return str(data_texto)


def carregar_df(query, params=()):
    conn = conectar()
    try:
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()


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


def card_info(titulo, linhas, icone="📌"):
    conteudo = "<br>".join(linhas)
    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">{icone} {titulo}</div>
            <div class="op-msg">{conteudo}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def calcular_saude_comercial(faturamento, lucro, qtd_pedidos, ticket_medio, produtos_baixo, clientes_total):
    pontos = 0
    motivos = []

    if faturamento > 0:
        pontos += 25
        motivos.append("Houve faturamento no período.")
    else:
        motivos.append("Não houve faturamento no período.")

    margem = (lucro / faturamento * 100) if faturamento else 0
    if margem >= 35:
        pontos += 25
        motivos.append("Margem de lucro forte.")
    elif margem >= 20:
        pontos += 15
        motivos.append("Margem de lucro aceitável.")
    else:
        motivos.append("Margem de lucro baixa ou inexistente.")

    if qtd_pedidos >= 20:
        pontos += 20
        motivos.append("Bom volume de pedidos.")
    elif qtd_pedidos > 0:
        pontos += 10
        motivos.append("Há pedidos, mas o volume ainda pode crescer.")
    else:
        motivos.append("Nenhum pedido no período.")

    if ticket_medio > 0:
        pontos += 10

    if produtos_baixo == 0:
        pontos += 10
        motivos.append("Estoque sem alertas críticos.")
    else:
        motivos.append(f"{produtos_baixo} produto(s) precisam de atenção no estoque.")

    if clientes_total >= 20:
        pontos += 10
        motivos.append("Base de clientes em construção consistente.")
    elif clientes_total > 0:
        pontos += 5
        motivos.append("Base de clientes iniciada.")
    else:
        motivos.append("Sem clientes cadastrados.")

    if pontos >= 80:
        status = "🟢 Saúde comercial forte"
    elif pontos >= 50:
        status = "🟡 Saúde comercial em atenção"
    else:
        status = "🔴 Saúde comercial fraca"

    return pontos, status, motivos


def tela_relatorios():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Centro de inteligência comercial</div>
            <div class="hero-title">Relatórios Inteligentes</div>
            <div class="hero-subtitle">
                Analise vendas, lucro, clientes, produtos, regiões, estoque, entregas e oportunidades em uma visão executiva.
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
    margem = (lucro / faturamento * 100) if faturamento else 0

    produtos_baixo = 0
    produtos_zerados = 0

    if not produtos.empty:
        produtos_baixo = int((produtos["estoque_atual"] <= produtos["estoque_minimo"]).sum())
        produtos_zerados = int((produtos["estoque_atual"] <= 0).sum())

    clientes_total = len(clientes)

    st.markdown('<div class="section-title">Resumo executivo</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        card_resumo("Faturamento", dinheiro(faturamento), "Total vendido")

    with c2:
        card_resumo("Lucro bruto", dinheiro(lucro), f"Margem {margem:.1f}%")

    with c3:
        card_resumo("Pedidos", qtd_pedidos, "Pedidos válidos")

    with c4:
        card_resumo("Ticket médio", dinheiro(ticket_medio), "Média por pedido")

    pontos, saude_status, motivos_saude = calcular_saude_comercial(
        faturamento,
        lucro,
        qtd_pedidos,
        ticket_medio,
        produtos_baixo,
        clientes_total,
    )

    motivos_html = "".join([f"<li>{m}</li>" for m in motivos_saude])

    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">{saude_status}</div>
            <div class="metric-value">{pontos}/100</div>
            <div class="op-msg">
                <ul>{motivos_html}</ul>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-title">Destaques do período</div>', unsafe_allow_html=True)

    d1, d2 = st.columns(2)

    produto_campeao = None
    produto_lucrativo = None
    top_cliente = None
    top_regiao = None

    if not itens.empty:
        mais_vendidos = itens.groupby("produto").agg(
            Quantidade=("quantidade", "sum"),
            Faturamento=("total_item", "sum"),
            Lucro=("lucro_item", "sum"),
        ).reset_index().sort_values("Quantidade", ascending=False)

        lucro_produtos = itens.groupby("produto").agg(
            Quantidade=("quantidade", "sum"),
            Faturamento=("total_item", "sum"),
            Lucro=("lucro_item", "sum"),
        ).reset_index().sort_values("Lucro", ascending=False)

        produto_campeao = mais_vendidos.iloc[0]
        produto_lucrativo = lucro_produtos.iloc[0]
    else:
        mais_vendidos = pd.DataFrame()
        lucro_produtos = pd.DataFrame()

    if not pedidos.empty and "cliente" in pedidos.columns:
        clientes_faturamento = pedidos.dropna(subset=["cliente"]).groupby("cliente").agg(
            Pedidos=("id", "count"),
            Total=("total", "sum"),
            Lucro=("lucro_bruto", "sum"),
        ).reset_index().sort_values("Total", ascending=False)

        if not clientes_faturamento.empty:
            top_cliente = clientes_faturamento.iloc[0]
    else:
        clientes_faturamento = pd.DataFrame()

    if not clientes.empty:
        regioes_clientes = clientes.groupby("bairro_povoado").size().reset_index(name="Clientes")
        regioes_clientes = regioes_clientes.dropna().sort_values("Clientes", ascending=False)

        if not regioes_clientes.empty:
            top_regiao = regioes_clientes.iloc[0]
    else:
        regioes_clientes = pd.DataFrame()

    with d1:
        if produto_campeao is not None:
            card_info(
                "Produto campeão",
                [
                    f"Produto: <b>{produto_campeao['produto']}</b>",
                    f"Quantidade vendida: <b>{int(produto_campeao['Quantidade'])}</b>",
                    f"Faturamento: <b>{dinheiro(produto_campeao['Faturamento'])}</b>",
                ],
                "🏆",
            )
        else:
            card_info("Produto campeão", ["Sem vendas suficientes no período."], "🏆")

    with d2:
        if produto_lucrativo is not None:
            card_info(
                "Produto mais lucrativo",
                [
                    f"Produto: <b>{produto_lucrativo['produto']}</b>",
                    f"Lucro gerado: <b>{dinheiro(produto_lucrativo['Lucro'])}</b>",
                    f"Quantidade: <b>{int(produto_lucrativo['Quantidade'])}</b>",
                ],
                "⭐",
            )
        else:
            card_info("Produto mais lucrativo", ["Sem dados de lucro no período."], "⭐")

    d3, d4 = st.columns(2)

    with d3:
        if top_cliente is not None:
            card_info(
                "Cliente de maior valor",
                [
                    f"Cliente: <b>{top_cliente['cliente']}</b>",
                    f"Total comprado: <b>{dinheiro(top_cliente['Total'])}</b>",
                    f"Pedidos: <b>{int(top_cliente['Pedidos'])}</b>",
                ],
                "👤",
            )
        else:
            card_info("Cliente de maior valor", ["Sem cliente vinculado às vendas no período."], "👤")

    with d4:
        if top_regiao is not None:
            card_info(
                "Região mais forte",
                [
                    f"Região: <b>{top_regiao['bairro_povoado']}</b>",
                    f"Clientes cadastrados: <b>{int(top_regiao['Clientes'])}</b>",
                ],
                "📍",
            )
        else:
            card_info("Região mais forte", ["Sem regiões suficientes cadastradas."], "📍")

    st.markdown('<div class="section-title">Radar de oportunidades</div>', unsafe_allow_html=True)

    oportunidades = []

    if produtos_baixo > 0:
        oportunidades.append(
            {
                "titulo": "Reabastecer estoque",
                "impacto": "Alto" if produtos_zerados > 0 else "Médio",
                "mensagem": f"{produtos_baixo} produto(s) estão com estoque baixo. {produtos_zerados} produto(s) estão zerados.",
                "icone": "⚠️",
            }
        )

    if top_regiao is not None:
        oportunidades.append(
            {
                "titulo": "Fortalecer região",
                "impacto": "Médio",
                "mensagem": f"A região {top_regiao['bairro_povoado']} concentra {int(top_regiao['Clientes'])} cliente(s). Pode valer uma ação comercial específica.",
                "icone": "📍",
            }
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
            oportunidades.append(
                {
                    "titulo": "Acompanhar entregas",
                    "impacto": "Médio",
                    "mensagem": f"Existem {pend} entrega(s) pendente(s). Isso pode impactar a experiência do cliente.",
                    "icone": "🚚",
                }
            )

    if produto_lucrativo is not None:
        oportunidades.append(
            {
                "titulo": "Explorar produto lucrativo",
                "impacto": "Alto",
                "mensagem": f"{produto_lucrativo['produto']} gerou {dinheiro(produto_lucrativo['Lucro'])} de lucro. Considere destaque, combo ou reposição.",
                "icone": "⭐",
            }
        )

    if oportunidades:
        for op in oportunidades:
            st.markdown(
                f"""
                <div class="op-card">
                    <div class="op-title">{op["icone"]} {op["titulo"]} · Impacto {op["impacto"]}</div>
                    <div class="op-msg">{op["mensagem"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="empty-state">Ainda não há dados suficientes para gerar oportunidades.</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Rankings comerciais</div>', unsafe_allow_html=True)

    r1, r2 = st.columns(2)

    with r1:
        st.markdown('<div class="panel-title">Produtos mais vendidos</div>', unsafe_allow_html=True)

        if mais_vendidos.empty:
            st.markdown('<div class="empty-state">Sem vendas no período.</div>', unsafe_allow_html=True)
        else:
            for _, linha in mais_vendidos.head(5).iterrows():
                card_info(
                    linha["produto"],
                    [
                        f"Quantidade: <b>{int(linha['Quantidade'])}</b>",
                        f"Faturamento: <b>{dinheiro(linha['Faturamento'])}</b>",
                        f"Lucro: <b>{dinheiro(linha['Lucro'])}</b>",
                    ],
                    "📦",
                )

            with st.expander("Ver gráfico de produtos vendidos"):
                fig = px.bar(mais_vendidos.head(10), x="produto", y="Quantidade")
                fig.update_layout(
                    height=360,
                    xaxis_title="Produto",
                    yaxis_title="Quantidade",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#3A2A2A"),
                    margin=dict(l=10, r=10, t=20, b=90),
                )
                st.plotly_chart(fig, use_container_width=True)

    with r2:
        st.markdown('<div class="panel-title">Ranking de lucro por produto</div>', unsafe_allow_html=True)

        if lucro_produtos.empty:
            st.markdown('<div class="empty-state">Sem dados de lucro no período.</div>', unsafe_allow_html=True)
        else:
            for _, linha in lucro_produtos.head(5).iterrows():
                card_info(
                    linha["produto"],
                    [
                        f"Lucro: <b>{dinheiro(linha['Lucro'])}</b>",
                        f"Faturamento: <b>{dinheiro(linha['Faturamento'])}</b>",
                        f"Quantidade: <b>{int(linha['Quantidade'])}</b>",
                    ],
                    "💰",
                )

            with st.expander("Ver tabela de lucro por produto"):
                tabela_lucro = lucro_produtos.copy()
                tabela_lucro["Faturamento"] = tabela_lucro["Faturamento"].apply(dinheiro)
                tabela_lucro["Lucro"] = tabela_lucro["Lucro"].apply(dinheiro)
                tabela_lucro = tabela_lucro.rename(columns={"produto": "Produto"})
                st.dataframe(tabela_lucro, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Clientes e regiões</div>', unsafe_allow_html=True)

    g1, g2 = st.columns(2)

    with g1:
        st.markdown('<div class="panel-title">Top clientes</div>', unsafe_allow_html=True)

        if clientes_faturamento.empty:
            st.markdown('<div class="empty-state">Sem clientes vinculados às vendas.</div>', unsafe_allow_html=True)
        else:
            for _, linha in clientes_faturamento.head(5).iterrows():
                card_info(
                    linha["cliente"],
                    [
                        f"Total comprado: <b>{dinheiro(linha['Total'])}</b>",
                        f"Pedidos: <b>{int(linha['Pedidos'])}</b>",
                        f"Lucro: <b>{dinheiro(linha['Lucro'])}</b>",
                    ],
                    "👤",
                )

            with st.expander("Ver tabela de clientes"):
                tabela_clientes = clientes_faturamento.copy()
                tabela_clientes["Total"] = tabela_clientes["Total"].apply(dinheiro)
                tabela_clientes["Lucro"] = tabela_clientes["Lucro"].apply(dinheiro)
                st.dataframe(tabela_clientes, use_container_width=True, hide_index=True)

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
                for _, linha in origem.head(6).iterrows():
                    card_info(
                        linha["origem"],
                        [f"Clientes: <b>{int(linha['Clientes'])}</b>"],
                        "🎯",
                    )

                with st.expander("Ver gráfico de origem"):
                    fig = px.pie(origem, names="origem", values="Clientes", hole=0.45)
                    fig.update_layout(
                        height=360,
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#3A2A2A"),
                        margin=dict(l=10, r=10, t=20, b=20),
                    )
                    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-title">Mapa de expansão</div>', unsafe_allow_html=True)

    if regioes_clientes.empty:
        st.markdown(
            '<div class="empty-state">Cadastre regiões nos clientes para gerar o mapa de expansão.</div>',
            unsafe_allow_html=True,
        )
    else:
        def potencial(row):
            if row["Clientes"] >= 20:
                return "ALTO - fortalecer presença na região"
            if row["Clientes"] >= 10:
                return "MÉDIO - observar região"
            return "BAIXO - manter relacionamento"

        mapa = regioes_clientes.copy()
        mapa["Potencial"] = mapa.apply(potencial, axis=1)
        mapa = mapa.sort_values("Clientes", ascending=False)

        for _, linha in mapa.head(8).iterrows():
            card_info(
                linha["bairro_povoado"],
                [
                    f"Clientes: <b>{int(linha['Clientes'])}</b>",
                    f"Potencial: <b>{linha['Potencial']}</b>",
                ],
                "📍",
            )

        with st.expander("Ver tabela do mapa de expansão"):
            mapa_view = mapa.rename(columns={"bairro_povoado": "Região"})
            st.dataframe(mapa_view, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Categorias e mix de produtos</div>', unsafe_allow_html=True)

    if itens.empty:
        st.markdown('<div class="empty-state">Sem vendas por categoria no período.</div>', unsafe_allow_html=True)
    else:
        categorias = itens.groupby("categoria").agg(
            Quantidade=("quantidade", "sum"),
            Faturamento=("total_item", "sum"),
            Lucro=("lucro_item", "sum"),
        ).reset_index().sort_values("Faturamento", ascending=False)

        for _, linha in categorias.head(8).iterrows():
            card_info(
                linha["categoria"] or "Sem categoria",
                [
                    f"Faturamento: <b>{dinheiro(linha['Faturamento'])}</b>",
                    f"Lucro: <b>{dinheiro(linha['Lucro'])}</b>",
                    f"Quantidade: <b>{int(linha['Quantidade'])}</b>",
                ],
                "🏷️",
            )

        with st.expander("Ver tabela de categorias"):
            categorias_view = categorias.copy()
            categorias_view["Faturamento"] = categorias_view["Faturamento"].apply(dinheiro)
            categorias_view["Lucro"] = categorias_view["Lucro"].apply(dinheiro)
            st.dataframe(categorias_view, use_container_width=True, hide_index=True)

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
                for _, produto in baixo.head(8).iterrows():
                    card_info(
                        produto["nome"],
                        [
                            f"SKU: <b>{produto['codigo_sku'] or '-'}</b>",
                            f"Estoque: <b>{int(produto['estoque_atual'])}</b>",
                            f"Mínimo: <b>{int(produto['estoque_minimo'])}</b>",
                        ],
                        "⚠️",
                    )

                with st.expander("Ver tabela de estoque baixo"):
                    baixo_view = baixo[["codigo_sku", "nome", "categoria", "estoque_atual", "estoque_minimo"]]
                    baixo_view = baixo_view.rename(
                        columns={
                            "codigo_sku": "SKU",
                            "nome": "Produto",
                            "categoria": "Categoria",
                            "estoque_atual": "Estoque",
                            "estoque_minimo": "Mínimo",
                        }
                    )
                    st.dataframe(baixo_view, use_container_width=True, hide_index=True)

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
                for _, produto in parados.head(8).iterrows():
                    card_info(
                        produto["nome"],
                        [
                            f"SKU: <b>{produto['codigo_sku'] or '-'}</b>",
                            f"Categoria: <b>{produto['categoria'] or '-'}</b>",
                            f"Estoque: <b>{int(produto['estoque_atual'])}</b>",
                        ],
                        "📦",
                    )

                with st.expander("Ver tabela de produtos parados"):
                    parados_view = parados[["codigo_sku", "nome", "categoria", "estoque_atual"]]
                    parados_view = parados_view.rename(
                        columns={
                            "codigo_sku": "SKU",
                            "nome": "Produto",
                            "categoria": "Categoria",
                            "estoque_atual": "Estoque",
                        }
                    )
                    st.dataframe(parados_view, use_container_width=True, hide_index=True)

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

            for _, linha in pagamento.head(6).iterrows():
                card_info(
                    linha["Forma"] or "Não informado",
                    [f"Total: <b>{linha['Total']}</b>"],
                    "💳",
                )

            with st.expander("Ver tabela de pagamentos"):
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

                for _, linha in entregas_bairro.head(6).iterrows():
                    card_info(
                        linha["Região"] or "Sem região",
                        [
                            f"Entregas: <b>{int(linha['Entregas'])}</b>",
                            f"Faturamento: <b>{linha['Faturamento']}</b>",
                        ],
                        "🚚",
                    )

                with st.expander("Ver tabela de entregas"):
                    st.dataframe(entregas_bairro, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Crescimento</div>', unsafe_allow_html=True)

    crescimento_clientes = clientes.copy()

    if not crescimento_clientes.empty:
        crescimento_clientes["Mes"] = pd.to_datetime(
            crescimento_clientes["criado_em"],
            errors="coerce",
        ).dt.to_period("M").astype(str)

        clientes_mes = crescimento_clientes.dropna(subset=["Mes"]).groupby("Mes").size().reset_index(
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
            height=360,
            xaxis_title="Mês",
            yaxis_title="Clientes novos",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#3A2A2A"),
            margin=dict(l=10, r=10, t=20, b=30),
        )
        st.plotly_chart(fig, use_container_width=True)