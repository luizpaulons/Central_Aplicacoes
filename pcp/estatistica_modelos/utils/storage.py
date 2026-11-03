import os
from sqlalchemy import create_engine

CAMINHO_DB = "/opt/pcp_dados/pcp_local.db"
ENGINE_SQLITE = create_engine(f"sqlite:///{CAMINHO_DB}", echo=False)


def inicializar_banco():
    """Cria as tabelas estruturais no SQLite se ainda não existirem."""
    with ENGINE_SQLITE.connect() as conn:
        # 1. Tabela de Solados
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS solados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL
            );
        """))
        
        # 2. Tabela de Cores de EVA
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cores_eva (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT,
                cor TEXT UNIQUE NOT NULL
            );
        """))
        
        # 3. Tabela De-Para (Chave primária: Linha + Cor)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS de_para (
                linha TEXT NOT NULL,
                cor TEXT NOT NULL,
                modelo TEXT,
                descricao_cor TEXT,
                nome_solado TEXT,
                cor_eva TEXT,
                PRIMARY KEY (linha, cor)
            );
        """))
        conn.commit()

# Inicializa as tabelas na importação do módulo
inicializar_banco()


# =========================================================================
# 1. CADASTROS DE BASE (Solados e Cores de EVA)
# =========================================================================

def carregar_cadastros_base():
    """Retorna os cadastros no formato de dicionário compatível com a tela."""
    cadastros = {"solados": [], "cores_eva": []}
    
    with ENGINE_SQLITE.connect() as conn:
        df_sol = pd.read_sql_query("SELECT nome FROM solados ORDER BY nome", conn)
        cadastros["solados"] = df_sol["nome"].dropna().astype(str).tolist()
        
        df_cor = pd.read_sql_query("SELECT codigo, cor FROM cores_eva ORDER BY cor", conn)
        cadastros["cores_eva"] = [
            {"codigo": str(r["codigo"] or "").strip(), "cor": str(r["cor"] or "").strip()}
            for _, r in df_cor.iterrows()
        ]
        
    return cadastros


def salvar_cadastros_base(cadastros):
    """Atualiza as tabelas de solados e cores de EVA com substituição total."""
    solados = cadastros.get("solados", [])
    cores = cadastros.get("cores_eva", [])
    
    with ENGINE_SQLITE.begin() as conn:
        conn.execute(text("DELETE FROM solados"))
        for s in solados:
            nome_limpo = str(s).strip().upper()
            if nome_limpo:
                conn.execute(
                    text("INSERT OR IGNORE INTO solados (nome) VALUES (:nome)"),
                    {"nome": nome_limpo}
                )
        
        conn.execute(text("DELETE FROM cores_eva"))
        for item in cores:
            if isinstance(item, dict):
                cod = str(item.get("codigo", "")).strip()
                cor = str(item.get("cor", "")).strip().upper()
            else:
                cod = ""
                cor = str(item).strip().upper()
                
            if cor:
                conn.execute(
                    text("INSERT OR IGNORE INTO cores_eva (codigo, cor) VALUES (:cod, :cor)"),
                    {"cod": cod, "cor": cor}
                )


# =========================================================================
# 2. VÍNCULOS DE-PARA
# =========================================================================

def carregar_de_para():
    """Retorna o DataFrame de De-Para."""
    colunas_padrao = ["linha", "modelo", "cor", "descricao_cor", "nome_solado", "cor_eva"]
    with ENGINE_SQLITE.connect() as conn:
        df = pd.read_sql_query("SELECT * FROM de_para", conn, dtype=str)
        
    if df.empty:
        return pd.DataFrame(columns=colunas_padrao)
        
    for c in colunas_padrao:
        if c not in df.columns:
            df[c] = ""
            
    return df[colunas_padrao]


def salvar_de_para(df_novos):
    """Executa UPSERT dos vínculos mantendo (linha, cor) únicos."""
    if df_novos is None or df_novos.empty:
        return carregar_de_para()
        
    df_copia = df_novos.copy()
    df_copia["linha"] = df_copia["linha"].astype(str).str.strip().str.upper()
    df_copia["cor"] = df_copia["cor"].astype(str).str.strip().str.upper()
    df_copia["modelo"] = df_copia.get("modelo", "").astype(str).str.strip()
    df_copia["descricao_cor"] = df_copia.get("descricao_cor", "").astype(str).str.strip()
    df_copia["nome_solado"] = df_copia.get("nome_solado", "").astype(str).str.strip().str.upper()
    df_copia["cor_eva"] = df_copia.get("cor_eva", "").astype(str).str.strip().str.upper()
    
    df_copia = df_copia.drop_duplicates(subset=["linha", "cor"], keep="last")
    
    upsert_query = text("""
        INSERT INTO de_para (linha, cor, modelo, descricao_cor, nome_solado, cor_eva)
        VALUES (:linha, :cor, :modelo, :descricao_cor, :nome_solado, :cor_eva)
        ON CONFLICT(linha, cor) DO UPDATE SET
            modelo = excluded.modelo,
            descricao_cor = excluded.descricao_cor,
            nome_solado = excluded.nome_solado,
            cor_eva = excluded.cor_eva;
    """)
    
    registros = df_copia[["linha", "cor", "modelo", "descricao_cor", "nome_solado", "cor_eva"]].to_dict(orient="records")
    
    with ENGINE_SQLITE.begin() as conn:
        conn.execute(upsert_query, registros)
        
    return carregar_de_para()


def fmt_milhar(v):
    """Formata inteiros com separador de milhar brasileiro."""
    try:
        n = int(round(float(str(v).replace(".", "").replace(",", "."))))
        return f"{n:,}".replace(",", ".")
    except Exception:
        return str(v)