# ============================================================
# BANCO DE DADOS DO SISTEMA COMERCIAL
# ============================================================

import sqlite3
from pathlib import Path
from datetime import datetime
import bcrypt

from config import DATABASE_PATH


def get_connection():
    Path("database").mkdir(exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def executar_sql(sql, parametros=()):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, parametros)
        conn.commit()
    finally:
        conn.close()


def consultar_sql(sql, parametros=()):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, parametros)
        dados = cursor.fetchall()
        return dados
    finally:
        conn.close()


def gerar_hash_senha(senha):
    senha_bytes = senha.encode("utf-8")
    return bcrypt.hashpw(senha_bytes, bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha_digitada, senha_hash):
    try:
        return bcrypt.checkpw(
            senha_digitada.encode("utf-8"),
            senha_hash.encode("utf-8")
        )
    except Exception:
        return False


def criar_tabelas():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            usuario TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            perfil TEXT NOT NULL DEFAULT 'admin',
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            ultimo_login TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            cidade TEXT,
            bairro TEXT,
            observacoes TEXT,
            criado_em TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT,
            codigo_sku TEXT UNIQUE,
            custo REAL NOT NULL DEFAULT 0,
            preco_venda REAL NOT NULL DEFAULT 0,
            preco_atacado REAL NOT NULL DEFAULT 0,
            estoque_atual INTEGER NOT NULL DEFAULT 0,
            estoque_minimo INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estoque_movimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            motivo TEXT,
            data_movimento TEXT NOT NULL,
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_pedido TEXT NOT NULL,
            cliente_id INTEGER,
            tipo_venda TEXT NOT NULL DEFAULT 'Loja',
            forma_pagamento TEXT,
            status TEXT NOT NULL DEFAULT 'Pago',
            subtotal REAL NOT NULL DEFAULT 0,
            desconto REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            custo_total REAL NOT NULL DEFAULT 0,
            lucro_bruto REAL NOT NULL DEFAULT 0,
            observacoes TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedido_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade INTEGER NOT NULL,
            preco_unitario REAL NOT NULL,
            custo_unitario REAL NOT NULL,
            total_item REAL NOT NULL,
            custo_total_item REAL NOT NULL,
            lucro_item REAL NOT NULL,
            FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS despesas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_despesa TEXT NOT NULL,
            descricao TEXT NOT NULL,
            categoria TEXT,
            valor REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pago',
            observacoes TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mes INTEGER NOT NULL,
            ano INTEGER NOT NULL,
            meta_faturamento REAL NOT NULL DEFAULT 0,
            meta_lucro REAL NOT NULL DEFAULT 0,
            observacoes TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_log TEXT NOT NULL,
            usuario TEXT,
            acao TEXT NOT NULL,
            detalhes TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calendario_comercial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL UNIQUE,
            descricao TEXT,
            tipo TEXT NOT NULL DEFAULT 'Fechado',
            criado_em TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def adicionar_coluna_se_nao_existir(tabela, coluna, definicao):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({tabela})")
        colunas = [info["name"] for info in cursor.fetchall()]

        if coluna not in colunas:
            cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")
            conn.commit()
    finally:
        conn.close()


def atualizar_estrutura_banco():
    adicionar_coluna_se_nao_existir("usuarios", "ultimo_login", "TEXT")

    adicionar_coluna_se_nao_existir("produtos", "preco_atacado", "REAL DEFAULT 0")
    adicionar_coluna_se_nao_existir("produtos", "marca", "TEXT")
    adicionar_coluna_se_nao_existir("produtos", "fornecedor", "TEXT")
    adicionar_coluna_se_nao_existir("produtos", "localizacao", "TEXT")

    adicionar_coluna_se_nao_existir("clientes", "bairro_povoado", "TEXT")
    adicionar_coluna_se_nao_existir("clientes", "origem", "TEXT")
    adicionar_coluna_se_nao_existir("clientes", "data_nascimento", "TEXT")
    adicionar_coluna_se_nao_existir("clientes", "vip", "TEXT DEFAULT 'Não'")

    adicionar_coluna_se_nao_existir("pedidos", "tipo_entrega", "TEXT DEFAULT 'Retirada'")
    adicionar_coluna_se_nao_existir("pedidos", "endereco_entrega", "TEXT")
    adicionar_coluna_se_nao_existir("pedidos", "bairro_entrega", "TEXT")
    adicionar_coluna_se_nao_existir("pedidos", "referencia_entrega", "TEXT")
    adicionar_coluna_se_nao_existir("pedidos", "taxa_entrega", "REAL DEFAULT 0")


def criar_usuario_admin_padrao():
    usuarios = consultar_sql("SELECT * FROM usuarios WHERE usuario = ?", ("admin",))

    if not usuarios:
        senha_hash = gerar_hash_senha("admin123")
        executar_sql("""
            INSERT INTO usuarios (nome, usuario, senha_hash, perfil, ativo, criado_em)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "Administrador",
            "admin",
            senha_hash,
            "admin",
            1,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))


def autenticar_usuario(usuario, senha):
    dados = consultar_sql(
        """
        SELECT id, nome, usuario, senha_hash, perfil, ativo
        FROM usuarios
        WHERE usuario = ?
        LIMIT 1
        """,
        (usuario,)
    )

    if not dados:
        return None

    usuario_db = dados[0]

    if int(usuario_db["ativo"]) != 1:
        return None

    if not verificar_senha(senha, usuario_db["senha_hash"]):
        return None

    executar_sql(
        """
        UPDATE usuarios
        SET ultimo_login = ?
        WHERE id = ?
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            usuario_db["id"]
        )
    )

    return {
        "id": usuario_db["id"],
        "nome": usuario_db["nome"],
        "usuario": usuario_db["usuario"],
        "perfil": usuario_db["perfil"],
    }


def listar_usuarios():
    return consultar_sql(
        """
        SELECT id, nome, usuario, perfil, ativo, criado_em, ultimo_login
        FROM usuarios
        ORDER BY id DESC
        """
    )


def criar_usuario(nome, usuario, senha, perfil="funcionario", ativo=1):
    senha_hash = gerar_hash_senha(senha)
    executar_sql("""
        INSERT INTO usuarios (nome, usuario, senha_hash, perfil, ativo, criado_em)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        nome,
        usuario,
        senha_hash,
        perfil,
        ativo,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))


def alterar_senha_usuario(usuario_id, nova_senha):
    senha_hash = gerar_hash_senha(nova_senha)
    executar_sql(
        """
        UPDATE usuarios
        SET senha_hash = ?
        WHERE id = ?
        """,
        (senha_hash, usuario_id)
    )


def ativar_desativar_usuario(usuario_id, ativo):
    executar_sql(
        """
        UPDATE usuarios
        SET ativo = ?
        WHERE id = ?
        """,
        (ativo, usuario_id)
    )


def registrar_log(usuario, acao, detalhes=""):
    executar_sql("""
        INSERT INTO logs (data_log, usuario, acao, detalhes)
        VALUES (?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        usuario,
        acao,
        detalhes
    ))


def inicializar_banco():
    criar_tabelas()
    atualizar_estrutura_banco()
    criar_usuario_admin_padrao()