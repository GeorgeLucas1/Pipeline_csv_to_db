import re
import sqlite3
from pathlib import Path

import pandas as pd

# Caminhos dinamicos: resolvidos a partir da localizacao deste arquivo
RAIZ_PROJETO = Path(__file__).resolve().parent.parent
CAMINHO_BASE = RAIZ_PROJETO / "medallion" / "gold" / "database"
DB_PROCESSADOS = CAMINHO_BASE / "tabela_dados_processados.db"
DB_ANOMALIAS = CAMINHO_BASE / "dados_nao_validados.db"
DB_INSIGHTS = CAMINHO_BASE / "insights.db"

CATEGORIAS_PERMITIDAS = {
    "Oportunidade",
    "Risco Identificado",
    "Resumo Executivo",
    "Erro de Origem",
    "Inconsistencia de Dados",
    "Regra de Negocio Violada",
}

PADROES_SOSPETOS = re.compile(
    r"(ignore|ignore|esqueca|desconsidere|esqueca|destrua|delete|remova|"
    r"ignore.*instrucoes|ignore.*regras|ignore.*sistema|"
    r"voce.*agora.*e|voce.*nao.*e|voce.*pode|"
    r"crie.*mentira|inventa|falso|phishing|malicioso)",
    re.IGNORECASE,
)


def _sanitizar_texto(texto: str) -> str:
    texto = texto.strip()[:2000]
    texto = re.sub(r"<[^>]+>", "", texto)
    return texto


def _detectar_injecao(texto: str) -> bool:
    return bool(PADROES_SOSPETOS.search(texto))


def _validar_categoria(categoria: str) -> str:
    if categoria not in CATEGORIAS_PERMITIDAS:
        raise ValueError(
            f"Categoria invalida: '{categoria}'. "
            f"Use apenas: {', '.join(sorted(CATEGORIAS_PERMITIDAS))}"
        )
    return categoria


def _validar_nome_tabela_sql(tabela: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", tabela):
        raise ValueError(f"Nome de tabela invalido: '{tabela}'")
    return tabela


def ler_dados_anomalos():
    """Lê os registros que falharam na validação para análise de causa raiz."""
    if not DB_ANOMALIAS.exists():
        return "Banco de anomalias ainda não existe."
    conn = sqlite3.connect(DB_ANOMALIAS)
    df = pd.read_sql_query("SELECT * FROM dados_nao_validados LIMIT 20", conn)
    conn.close()
    return df.to_json(orient="records")

def ler_dados_processados(tabela: str):
    """Lê os dados limpos e processados para gerar insights de negócio."""
    tabela = _validar_nome_tabela_sql(tabela)
    if not DB_PROCESSADOS.exists():
        return "Banco de dados processados não encontrado."
    conn = sqlite3.connect(DB_PROCESSADOS)
    df = pd.read_sql_query(f"SELECT * FROM {tabela} LIMIT 20", conn)
    conn.close()
    return df.to_json(orient="records")

def salvar_insight(categoria: str, observacao: str, tabela_origem: str = "N/A"):
    """Grava um novo insight no banco insights.db"""
    observacao = _sanitizar_texto(observacao)
    tabela_origem = _sanitizar_texto(tabela_origem)

    if _detectar_injecao(observacao):
        return "ERRO: Insight rejeitado. Conteudo suspeito detectado."

    categoria = _validar_categoria(categoria)

    conn = sqlite3.connect(DB_INSIGHTS)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insights (
            categoria TEXT,
            observacao TEXT,
            tabela_origem TEXT DEFAULT 'N/A',
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute(
        "INSERT INTO insights (categoria, observacao, tabela_origem) VALUES (?, ?, ?)",
        (categoria, observacao, tabela_origem),
    )
    conn.commit()
    conn.close()
    return f"Sucesso: Insight de {categoria} registrado."
