import importlib.util
import os
import sqlite3
from pathlib import Path

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


# ── INSIGHTS CAPTADOS ────────────────────────────────────────────────────────

INSIGHTS_DB = Path(__file__).resolve().parent.parent / "medallion" / "gold" / "database" / "insights.db"

COR_CATEGORIA = {
    "Oportunidade": "green",
    "Risco Identificado": "orange",
    "Resumo Executivo": "blue",
    "Erro de Origem": "red",
    "Inconsistencia de Dados": "violet",
    "Regra de Negocio Violada": "red",
}


def _carregar_insights() -> pd.DataFrame:
    if not INSIGHTS_DB.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(INSIGHTS_DB)
    df = pd.read_sql_query(
        "SELECT rowid AS id, categoria, observacao, data FROM insights ORDER BY data DESC",
        conn,
    )
    conn.close()
    return df


def _badge(categoria: str) -> str:
    cor = COR_CATEGORIA.get(categoria, "gray")
    return f":{cor}-badge[{categoria}]"


st.divider()
st.subheader("Insights Captados")

df_insights = _carregar_insights()

if df_insights.empty:
    st.info("Nenhum insight registrado ainda. Execute o Agente de Insights primeiro.")
else:
    total = len(df_insights)
    categorias = df_insights["categoria"].value_counts()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Insights", total)
    col2.metric("Categorias", len(categorias))
    col3.metric(
        "Ultimo registro",
        pd.to_datetime(df_insights["data"]).max().strftime("%d/%m/%H:%M")
        if total > 0
        else "-",
    )

    st.markdown("### Por categoria")
    cat_cols = st.columns(min(len(categorias), 4))
    for i, (cat, qtd) in enumerate(categorias.items()):
        with cat_cols[i % len(cat_cols)]:
            cor = COR_CATEGORIA.get(cat, "gray")
            st.metric(label=cat, value=qtd)

    st.markdown("---")
    opcoes_cat = ["Todas"] + list(categorias.index)
    filtro = st.selectbox("Filtrar por categoria", opcoes_cat)

    df_filtrado = df_insights if filtro == "Todas" else df_insights[df_insights["categoria"] == filtro]

    st.markdown("### Detalhes")

    for _, row in df_filtrado.iterrows():
        data_fmt = pd.to_datetime(row["data"]).strftime("%d/%m/%Y %H:%M")
        with st.container(border=True):
            col_a, col_b = st.columns([1, 3])
            with col_a:
                st.markdown(f"**{row['categoria']}**")
                st.caption(data_fmt)
            with col_b:
                st.markdown(row["observacao"])

    st.markdown("---")
    with st.expander("Tabela completa"):
        st.dataframe(
            df_filtrado[["categoria", "observacao", "data"]].reset_index(drop=True),
            use_container_width=True,
        )
