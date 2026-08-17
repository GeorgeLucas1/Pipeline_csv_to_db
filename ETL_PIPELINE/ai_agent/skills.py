import sqlite3
from pathlib import Path

import pandas as pd

# Caminhos dinamicos: resolvidos a partir da localizacao deste arquivo
RAIZ_PROJETO = Path(__file__).resolve().parent.parent
CAMINHO_BASE = RAIZ_PROJETO / "medallion" / "gold" / "database"
DB_PROCESSADOS = CAMINHO_BASE / "tabela_dados_processados.db"
DB_ANOMALIAS = CAMINHO_BASE / "dados_nao_validados.db"
DB_INSIGHTS = CAMINHO_BASE / "insights.db"

def ler_dados_anomalos():
    """Lê os registros que falharam na validação para análise de causa raiz."""
    if not DB_ANOMALIAS.exists():
        return "Banco de anomalias ainda não existe."
    conn = sqlite3.connect(DB_ANOMALIAS)
    # Ajuste o nome da tabela se for diferente de 'dados_nao_validados'
    df = pd.read_sql_query("SELECT * FROM dados_nao_validados LIMIT 20", conn)
    conn.close()
    return df.to_json(orient="records")

def ler_dados_processados(tabela: str):
    """Lê os dados limpos e processados para gerar insights de negócio."""
    if not DB_PROCESSADOS.exists():
        return "Banco de dados processados não encontrado."
    conn = sqlite3.connect(DB_PROCESSADOS)
    df = pd.read_sql_query(f"SELECT * FROM {tabela} LIMIT 20", conn)
    conn.close()
    return df.to_json(orient="records")

def salvar_insight(categoria: str, observacao: str, tabela_origem: str = "N/A"):
    """Grava um novo insight no banco insights.db"""
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
