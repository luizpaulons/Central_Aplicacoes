import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

def criar_engine_sql():
    host = (os.getenv("DB_HOST") or os.getenv("SQL_SERVER_HOST", "")).strip()
    port = int((os.getenv("DB_PORT") or os.getenv("SQL_SERVER_PORT", "1433")).strip())
    database = (os.getenv("DB_NAME") or os.getenv("SQL_SERVER_DATABASE", "CHB")).strip()
    username = (os.getenv("DB_USER") or os.getenv("SQL_SERVER_USER", "Producao")).strip()
    password = (os.getenv("DB_PASSWORD") or os.getenv("SQL_SERVER_PASSWORD", "")).strip()

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

def buscar_descricao_cor_pontual(codigo_cor: str) -> str:
    """Busca pontualmente no SQL Server apenas a cor informada."""
    engine = criar_engine_sql()
    query = text("SELECT PC10Descr FROM PC10T WHERE PC10Codigo = :cod")
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"cod": str(codigo_cor).strip()}).fetchone()
            if result and result[0]:
                return str(result[0]).strip().upper()
    except Exception as e:
        st.error(f"Erro ao consultar cor {codigo_cor} no SQL Server: {e}")
    return ""

def sincronizar_dados_base_sql_para_sqlite():
    """Busca dados no SQL Server e sincroniza na tabela local do SQLite."""
    from utils.storage import ENGINE_SQLITE
    
    engine_sql = criar_engine_sql()
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
    with engine_sql.connect() as conn_sql:
        df_sql = pd.read_sql_query(query, con=conn_sql)
        
    if not df_sql.empty:
        # Salva/Substitui a tabela cache no SQLite
        with ENGINE_SQLITE.begin() as conn_lite:
            df_sql.to_sql("dados_base_pcp", con=conn_lite, if_exists="replace", index=False)
            
    return len(df_sql)