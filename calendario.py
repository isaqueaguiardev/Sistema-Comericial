import sqlite3
from datetime import date, datetime, timedelta

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


def carregar_df(query, params=()):
    conn = conectar()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def calcular_pascoa(ano):
    a = ano % 19
    b = ano // 100
    c = ano % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados_base_ano(ano):
    pascoa = calcular_pascoa(ano)

    feriados = [
        (date(ano, 1, 1), "Confraternização Universal", "Feriado nacional"),
        (pascoa - timedelta(days=48), "Carnaval", "Feriado nacional"),
        (pascoa - timedelta(days=47), "Carnaval", "Feriado nacional"),
        (pascoa - timedelta(days=2), "Paixão de Cristo", "Feriado nacional"),
        (date(ano, 4, 21), "Tiradentes", "Feriado nacional"),
        (date(ano, 5, 1), "Dia do Trabalho", "Feriado nacional"),
        (pascoa + timedelta(days=60), "Corpus Christi", "Feriado nacional"),
        (date(ano, 9, 7), "Independência do Brasil", "Feriado nacional"),
        (date(ano, 10, 12), "Nossa Senhora Aparecida", "Feriado nacional"),
        (date(ano, 11, 2), "Finados", "Feriado nacional"),
        (date(ano, 11, 15), "Proclamação da República", "Feriado nacional"),
        (date(ano, 11, 20), "Consciência Negra", "Feriado nacional"),
        (date(ano, 12, 25), "Natal", "Feriado nacional"),

        (date(ano, 7, 28), "Adesão do Maranhão à Independência", "Feriado estadual"),

        (date(ano, 7, 21), "Aniversário de Itapecuru Mirim", "Feriado municipal"),
        (date(ano, 9, 15), "Nossa Senhora das Dores", "Feriado municipal"),
    ]

    if ano == 2026:
        feriados.append(
            (date(2026, 4, 23), "Dia Municipal das Religiões de Matriz Africana", "Feriado municipal")
        )

    return feriados


def importar_feriados_ano(ano):
    adicionados = 0

    for data_item, descricao, tipo in feriados_base_ano(ano):
        try:
            executar_sql(
                """
                INSERT INTO calendario_comercial (data, descricao, tipo, criado_em)
                VALUES (?, ?, ?, ?)
                """,
                (
                    data_item.strftime("%Y-%m-%d"),
                    descricao,
                    tipo,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            adicionados += 1
        except sqlite3.IntegrityError:
            pass

    return adicionados


def cadastrar_data_especial(data_item, descricao, tipo):
    executar_sql(
        """
        INSERT OR REPLACE INTO calendario_comercial (data, descricao, tipo, criado_em)
        VALUES (?, ?, ?, ?)
        """,
        (
            data_item.strftime("%Y-%m-%d"),
            descricao,
            tipo,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )


def excluir_data_especial(registro_id):
    executar_sql(
        """
        DELETE FROM calendario_comercial
        WHERE id = ?
        """,
        (registro_id,),
    )


def carregar_calendario(ano):
    return carregar_df(
        """
        SELECT id, data, descricao, tipo, criado_em
        FROM calendario_comercial
        WHERE strftime('%Y', data) = ?
        ORDER BY data ASC
        """,
        (str(ano),),
    )


def eh_dia_meta(data_item, datas_fechadas):
    if data_item.weekday() == 6:
        return False

    if data_item.strftime("%Y-%m-%d") in datas_fechadas:
        return False

    return True


def calcular_dias_meta_mes(ano, mes):
    inicio = date(ano, mes, 1)

    if mes == 12:
        fim = date(ano + 1, 1, 1) - timedelta(days=1)
    else:
        fim = date(ano, mes + 1, 1) - timedelta(days=1)

    calendario = carregar_df(
        """
        SELECT data, tipo
        FROM calendario_comercial
        WHERE DATE(data) BETWEEN ? AND ?
        AND tipo IN ('Feriado nacional', 'Feriado estadual', 'Feriado municipal', 'Loja fechada')
        """,
        (inicio.strftime("%Y-%m-%d"), fim.strftime("%Y-%m-%d")),
    )

    datas_fechadas = set(calendario["data"].tolist()) if not calendario.empty else set()

    dias_meta = []
    atual = inicio

    while atual <= fim:
        if eh_dia_meta(atual, datas_fechadas):
            dias_meta.append(atual)
        atual += timedelta(days=1)

    return dias_meta


def calcular_dias_meta_restantes(ano, mes):
    hoje = date.today()
    dias_meta = calcular_dias_meta_mes(ano, mes)
    return [d for d in dias_meta if d >= hoje]


def tela_calendario():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-small">Calendário comercial</div>
            <div class="hero-title">Calendário da Airesbella</div>
            <div class="hero-subtitle">
                Controle feriados, dias fechados e eventos especiais para calcular metas reais
                considerando apenas os dias em que a loja deve vender.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    hoje = date.today()
    ano = st.number_input("Ano", min_value=2025, max_value=2035, value=hoje.year, step=1)

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("Importar feriados do ano"):
            qtd = importar_feriados_ano(int(ano))
            st.success(f"{qtd} feriado(s) importado(s). Datas já existentes foram mantidas.")
            st.rerun()

    with c2:
        dias_meta_mes = calcular_dias_meta_mes(int(ano), hoje.month)
        st.metric("Dias de meta no mês atual", len(dias_meta_mes))

    with c3:
        dias_restantes = calcular_dias_meta_restantes(int(ano), hoje.month)
        st.metric("Dias de meta restantes", len(dias_restantes))

    st.markdown('<div class="section-title">Cadastrar data especial</div>', unsafe_allow_html=True)

    with st.form("form_calendario"):
        f1, f2, f3 = st.columns([1, 2, 1])

        with f1:
            data_item = st.date_input("Data", value=hoje)

        with f2:
            descricao = st.text_input("Descrição", placeholder="Ex: Feriado municipal, inventário, evento especial...")

        with f3:
            tipo = st.selectbox(
                "Tipo",
                [
                    "Feriado nacional",
                    "Feriado estadual",
                    "Feriado municipal",
                    "Loja fechada",
                    "Evento especial",
                ],
            )

        salvar = st.form_submit_button("Salvar data")

        if salvar:
            if not descricao.strip():
                st.error("Informe uma descrição.")
            else:
                cadastrar_data_especial(data_item, descricao.strip(), tipo)
                st.success("Data salva com sucesso.")
                st.rerun()

    st.markdown('<div class="section-title">Datas cadastradas</div>', unsafe_allow_html=True)

    calendario = carregar_calendario(int(ano))

    if calendario.empty:
        st.markdown(
            '<div class="empty-state">Nenhuma data cadastrada para este ano. Clique em importar feriados do ano.</div>',
            unsafe_allow_html=True,
        )
    else:
        tabela = calendario.copy()
        tabela["Data"] = pd.to_datetime(tabela["data"]).dt.strftime("%d/%m/%Y")
        tabela = tabela[["id", "Data", "descricao", "tipo"]].rename(
            columns={
                "id": "ID",
                "descricao": "Descrição",
                "tipo": "Tipo",
            }
        )
        st.dataframe(tabela, use_container_width=True, hide_index=True)

        st.markdown('<div class="section-title">Excluir data</div>', unsafe_allow_html=True)

        opcoes = calendario["id"].astype(str) + " - " + calendario["data"] + " - " + calendario["descricao"]
        selecionado = st.selectbox("Selecione uma data para excluir", opcoes)

        if st.button("Excluir data selecionada"):
            registro_id = int(selecionado.split(" - ")[0])
            excluir_data_especial(registro_id)
            st.success("Data excluída com sucesso.")
            st.rerun()