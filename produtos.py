import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

from config import DATABASE_PATH, CATEGORIAS_PRODUTO


def conectar():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dinheiro(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def executar_sql(sql, params=()):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    conn.close()


def carregar_produtos():
    conn = conectar()
    df = pd.read_sql_query(
        """
        SELECT
            id,
            nome,
            categoria,
            codigo_sku,
            marca,
            fornecedor,
            localizacao,
            custo,
            preco_venda,
            preco_atacado,
            estoque_atual,
            estoque_minimo,
            ativo,
            criado_em
        FROM produtos
        ORDER BY id DESC
        """,
        conn,
    )
    conn.close()
    return df


def gerar_sku_automatico():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(id) FROM produtos")
    ultimo_id = cursor.fetchone()[0]
    conn.close()

    proximo_id = 1 if ultimo_id is None else int(ultimo_id) + 1
    return f"AB{proximo_id:05d}"


def calcular_margem(preco, custo):
    if preco <= 0:
        return 0
    return ((preco - custo) / preco) * 100


def cadastrar_produto(
    nome,
    categoria,
    codigo_sku,
    marca,
    fornecedor,
    localizacao,
    custo,
    preco_venda,
    preco_atacado,
    estoque_atual,
    estoque_minimo,
):
    executar_sql(
        """
        INSERT INTO produtos (
            nome,
            categoria,
            codigo_sku,
            marca,
            fornecedor,
            localizacao,
            custo,
            preco_venda,
            preco_atacado,
            estoque_atual,
            estoque_minimo,
            ativo,
            criado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            nome,
            categoria,
            codigo_sku,
            marca,
            fornecedor,
            localizacao,
            custo,
            preco_venda,
            preco_atacado,
            estoque_atual,
            estoque_minimo,
            1,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )


def atualizar_produto(
    produto_id,
    nome,
    categoria,
    codigo_sku,
    marca,
    fornecedor,
    localizacao,
    custo,
    preco_venda,
    preco_atacado,
    estoque_atual,
    estoque_minimo,
    ativo,
):
    executar_sql(
        """
        UPDATE produtos
        SET
            nome = ?,
            categoria = ?,
            codigo_sku = ?,
            marca = ?,
            fornecedor = ?,
            localizacao = ?,
            custo = ?,
            preco_venda = ?,
            preco_atacado = ?,
            estoque_atual = ?,
            estoque_minimo = ?,
            ativo = ?
        WHERE id = ?
        """,
        (
            nome,
            categoria,
            codigo_sku,
            marca,
            fornecedor,
            localizacao,
            custo,
            preco_venda,
            preco_atacado,
            estoque_atual,
            estoque_minimo,
            ativo,
            produto_id,
        ),
    )


def tela_produtos():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Catálogo Airesbella</div>
            <div class="hero-title">Produtos</div>
            <div class="hero-subtitle">
                Cadastro simples para operação real: produto, preço, estoque, marca, fornecedor e localização.
                O SKU e a data são gerados automaticamente pelo sistema.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    produtos_df = carregar_produtos()

    total_produtos = len(produtos_df)
    produtos_ativos = int(produtos_df["ativo"].sum()) if not produtos_df.empty else 0
    estoque_total = int(produtos_df["estoque_atual"].sum()) if not produtos_df.empty else 0

    estoque_baixo = 0
    if not produtos_df.empty:
        estoque_baixo = int(
            produtos_df[
                (produtos_df["ativo"] == 1)
                & (produtos_df["estoque_atual"] <= produtos_df["estoque_minimo"])
            ].shape[0]
        )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Produtos cadastrados</div>
                <div class="metric-value">{total_produtos}</div>
                <div class="metric-help">Total geral no sistema</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Produtos ativos</div>
                <div class="metric-value">{produtos_ativos}</div>
                <div class="metric-help">Disponíveis para venda</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Itens em estoque</div>
                <div class="metric-value">{estoque_total}</div>
                <div class="metric-help">Soma de todas as unidades</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Estoque baixo</div>
                <div class="metric-value">{estoque_baixo}</div>
                <div class="metric-help">Produtos em alerta</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">Cadastrar novo produto</div>', unsafe_allow_html=True)

    sku_sugerido = gerar_sku_automatico()

    with st.form("form_cadastrar_produto", clear_on_submit=True):
        st.info(f"SKU automático sugerido: {sku_sugerido}")

        c1, c2 = st.columns([2, 1])

        with c1:
            nome = st.text_input("Nome do produto *", placeholder="Ex: Gloss Morango Vivai")

        with c2:
            categoria = st.selectbox("Categoria", CATEGORIAS_PRODUTO)

        c3, c4, c5 = st.columns(3)

        with c3:
            marca = st.text_input("Marca", placeholder="Ex: Vivai, Ruby Rose, Wepink")

        with c4:
            fornecedor = st.text_input("Fornecedor", placeholder="Ex: SatisMake, SP Atacado")

        with c5:
            localizacao = st.text_input("Localização na loja", placeholder="Ex: Expositor A, Cesto 1")

        c6, c7, c8 = st.columns(3)

        with c6:
            custo = st.number_input("Custo unitário", min_value=0.0, step=0.5, format="%.2f")

        with c7:
            preco_venda = st.number_input("Preço de venda", min_value=0.0, step=0.5, format="%.2f")

        with c8:
            preco_atacado = st.number_input("Preço atacado", min_value=0.0, step=0.5, format="%.2f")

        c9, c10, c11, c12 = st.columns(4)

        with c9:
            estoque_atual = st.number_input("Quantidade em estoque", min_value=0, step=1)

        with c10:
            estoque_minimo = st.number_input("Estoque mínimo", min_value=0, step=1)

        with c11:
            margem_loja = calcular_margem(preco_venda, custo)
            st.metric("Margem loja", f"{margem_loja:.1f}%")

        with c12:
            margem_atacado = calcular_margem(preco_atacado, custo)
            st.metric("Margem atacado", f"{margem_atacado:.1f}%")

        salvar = st.form_submit_button("Salvar produto")

        if salvar:
            if not nome.strip():
                st.error("Informe o nome do produto.")
            elif preco_venda < custo:
                st.error("O preço de venda está menor que o custo.")
            elif preco_atacado < custo:
                st.warning("Atenção: preço consultora está menor que o custo.")
                cadastrar_produto(
                    nome.strip(),
                    categoria,
                    sku_sugerido,
                    marca.strip(),
                    fornecedor.strip(),
                    localizacao.strip(),
                    custo,
                    preco_venda,
                    preco_atacado,
                    estoque_atual,
                    estoque_minimo,
                )
                st.success("Produto cadastrado com aviso de margem.")
                st.rerun()
            else:
                try:
                    cadastrar_produto(
                        nome.strip(),
                        categoria,
                        sku_sugerido,
                        marca.strip(),
                        fornecedor.strip(),
                        localizacao.strip(),
                        custo,
                        preco_venda,
                        preco_atacado,
                        estoque_atual,
                        estoque_minimo,
                    )
                    st.success("Produto cadastrado com sucesso.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Erro: SKU já existente. Atualize a página e tente novamente.")
                except Exception as e:
                    st.error(f"Erro ao cadastrar produto: {e}")

    st.markdown('<div class="section-title">Consultar produtos</div>', unsafe_allow_html=True)

    produtos_df = carregar_produtos()

    if produtos_df.empty:
        st.markdown(
            """
            <div class="empty-state">
                Nenhum produto cadastrado ainda. Cadastre o primeiro produto acima.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    f1, f2, f3 = st.columns([2, 1, 1])

    with f1:
        busca = st.text_input("Buscar produto", placeholder="Digite nome, SKU, marca ou fornecedor...")

    with f2:
        categorias = ["Todas"] + sorted([x for x in produtos_df["categoria"].dropna().unique()])
        filtro_categoria = st.selectbox("Categoria", categorias)

    with f3:
        filtro_status = st.selectbox("Status", ["Todos", "Ativos", "Inativos", "Estoque baixo"])

    df = produtos_df.copy()

    if busca:
        busca_lower = busca.lower()
        df = df[
            df["nome"].str.lower().str.contains(busca_lower, na=False)
            | df["codigo_sku"].fillna("").str.lower().str.contains(busca_lower, na=False)
            | df["marca"].fillna("").str.lower().str.contains(busca_lower, na=False)
            | df["fornecedor"].fillna("").str.lower().str.contains(busca_lower, na=False)
        ]

    if filtro_categoria != "Todas":
        df = df[df["categoria"] == filtro_categoria]

    if filtro_status == "Ativos":
        df = df[df["ativo"] == 1]
    elif filtro_status == "Inativos":
        df = df[df["ativo"] == 0]
    elif filtro_status == "Estoque baixo":
        df = df[(df["ativo"] == 1) & (df["estoque_atual"] <= df["estoque_minimo"])]

    df["Margem Loja"] = df.apply(lambda x: f"{calcular_margem(x['preco_venda'], x['custo']):.1f}%", axis=1)
    df["Margem Consultora"] = df.apply(
        lambda x: f"{calcular_margem(x['preco_atacado'], x['custo']):.1f}%", axis=1
    )
    df["Custo"] = df["custo"].apply(dinheiro)
    df["Preço Venda"] = df["preco_venda"].apply(dinheiro)
    df["Preço Consultora"] = df["preco_atacado"].apply(dinheiro)
    df["Status"] = df["ativo"].apply(lambda x: "Ativo" if x == 1 else "Inativo")
    df["Alerta"] = df.apply(
        lambda x: "⚠️ Baixo" if x["ativo"] == 1 and x["estoque_atual"] <= x["estoque_minimo"] else "OK",
        axis=1,
    )

    tabela = df[
        [
            "id",
            "codigo_sku",
            "nome",
            "categoria",
            "marca",
            "fornecedor",
            "localizacao",
            "Custo",
            "Preço Venda",
            "Preço Consultora",
            "Margem Loja",
            "Margem Consultora",
            "estoque_atual",
            "estoque_minimo",
            "Status",
            "Alerta",
        ]
    ].rename(
        columns={
            "id": "ID",
            "codigo_sku": "SKU",
            "nome": "Produto",
            "categoria": "Categoria",
            "marca": "Marca",
            "fornecedor": "Fornecedor",
            "localizacao": "Local",
            "estoque_atual": "Estoque",
            "estoque_minimo": "Mínimo",
        }
    )

    st.dataframe(tabela, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Editar produto</div>', unsafe_allow_html=True)

    produtos_opcoes = produtos_df["id"].astype(str) + " - " + produtos_df["nome"]
    selecionado = st.selectbox("Selecione um produto", produtos_opcoes)

    produto_id = int(selecionado.split(" - ")[0])
    produto = produtos_df[produtos_df["id"] == produto_id].iloc[0]

    with st.form("form_editar_produto"):
        e1, e2 = st.columns([2, 1])

        with e1:
            nome_edit = st.text_input("Nome", value=produto["nome"])

        with e2:
            sku_edit = st.text_input("SKU", value=produto["codigo_sku"] or "", disabled=True)

        e3, e4, e5 = st.columns(3)

        with e3:
            categoria_edit = st.selectbox(
                "Categoria",
                CATEGORIAS_PRODUTO,
                index=CATEGORIAS_PRODUTO.index(produto["categoria"])
                if produto["categoria"] in CATEGORIAS_PRODUTO
                else 0,
            )

        with e4:
            marca_edit = st.text_input("Marca", value=produto["marca"] or "")

        with e5:
            fornecedor_edit = st.text_input("Fornecedor", value=produto["fornecedor"] or "")

        e6, e7, e8 = st.columns(3)

        with e6:
            localizacao_edit = st.text_input("Localização", value=produto["localizacao"] or "")

        with e7:
            status_edit = st.selectbox(
                "Status",
                ["Ativo", "Inativo"],
                index=0 if int(produto["ativo"]) == 1 else 1,
            )

        with e8:
            estoque_minimo_edit = st.number_input(
                "Estoque mínimo",
                min_value=0,
                step=1,
                value=int(produto["estoque_minimo"]),
            )

        e9, e10, e11, e12 = st.columns(4)

        with e9:
            custo_edit = st.number_input(
                "Custo",
                min_value=0.0,
                step=0.5,
                value=float(produto["custo"]),
                format="%.2f",
            )

        with e10:
            preco_venda_edit = st.number_input(
                "Preço venda",
                min_value=0.0,
                step=0.5,
                value=float(produto["preco_venda"]),
                format="%.2f",
            )

        with e11:
            preco_atacado_edit = st.number_input(
                "Preço consultora",
                min_value=0.0,
                step=0.5,
                value=float(produto["preco_atacado"]),
                format="%.2f",
            )

        with e12:
            estoque_edit = st.number_input(
                "Estoque atual",
                min_value=0,
                step=1,
                value=int(produto["estoque_atual"]),
            )

        b1, b2 = st.columns(2)

        with b1:
            salvar_edicao = st.form_submit_button("Salvar alterações")

        with b2:
            inativar = st.form_submit_button("Inativar produto")

        if salvar_edicao:
            try:
                atualizar_produto(
                    produto_id,
                    nome_edit.strip(),
                    categoria_edit,
                    sku_edit.strip(),
                    marca_edit.strip(),
                    fornecedor_edit.strip(),
                    localizacao_edit.strip(),
                    custo_edit,
                    preco_venda_edit,
                    preco_atacado_edit,
                    estoque_edit,
                    estoque_minimo_edit,
                    1 if status_edit == "Ativo" else 0,
                )
                st.success("Produto atualizado com sucesso.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao atualizar produto: {e}")

        if inativar:
            atualizar_produto(
                produto_id,
                produto["nome"],
                produto["categoria"],
                produto["codigo_sku"],
                produto["marca"] or "",
                produto["fornecedor"] or "",
                produto["localizacao"] or "",
                float(produto["custo"]),
                float(produto["preco_venda"]),
                float(produto["preco_atacado"]),
                int(produto["estoque_atual"]),
                int(produto["estoque_minimo"]),
                0,
            )
            st.success("Produto inativado com sucesso.")
            st.rerun()