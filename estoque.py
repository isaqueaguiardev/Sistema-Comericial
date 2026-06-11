import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

from config import DATABASE_PATH


TIPOS_MOVIMENTO = [
    "Entrada",
    "Saída",
    "Perda",
    "Ajuste positivo",
    "Ajuste negativo",
]


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


def carregar_estoque():
    conn = conectar()
    try:
        return pd.read_sql_query(
            """
            SELECT
                id,
                codigo_sku,
                nome,
                categoria,
                marca,
                fornecedor,
                localizacao,
                custo,
                preco_venda,
                preco_atacado,
                estoque_atual,
                estoque_minimo,
                ativo
            FROM produtos
            WHERE ativo = 1
            ORDER BY nome ASC
            """,
            conn,
        )
    finally:
        conn.close()


def carregar_movimentos():
    conn = conectar()
    try:
        return pd.read_sql_query(
            """
            SELECT
                em.id,
                em.data_movimento,
                p.codigo_sku,
                p.nome AS produto,
                em.tipo,
                em.quantidade,
                em.motivo
            FROM estoque_movimentos em
            JOIN produtos p ON p.id = em.produto_id
            ORDER BY em.id DESC
            LIMIT 100
            """,
            conn,
        )
    finally:
        conn.close()


def ajustar_estoque(produto_id, tipo, quantidade, motivo):
    conn = conectar()
    cursor = conn.cursor()

    try:
        if tipo in ["Entrada", "Ajuste positivo"]:
            cursor.execute(
                """
                UPDATE produtos
                SET estoque_atual = estoque_atual + ?
                WHERE id = ?
                """,
                (quantidade, produto_id),
            )

        elif tipo in ["Saída", "Perda", "Ajuste negativo"]:
            cursor.execute(
                """
                UPDATE produtos
                SET estoque_atual = estoque_atual - ?
                WHERE id = ?
                """,
                (quantidade, produto_id),
            )

        cursor.execute(
            """
            INSERT INTO estoque_movimentos (
                produto_id, tipo, quantidade, motivo, data_movimento
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                produto_id,
                tipo,
                quantidade,
                motivo,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def definir_status_estoque(row):
    if int(row["estoque_atual"]) <= 0:
        return "SEM ESTOQUE"
    if int(row["estoque_atual"]) <= int(row["estoque_minimo"]):
        return "BAIXO"
    return "OK"


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


def badge_status(status):
    if status == "SEM ESTOQUE":
        return "🔴 Sem estoque"
    if status == "BAIXO":
        return "🟡 Estoque baixo"
    return "🟢 Estoque OK"


def renderizar_produto_estoque(produto):
    valor_estoque = float(produto["custo"]) * int(produto["estoque_atual"])

    with st.container(border=True):
        st.markdown(f"### 📦 {produto['nome']}")
        st.write(f"**SKU:** {produto['codigo_sku'] or '-'}")
        st.write(f"**Categoria:** {produto['categoria'] or '-'}")
        st.write(f"**Marca:** {produto['marca'] or '-'}")
        st.write(f"**Localização:** {produto['localizacao'] or '-'}")
        st.divider()
        st.write(f"**Estoque atual:** {int(produto['estoque_atual'])}")
        st.write(f"**Estoque mínimo:** {int(produto['estoque_minimo'])}")
        st.write(f"**Custo unitário:** {dinheiro(produto['custo'])}")
        st.write(f"**Valor em estoque:** {dinheiro(valor_estoque)}")
        st.write(badge_status(produto["Status"]))


def renderizar_movimento(mov):
    tipo = mov["Tipo"]

    if tipo in ["Entrada", "Ajuste positivo"]:
        icone = "🟢"
    elif tipo in ["Saída", "Perda", "Ajuste negativo"]:
        icone = "🔴"
    else:
        icone = "⚪"

    with st.container(border=True):
        st.markdown(f"### {icone} {tipo}")
        st.write(f"**Produto:** {mov['Produto']}")
        st.write(f"**SKU:** {mov['SKU'] or '-'}")
        st.write(f"**Quantidade:** {int(mov['Quantidade'])}")
        st.write(f"**Data:** {formatar_data(mov['Data'])}")
        st.write(f"**Motivo:** {mov['Motivo'] or '-'}")


def tela_estoque():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Controle operacional</div>
            <div class="hero-title">Estoque</div>
            <div class="hero-subtitle">
                Controle produtos disponíveis, estoque baixo, itens zerados e movimentações manuais.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    estoque_df = carregar_estoque()

    if estoque_df.empty:
        st.warning("Nenhum produto ativo cadastrado ainda.")
        return

    estoque_df["Status"] = estoque_df.apply(definir_status_estoque, axis=1)
    estoque_df["valor_estoque"] = estoque_df["estoque_atual"] * estoque_df["custo"]

    total_produtos = len(estoque_df)
    itens_estoque = int(estoque_df["estoque_atual"].sum())
    estoque_baixo = int((estoque_df["Status"] == "BAIXO").sum())
    sem_estoque = int((estoque_df["Status"] == "SEM ESTOQUE").sum())
    valor_total_estoque = float(estoque_df["valor_estoque"].sum())

    st.markdown('<div class="section-title">Resumo do estoque</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        card_resumo("Produtos", total_produtos, "Ativos no controle")

    with c2:
        card_resumo("Unidades", itens_estoque, "Soma total")

    with c3:
        card_resumo("Alertas", estoque_baixo, "Estoque baixo")

    with c4:
        card_resumo("Zerados", sem_estoque, "Sem estoque")

    card_resumo("Valor em estoque", dinheiro(valor_total_estoque), "Baseado no custo cadastrado")

    if sem_estoque > 0:
        st.warning(f"Existem {sem_estoque} produto(s) sem estoque.")

    if estoque_baixo > 0:
        st.info(f"Existem {estoque_baixo} produto(s) no nível mínimo ou abaixo dele.")

    st.markdown('<div class="section-title">Consulta de estoque</div>', unsafe_allow_html=True)

    f1, f2 = st.columns([2, 1])

    with f1:
        busca = st.text_input("Buscar produto", placeholder="Nome, SKU, marca, fornecedor ou localização...")

    with f2:
        filtro_status = st.selectbox("Status", ["Todos", "OK", "BAIXO", "SEM ESTOQUE"])

    categorias = ["Todas"] + sorted([x for x in estoque_df["categoria"].dropna().unique()])
    filtro_categoria = st.selectbox("Categoria", categorias)

    df = estoque_df.copy()

    if busca:
        b = busca.lower()
        df = df[
            df["nome"].fillna("").str.lower().str.contains(b)
            | df["codigo_sku"].fillna("").str.lower().str.contains(b)
            | df["marca"].fillna("").str.lower().str.contains(b)
            | df["fornecedor"].fillna("").str.lower().str.contains(b)
            | df["localizacao"].fillna("").str.lower().str.contains(b)
        ]

    if filtro_categoria != "Todas":
        df = df[df["categoria"] == filtro_categoria]

    if filtro_status != "Todos":
        df = df[df["Status"] == filtro_status]

    if df.empty:
        st.markdown(
            '<div class="empty-state">Nenhum produto encontrado com os filtros atuais.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.success(f"{len(df)} produto(s) encontrado(s).")

        ordenado = df.copy()
        ordem_status = {"SEM ESTOQUE": 0, "BAIXO": 1, "OK": 2}
        ordenado["ordem_status"] = ordenado["Status"].map(ordem_status)
        ordenado = ordenado.sort_values(["ordem_status", "nome"])

        for _, produto in ordenado.head(15).iterrows():
            renderizar_produto_estoque(produto)

        if len(ordenado) > 15:
            st.info("Mostrando os 15 primeiros produtos. Use a busca ou filtros para refinar.")

        with st.expander("Ver tabela completa de estoque"):
            tabela = df[
                [
                    "codigo_sku",
                    "nome",
                    "categoria",
                    "marca",
                    "localizacao",
                    "estoque_atual",
                    "estoque_minimo",
                    "Status",
                    "valor_estoque",
                ]
            ].copy()

            tabela["Valor estoque"] = tabela["valor_estoque"].apply(dinheiro)

            tabela = tabela.rename(
                columns={
                    "codigo_sku": "SKU",
                    "nome": "Produto",
                    "categoria": "Categoria",
                    "marca": "Marca",
                    "localizacao": "Local",
                    "estoque_atual": "Estoque Atual",
                    "estoque_minimo": "Estoque Mínimo",
                }
            )

            tabela = tabela.drop(columns=["valor_estoque"])
            st.dataframe(tabela, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Ajuste manual de estoque</div>', unsafe_allow_html=True)

    with st.form("form_ajuste_estoque", clear_on_submit=True):
        st.info(
            "Use esta área apenas para ajustes manuais. Vendas feitas pelo PDV já baixam estoque automaticamente."
        )

        produtos_opcoes = (
            estoque_df["id"].astype(str)
            + " - "
            + estoque_df["nome"]
            + " | Estoque: "
            + estoque_df["estoque_atual"].astype(str)
        )

        produto_selecionado = st.selectbox("Produto", produtos_opcoes)

        a1, a2 = st.columns(2)

        with a1:
            tipo = st.selectbox("Tipo de movimento", TIPOS_MOVIMENTO)

        with a2:
            quantidade = st.number_input("Quantidade", min_value=1, step=1)

        motivo = st.text_input("Motivo", placeholder="Ex: chegada de mercadoria, conferência, perda, ajuste...")

        produto_id_preview = int(produto_selecionado.split(" - ")[0])
        produto_preview = estoque_df[estoque_df["id"] == produto_id_preview].iloc[0]
        estoque_atual_preview = int(produto_preview["estoque_atual"])

        if tipo in ["Entrada", "Ajuste positivo"]:
            estoque_resultante = estoque_atual_preview + int(quantidade)
        else:
            estoque_resultante = estoque_atual_preview - int(quantidade)

        st.info(
            f"Produto: {produto_preview['nome']} | "
            f"Estoque atual: {estoque_atual_preview} | "
            f"Após movimento: {estoque_resultante}"
        )

        salvar = st.form_submit_button("Registrar movimento")

        if salvar:
            produto_id = int(produto_selecionado.split(" - ")[0])
            produto_atual = estoque_df[estoque_df["id"] == produto_id].iloc[0]

            if tipo in ["Saída", "Perda", "Ajuste negativo"] and quantidade > int(produto_atual["estoque_atual"]):
                st.error("Quantidade maior que o estoque atual.")
            elif not motivo.strip():
                st.error("Informe o motivo da movimentação.")
            else:
                ajustar_estoque(produto_id, tipo, quantidade, motivo.strip())
                st.success("Movimentação registrada com sucesso.")
                st.rerun()

    st.markdown('<div class="section-title">Últimas movimentações</div>', unsafe_allow_html=True)

    movimentos = carregar_movimentos()

    if movimentos.empty:
        st.markdown(
            """
            <div class="empty-state">
                Nenhuma movimentação de estoque registrada ainda.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        movimentos = movimentos.rename(
            columns={
                "data_movimento": "Data",
                "codigo_sku": "SKU",
                "produto": "Produto",
                "tipo": "Tipo",
                "quantidade": "Quantidade",
                "motivo": "Motivo",
            }
        )

        for _, mov in movimentos.head(12).iterrows():
            renderizar_movimento(mov)

        if len(movimentos) > 12:
            st.info("Mostrando as 12 movimentações mais recentes.")

        with st.expander("Ver tabela completa de movimentações"):
            tabela_mov = movimentos.copy()
            tabela_mov["Data"] = tabela_mov["Data"].apply(formatar_data)
            st.dataframe(tabela_mov, use_container_width=True, hide_index=True)