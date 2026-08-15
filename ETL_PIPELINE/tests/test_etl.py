import importlib.util
from pathlib import Path

import pandas as pd
import pytest

_ETL_PATH = Path(__file__).resolve().parents[1] / "eda" / ".eda_ETl.py"


def _carregar_etl():
    spec = importlib.util.spec_from_file_location("etl", _ETL_PATH)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


etl = _carregar_etl()


def test_cpf_valido():
    assert etl._cpf_valido("123.456.789-09") is True
    assert etl._cpf_valido("000.000.000-00") is False
    assert etl._cpf_valido("111.111.111-11") is False


def test_cnpj_valido():
    assert etl._cnpj_valido("11.222.333/0001-81") is True
    assert etl._cnpj_valido("00.000.000/0000-00") is False


def test_email_status():
    assert etl._email_status("joao@empresa.com") == "valido"
    assert etl._email_status("nao-e-email") == "invalido"
    assert etl._email_status(None) == "ausente"
    assert etl._email_status(float("nan")) == "ausente"


def test_padronizar_nomes_colunas():
    df = pd.DataFrame(columns=["  Nome Cliente ", "Data Venda", "Valor"])
    resultado = etl._padronizar_nomes_colunas(df)
    assert list(resultado.columns) == ["nome_cliente", "data_venda", "valor"]


def test_transform_silver_remove_duplicadas_e_nulos():
    df = pd.DataFrame({"id": [1, 1, 2, None], "valor": [10, 10, 20, 5]})
    resultado = etl.transform_silver(df)
    assert len(resultado) == 2


def test_converter_numero_com_virgula():
    serie = pd.Series(["10,5", "20", "30,25"])
    resultado = etl._tentar_converter_numero_com_virgula(serie)
    assert resultado.tolist() == [10.5, 20.0, 30.25]


def test_sanitizar_nome_tabela():
    assert etl._sanitizar_nome_tabela("Vendas 2024!") == "vendas_2024"


def test_validar_nome_tabela():
    assert etl.validar_nome_tabela("fato_vendas") == "fato_vendas"
    with pytest.raises(ValueError):
        etl.validar_nome_tabela("select")
