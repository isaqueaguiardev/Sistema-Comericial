# ============================================================
# CONFIGURAÇÕES GERAIS DO SISTEMA COMERCIAL
# ============================================================

APP_NAME = "Sistema de Gestão"
APP_VERSION = "1.0.0"

DATABASE_PATH = "database/sistema.db"

EMPRESA = {
    "logo": "",
    "nome": "Sistema Comercial",
    "slogan": "Seu slogan aqui",
    "cidade": "Sua cidade aqui",
    "estado": "",
    "segmento": "Loja/Comércio",
    "icone": "🏪",
    "saudacao_dashboard": "Olá 👋",
    "mensagem_dashboard": "Bem-vindo de volta.",
}

CORES = {
    "rosa_claro": "#F8D7E8",
    "nude": "#F4E5DE",
    "branco_quente": "#FFFDF9",
    "rose_gold": "#D9A5A5",
    "dourado_suave": "#C9A86A",
    "marrom_texto": "#3A2A2A",
    "texto_escuro": "#3A2A2A",
    "cinza_suave": "#F7F3F0",
    "verde_sucesso": "#2E7D32",
    "vermelho_alerta": "#C62828",
    "amarelo_atencao": "#F9A825",
}

FORMAS_PAGAMENTO = [
    "Dinheiro",
    "Pix",
    "Cartão de Débito",
    "Cartão de Crédito",
    "Fiado",
    "Outro",
]

STATUS_PEDIDO = [
    "Aberto",
    "Pago",
    "Entregue",
    "Cancelado",
]

CATEGORIAS_PRODUTO = [
    "Maquiagem",
    "Acessório",
    "Perfume",
    "Skincare",
    "Cabelo",
    "Kit",
    "Outro",
]

TIPOS_MOVIMENTO_ESTOQUE = [
    "Entrada",
    "Venda",
    "Ajuste",
    "Perda",
    "Devolução",
]