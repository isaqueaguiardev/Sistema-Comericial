import sqlite3
from datetime import date

import pandas as pd

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


def obter_pedidos_periodo(data_ini, data_fim):
    return carregar_df(
        """
        SELECT
            id,
            DATE(data_pedido) AS data,
            tipo_venda,
            forma_pagamento,
            status,
            total,
            custo_total,
            lucro_bruto,
            tipo_entrega,
            bairro_entrega,
            taxa_entrega
        FROM pedidos
        WHERE DATE(data_pedido) BETWEEN ? AND ?
        AND status != 'Cancelado'
        """,
        (data_ini, data_fim),
    )


def obter_itens_periodo(data_ini, data_fim):
    return carregar_df(
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


def obter_produtos_ativos():
    return carregar_df(
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
        """
    )


def obter_indicadores_periodo(data_ini, data_fim):
    pedidos = obter_pedidos_periodo(data_ini, data_fim)

    if pedidos.empty:
        return {
            "faturamento": 0,
            "lucro": 0,
            "pedidos": 0,
            "ticket_medio": 0,
        }

    faturamento = float(pedidos["total"].sum())
    lucro = float(pedidos["lucro_bruto"].sum())
    qtd_pedidos = int(len(pedidos))
    ticket_medio = faturamento / qtd_pedidos if qtd_pedidos else 0

    return {
        "faturamento": faturamento,
        "lucro": lucro,
        "pedidos": qtd_pedidos,
        "ticket_medio": ticket_medio,
    }


def obter_top_produtos(data_ini, data_fim, limite=5):
    itens = obter_itens_periodo(data_ini, data_fim)

    if itens.empty:
        return pd.DataFrame(columns=["Produto", "Quantidade", "Faturamento", "Lucro"])

    top = (
        itens.groupby("produto")
        .agg(
            Quantidade=("quantidade", "sum"),
            Faturamento=("total_item", "sum"),
            Lucro=("lucro_item", "sum"),
        )
        .reset_index()
        .sort_values("Quantidade", ascending=False)
        .head(limite)
    )

    return top.rename(columns={"produto": "Produto"})


def obter_ultimas_atividades(limite=8):
    pedidos = carregar_df(
        """
        SELECT
            id,
            data_pedido AS data,
            'Venda' AS tipo,
            'Pedido #' || id || ' - ' || COALESCE(tipo_venda, '') || ' - R$ ' || printf('%.2f', total) AS descricao
        FROM pedidos
        ORDER BY id DESC
        LIMIT ?
        """,
        (limite,),
    )

    clientes = carregar_df(
        """
        SELECT
            id,
            criado_em AS data,
            'Cliente' AS tipo,
            'Cliente cadastrado: ' || nome AS descricao
        FROM clientes
        ORDER BY id DESC
        LIMIT ?
        """,
        (limite,),
    )

    produtos = carregar_df(
        """
        SELECT
            id,
            criado_em AS data,
            'Produto' AS tipo,
            'Produto cadastrado: ' || nome AS descricao
        FROM produtos
        ORDER BY id DESC
        LIMIT ?
        """,
        (limite,),
    )

    atividades = pd.concat([pedidos, clientes, produtos], ignore_index=True)

    if atividades.empty:
        return atividades

    atividades["data"] = pd.to_datetime(atividades["data"], errors="coerce")
    atividades = atividades.sort_values("data", ascending=False).head(limite)

    atividades["data"] = atividades["data"].dt.strftime("%d/%m/%Y %H:%M")

    return atividades


def obter_radar_oportunidades(data_ini, data_fim):
    oportunidades = []

    produtos = obter_produtos_ativos()
    pedidos = obter_pedidos_periodo(data_ini, data_fim)
    itens = obter_itens_periodo(data_ini, data_fim)

    if not produtos.empty:
        baixos = produtos[produtos["estoque_atual"] <= produtos["estoque_minimo"]]
        zerados = produtos[produtos["estoque_atual"] <= 0]

        if len(zerados) > 0:
            oportunidades.append({
                "tipo": "crítico",
                "icone": "🚨",
                "titulo": "Produtos sem estoque",
                "mensagem": f"{len(zerados)} produto(s) zerado(s). Reposição deve ser prioridade."
            })

        if len(baixos) > 0:
            oportunidades.append({
                "tipo": "atenção",
                "icone": "⚠️",
                "titulo": "Estoque baixo",
                "mensagem": f"{len(baixos)} produto(s) abaixo ou igual ao estoque mínimo."
            })

    entregas = carregar_df(
        """
        SELECT COUNT(*) AS total
        FROM pedidos
        WHERE tipo_entrega = 'Entrega'
        AND status NOT IN ('Entregue', 'Cancelado')
        """
    )

    if not entregas.empty:
        pendentes = int(entregas.iloc[0]["total"])
        if pendentes > 0:
            oportunidades.append({
                "tipo": "atenção",
                "icone": "🚚",
                "titulo": "Entregas pendentes",
                "mensagem": f"{pendentes} entrega(s) ainda precisam ser concluídas."
            })

    if not itens.empty:
        lucro_produto = itens.groupby("produto")["lucro_item"].sum().reset_index()

        if not lucro_produto.empty:
            melhor = lucro_produto.sort_values("lucro_item", ascending=False).iloc[0]
            oportunidades.append({
                "tipo": "bom",
                "icone": "⭐",
                "titulo": "Produto mais lucrativo",
                "mensagem": f"{melhor['produto']} gerou {dinheiro(melhor['lucro_item'])} de lucro bruto no período."
            })

    if not produtos.empty:
        vendidos_ids = itens["produto_id"].unique() if not itens.empty else []
        parados = produtos[~produtos["id"].isin(vendidos_ids)]

        if len(parados) > 0:
            oportunidades.append({
                "tipo": "atenção",
                "icone": "📦",
                "titulo": "Produtos sem venda no período",
                "mensagem": f"{len(parados)} produto(s) ativo(s) não venderam no período selecionado."
            })

    if not oportunidades:
        oportunidades.append({
            "tipo": "bom",
            "icone": "✅",
            "titulo": "Operação sem alertas críticos",
            "mensagem": "Nenhum alerta relevante encontrado para o período."
        })

    return oportunidades[:6]


def obter_clima_empresa(data_ini, data_fim):
    produtos = obter_produtos_ativos()
    pedidos = obter_pedidos_periodo(data_ini, data_fim)

    pontos = 100
    motivos = []

    # Estoque
    if not produtos.empty:
        zerados = produtos[produtos["estoque_atual"] <= 0]
        baixos = produtos[produtos["estoque_atual"] <= produtos["estoque_minimo"]]

        if len(zerados) >= 5:
            pontos -= 35
            motivos.append(f"{len(zerados)} produtos zerados")
        elif len(zerados) > 0:
            pontos -= 20
            motivos.append(f"{len(zerados)} produtos zerados")

        if len(baixos) >= 10:
            pontos -= 20
            motivos.append(f"{len(baixos)} produtos com estoque baixo")
        elif len(baixos) > 0:
            pontos -= 10
            motivos.append(f"{len(baixos)} produtos com estoque baixo")

    # Entregas
    entregas = carregar_df(
        """
        SELECT COUNT(*) AS total
        FROM pedidos
        WHERE tipo_entrega = 'Entrega'
        AND status NOT IN ('Entregue', 'Cancelado')
        """
    )

    pendentes = int(entregas.iloc[0]["total"]) if not entregas.empty else 0

    if pendentes >= 5:
        pontos -= 25
        motivos.append(f"{pendentes} entregas pendentes")
    elif pendentes > 0:
        pontos -= 10
        motivos.append(f"{pendentes} entregas pendentes")

    # Vendas
    if pedidos.empty:
        pontos -= 10
        motivos.append("sem vendas no período")

    if pontos >= 85:
        status = "Excelente"
        cor = "🟢"
        mensagem = "Operação saudável."
    elif pontos >= 60:
        status = "Atenção"
        cor = "🟡"
        mensagem = "Existem pontos que precisam de acompanhamento."
    else:
        status = "Crítico"
        cor = "🔴"
        mensagem = "A operação precisa de ação imediata."

    if not motivos:
        motivos = ["sem problemas críticos identificados"]

    return {
        "pontos": max(pontos, 0),
        "status": status,
        "cor": cor,
        "mensagem": mensagem,
        "motivos": motivos,
    }
    

def calcular_meta_inteligente(data_ini, data_fim):
    """
    Calcula a meta inteligente da Airesbella com base em:
    60% histórico dos últimos 30 dias
    40% potencial de estoque atual

    A meta diária considera apenas dias de meta restantes:
    segunda a sábado, excluindo feriados e dias fechados cadastrados.
    """
    hoje = date.today()

    # Histórico dos últimos 30 dias
    data_inicio_historico = (hoje - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    data_fim_historico = hoje.strftime("%Y-%m-%d")

    historico = carregar_df(
        """
        SELECT SUM(total) AS total
        FROM pedidos
        WHERE DATE(data_pedido) BETWEEN ? AND ?
        AND status != 'Cancelado'
        """,
        (data_inicio_historico, data_fim_historico),
    )

    vendas_30_dias = float(historico.iloc[0]["total"] or 0) if not historico.empty else 0

    # Crescimento de 20% sobre histórico
    meta_historico = vendas_30_dias * 1.20

    # Potencial do estoque atual
    estoque = carregar_df(
        """
        SELECT SUM(estoque_atual * preco_venda) AS potencial
        FROM produtos
        WHERE ativo = 1
        """
    )

    potencial_estoque = float(estoque.iloc[0]["potencial"] or 0) if not estoque.empty else 0

    # Meta baseada em 50% do estoque disponível
    meta_estoque = potencial_estoque * 0.50

    # Meta inteligente final
    meta_inteligente = (meta_historico * 0.60) + (meta_estoque * 0.40)

    # Vendido no período selecionado
    vendido_periodo = carregar_df(
        """
        SELECT SUM(total) AS total
        FROM pedidos
        WHERE DATE(data_pedido) BETWEEN ? AND ?
        AND status != 'Cancelado'
        """,
        (data_ini, data_fim),
    )

    vendido = float(vendido_periodo.iloc[0]["total"] or 0) if not vendido_periodo.empty else 0

    faltante = max(meta_inteligente - vendido, 0)
    progresso = (vendido / meta_inteligente * 100) if meta_inteligente > 0 else 0

    # Dias de meta restantes: segunda a sábado, sem feriados/dias fechados
    ano = hoje.year
    mes = hoje.month

    if mes == 12:
        fim_mes = date(ano + 1, 1, 1) - pd.Timedelta(days=1)
    else:
        fim_mes = date(ano, mes + 1, 1) - pd.Timedelta(days=1)

    fechados_df = carregar_df(
        """
        SELECT data
        FROM calendario_comercial
        WHERE DATE(data) BETWEEN ? AND ?
        AND tipo IN ('Feriado nacional', 'Feriado estadual', 'Feriado municipal', 'Loja fechada')
        """,
        (hoje.strftime("%Y-%m-%d"), fim_mes.strftime("%Y-%m-%d")),
    )

    datas_fechadas = set(fechados_df["data"].tolist()) if not fechados_df.empty else set()

    dias_meta_restantes = 0
    dia_atual = hoje

    while dia_atual <= fim_mes:
        # Domingo = 6
        if dia_atual.weekday() != 6 and dia_atual.strftime("%Y-%m-%d") not in datas_fechadas:
            dias_meta_restantes += 1
        dia_atual = dia_atual + pd.Timedelta(days=1)

    media_diaria_necessaria = faltante / dias_meta_restantes if dias_meta_restantes > 0 else 0

    if vendas_30_dias <= 0 and potencial_estoque <= 0:
        confianca = "Sem dados"
    elif vendas_30_dias <= 0:
        confianca = "Estimativa por estoque"
    elif potencial_estoque <= 0:
        confianca = "Estimativa por histórico"
    else:
        confianca = "Alta"

    return {
        "meta": meta_inteligente,
        "vendido": vendido,
        "faltante": faltante,
        "progresso": progresso,
        "media_diaria": media_diaria_necessaria,
        "dias_meta_restantes": dias_meta_restantes,
        "vendas_30_dias": vendas_30_dias,
        "potencial_estoque": potencial_estoque,
        "confianca": confianca,
    }    