import pyodbc
import urllib.parse
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

def obter_driver_compativel():
    """Detecta automaticamente o driver instalado (ODBC 18 no Linux/VPS ou SQL Server no Windows)."""
    drivers_instalados = pyodbc.drivers()
    preferencias = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server"
    ]
    for d in preferencias:
        if d in drivers_instalados:
            return d
    return "SQL Server"

def criar_engine_sql():
    sec = st.secrets["sql_server_CHB"]
    if "url" in sec and sec["url"]:
        return create_engine(sec["url"])
    
    host = sec.get("host") or sec.get("server", "")
    port = sec.get("port", 1433)
    database = sec.get("database", "CHB")
    username = sec.get("username", "")
    password = urllib.parse.quote_plus(str(sec.get("password", "")))
    
    driver_real = obter_driver_compativel()
    driver_codificado = urllib.parse.quote_plus(driver_real)
    flags = "&TrustServerCertificate=yes" if "ODBC Driver" in driver_real else ""
    
    conn_str = f"mssql+pyodbc://{username}:{password}@{host}:{port}/{database}?driver={driver_codificado}{flags}"
    return create_engine(conn_str)

@st.cache_data(ttl=600)
def buscar_dados_base_sql():
    """Consulta 1: Modelos e Cores ativas (PC13T, PC10T, PC03T) para o De-Para."""
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
    """Consulta 2: Relação oficial de cores cadastradas na PC10T."""
    engine = criar_engine_sql()
    query = "SELECT PC10Codigo, PC10Descr FROM PC10T ORDER BY PC10Codigo"
    with engine.connect() as conexao:
        df = pd.read_sql_query(query, con=conexao)
    df["PC10Codigo"] = df["PC10Codigo"].astype(str).str.strip()
    df["PC10Descr"] = df["PC10Descr"].astype(str).str.strip()
    return df