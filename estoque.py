import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

from config import DATABASE_PATH


def conectar():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def executar_sql(sql, params=()):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    conn.close()


def dinheiro(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def carregar_estoque():
    conn = conectar()
    df = pd.read_sql_query(
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
    conn.close()
    return df


def carregar_movimentos():
    conn = conectar()
    df = pd.read_sql_query(
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
    conn.close()
    return df


def ajustar_estoque(produto_id, tipo, quantidade, motivo):
    conn = conectar()
    cursor = conn.cursor()

    if tipo == "Entrada":
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
    elif tipo == "Ajuste positivo":
        cursor.execute(
            """
            UPDATE produtos
            SET estoque_atual = estoque_atual + ?
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
    conn.close()


def definir_status_estoque(row):
    if row["estoque_atual"] <= 0:
        return "SEM ESTOQUE"
    if row["estoque_atual"] <= row["estoque_minimo"]:
        return "BAIXO"
    return "OK"


def tela_estoque():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Controle operacional</div>
            <div class="hero-title">Estoque</div>
            <div class="hero-subtitle">
                Acompanhe estoque atual, produtos em alerta, itens zerados e histórico de movimentações.
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

    total_produtos = len(estoque_df)
    itens_estoque = int(estoque_df["estoque_atual"].sum())
    estoque_baixo = int((estoque_df["Status"] == "BAIXO").sum())
    sem_estoque = int((estoque_df["Status"] == "SEM ESTOQUE").sum())

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Produtos ativos</div>
            <div class="metric-value">{total_produtos}</div>
            <div class="metric-help">Produtos disponíveis no controle</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Itens em estoque</div>
            <div class="metric-value">{itens_estoque}</div>
            <div class="metric-help">Soma total de unidades</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Estoque baixo</div>
            <div class="metric-value">{estoque_baixo}</div>
            <div class="metric-help">Produtos abaixo do mínimo</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Sem estoque</div>
            <div class="metric-value">{sem_estoque}</div>
            <div class="metric-help">Produtos zerados</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">Consulta de estoque</div>', unsafe_allow_html=True)

    f1, f2, f3 = st.columns([2, 1, 1])

    with f1:
        busca = st.text_input("Buscar produto", placeholder="Nome, SKU, marca, fornecedor ou localização...")

    with f2:
        categorias = ["Todas"] + sorted([x for x in estoque_df["categoria"].dropna().unique()])
        filtro_categoria = st.selectbox("Categoria", categorias)

    with f3:
        filtro_status = st.selectbox("Status", ["Todos", "OK", "BAIXO", "SEM ESTOQUE"])

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
        ]
    ].rename(
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

    st.dataframe(tabela, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Ajuste manual de estoque</div>', unsafe_allow_html=True)

    with st.form("form_ajuste_estoque", clear_on_submit=True):
        produtos_opcoes = estoque_df["id"].astype(str) + " - " + estoque_df["nome"] + " | Estoque: " + estoque_df["estoque_atual"].astype(str)

        a1, a2, a3 = st.columns([2, 1, 1])

        with a1:
            produto_selecionado = st.selectbox("Produto", produtos_opcoes)

        with a2:
            tipo = st.selectbox("Tipo de movimento", ["Entrada", "Saída", "Perda", "Ajuste positivo", "Ajuste negativo"])

        with a3:
            quantidade = st.number_input("Quantidade", min_value=1, step=1)

        motivo = st.text_input("Motivo", placeholder="Ex: chegada de mercadoria, conferência, perda, ajuste...")

        salvar = st.form_submit_button("Registrar movimento")

        if salvar:
            produto_id = int(produto_selecionado.split(" - ")[0])
            produto_atual = estoque_df[estoque_df["id"] == produto_id].iloc[0]

            if tipo in ["Saída", "Perda", "Ajuste negativo"] and quantidade > int(produto_atual["estoque_atual"]):
                st.error("Quantidade maior que o estoque atual.")
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
        st.dataframe(movimentos, use_container_width=True, hide_index=True)