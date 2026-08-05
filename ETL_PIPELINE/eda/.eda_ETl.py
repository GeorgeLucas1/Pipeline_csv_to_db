
import os
import re
import glob
import shutil
import pandas as pd
from sqlalchemy import create_engine

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_RAW_DIR = os.path.join(RAIZ, "medallion", "bronze")
PROCESSED_DIR = os.path.join(DATA_RAW_DIR, "processed")
SILVER_DIR = os.path.join(RAIZ, "medallion", "silver")
GOLD_DIR = os.path.join(RAIZ, "medallion", "gold")
DB_PATH = "sqlite:///" + os.path.join(RAIZ, "medallion", "gold", "database", "dynamic.db")

EXTENSOES_SUPORTADAS = (".csv", ".xlsx", ".xls")

#camada bronze /extract -> apenas leitura do arquivo, sem alterações
def extract(caminho_arquivo: str) -> pd.DataFrame:
    extensao = os.path.splitext(caminho_arquivo)[1].lower()


    if extensao == ".csv":
        try:
            df = pd.read_csv(caminho_arquivo, sep=";", encoding="utf-8-sig")
            if df.shape[1] == 1:
                raise ValueError("separador provavelmente errado")
        except (ValueError, pd.errors.ParserError):
            df = pd.read_csv(caminho_arquivo, sep=",", encoding="utf-8-sig")
    elif extensao in (".xlsx", ".xls"):
        df = pd.read_excel(caminho_arquivo)
    else:
        raise ValueError(f"Extensão não suportada: {extensao}")

    print(f"[BRONZE] {os.path.basename(caminho_arquivo)}: "
          f"{df.shape[0]} linhas, {df.shape[1]} colunas.")
    return df


def eda(df: pd.DataFrame) -> None:
    print("[EDA] Tipos de dado por coluna:")
    print(df.dtypes)

    print("[EDA] Valores nulos por coluna:")
    print(df.isnull().sum())

    print("[EDA] Linhas duplicadas:", df.duplicated().sum())

    colunas_categoricas = [
        col for col in df.columns
        if (df[col].dtype == "object" or str(df[col].dtype) == "str")
        and df[col].nunique(dropna=True) <= 15
    ]
    print("[EDA] Colunas categóricas detectadas:", colunas_categoricas)
    for col in colunas_categoricas:
        print(f"  {col}: {df[col].unique().tolist()}")

# 
def _padronizar_nomes_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns.astype(str).str.strip()
        .str.lower()
        .str.replace("%", "pct", regex=False)
        .str.replace(r"[^0-9a-zà-ú_]+", "_", regex=True)
        .str.strip("_")
    )
    return df

#camada silver> transformar os dados
def transform_silver(df: pd.DataFrame) -> pd.DataFrame:
    """Limpeza estrutural: nomes de coluna, espaços em branco, duplicados."""
    df = df.copy()
    df = _padronizar_nomes_colunas(df)

    antes = len(df)
    df = df.drop_duplicates()
    print(f"[SILVER] Removidas {antes - len(df)} linhas duplicadas.")

    for col in df.columns:
        if df[col].dtype == "object" or str(df[col].dtype) == "str":
            df[col] = df[col].astype("object").astype(str).str.strip()
            df[col] = df[col].replace({"nan": None, "None": None})

    print(f"[SILVER] Resultado: {df.shape[0]} linhas, {df.shape[1]} colunas.")
    return df


#Gold-preparar dados para consumo final, detectando e convertendo tipos reais (bool, número, data)

def _tentar_converter_booleano(serie: pd.Series) -> pd.Series:
    valores = serie.dropna().astype(str).str.strip().str.lower().unique().tolist()
    mapas_possiveis = [
        {"sim": True, "não": False, "nao": False},
        {"yes": True, "no": False},
        {"true": True, "false": False},
        {"verdadeiro": True, "falso": False},
    ]
    for mapa in mapas_possiveis:
        if set(valores).issubset(set(mapa.keys())):
            return serie.astype(str).str.strip().str.lower().map(mapa)
    return serie


def _tentar_converter_numero_com_virgula(serie: pd.Series) -> pd.Series:
    amostra = serie.dropna().astype(str).str.strip()
    padrao_numero = amostra.str.match(r"^-?\d+(,\d+)?$")
    if len(amostra) > 0 and padrao_numero.mean() > 0.95:
        return pd.to_numeric(
            serie.astype(str).str.replace(",", ".", regex=False), errors="coerce"
        )
    return serie


def _tentar_converter_data(nome_col: str, serie: pd.Series) -> pd.Series:
    palavras_chave = ("data", "date", "dt_")
    if any(p in nome_col for p in palavras_chave):
        convertida = pd.to_datetime(serie, dayfirst=True, errors="coerce")
        if convertida.notna().mean() >= 0.9:
            return convertida
    return serie


def transform_gold(df: pd.DataFrame) -> pd.DataFrame:
    """Detecta e converte o tipo real de cada coluna (bool, número, data)."""
    df = df.copy()

    for col in df.columns:
        if df[col].dtype == "object" or str(df[col].dtype) == "str":
            df[col] = _tentar_converter_booleano(df[col])
            if df[col].dtype == "object" or str(df[col].dtype) == "str":
                df[col] = _tentar_converter_numero_com_virgula(df[col])
            if df[col].dtype == "object" or str(df[col].dtype) == "str":
                df[col] = _tentar_converter_data(col, df[col])

    nulos_restantes = df.isnull().sum().sum()
    print(f"[GOLD] Valores nulos após conversão de tipos: {nulos_restantes}")
    print(f"[GOLD] Resultado final: {df.shape[0]} linhas, {df.shape[1]} colunas.")
    return df


# ============================================================
# LOAD -> grava a tabela no banco
# ============================================================
def nome_tabela_a_partir_do_arquivo(caminho_arquivo: str) -> str:
    nome = os.path.splitext(os.path.basename(caminho_arquivo))[0]
    return _sanitizar_nome_tabela(nome)


def _sanitizar_nome_tabela(nome: str) -> str:
    return re.sub(r"[^0-9a-zA-Z_]+", "_", nome).lower().strip("_")


PALAVRAS_RESERVADAS_SQL = {
    "select", "from", "where", "insert", "into", "values", "update", "set",
    "delete", "create", "drop", "alter", "table", "index", "view", "grant",
    "revoke", "primary", "key", "foreign", "references", "not", "null",
    "and", "or", "like", "between", "in", "is", "join", "inner", "left",
    "right", "full", "outer", "on", "group", "order", "by", "having",
    "limit", "offset", "union", "all", "distinct", "as", "with", "case",
    "when", "then", "else", "end", "add", "column", "check", "default",
    "unique", "constraint", "trigger", "transaction", "commit", "rollback",
    "begin", "pragma", "explain", "vacuum", "reindex", "analyze", "attach",
}


def validar_nome_tabela(nome: str) -> str:
    """Valida o nome da tabela e devolve ele normalizado (minúsculo)."""
    nome = nome.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", nome):
        raise ValueError(
            "Nome de tabela inválido. Use apenas letras minúsculas, números e '_', "
            "começando com letra (até 63 caracteres), sem espaços ou caracteres especiais."
        )
    if nome in PALAVRAS_RESERVADAS_SQL:
        raise ValueError(
            f"'{nome}' é uma palavra reservada do SQL e não pode ser usada como nome de tabela."
        )
    return nome


def load(df: pd.DataFrame, db_path: str, table_name: str) -> None:
    pasta = os.path.dirname(db_path.replace("sqlite:///", ""))
    if pasta and not os.path.exists(pasta):
        os.makedirs(pasta)
        print(f"[LOAD] Pasta '{pasta}' criada.")

    engine = create_engine(db_path)
    with engine.connect() as conn:
        existe = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
    if existe:
        raise ValueError(
            f"Pipeline rejeitado: a tabela '{table_name}' já existe no banco. "
            "Escolha outro nome de tabela."
        )

    df.to_sql(table_name, engine, if_exists="fail", index=False)

    with engine.connect() as conn:
        total = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"[LOAD] Tabela '{table_name}': {total} linhas gravadas.")


# ============================================================
# ORQUESTRAÇÃO: bronze -> silver -> gold -> banco
# ============================================================
def processar_arquivo(caminho_arquivo: str, table_name: str | None = None) -> None:
    if table_name:
        nome_tabela = validar_nome_tabela(table_name)
    else:
        nome_tabela = nome_tabela_a_partir_do_arquivo(caminho_arquivo)
    nome_base = os.path.splitext(os.path.basename(caminho_arquivo))[0]
    print(f"\n=== Processando '{os.path.basename(caminho_arquivo)}' "
          f"-> tabela '{nome_tabela}' ===")

    # BRONZE
    df_bronze = extract(caminho_arquivo)
    eda(df_bronze)

    # SILVER
    df_silver = transform_silver(df_bronze)
    os.makedirs(SILVER_DIR, exist_ok=True)
    caminho_silver = os.path.join(SILVER_DIR, f"{nome_base}_silver.csv")
    df_silver.to_csv(caminho_silver, index=False)
    print(f"[SILVER] Salvo em '{caminho_silver}'.")

    # GOLD
    df_gold = transform_gold(df_silver)
    os.makedirs(GOLD_DIR, exist_ok=True)
    caminho_gold = os.path.join(GOLD_DIR, f"{nome_base}_gold.csv")
    df_gold.to_csv(caminho_gold, index=False)
    print(f"[GOLD] Salvo em '{caminho_gold}'.")

    # LOAD
    load(df_gold, DB_PATH, nome_tabela)

    # Move o arquivo original (bronze) pra processed/
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    destino = os.path.join(PROCESSED_DIR, os.path.basename(caminho_arquivo))
    shutil.move(caminho_arquivo, destino)
    print(f"[OK] Arquivo original movido para '{destino}'.")


def processar_pendentes() -> None:
    padroes = [os.path.join(DATA_RAW_DIR, f"*{ext}") for ext in EXTENSOES_SUPORTADAS]
    arquivos_pendentes = sorted(set(sum((glob.glob(p) for p in padroes), [])))

    if not arquivos_pendentes:
        print("Nenhum arquivo novo encontrado em data_raw/.")
        return

    for caminho_arquivo in arquivos_pendentes:
        processar_arquivo(caminho_arquivo)


if __name__ == "__main__":
    processar_pendentes()