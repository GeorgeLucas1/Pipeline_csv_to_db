
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
nome_tabela_a_partir_do_arquivo = etl.nome_tabela_a_partir_do_arquivo
validar_nome_tabela = etl.validar_nome_tabela
DATA_RAW_DIR = etl.DATA_RAW_DIR
DB_PATH = etl.DB_PATH


st.set_page_config(page_title="Upload de Arquivos", layout="centered")
st.title("PIPELINE DE ARQUIVOS CSV/EXCEL → BANCO DE DADOS")

st.write(
    "Envie um arquivo CSV ou Excel (xlsx/xls) abaixo. Ele será processado "
    " usando os fundamentos de arquitetura Medalhão pelas camadas bronze → silver → gold, e uma tabela será "
    "criada (ou substituída/inserida) no banco."
)

arquivo_enviado = st.file_uploader(
    "Escolha um arquivo CSV ou Excel", type=["csv", "xlsx", "xls"]
)

def tabelas_existentes() -> list[str]:
    caminho_db = DB_PATH.replace("sqlite:///", "")
    if not os.path.exists(caminho_db):
        return []
    conn = sqlite3.connect(caminho_db)
    nomes = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table'", conn
    )["name"].tolist()
    conn.close()
    return nomes

if arquivo_enviado is not None:
    os.makedirs(DATA_RAW_DIR, exist_ok=True)
    caminho_destino = os.path.join(DATA_RAW_DIR, arquivo_enviado.name)

    with open(caminho_destino, "wb") as f:
        f.write(arquivo_enviado.getbuffer())

    st.info(f"Arquivo salvo em `medallion/bronze/{arquivo_enviado.name}`.")

    @st.dialog("Confirmar nome da tabela")
    def confirmar_tabela(nome_sugerido: str):
        novo_nome = st.text_input(
            "Nome da tabela no banco de dados:",
            value=nome_sugerido,
        )
        try:
            nome_validado = validar_nome_tabela(novo_nome)
        except ValueError as erro:
            st.error(str(erro))
            return

        if nome_validado in tabelas_existentes():
            st.error(
                f"Pipeline rejeitado: a tabela `{nome_validado}` já existe no banco. "
                "Escolha outro nome de tabela."
            )
            return

        c1, c2 = st.columns(2)
        if c1.button("Confirmar", type="primary", use_container_width=True):
            st.session_state["tabela_confirmada"] = nome_validado
            st.rerun()
        if c2.button("Cancelar", use_container_width=True):
            st.session_state["tabela_confirmada"] = ""
            st.rerun()

    if arquivo_enviado.name != st.session_state.get("arquivo_processado"):
        if "tabela_confirmada" not in st.session_state:
            confirmar_tabela(nome_tabela_a_partir_do_arquivo(caminho_destino))

    nome_confirmado = st.session_state.get("tabela_confirmada", "")

    if nome_confirmado:
        try:
            with st.spinner("Executando o pipeline (extract → transform → load)..."):
                processar_arquivo(caminho_destino, table_name=nome_confirmado)
            st.session_state["arquivo_processado"] = arquivo_enviado.name
            st.success(
                f"Arquivo processado e carregado na tabela `{nome_confirmado}` com sucesso!"
            )
            st.session_state.pop("tabela_confirmada", None)
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