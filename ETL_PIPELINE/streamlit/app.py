
import importlib.util
import os
import sqlite3

import pandas as pd
import streamlit as st

_ETL_CAMINHO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "eda", ".eda_ETl.py",
)
_ETL_SPEC = importlib.util.spec_from_file_location("etl", _ETL_CAMINHO)
etl = importlib.util.module_from_spec(_ETL_SPEC)
_ETL_SPEC.loader.exec_module(etl)

processar_arquivo = etl.processar_arquivo
DATA_RAW_DIR = etl.DATA_RAW_DIR
DB_PATH = etl.DB_PATH


st.set_page_config(page_title="Upload de Arquivos", layout="centered")
st.title("PIPELINE DE ARQUIVOS CSV/EXCEL → BANCO DE DADOS")

st.write(
    "Envie um arquivo CSV ou Excel (xlsx/xls) abaixo. Ele será processado "
    " usando os fundamentos de arquitetura Medalhão pelas camadas bronze → silver → gold, e uma tabela será "
    "criada (ou substituída/inserida) no banco, com o nome baseado no nome do arquivo."
)

arquivo_enviado = st.file_uploader(
    "Escolha um arquivo CSV ou Excel", type=["csv", "xlsx", "xls"]
)

if arquivo_enviado is not None:
    os.makedirs(DATA_RAW_DIR, exist_ok=True)
    caminho_destino = os.path.join(DATA_RAW_DIR, arquivo_enviado.name)

    with open(caminho_destino, "wb") as f:
        f.write(arquivo_enviado.getbuffer())

    st.info(f"Arquivo salvo em `medallion/bronze/{arquivo_enviado.name}`. Processando...")

    try:
        with st.spinner("Executando o pipeline (extract → transform → load)..."):
            processar_arquivo(caminho_destino)
        st.success("Arquivo processado e carregado no banco com sucesso!")
    except Exception as erro:
        st.error(f"Erro ao processar o arquivo: {erro}")

st.divider()
st.subheader("Tabelas atualmente no banco")

caminho_db = DB_PATH.replace("sqlite:///", "")

if os.path.exists(caminho_db):
    conn = sqlite3.connect(caminho_db)
    tabelas = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table'", conn
    )["name"].tolist()

    if tabelas:
        tabela_selecionada = st.selectbox("Escolha uma tabela para pré-visualizar", tabelas)
        if tabela_selecionada:
            df_preview = pd.read_sql(f"SELECT * FROM {tabela_selecionada} LIMIT 20", conn)
            st.write(f"Prévia de `{tabela_selecionada}` ({len(df_preview)} linhas mostradas):")
            st.dataframe(df_preview)
    else:
        st.write("Nenhuma tabela encontrada ainda. Envie um CSV para começar.")

    conn.close()
else:
    st.write("Banco de dados ainda não foi criado. Envie um CSV para começar.")