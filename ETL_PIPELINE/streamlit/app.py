import importlib.util
import os

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
sanitizar_nome_tabela = etl._sanitizar_nome_tabela
extract = etl.extract
DATA_RAW_DIR = etl.DATA_RAW_DIR


st.set_page_config(page_title="Upload de Arquivos", layout="centered")
st.title("PIPELINE DE ARQUIVOS CSV/EXCEL → BANCO DE DADOS")

st.write(
    "Envie um arquivo CSV ou Excel (xlsx/xls) abaixo. Ele será processado "
    "usando os fundamentos de arquitetura Medalhão pelas camadas bronze → silver → gold."
)

arquivo_enviado = st.file_uploader(
    "Escolha um arquivo CSV ou Excel", type=["csv", "xlsx", "xls"]
)

if arquivo_enviado is not None:
    os.makedirs(DATA_RAW_DIR, exist_ok=True)
    caminho_destino = os.path.join(DATA_RAW_DIR, arquivo_enviado.name)

    with open(caminho_destino, "wb") as f:
        f.write(arquivo_enviado.getbuffer())

    st.info(f"Arquivo salvo em `medallion/bronze/{arquivo_enviado.name}`.")

    df_previa = extract(caminho_destino)
    st.subheader("Prévia do arquivo enviado")
    st.dataframe(df_previa.head(20))

    @st.dialog("Confirmar nome da tabela")
    def confirmar_tabela():
        nome_bruto = st.text_input(
            "Nome da tabela no banco de dados:",
            key="nome_tabela_input",
        )
        nome_bruto = nome_bruto or ""
        nome_sanitizado = sanitizar_nome_tabela(nome_bruto)
        if nome_sanitizado != nome_bruto:
            st.session_state["nome_tabela_input"] = nome_sanitizado
            st.rerun()

        try:
            nome_validado = validar_nome_tabela(nome_sanitizado)
        except ValueError as erro:
            st.error(str(erro))
            return

        c1, c2 = st.columns(2)
        if c1.button("Confirmar", type="primary", use_container_width=True):
            st.session_state["tabela_confirmada"] = nome_validado
            st.rerun()
        if c2.button("Cancelar", use_container_width=True):
            st.session_state["tabela_confirmada"] = ""
            st.rerun()

    if (
        arquivo_enviado.name != st.session_state.get("arquivo_processado")
        and "tabela_confirmada" not in st.session_state
        and "nome_tabela_input" not in st.session_state
    ):
        st.session_state["nome_tabela_input"] = (
            nome_tabela_a_partir_do_arquivo(caminho_destino)
        )
        confirmar_tabela()

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
        except Exception as erro:  # noqa: BLE001 - UI deve exibir qualquer erro ao usuario
            st.error(f"{erro}")
