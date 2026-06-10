import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

from config import DATABASE_PATH


STATUS_PEDIDOS_GESTAO = [
    "Aberto",
    "Pago",
    "Separando",
    "Pronto para entrega",
    "Saiu para entrega",
    "Entregue",
    "Cancelado",
]


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


def carregar_pedidos(data_ini, data_fim):
    return carregar_df(
        """
        SELECT
            p.id,
            p.data_pedido,
            p.tipo_venda,
            p.forma_pagamento,
            p.status,
            p.subtotal,
            p.desconto,
            p.total,
            p.lucro_bruto,
            p.tipo_entrega,
            p.endereco_entrega,
            p.bairro_entrega,
            p.referencia_entrega,
            p.taxa_entrega,
            p.observacoes,
            c.nome AS cliente,
            c.telefone AS telefone_cliente
        FROM pedidos p
        LEFT JOIN clientes c ON c.id = p.cliente_id
        WHERE DATE(p.data_pedido) BETWEEN ? AND ?
        ORDER BY p.id DESC
        """,
        (data_ini, data_fim),
    )


def carregar_itens_pedido(pedido_id):
    return carregar_df(
        """
        SELECT
            pi.produto_id,
            pr.codigo_sku,
            pr.nome AS produto,
            pi.quantidade,
            pi.preco_unitario,
            pi.total_item,
            pi.custo_total_item,
            pi.lucro_item
        FROM pedido_itens pi
        JOIN produtos pr ON pr.id = pi.produto_id
        WHERE pi.pedido_id = ?
        ORDER BY pi.id ASC
        """,
        (pedido_id,),
    )


def atualizar_status_pedido(pedido_id, novo_status):
    executar_sql(
        """
        UPDATE pedidos
        SET status = ?
        WHERE id = ?
        """,
        (novo_status, pedido_id),
    )


def pedido_ja_cancelado(pedido_id):
    df = carregar_df("SELECT status FROM pedidos WHERE id = ?", (pedido_id,))
    if df.empty:
        return False
    return df.iloc[0]["status"] == "Cancelado"


def cancelar_pedido_com_estorno(pedido_id):
    if pedido_ja_cancelado(pedido_id):
        return False, "Este pedido já está cancelado."

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT produto_id, quantidade
        FROM pedido_itens
        WHERE pedido_id = ?
        """,
        (pedido_id,),
    )
    itens = cursor.fetchall()

    for item in itens:
        cursor.execute(
            """
            UPDATE produtos
            SET estoque_atual = estoque_atual + ?
            WHERE id = ?
            """,
            (item["quantidade"], item["produto_id"]),
        )

        cursor.execute(
            """
            INSERT INTO estoque_movimentos (
                produto_id, tipo, quantidade, motivo, data_movimento
            )
            VALUES (?, ?, ?, ?, datetime('now', 'localtime'))
            """,
            (
                item["produto_id"],
                "Devolução",
                item["quantidade"],
                f"Cancelamento do pedido #{pedido_id}",
            ),
        )

    cursor.execute(
        """
        UPDATE pedidos
        SET status = 'Cancelado'
        WHERE id = ?
        """,
        (pedido_id,),
    )

    conn.commit()
    conn.close()

    return True, "Pedido cancelado e estoque devolvido com sucesso."


def tela_pedidos():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Central operacional</div>
            <div class="hero-title">Pedidos</div>
            <div class="hero-subtitle">
                Consulte pedidos, acompanhe entregas, visualize itens, altere status e cancele pedidos com devolução automática ao estoque.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-title">Filtros</div>', unsafe_allow_html=True)

    hoje = date.today()
    inicio_mes = hoje.replace(day=1)

    f1, f2, f3, f4 = st.columns([1, 1, 1, 1])

    with f1:
        data_inicial = st.date_input("Data inicial", value=inicio_mes)

    with f2:
        data_final = st.date_input("Data final", value=hoje)

    if data_inicial > data_final:
        st.error("A data inicial não pode ser maior que a data final.")
        return

    pedidos_df = carregar_pedidos(
        data_inicial.strftime("%Y-%m-%d"),
        data_final.strftime("%Y-%m-%d"),
    )

    with f3:
        filtro_status = st.selectbox(
            "Status",
            ["Todos"] + STATUS_PEDIDOS_GESTAO,
        )

    with f4:
        filtro_entrega = st.selectbox(
            "Entrega",
            ["Todos", "Retirada", "Entrega"],
        )

    busca = st.text_input(
        "Buscar pedido",
        placeholder="Digite número do pedido, cliente, telefone ou outros...",
    )

    df = pedidos_df.copy()

    if filtro_status != "Todos":
        df = df[df["status"] == filtro_status]

    if filtro_entrega != "Todos":
        df = df[df["tipo_entrega"] == filtro_entrega]

    if busca:
        b = busca.lower()
        df = df[
            df["id"].astype(str).str.contains(b)
            | df["cliente"].fillna("").str.lower().str.contains(b)
            | df["telefone_cliente"].fillna("").str.lower().str.contains(b)
        ]

    total_pedidos = len(df)
    faturamento = df["total"].sum() if not df.empty else 0
    lucro = df["lucro_bruto"].sum() if not df.empty else 0
    entregas_pendentes = (
        df[
            (df["tipo_entrega"] == "Entrega")
            & (~df["status"].isin(["Entregue", "Cancelado"]))
        ].shape[0]
        if not df.empty
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Pedidos</div>
            <div class="metric-value">{total_pedidos}</div>
            <div class="metric-help">Dentro dos filtros</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Faturamento</div>
            <div class="metric-value">{dinheiro(faturamento)}</div>
            <div class="metric-help">Total dos pedidos</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Lucro bruto</div>
            <div class="metric-value">{dinheiro(lucro)}</div>
            <div class="metric-help">Venda menos custo</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Entregas pendentes</div>
            <div class="metric-value">{entregas_pendentes}</div>
            <div class="metric-help">Ainda não entregues</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">Lista de pedidos</div>', unsafe_allow_html=True)

    if df.empty:
        st.markdown(
            '<div class="empty-state">Nenhum pedido encontrado no período/filtro selecionado.</div>',
            unsafe_allow_html=True,
        )
        return

    tabela = df.copy()
    tabela["Cliente"] = tabela["cliente"].fillna("Consumidor final")
    tabela["Total"] = tabela["total"].apply(dinheiro)
    tabela["Lucro"] = tabela["lucro_bruto"].apply(dinheiro)
    tabela["Taxa Entrega"] = tabela["taxa_entrega"].fillna(0).apply(dinheiro)

    tabela_view = tabela[
        [
            "id",
            "data_pedido",
            "Cliente",
            "telefone_cliente",
            "tipo_venda",
            "forma_pagamento",
            "status",
            "tipo_entrega",
            "bairro_entrega",
            "Taxa Entrega",
            "Total",
            "Lucro",
        ]
    ].rename(
        columns={
            "id": "Pedido",
            "data_pedido": "Data",
            "telefone_cliente": "Telefone",
            "tipo_venda": "Tipo venda",
            "forma_pagamento": "Pagamento",
            "status": "Status",
            "tipo_entrega": "Entrega",
            "bairro_entrega": "Bairro entrega",
        }
    )

    st.dataframe(tabela_view, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Detalhes e gestão do pedido</div>', unsafe_allow_html=True)

    opcoes = df["id"].astype(str) + " - " + df["cliente"].fillna("Consumidor final") + " - " + df["total"].apply(dinheiro)
    pedido_selecionado = st.selectbox("Selecione um pedido", opcoes)

    pedido_id = int(pedido_selecionado.split(" - ")[0])
    pedido = pedidos_df[pedidos_df["id"] == pedido_id].iloc[0]
    itens = carregar_itens_pedido(pedido_id)

    d1, d2, d3 = st.columns(3)

    with d1:
        st.markdown("### Cliente")
        st.write(pedido["cliente"] if pd.notna(pedido["cliente"]) else "Consumidor final")
        st.write(pedido["telefone_cliente"] if pd.notna(pedido["telefone_cliente"]) else "-")

    with d2:
        st.markdown("### Pedido")
        st.write(f"Pedido #{pedido_id}")
        st.write(f"Status: {pedido['status']}")
        st.write(f"Pagamento: {pedido['forma_pagamento']}")

    with d3:
        st.markdown("### Valores")
        st.write(f"Total: {dinheiro(pedido['total'])}")
        st.write(f"Lucro bruto: {dinheiro(pedido['lucro_bruto'])}")
        st.write(f"Desconto: {dinheiro(pedido['desconto'])}")

    if pedido["tipo_entrega"] == "Entrega":
        st.markdown("### Dados de entrega")
        st.write(f"Endereço: {pedido['endereco_entrega']}")
        st.write(f"Bairro/Povoado: {pedido['bairro_entrega']}")
        st.write(f"Referência: {pedido['referencia_entrega']}")
        st.write(f"Taxa: {dinheiro(pedido['taxa_entrega'])}")
    else:
        st.info("Tipo de entrega: Retirada")

    st.markdown("### Itens do pedido")

    if itens.empty:
        st.warning("Nenhum item encontrado para este pedido.")
    else:
        itens_view = itens.copy()
        itens_view["Preço"] = itens_view["preco_unitario"].apply(dinheiro)
        itens_view["Total"] = itens_view["total_item"].apply(dinheiro)
        itens_view["Lucro"] = itens_view["lucro_item"].apply(dinheiro)

        itens_view = itens_view[
            ["codigo_sku", "produto", "quantidade", "Preço", "Total", "Lucro"]
        ].rename(
            columns={
                "codigo_sku": "SKU",
                "produto": "Produto",
                "quantidade": "Qtd",
            }
        )

        st.dataframe(itens_view, use_container_width=True, hide_index=True)

    st.markdown("### Alterar status")

    status_atual = pedido["status"]
    index_status = STATUS_PEDIDOS_GESTAO.index(status_atual) if status_atual in STATUS_PEDIDOS_GESTAO else 0

    novo_status = st.selectbox("Novo status", STATUS_PEDIDOS_GESTAO, index=index_status)

    a1, a2 = st.columns(2)

    with a1:
        if st.button("Salvar novo status"):
            if status_atual == "Cancelado":
                st.warning("Pedido cancelado não deve ter status alterado.")
            elif novo_status == "Cancelado":
                st.warning("Para cancelar, use o botão de cancelamento com estorno de estoque.")
            else:
                atualizar_status_pedido(pedido_id, novo_status)
                st.success("Status atualizado com sucesso.")
                st.rerun()

    with a2:
        if st.button("Cancelar pedido e devolver estoque"):
            ok, msg = cancelar_pedido_com_estorno(pedido_id)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.warning(msg)