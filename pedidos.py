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
        return pd.to_datetime(data_texto).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(data_texto)


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

    try:
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
        return True, "Pedido cancelado e estoque devolvido com sucesso."

    except Exception as e:
        conn.rollback()
        return False, f"Erro ao cancelar pedido: {e}"

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


def status_badge(status):
    if status == "Cancelado":
        return "🔴 Cancelado"
    if status == "Entregue":
        return "🟢 Entregue"
    if status == "Pago":
        return "✅ Pago"
    if status in ["Separando", "Pronto para entrega"]:
        return "🟡 " + status
    if status == "Saiu para entrega":
        return "🚚 Saiu para entrega"
    return "⚪ " + str(status)


def tipo_entrega_badge(tipo):
    if tipo == "Entrega":
        return "🚚 Entrega"
    return "🏪 Retirada"


def filtrar_pedidos(df, filtro_status, filtro_entrega, busca):
    filtrado = df.copy()

    if filtro_status != "Todos":
        filtrado = filtrado[filtrado["status"] == filtro_status]

    if filtro_entrega != "Todos":
        filtrado = filtrado[filtrado["tipo_entrega"] == filtro_entrega]

    if busca:
        b = busca.lower()
        filtrado = filtrado[
            filtrado["id"].astype(str).str.contains(b)
            | filtrado["cliente"].fillna("").str.lower().str.contains(b)
            | filtrado["telefone_cliente"].fillna("").str.lower().str.contains(b)
            | filtrado["forma_pagamento"].fillna("").str.lower().str.contains(b)
            | filtrado["status"].fillna("").str.lower().str.contains(b)
        ]

    return filtrado


def renderizar_card_pedido(pedido):
    cliente = pedido["cliente"] if pd.notna(pedido["cliente"]) else "Consumidor final"
    telefone = pedido["telefone_cliente"] if pd.notna(pedido["telefone_cliente"]) else "-"
    bairro = pedido["bairro_entrega"] if pd.notna(pedido["bairro_entrega"]) else "-"

    st.markdown(f"### 🧾 Pedido #{int(pedido['id'])}")
    st.write(f"👤 **Cliente:** {cliente}")
    st.write(f"📱 **Telefone:** {telefone}")
    st.write(f"📅 **Data:** {formatar_data(pedido['data_pedido'])}")
    st.write(f"💰 **Total:** {dinheiro(pedido['total'])}")
    st.write(f"📈 **Lucro:** {dinheiro(pedido['lucro_bruto'])}")
    st.write(f"💳 **Pagamento:** {pedido['forma_pagamento'] or '-'}")
    st.write(status_badge(pedido["status"]))
    st.write(f"{tipo_entrega_badge(pedido['tipo_entrega'])} · Região: **{bairro}**")


def renderizar_item_pedido(item):
    st.markdown(f"#### 📦 {item['produto']}")
    st.write(f"SKU: **{item['codigo_sku'] or '-'}**")
    st.write(f"Quantidade: **{int(item['quantidade'])}**")
    st.write(f"Preço unitário: **{dinheiro(item['preco_unitario'])}**")
    st.write(f"Total: **{dinheiro(item['total_item'])}**")
    st.write(f"Lucro: **{dinheiro(item['lucro_item'])}**")
    st.divider()


def tela_pedidos():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Central operacional</div>
            <div class="hero-title">Pedidos</div>
            <div class="hero-subtitle">
                Acompanhe vendas, entregas, status, itens e cancelamentos com devolução automática ao estoque.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    hoje = date.today()
    inicio_mes = hoje.replace(day=1)

    st.markdown('<div class="section-title">Filtros</div>', unsafe_allow_html=True)

    f1, f2 = st.columns(2)

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

    f3, f4 = st.columns(2)

    with f3:
        filtro_status = st.selectbox("Status", ["Todos"] + STATUS_PEDIDOS_GESTAO)

    with f4:
        filtro_entrega = st.selectbox("Entrega", ["Todos", "Retirada", "Entrega"])

    busca = st.text_input(
        "Buscar pedido",
        placeholder="Pedido, cliente, telefone, pagamento ou status...",
    )

    df = filtrar_pedidos(pedidos_df, filtro_status, filtro_entrega, busca)

    total_pedidos = len(df)
    faturamento = df["total"].sum() if not df.empty else 0
    lucro = df["lucro_bruto"].sum() if not df.empty else 0
    ticket_medio = faturamento / total_pedidos if total_pedidos else 0
    maior_venda = df["total"].max() if not df.empty else 0

    entregas_pendentes = (
        df[
            (df["tipo_entrega"] == "Entrega")
            & (~df["status"].isin(["Entregue", "Cancelado"]))
        ].shape[0]
        if not df.empty
        else 0
    )

    pedidos_cancelados = int((df["status"] == "Cancelado").sum()) if not df.empty else 0

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        card_resumo("Pedidos", total_pedidos, "Dentro dos filtros")

    with c2:
        card_resumo("Faturamento", dinheiro(faturamento), "Total vendido")

    with c3:
        card_resumo("Ticket médio", dinheiro(ticket_medio), "Média por pedido")

    with c4:
        card_resumo("Entregas", entregas_pendentes, "Pendentes")

    c5, c6 = st.columns(2)

    with c5:
        card_resumo("Maior venda", dinheiro(maior_venda), "Maior pedido filtrado")

    with c6:
        card_resumo("Cancelados", pedidos_cancelados, "Pedidos cancelados")

    st.markdown('<div class="section-title">Lista de pedidos</div>', unsafe_allow_html=True)

    if df.empty:
        st.markdown(
            '<div class="empty-state">Nenhum pedido encontrado no período/filtro selecionado.</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"""
        <div class="alert-good">
            {len(df)} pedido(s) encontrado(s). Toque em um pedido para ver detalhes e ações.
        </div>
        """,
        unsafe_allow_html=True,
    )

    for _, pedido in df.head(15).iterrows():
        cliente_nome = pedido["cliente"] if pd.notna(pedido["cliente"]) else "Consumidor final"
        titulo_expander = (
            f"Pedido #{int(pedido['id'])} · {cliente_nome} · "
            f"{dinheiro(pedido['total'])} · {pedido['status']}"
        )

        with st.expander(titulo_expander):
            renderizar_card_pedido(pedido)

            itens = carregar_itens_pedido(int(pedido["id"]))

            st.markdown("### Itens do pedido")

            if itens.empty:
                st.warning("Nenhum item encontrado para este pedido.")
            else:
                for _, item in itens.iterrows():
                    renderizar_item_pedido(item)

            if pedido["tipo_entrega"] == "Entrega":
                st.markdown("### 🚚 Dados de entrega")
                st.write(f"**Endereço:** {pedido['endereco_entrega'] or '-'}")
                st.write(f"**Bairro/Região:** {pedido['bairro_entrega'] or '-'}")
                st.write(f"**Referência:** {pedido['referencia_entrega'] or '-'}")
                st.write(f"**Taxa:** {dinheiro(pedido['taxa_entrega'])}")
            else:
                st.info("Tipo de entrega: Retirada")

            st.markdown("### Gestão do pedido")

            status_atual = pedido["status"]
            index_status = (
                STATUS_PEDIDOS_GESTAO.index(status_atual)
                if status_atual in STATUS_PEDIDOS_GESTAO
                else 0
            )

            novo_status = st.selectbox(
                "Novo status",
                STATUS_PEDIDOS_GESTAO,
                index=index_status,
                key=f"novo_status_{int(pedido['id'])}",
            )

            a1, a2 = st.columns(2)

            with a1:
                salvar_status = st.button(
                    "Salvar status",
                    key=f"salvar_status_{int(pedido['id'])}",
                )

            with a2:
                cancelar = st.button(
                    "Cancelar e devolver estoque",
                    key=f"cancelar_pedido_{int(pedido['id'])}",
                )

            if salvar_status:
                if status_atual == "Cancelado":
                    st.warning("Pedido cancelado não deve ter status alterado.")
                elif novo_status == "Cancelado":
                    st.warning("Para cancelar, use o botão de cancelamento com estorno de estoque.")
                else:
                    atualizar_status_pedido(int(pedido["id"]), novo_status)
                    st.success("Status atualizado com sucesso.")
                    st.rerun()

            if cancelar:
                ok, msg = cancelar_pedido_com_estorno(int(pedido["id"]))
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.warning(msg)

    if len(df) > 15:
        st.info("Mostrando os 15 pedidos mais recentes dentro do filtro. Use a busca para localizar pedidos antigos.")

    with st.expander("Ver tabela completa"):
        tabela = df.copy()
        tabela["Cliente"] = tabela["cliente"].fillna("Consumidor final")
        tabela["Total"] = tabela["total"].apply(dinheiro)
        tabela["Lucro"] = tabela["lucro_bruto"].apply(dinheiro)
        tabela["Taxa Entrega"] = tabela["taxa_entrega"].fillna(0).apply(dinheiro)
        tabela["Data"] = tabela["data_pedido"].apply(formatar_data)

        tabela_view = tabela[
            [
                "id",
                "Data",
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
                "telefone_cliente": "Telefone",
                "tipo_venda": "Tipo venda",
                "forma_pagamento": "Pagamento",
                "status": "Status",
                "tipo_entrega": "Entrega",
                "bairro_entrega": "Bairro entrega",
            }
        )

        st.dataframe(tabela_view, use_container_width=True, hide_index=True)