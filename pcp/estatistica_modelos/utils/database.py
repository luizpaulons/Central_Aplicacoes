import pyodbc
import urllib.parse
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

import os

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
    # Tenta carregar do st.secrets de forma segura, se falhar ou não existir, usa um dicionário vazio
    try:
        if "sql_server_CHB" in st.secrets:
            sec = st.secrets["sql_server_CHB"]
        elif "sql_server" in st.secrets:
            sec = st.secrets["sql_server"]
        else:
            sec = {}
    except Exception:
        sec = {}

    # Se houver uma URL pronta no secrets, usa ela
    if "url" in sec and sec["url"]:
        return create_engine(sec["url"])
    
    # Prioriza o .env (os.getenv), mas aceita o st.secrets ou valores padrão como fallback
    host = os.getenv("DB_HOST") or sec.get("host") or sec.get("server", "localhost")
    port = int(os.getenv("DB_PORT") or sec.get("port", 1433))
    database = os.getenv("DB_NAME") or sec.get("database", "CHB")
    username = os.getenv("DB_USER") or sec.get("username", "")
    
    # Pega a senha do .env ou do secrets, garantindo que não dê erro se estiver vazia
    raw_password = os.getenv("DB_PASS") if os.getenv("DB_PASS") is not None else sec.get("password", "")
    password = urllib.parse.quote_plus(str(raw_password))
    
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