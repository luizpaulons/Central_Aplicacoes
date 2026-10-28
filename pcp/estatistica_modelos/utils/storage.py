import os
import json
import pandas as pd

ARQUIVO_DE_PARA = "de_para_solados_eva.csv"
ARQUIVO_CADASTROS = "cadastros_base.json"

def carregar_cadastros_base():
    if os.path.exists(ARQUIVO_CADASTROS):
        with open(ARQUIVO_CADASTROS, "r", encoding="utf-8") as f:
            dados = json.load(f)
            dados.setdefault("solados", [])
            dados.setdefault("cores_eva", [])
            return dados
    return {"solados": [], "cores_eva": []}

def salvar_cadastros_base(cadastros):
    with open(ARQUIVO_CADASTROS, "w", encoding="utf-8") as f:
        json.dump(cadastros, f, ensure_ascii=False, indent=2)

def carregar_de_para():
    if os.path.exists(ARQUIVO_DE_PARA):
        return pd.read_csv(ARQUIVO_DE_PARA, dtype=str)
    return pd.DataFrame(columns=["linha", "modelo", "cor", "descricao_cor", "nome_solado", "cor_eva"])

def salvar_de_para(df_novos):
    df_existente = carregar_de_para()
    df_novos["linha"] = df_novos["linha"].astype(str).str.strip().str.upper()
    df_novos["cor"] = df_novos["cor"].astype(str).str.strip().str.upper()
    
    if not df_existente.empty:
        df_existente["linha"] = df_existente["linha"].astype(str).str.strip().str.upper()
        df_existente["cor"] = df_existente["cor"].astype(str).str.strip().str.upper()
        df_final = pd.concat([df_existente, df_novos]).drop_duplicates(subset=["linha", "cor"], keep="last")
    else:
        df_final = df_novos
        
    df_final.to_csv(ARQUIVO_DE_PARA, index=False)
    return df_final

def fmt_milhar(v):
    try:
        n = int(round(float(str(v).replace(".", "").replace(",", "."))))
        return f"{n:,}".replace(",", ".")
    except:
        return str(v)