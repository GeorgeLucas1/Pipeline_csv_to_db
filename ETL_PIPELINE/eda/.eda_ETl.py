import os
import pandas as pd
from sqlalchemy import create_engine

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSV_PATH = os.path.join(RAIZ, "data_raw", "dataset.csv")
DB_PATH = "sqlite:///" + os.path.join(RAIZ, "database", "meu_banco.db")
TABLE_NAME = "compras"


def extract(caminho_csv: str) -> pd.DataFrame:
    df = pd.read_csv(caminho_csv, sep=";", encoding="utf-8-sig")
    print(f"[EXTRACT] {df.shape[0]} linhas e {df.shape[1]} colunas carregadas.")
    return df


def eda(df: pd.DataFrame) -> None:
    print("\n[EDA] Tipos de dado por coluna:")
    print(df.dtypes)

    print("\n[EDA] Valores nulos por coluna:")
    print(df.isnull().sum())

    print("\n[EDA] Linhas duplicadas:", df.duplicated().sum())

    print("\n[EDA] Resumo estatístico (colunas numéricas):")
    print(df.describe())

    colunas_categoricas = [
        "Sexo", "Estado_Civil", "Regiao", "Canal", "Forma_Pagamento",
        "Cupom", "Programa_Fidelidade", "Cancelou", "Fraude",
    ]
    print("\n[EDA] Valores únicos das colunas categóricas:")
    for col in colunas_categoricas:
        print(f"  {col}: {df[col].unique().tolist()}")


def transform(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df.columns = (
        df.columns.str.lower()
        .str.replace("%", "pct", regex=False)
        .str.strip()
    )

    antes = len(df)
    df = df.drop_duplicates()
    print(f"[TRANSFORM] Removidas {antes - len(df)} linhas duplicadas.")

    df["valor_total"] = (
        df["valor_total"]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )

    df["data_compra"] = pd.to_datetime(
        df["data_compra"], format="%d/%m/%Y", errors="coerce"
    )

    colunas_sim_nao = ["cupom", "programa_fidelidade", "cancelou", "fraude"]
    for col in colunas_sim_nao:
        df[col] = df[col].str.strip().map({"Sim": True, "Não": False})

    colunas_texto = [
        "id_cliente", "sexo", "estado_civil", "cidade", "regiao",
        "canal", "produto", "categoria", "forma_pagamento", "mes",
    ]
    for col in colunas_texto:
        df[col] = df[col].str.strip()

    nulos_restantes = df.isnull().sum().sum()
    print(f"[TRANSFORM] Total de valores nulos após limpeza: {nulos_restantes}")

    print(f"[TRANSFORM] Dados finais: {df.shape[0]} linhas, {df.shape[1]} colunas.")
    return df


def load(df: pd.DataFrame, db_path: str, table_name: str) -> None:
    pasta = os.path.dirname(db_path.replace("sqlite:///", ""))
    if pasta and not os.path.exists(pasta):
        os.makedirs(pasta)
        print(f"[LOAD] Pasta '{pasta}' criada.")

    engine = create_engine(db_path)
    df.to_sql(table_name, engine, if_exists="replace", index=False)
    print(f"[LOAD] {len(df)} linhas gravadas na tabela '{table_name}'.")

    with engine.connect() as conn:
        resultado = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table_name}")
        total = resultado.fetchone()[0]
        print(f"[LOAD] Confirmação: {total} linhas encontradas no banco.")


if __name__ == "__main__":
    df_bruto = extract(CSV_PATH)
    eda(df_bruto)
    df_limpo = transform(df_bruto)
    load(df_limpo, DB_PATH, TABLE_NAME)
