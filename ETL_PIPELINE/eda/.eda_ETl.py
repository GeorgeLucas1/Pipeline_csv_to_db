import glob
import itertools
import os
import re
import shutil

import pandas as pd
from sqlalchemy import create_engine

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_RAW_DIR = os.path.join(RAIZ, "medallion", "bronze")
PROCESSED_DIR = os.path.join(DATA_RAW_DIR, "processed")
SILVER_DIR = os.path.join(RAIZ, "medallion", "silver")
GOLD_DIR = os.path.join(RAIZ, "medallion", "gold")
DB_PATH = "sqlite:///" + os.path.join(RAIZ, "medallion", "gold", "database", "tabela_dados_processados.db")
NON_VALIDATED_DB_PATH = "sqlite:///" + os.path.join(RAIZ, "medallion", "gold", "database", "dados_nao_validados.db")

EXTENSOES_SUPORTADAS = (".csv", ".xlsx", ".xls")


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


def _padronizar_nomes_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns.astype(str).str.strip()
        .str.lower()
        .str.replace("%", "pct", regex=False)
        .str.replace(r"[^0-9a-zà-ú_]+", "_", regex=True)
        .str.strip("_")
    )
    return df


def _colunas_por_termo(df: pd.DataFrame, termos: tuple) -> list:
    return [c for c in df.columns if any(t in c for t in termos)]


def transform_silver(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = _padronizar_nomes_colunas(df)

    antes = len(df)
    df = df.drop_duplicates()
    print(f"[SILVER] Removidas {antes - len(df)} linhas duplicadas.")

    for col in _colunas_por_termo(df, ("email", "e_mail", "e-mail")):
        df[col] = df[col].fillna("").astype("object")

    antes = len(df)
    df = df.dropna()
    print(f"[SILVER] Removidas {antes - len(df)} linhas com valores nulos.")

    for col in df.columns:
        if df[col].dtype == "object" or str(df[col].dtype) == "str":
            df[col] = df[col].astype("object").astype(str).str.strip()
            df[col] = df[col].replace({"nan": None, "None": None})

    print(f"[SILVER] Resultado: {df.shape[0]} linhas, {df.shape[1]} colunas.")
    return df


def _email_status(valor) -> str:
    texto = "" if pd.isna(valor) else str(valor).strip()
    if texto in ("", "nan", "none"):
        return "ausente"
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}", texto):
        return "valido"
    return "invalido"


def _cpf_valido(valor) -> bool:
    cpf = re.sub(r"[^0-9]", "", str(valor))
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in range(9, 11):
        soma = sum(int(cpf[j]) * (i + 1 - j) for j in range(i))
        digito = (soma * 10) % 11
        digito = 0 if digito == 10 else digito
        if digito != int(cpf[i]):
            return False
    return True


def _cnpj_valido(valor) -> bool:
    cnpj = re.sub(r"[^0-9]", "", str(valor))
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for pesos in (pesos1, pesos2):
        soma = sum(int(cnpj[j]) * pesos[j] for j in range(len(pesos)))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if digito != int(cnpj[len(pesos)]):
            return False
    return True


def validar_dados_silver(df: pd.DataFrame) -> tuple:
    df = df.copy()

    colunas_email = _colunas_por_termo(df, ("email", "e_mail", "e-mail"))
    colunas_cpf = _colunas_por_termo(df, ("cpf",))
    colunas_cnpj = _colunas_por_termo(df, ("cnpj",))

    for col in colunas_email:
        df[f"{col}_status"] = [_email_status(v) for v in df[col]]
    for col in colunas_cpf:
        df[f"{col}_valido"] = [_cpf_valido(v) for v in df[col]]
    for col in colunas_cnpj:
        df[f"{col}_valido"] = [_cnpj_valido(v) for v in df[col]]

    mascara_anomalia = pd.Series(False, index=df.index)
    for col in colunas_email:
        mascara_anomalia |= df[f"{col}_status"].isin(["invalido", "ausente"])
    for col in colunas_cpf:
        mascara_anomalia |= ~df[f"{col}_valido"]
    for col in colunas_cnpj:
        mascara_anomalia |= ~df[f"{col}_valido"]

    colunas_auxiliares = [
        c for c in df.columns if c.endswith(("_status", "_valido"))
    ]
    dados_validos = df[~mascara_anomalia].drop(columns=colunas_auxiliares)

    dados_nao_validados = df[mascara_anomalia].copy()
    dados_nao_validados["motivo_rejeicao"] = ""
    for col in colunas_email:
        status = dados_nao_validados[f"{col}_status"]
        dados_nao_validados.loc[status == "invalido", "motivo_rejeicao"] += (
            f"{col}: email invalido; "
        )
        dados_nao_validados.loc[status == "ausente", "motivo_rejeicao"] += (
            f"{col}: email ausente; "
        )
    for col in colunas_cpf:
        dados_nao_validados.loc[
            ~dados_nao_validados[f"{col}_valido"], "motivo_rejeicao"
        ] += f"{col}: cpf invalido; "
    for col in colunas_cnpj:
        dados_nao_validados.loc[
            ~dados_nao_validados[f"{col}_valido"], "motivo_rejeicao"
        ] += f"{col}: cnpj invalido; "
    dados_nao_validados["motivo_rejeicao"] = (
        dados_nao_validados["motivo_rejeicao"].str.rstrip("; ")
    )
    dados_nao_validados = dados_nao_validados.drop(columns=colunas_auxiliares)

    print(f"[SILVER] Validação: {len(dados_validos)} linhas válidas, "
          f"{len(dados_nao_validados)} linhas com anomalias.")
    return dados_validos, dados_nao_validados


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


def nome_tabela_a_partir_do_arquivo(caminho_arquivo: str) -> str:
    nome = os.path.splitext(os.path.basename(caminho_arquivo))[0]
    return _sanitizar_nome_tabela(nome)


def _sanitizar_nome_tabela(nome: str) -> str:
    nome = re.sub(r"[^0-9a-zA-Z_]+", "_", nome).lower()
    nome = re.sub(r"^[0-9_]+", "", nome)
    nome = nome.strip("_")
    return nome[:63]


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


def salvar_nao_validados(df: pd.DataFrame, table_name: str) -> None:
    if df.empty:
        print("[NAO_VALIDADOS] Nenhuma anomalia encontrada, nada a salvar.")
        return

    pasta = os.path.dirname(NON_VALIDATED_DB_PATH.replace("sqlite:///", ""))
    os.makedirs(pasta, exist_ok=True)

    engine = create_engine(NON_VALIDATED_DB_PATH)
    df.to_sql(table_name, engine, if_exists="append", index=False)

    with engine.connect() as conn:
        total = conn.exec_driver_sql(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"[NAO_VALIDADOS] {len(df)} linhas acumuladas na tabela "
              f"'{table_name}' (total no banco: {total}).")


def processar_arquivo(caminho_arquivo: str, table_name: str | None = None) -> None:
    if table_name:
        nome_tabela = validar_nome_tabela(table_name)
    else:
        nome_tabela = nome_tabela_a_partir_do_arquivo(caminho_arquivo)
    nome_base = os.path.splitext(os.path.basename(caminho_arquivo))[0]
    print(f"\n=== Processando '{os.path.basename(caminho_arquivo)}' "
          f"-> tabela '{nome_tabela}' ===")

    df_bronze = extract(caminho_arquivo)
    eda(df_bronze)

    df_silver = transform_silver(df_bronze)
    df_silver, df_nao_validados = validar_dados_silver(df_silver)
    os.makedirs(SILVER_DIR, exist_ok=True)
    caminho_silver = os.path.join(SILVER_DIR, f"{nome_base}_silver.csv")
    df_silver.to_csv(caminho_silver, index=False)
    print(f"[SILVER] Salvo em '{caminho_silver}'.")

    df_gold = transform_gold(df_silver)
    os.makedirs(GOLD_DIR, exist_ok=True)
    caminho_gold = os.path.join(GOLD_DIR, f"{nome_base}_gold.csv")
    df_gold.to_csv(caminho_gold, index=False)
    print(f"[GOLD] Salvo em '{caminho_gold}'.")

    load(df_gold, DB_PATH, nome_tabela)

    salvar_nao_validados(df_nao_validados, table_name="dados_nao_validados")

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    destino = os.path.join(PROCESSED_DIR, os.path.basename(caminho_arquivo))
    shutil.move(caminho_arquivo, destino)
    print(f"[OK] Arquivo original movido para '{destino}'.")


def processar_pendentes() -> None:
    padroes = [os.path.join(DATA_RAW_DIR, f"*{ext}") for ext in EXTENSOES_SUPORTADAS]
    arquivos_pendentes = sorted(
        set(itertools.chain.from_iterable(glob.glob(p) for p in padroes))
    )

    if not arquivos_pendentes:
        print("Nenhum arquivo novo encontrado em data_raw/.")
        return

    for caminho_arquivo in arquivos_pendentes:
        processar_arquivo(caminho_arquivo)


if __name__ == "__main__":
    processar_pendentes()
