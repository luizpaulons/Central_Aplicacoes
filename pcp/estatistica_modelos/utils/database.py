import os
import urllib.parse
import pyodbc
import streamlit as st
from sqlalchemy import create_engine

def obter_driver_compativel():
    """Detecta automaticamente o driver de SQL Server instalado."""
    drivers_instalados = pyodbc.drivers()
    preferencias = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server"
    ]
    for d in preferencias:
        if d in drivers_instalados:
            return d
    return "ODBC Driver 18 for SQL Server"

def criar_engine_sql():
    # 1. Tenta ler direto das Variáveis de Ambiente configuradas no Portainer
    host = os.getenv("DB_HOST") or os.getenv("SQL_SERVER_HOST") or os.getenv("SERVER", "")
    port = os.getenv("DB_PORT") or os.getenv("SQL_SERVER_PORT", "1433")
    database = os.getenv("DB_NAME") or os.getenv("SQL_SERVER_DATABASE", "CHB")
    username = os.getenv("DB_USER") or os.getenv("SQL_SERVER_USER", "")
    password = os.getenv("DB_PASSWORD") or os.getenv("SQL_SERVER_PASSWORD", "")
    
    # 2. Se não estiver no ambiente, tenta ler de st.secrets como contingência
    if not host and hasattr(st, "secrets") and "sql_server_CHB" in st.secrets:
        sec = st.secrets["sql_server_CHB"]
        host = sec.get("host") or sec.get("server", "")
        port = sec.get("port", 1433)
        database = sec.get("database", "CHB")
        username = sec.get("username", "")
        password = str(sec.get("password", ""))

    pwd_quoted = urllib.parse.quote_plus(str(password).strip())
    driver_real = obter_driver_compativel()
    driver_codificado = urllib.parse.quote_plus(driver_real)
    flags = "&TrustServerCertificate=yes" if "ODBC Driver" in driver_real else ""

    conn_str = (
        f"mssql+pyodbc://{username.strip()}:{pwd_quoted}@{host.strip()}:{port}/{database.strip()}"
        f"?driver={driver_codificado}{flags}&timeout=30"
    )
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