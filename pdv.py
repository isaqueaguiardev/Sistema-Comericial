import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

from config import DATABASE_PATH, FORMAS_PAGAMENTO, STATUS_PEDIDO


ORIGENS_CLIENTE = [
    "Loja Física",
    "Instagram",
    "WhatsApp",
    "Indicação",
    "Facebook",
    "TikTok",
    "Outro",
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


def carregar_produtos_ativos():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(produtos)")
    colunas = [col[1] for col in cursor.fetchall()]

    if "preco_atacado" not in colunas:
        cursor.execute("ALTER TABLE produtos ADD COLUMN preco_atacado REAL DEFAULT 0")
        conn.commit()

    df = pd.read_sql_query(
        """
        SELECT id, nome, codigo_sku, custo, preco_venda, preco_atacado, estoque_atual
        FROM produtos
        WHERE ativo = 1
        ORDER BY nome
        """,
        conn,
    )

    conn.close()
    return df


def buscar_cliente_por_telefone(telefone):
    conn = conectar()
    df = pd.read_sql_query(
        """
        SELECT
            id,
            nome,
            telefone,
            cidade,
            COALESCE(bairro_povoado, bairro) AS bairro_povoado,
            origem,
            vip
        FROM clientes
        WHERE telefone = ?
        LIMIT 1
        """,
        conn,
        params=(telefone,),
    )
    conn.close()
    return df


def cadastrar_cliente_rapido(nome, telefone, cidade, bairro_povoado, origem, vip):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO clientes (
            nome,
            telefone,
            cidade,
            bairro,
            bairro_povoado,
            origem,
            vip,
            observacoes,
            criado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            nome,
            telefone,
            cidade,
            bairro_povoado,
            bairro_povoado,
            origem,
            vip,
            "Cliente cadastrado rapidamente pelo PDV.",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )

    cliente_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return cliente_id


def registrar_pedido(
    tipo_venda,
    cliente_id,
    forma_pagamento,
    status,
    desconto,
    observacoes,
    carrinho,
    tipo_entrega,
    endereco_entrega,
    bairro_entrega,
    referencia_entrega,
    taxa_entrega,
):
    conn = conectar()
    cursor = conn.cursor()

    subtotal_produtos = sum(item["total_item"] for item in carrinho)
    custo_total = sum(item["custo_total_item"] for item in carrinho)

    subtotal = subtotal_produtos + taxa_entrega
    total = subtotal - desconto
    lucro_bruto = total - custo_total

    cursor.execute(
        """
        INSERT INTO pedidos (
            data_pedido,
            cliente_id,
            tipo_venda,
            forma_pagamento,
            status,
            subtotal,
            desconto,
            total,
            custo_total,
            lucro_bruto,
            observacoes,
            tipo_entrega,
            endereco_entrega,
            bairro_entrega,
            referencia_entrega,
            taxa_entrega
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            cliente_id,
            tipo_venda,
            forma_pagamento,
            status,
            subtotal,
            desconto,
            total,
            custo_total,
            lucro_bruto,
            observacoes,
            tipo_entrega,
            endereco_entrega,
            bairro_entrega,
            referencia_entrega,
            taxa_entrega,
        ),
    )

    pedido_id = cursor.lastrowid

    for item in carrinho:
        cursor.execute(
            """
            INSERT INTO pedido_itens (
                pedido_id,
                produto_id,
                quantidade,
                preco_unitario,
                custo_unitario,
                total_item,
                custo_total_item,
                lucro_item
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pedido_id,
                item["produto_id"],
                item["quantidade"],
                item["preco_unitario"],
                item["custo_unitario"],
                item["total_item"],
                item["custo_total_item"],
                item["lucro_item"],
            ),
        )

        cursor.execute(
            """
            UPDATE produtos
            SET estoque_atual = estoque_atual - ?
            WHERE id = ?
            """,
            (item["quantidade"], item["produto_id"]),
        )

        cursor.execute(
            """
            INSERT INTO estoque_movimentos (
                produto_id,
                tipo,
                quantidade,
                motivo,
                data_movimento
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                item["produto_id"],
                "Venda",
                item["quantidade"],
                f"Pedido #{pedido_id}",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

    conn.commit()
    conn.close()
    return pedido_id


def limpar_pdv():
    st.session_state.carrinho_pdv = []

    for chave in [
        "cliente_id_pdv",
        "cliente_nome_pdv",
        "cliente_telefone_pdv",
        "cliente_encontrado_pdv",
        "cliente_bairro_pdv",
        "cliente_vip_pdv",
    ]:
        if chave in st.session_state:
            del st.session_state[chave]


def resumo_carrinho():
    carrinho = st.session_state.get("carrinho_pdv", [])

    if not carrinho:
        return {
            "itens": 0,
            "subtotal": 0,
            "custo": 0,
            "lucro": 0,
        }

    subtotal = sum(item["total_item"] for item in carrinho)
    custo = sum(item["custo_total_item"] for item in carrinho)

    return {
        "itens": sum(item["quantidade"] for item in carrinho),
        "subtotal": subtotal,
        "custo": custo,
        "lucro": subtotal - custo,
    }


def card_resumo_pdv(titulo, valor, detalhe):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{titulo}</div>
            <div class="metric-value">{valor}</div>
            <div class="metric-help">{detalhe}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def renderizar_carrinho():
    carrinho = st.session_state.carrinho_pdv

    if not carrinho:
        st.markdown(
            '<div class="empty-state">Nenhum produto adicionado ainda.</div>',
            unsafe_allow_html=True,
        )
        return

    for i, item in enumerate(carrinho):
        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">{item["produto"]}</div>
                <div class="op-msg">
                    Quantidade: <b>{item["quantidade"]}</b><br>
                    Preço unitário: <b>{dinheiro(item["preco_unitario"])}</b><br>
                    Total do item: <b>{dinheiro(item["total_item"])}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(f"Remover item", key=f"remover_item_{i}"):
            st.session_state.carrinho_pdv.pop(i)
            st.rerun()


def tela_pdv():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Venda rápida</div>
            <div class="hero-title">PDV</div>
            <div class="hero-subtitle">
                Venda em poucos passos: cliente, produto, carrinho, entrega e pagamento.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    produtos = carregar_produtos_ativos()

    if "carrinho_pdv" not in st.session_state:
        st.session_state.carrinho_pdv = []

    if produtos.empty:
        st.warning("Cadastre produtos antes de usar o PDV.")
        return

    resumo = resumo_carrinho()

    r1, r2, r3 = st.columns(3)

    with r1:
        card_resumo_pdv("Itens", resumo["itens"], "Produtos no carrinho")

    with r2:
        card_resumo_pdv("Subtotal", dinheiro(resumo["subtotal"]), "Antes de entrega/desconto")

    with r3:
        card_resumo_pdv("Lucro estimado", dinheiro(resumo["lucro"]), "Baseado no custo cadastrado")

    st.markdown('<div class="section-title">1. Cliente da venda</div>', unsafe_allow_html=True)

    modo_cliente = st.radio(
        "Escolha como identificar o cliente",
        [
            "Consumidor final",
            "Buscar por telefone",
            "Cadastrar novo cliente",
        ],
        horizontal=True,
    )

    cliente_id = None
    cliente_nome_exibicao = "Consumidor final"
    cliente_bairro = ""

    if modo_cliente == "Consumidor final":
        cliente_id = None
        cliente_nome_exibicao = "Consumidor final"

    elif modo_cliente == "Buscar por telefone":
        telefone_busca = st.text_input(
            "Telefone do cliente",
            placeholder="Digite apenas números. Ex: 98999999999",
        )

        if st.button("Buscar cliente"):
            cliente_df = buscar_cliente_por_telefone(telefone_busca.strip())

            if cliente_df.empty:
                st.warning("Cliente não encontrado. Você pode cadastrar agora ou finalizar como consumidor final.")
            else:
                cliente = cliente_df.iloc[0]

                st.session_state["cliente_id_pdv"] = int(cliente["id"])
                st.session_state["cliente_nome_pdv"] = cliente["nome"]
                st.session_state["cliente_telefone_pdv"] = cliente["telefone"]
                st.session_state["cliente_bairro_pdv"] = cliente["bairro_povoado"] or ""
                st.session_state["cliente_vip_pdv"] = cliente["vip"] or "Não"
                st.session_state["cliente_encontrado_pdv"] = True

                st.success("Cliente encontrado e selecionado.")
                st.rerun()

    elif modo_cliente == "Cadastrar novo cliente":
        st.markdown(
            '<div class="empty-state">Cadastre o cliente rapidamente. Ele ficará salvo para compras futuras.</div>',
            unsafe_allow_html=True,
        )

        r1, r2 = st.columns([2, 1])

        with r1:
            novo_nome = st.text_input("Nome do cliente *")

        with r2:
            novo_telefone = st.text_input("Telefone/WhatsApp *")

        r3, r4 = st.columns(2)

        with r3:
            nova_cidade = st.text_input("Cidade", placeholder="Ex: Itapecuru Mirim")

        with r4:
            novo_bairro = st.text_input("Bairro/Região *")

        r5, r6 = st.columns(2)

        with r5:
            nova_origem = st.selectbox("Origem", ORIGENS_CLIENTE)

        with r6:
            novo_vip = st.selectbox("Cliente VIP?", ["Não", "Sim"])

        if st.button("Salvar e usar este cliente"):
            if not novo_nome.strip():
                st.error("Informe o nome do cliente.")
            elif not novo_telefone.strip():
                st.error("Informe o telefone.")
            elif not novo_bairro.strip():
                st.error("Informe o bairro/região.")
            else:
                novo_id = cadastrar_cliente_rapido(
                    novo_nome.strip(),
                    novo_telefone.strip(),
                    nova_cidade.strip(),
                    novo_bairro.strip(),
                    nova_origem,
                    novo_vip,
                )

                st.session_state["cliente_id_pdv"] = novo_id
                st.session_state["cliente_nome_pdv"] = novo_nome.strip()
                st.session_state["cliente_telefone_pdv"] = novo_telefone.strip()
                st.session_state["cliente_bairro_pdv"] = novo_bairro.strip()
                st.session_state["cliente_vip_pdv"] = novo_vip
                st.session_state["cliente_encontrado_pdv"] = True

                st.success("Cliente cadastrado e selecionado.")
                st.rerun()

    if st.session_state.get("cliente_encontrado_pdv"):
        cliente_id = st.session_state["cliente_id_pdv"]
        cliente_nome_exibicao = st.session_state["cliente_nome_pdv"]
        cliente_bairro = st.session_state.get("cliente_bairro_pdv", "")
        vip = st.session_state.get("cliente_vip_pdv", "Não")

        detalhe_vip = "⭐ Cliente VIP" if vip == "Sim" else "Cliente comum"

        st.markdown(
            f"""
            <div class="alert-good">
                Cliente selecionado: <b>{cliente_nome_exibicao}</b><br>
                {detalhe_vip}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title">2. Produto</div>', unsafe_allow_html=True)

    busca_produto = st.text_input("Pesquisar produto", placeholder="Digite parte do nome ou SKU")

    produtos_filtrados = produtos.copy()

    if busca_produto.strip():
        termo = busca_produto.strip().lower()
        produtos_filtrados = produtos_filtrados[
            produtos_filtrados["nome"].fillna("").str.lower().str.contains(termo)
            | produtos_filtrados["codigo_sku"].fillna("").str.lower().str.contains(termo)
        ]

    if produtos_filtrados.empty:
        st.warning("Nenhum produto encontrado com esse filtro.")
        return

    produto_opcoes = (
        produtos_filtrados["id"].astype(str)
        + " - "
        + produtos_filtrados["nome"]
        + " | Estoque: "
        + produtos_filtrados["estoque_atual"].astype(str)
    )

    produto_selecionado = st.selectbox("Produto", produto_opcoes)

    produto_id = int(produto_selecionado.split(" - ")[0])
    produto = produtos[produtos["id"] == produto_id].iloc[0]

    c1, c2 = st.columns(2)

    with c1:
        tipo_preco = st.selectbox("Preço usado", ["Varejo", "Atacado"])

    with c2:
        quantidade = st.number_input("Quantidade", min_value=1, step=1)

    preco_unitario = (
        float(produto["preco_venda"])
        if tipo_preco == "Varejo"
        else float(produto["preco_atacado"])
    )

    custo_unitario = float(produto["custo"])
    estoque_atual = int(produto["estoque_atual"])

    st.markdown(
        f"""
        <div class="alert-good">
            Produto selecionado: <b>{produto["nome"]}</b><br>
            Preço: <b>{dinheiro(preco_unitario)}</b> · Estoque disponível: <b>{estoque_atual}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Adicionar ao carrinho", type="primary"):
        if quantidade > estoque_atual:
            st.error("Quantidade maior que o estoque disponível.")
        else:
            total_item = preco_unitario * quantidade
            custo_total_item = custo_unitario * quantidade
            lucro_item = total_item - custo_total_item

            st.session_state.carrinho_pdv.append(
                {
                    "produto_id": int(produto["id"]),
                    "produto": produto["nome"],
                    "quantidade": int(quantidade),
                    "preco_unitario": preco_unitario,
                    "custo_unitario": custo_unitario,
                    "total_item": total_item,
                    "custo_total_item": custo_total_item,
                    "lucro_item": lucro_item,
                }
            )

            st.success("Produto adicionado ao carrinho.")
            st.rerun()

    st.markdown('<div class="section-title">3. Carrinho</div>', unsafe_allow_html=True)

    renderizar_carrinho()

    if not st.session_state.carrinho_pdv:
        return

    carrinho_df = pd.DataFrame(st.session_state.carrinho_pdv)
    subtotal_produtos = carrinho_df["total_item"].sum()
    custo_total = carrinho_df["custo_total_item"].sum()

    st.markdown('<div class="section-title">4. Entrega</div>', unsafe_allow_html=True)

    tipo_entrega = st.radio("Tipo de entrega", ["Retirada", "Entrega"], horizontal=True)

    endereco_entrega = ""
    bairro_entrega = ""
    referencia_entrega = ""
    taxa_entrega = 0.0

    if tipo_entrega == "Entrega":
        endereco_entrega = st.text_input(
            "Endereço de entrega *",
            placeholder="Rua, número, complemento",
        )

        bairro_entrega = st.text_input(
            "Bairro/Região da entrega *",
            value=cliente_bairro,
        )

        c1, c2 = st.columns([2, 1])

        with c1:
            referencia_entrega = st.text_input("Ponto de referência")

        with c2:
            taxa_entrega = st.number_input(
                "Taxa de entrega",
                min_value=0.0,
                step=1.0,
                format="%.2f",
            )

    st.markdown('<div class="section-title">5. Pagamento</div>', unsafe_allow_html=True)

    p1, p2 = st.columns(2)

    with p1:
        tipo_venda = st.selectbox("Tipo de venda", ["Varejo", "Atacado"])

    with p2:
        forma_pagamento = st.selectbox("Forma de pagamento", FORMAS_PAGAMENTO)

    p3, p4 = st.columns(2)

    with p3:
        status = st.selectbox(
            "Status do pedido",
            STATUS_PEDIDO,
            index=1 if "Pago" in STATUS_PEDIDO else 0,
        )

    with p4:
        desconto = st.number_input(
            "Desconto",
            min_value=0.0,
            step=1.0,
            format="%.2f",
        )

    total_final = subtotal_produtos + taxa_entrega - desconto
    lucro_estimado = total_final - custo_total

    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">Resumo da venda</div>
            <div class="op-msg">
                Cliente: <b>{cliente_nome_exibicao}</b><br><br>
                Produtos: <b>{dinheiro(subtotal_produtos)}</b><br>
                Entrega: <b>{dinheiro(taxa_entrega)}</b><br>
                Desconto: <b>{dinheiro(desconto)}</b><br><br>
                Total final: <b>{dinheiro(total_final)}</b><br>
                Lucro estimado: <b>{dinheiro(lucro_estimado)}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    observacoes = st.text_area("Observações")

    b1, b2 = st.columns(2)

    with b1:
        finalizar = st.button("Finalizar venda", type="primary")

    with b2:
        limpar = st.button("Limpar carrinho")

    if limpar:
        limpar_pdv()
        st.rerun()

    if finalizar:
        if desconto > subtotal_produtos + taxa_entrega:
            st.error("O desconto não pode ser maior que o total.")
        elif tipo_entrega == "Entrega" and not endereco_entrega.strip():
            st.error("Informe o endereço de entrega.")
        elif tipo_entrega == "Entrega" and not bairro_entrega.strip():
            st.error("Informe o bairro/região da entrega.")
        else:
            try:
                pedido_id = registrar_pedido(
                    tipo_venda,
                    cliente_id,
                    forma_pagamento,
                    status,
                    desconto,
                    observacoes.strip(),
                    st.session_state.carrinho_pdv,
                    tipo_entrega,
                    endereco_entrega.strip(),
                    bairro_entrega.strip(),
                    referencia_entrega.strip(),
                    taxa_entrega,
                )

                limpar_pdv()
                st.success(f"Venda finalizada com sucesso. Pedido #{pedido_id}")
                st.rerun()

            except Exception as e:
                st.error(f"Erro ao finalizar venda: {e}")