import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

from config import DATABASE_PATH, CATEGORIAS_PRODUTO


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
    return f"PR{proximo_id:05d}"


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


def card_produto(produto):
    status = "Ativo" if int(produto["ativo"]) == 1 else "Inativo"
    alerta = (
        "⚠️ Estoque baixo"
        if int(produto["ativo"]) == 1 and int(produto["estoque_atual"]) <= int(produto["estoque_minimo"])
        else "✅ Estoque ok"
    )

    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">📦 {produto["nome"]}</div>
            <div class="op-msg">
                SKU: <b>{produto["codigo_sku"] or "-"}</b><br>
                Categoria: <b>{produto["categoria"] or "-"}</b><br>
                Marca: <b>{produto["marca"] or "-"}</b><br><br>
                Venda: <b>{dinheiro(produto["preco_venda"])}</b><br>
                Atacado: <b>{dinheiro(produto["preco_atacado"])}</b><br>
                Custo: <b>{dinheiro(produto["custo"])}</b><br><br>
                Estoque: <b>{int(produto["estoque_atual"])}</b> · Mínimo: <b>{int(produto["estoque_minimo"])}</b><br>
                Status: <b>{status}</b><br>
                {alerta}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def tela_produtos():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Catálogo</div>
            <div class="hero-title">Produtos</div>
            <div class="hero-subtitle">
                Cadastre, consulte e edite produtos com preços, estoque, marca, fornecedor e localização.
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
        card_resumo("Produtos", total_produtos, "Total cadastrado")

    with col2:
        card_resumo("Ativos", produtos_ativos, "Disponíveis para venda")

    with col3:
        card_resumo("Estoque", estoque_total, "Unidades totais")

    with col4:
        card_resumo("Alertas", estoque_baixo, "Produtos com estoque baixo")

    st.markdown('<div class="section-title">Cadastrar produto</div>', unsafe_allow_html=True)

    sku_sugerido = gerar_sku_automatico()

    with st.form("form_cadastrar_produto", clear_on_submit=True):
        st.markdown(
            f"""
            <div class="alert-good">
                SKU automático sugerido: <b>{sku_sugerido}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="panel-title">📦 Dados do produto</div>', unsafe_allow_html=True)

        c1, c2 = st.columns([2, 1])

        with c1:
            nome = st.text_input("Nome do produto *", placeholder="Ex: Gloss Morango")

        with c2:
            categoria = st.selectbox("Categoria", CATEGORIAS_PRODUTO)

        c3, c4 = st.columns(2)

        with c3:
            marca = st.text_input("Marca", placeholder="Ex: Ruby Rose")

        with c4:
            fornecedor = st.text_input("Fornecedor", placeholder="Ex: Atacado SP")

        localizacao = st.text_input("Localização", placeholder="Ex: Expositor A, Prateleira 2")

        st.markdown('<div class="panel-title">💰 Preços</div>', unsafe_allow_html=True)

        p1, p2, p3 = st.columns(3)

        with p1:
            custo = st.number_input("Custo unitário", min_value=0.0, step=0.5, format="%.2f")

        with p2:
            preco_venda = st.number_input("Preço de venda", min_value=0.0, step=0.5, format="%.2f")

        with p3:
            preco_atacado = st.number_input("Preço atacado", min_value=0.0, step=0.5, format="%.2f")

        margem_loja = calcular_margem(preco_venda, custo)
        margem_atacado = calcular_margem(preco_atacado, custo)

        m1, m2 = st.columns(2)

        with m1:
            st.metric("Margem venda", f"{margem_loja:.1f}%")

        with m2:
            st.metric("Margem atacado", f"{margem_atacado:.1f}%")

        st.markdown('<div class="panel-title">📊 Estoque</div>', unsafe_allow_html=True)

        e1, e2 = st.columns(2)

        with e1:
            estoque_atual = st.number_input("Quantidade em estoque", min_value=0, step=1)

        with e2:
            estoque_minimo = st.number_input("Estoque mínimo", min_value=0, step=1)

        salvar = st.form_submit_button("Salvar produto")

        if salvar:
            if not nome.strip():
                st.error("Informe o nome do produto.")
            elif preco_venda < custo:
                st.error("O preço de venda está menor que o custo.")
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

                    if preco_atacado < custo:
                        st.warning("Produto cadastrado, mas o preço atacado está menor que o custo.")
                    else:
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

    f1, f2 = st.columns([2, 1])

    with f1:
        busca = st.text_input("Buscar produto", placeholder="Digite nome, SKU, marca ou fornecedor...")

    with f2:
        filtro_status = st.selectbox("Status", ["Todos", "Ativos", "Inativos", "Estoque baixo"])

    categorias = ["Todas"] + sorted([x for x in produtos_df["categoria"].dropna().unique()])
    filtro_categoria = st.selectbox("Categoria", categorias)

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

    if df.empty:
        st.markdown(
            '<div class="empty-state">Nenhum produto encontrado com os filtros atuais.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="alert-good">
                {len(df)} produto(s) encontrado(s).
            </div>
            """,
            unsafe_allow_html=True,
        )

        for _, produto in df.head(12).iterrows():
            card_produto(produto)

        if len(df) > 12:
            st.info("Mostrando os 12 primeiros produtos. Use a busca ou os filtros para refinar.")

        with st.expander("Ver tabela completa"):
            tabela = df.copy()

            tabela["Margem Venda"] = tabela.apply(
                lambda x: f"{calcular_margem(x['preco_venda'], x['custo']):.1f}%",
                axis=1,
            )

            tabela["Margem Atacado"] = tabela.apply(
                lambda x: f"{calcular_margem(x['preco_atacado'], x['custo']):.1f}%",
                axis=1,
            )

            tabela["Custo"] = tabela["custo"].apply(dinheiro)
            tabela["Preço Venda"] = tabela["preco_venda"].apply(dinheiro)
            tabela["Preço Atacado"] = tabela["preco_atacado"].apply(dinheiro)
            tabela["Status"] = tabela["ativo"].apply(lambda x: "Ativo" if x == 1 else "Inativo")

            tabela["Alerta"] = tabela.apply(
                lambda x: "⚠️ Baixo"
                if x["ativo"] == 1 and x["estoque_atual"] <= x["estoque_minimo"]
                else "OK",
                axis=1,
            )

            tabela = tabela[
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
                    "Preço Atacado",
                    "Margem Venda",
                    "Margem Atacado",
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

    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">Editando: {produto["nome"]}</div>
            <div class="op-msg">
                SKU: <b>{produto["codigo_sku"] or "-"}</b><br>
                Estoque atual: <b>{int(produto["estoque_atual"])}</b><br>
                Preço atual: <b>{dinheiro(produto["preco_venda"])}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("form_editar_produto"):
        st.markdown('<div class="panel-title">📦 Dados</div>', unsafe_allow_html=True)

        e1, e2 = st.columns([2, 1])

        with e1:
            nome_edit = st.text_input("Nome", value=produto["nome"])

        with e2:
            sku_edit = st.text_input("SKU", value=produto["codigo_sku"] or "", disabled=True)

        e3, e4 = st.columns(2)

        with e3:
            categoria_edit = st.selectbox(
                "Categoria",
                CATEGORIAS_PRODUTO,
                index=CATEGORIAS_PRODUTO.index(produto["categoria"])
                if produto["categoria"] in CATEGORIAS_PRODUTO
                else 0,
            )

        with e4:
            status_edit = st.selectbox(
                "Status",
                ["Ativo", "Inativo"],
                index=0 if int(produto["ativo"]) == 1 else 1,
            )

        e5, e6 = st.columns(2)

        with e5:
            marca_edit = st.text_input("Marca", value=produto["marca"] or "")

        with e6:
            fornecedor_edit = st.text_input("Fornecedor", value=produto["fornecedor"] or "")

        localizacao_edit = st.text_input("Localização", value=produto["localizacao"] or "")

        st.markdown('<div class="panel-title">💰 Preços</div>', unsafe_allow_html=True)

        p1, p2, p3 = st.columns(3)

        with p1:
            custo_edit = st.number_input(
                "Custo",
                min_value=0.0,
                step=0.5,
                value=float(produto["custo"]),
                format="%.2f",
            )

        with p2:
            preco_venda_edit = st.number_input(
                "Preço venda",
                min_value=0.0,
                step=0.5,
                value=float(produto["preco_venda"]),
                format="%.2f",
            )

        with p3:
            preco_atacado_edit = st.number_input(
                "Preço atacado",
                min_value=0.0,
                step=0.5,
                value=float(produto["preco_atacado"]),
                format="%.2f",
            )

        st.markdown('<div class="panel-title">📊 Estoque</div>', unsafe_allow_html=True)

        s1, s2 = st.columns(2)

        with s1:
            estoque_edit = st.number_input(
                "Estoque atual",
                min_value=0,
                step=1,
                value=int(produto["estoque_atual"]),
            )

        with s2:
            estoque_minimo_edit = st.number_input(
                "Estoque mínimo",
                min_value=0,
                step=1,
                value=int(produto["estoque_minimo"]),
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