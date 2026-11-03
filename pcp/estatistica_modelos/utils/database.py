import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

def criar_engine_sql():
    # 1. Lê as variáveis de ambiente com strip() para evitar quebras de linha
    host = (os.getenv("DB_HOST") or os.getenv("SQL_SERVER_HOST", "")).strip()
    port = int((os.getenv("DB_PORT") or os.getenv("SQL_SERVER_PORT", "1433")).strip())
    database = (os.getenv("DB_NAME") or os.getenv("SQL_SERVER_DATABASE", "CHB")).strip()
    username = (os.getenv("DB_USER") or os.getenv("SQL_SERVER_USER", "Producao")).strip()
    password = (os.getenv("DB_PASS") or os.getenv("SQL_SERVER_PASSWORD", "")).strip()

    # 2. Monta a URL de forma segura (URL.create trata qualquer caractere especial na senha)
    connection_url = URL.create(
        "mssql+pyodbc",
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
        query={
            "driver": "ODBC Driver 18 for SQL Server",
            "TrustServerCertificate": "yes",
            "timeout": "30",
        },
    )
    return create_engine(connection_url)

@st.cache_data(ttl=600)
def buscar_dados_base_sql():
    engine = criar_engine_sql()
    query = """
        SELECT 
            C.PC03Codigo AS Linha, 
            C.PC03Descr  AS Modelo, 
            B.PC10Codigo AS Cor, 
            B.PC10Descr  AS [Descrição Cor]
        FROM PC13T A
        INNER JOIN PC10T B ON (A.PC13Cor = B.PC10Codigo)
        INNER JOIN PC03T C ON (A.PC13Linha = C.PC03Codigo)
        WHERE A.PC13Emp08 = 1
          AND A.PC13AnoPed = 0
          AND A.PC13CodPed = 0
          AND C.PC03Codigo > 660
        GROUP BY C.PC03Codigo, C.PC03Descr, B.PC10Codigo, B.PC10Descr
        ORDER BY C.PC03Codigo, B.PC10Codigo
    """
    with engine.connect() as conexao:
        df = pd.read_sql_query(query, con=conexao)
    return df

@st.cache_data(ttl=600)
def buscar_cores_pc10t():
    engine = criar_engine_sql()
    query = "SELECT PC10Codigo, PC10Descr FROM PC10T ORDER BY PC10Codigo"
    with engine.connect() as conexao:
        df = pd.read_sql_query(query, con=conexao)
    df["PC10Codigo"] = df["PC10Codigo"].astype(str).str.strip()
    df["PC10Descr"] = df["PC10Descr"].astype(str).str.strip()
    return df